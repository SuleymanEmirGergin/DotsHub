"""LLM client abstraction backed by Wiro Run API + Task polling."""

import asyncio
import ast
import json
import logging
import time
from typing import Any, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

TERMINAL_SUCCESS_STATUSES = {"task_postprocess_end", "task_end"}
TERMINAL_ERROR_STATUSES = {"task_error", "task_error_full", "task_cancel", "task_kill"}


class LLMClient:
    """Async LLM client with JSON mode support and automatic retries."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.model = model or settings.LLM_MODEL
        self.temperature = temperature if temperature is not None else settings.TEMPERATURE
        self.api_key = api_key or settings.WIRO_API_KEY
        self.base_url = settings.WIRO_BASE_URL.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=settings.WIRO_HTTP_TIMEOUT_SECONDS,
            trust_env=False,
        )

    def _auth_headers(self) -> dict[str, str]:
        api_key = self.api_key or settings.WIRO_API_KEY
        if not api_key:
            raise ValueError("Missing WIRO_API_KEY. Set it in backend/.env.")
        headers = {"x-api-key": api_key}
        if settings.WIRO_API_SECRET:
            headers["x-api-secret"] = settings.WIRO_API_SECRET
        return headers

    def _build_prompt(self, system: str, user: str, response_format: str) -> str:
        prompt = f"System instructions:\n{system}\n\nUser input:\n{user}"
        if response_format == "json":
            prompt += "\n\nReturn only a valid JSON object. Do not add markdown code fences."
        return prompt

    async def _run_task(self, prompt: str) -> str:
        form_data = {
            "prompt": prompt,
            "reasoning": settings.WIRO_REASONING,
            "webSearch": str(settings.WIRO_WEB_SEARCH).lower(),
            "verbosity": settings.WIRO_VERBOSITY,
        }
        multipart_fields = {key: (None, str(value)) for key, value in form_data.items()}
        response = await self.client.post(
            f"{self.base_url}/v1/Run/openai/{self.model}",
            headers=self._auth_headers(),
            files=multipart_fields,
        )
        response.raise_for_status()
        payload = response.json()

        if not payload.get("result"):
            raise RuntimeError(f"Wiro run failed: {payload.get('errors')}")

        task_token = payload.get("socketaccesstoken")
        if not task_token:
            raise RuntimeError(f"Wiro run response missing task token: {payload}")
        return task_token

    async def _get_task_detail(self, task_token: str) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.base_url}/v1/Task/Detail",
            headers={"Content-Type": "application/json", **self._auth_headers()},
            json={"tasktoken": task_token},
        )
        response.raise_for_status()
        payload = response.json()

        if not payload.get("result"):
            raise RuntimeError(f"Wiro task detail failed: {payload.get('errors')}")

        task_list = payload.get("tasklist") or []
        if not task_list:
            raise RuntimeError(f"Wiro task detail response missing tasklist: {payload}")
        return task_list[0]

    async def _wait_for_task_completion(self, task_token: str) -> dict[str, Any]:
        deadline = time.monotonic() + settings.WIRO_POLL_TIMEOUT_SECONDS

        while True:
            task = await self._get_task_detail(task_token)
            status = str(task.get("status", "")).lower()

            if status in TERMINAL_SUCCESS_STATUSES:
                return task
            if status in TERMINAL_ERROR_STATUSES:
                raise RuntimeError(
                    f"Wiro task failed with status={status}, debugerror={task.get('debugerror')}"
                )

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Wiro task timed out after {settings.WIRO_POLL_TIMEOUT_SECONDS}s, last status={status}"
                )
            await asyncio.sleep(settings.WIRO_POLL_INTERVAL_SECONDS)

    async def _extract_text_from_output_urls(self, task: dict[str, Any]) -> Optional[str]:
        outputs = task.get("outputs") or []
        for output in outputs:
            if not isinstance(output, dict):
                continue

            content_type = str(output.get("contenttype") or "").lower()
            url = output.get("url")
            if not url:
                continue

            is_text_like = content_type.startswith("text/") or "json" in content_type
            if not is_text_like:
                continue

            try:
                file_resp = await self.client.get(url)
                file_resp.raise_for_status()
                text = file_resp.text.strip()
                if text:
                    return text
            except Exception as exc:
                logger.warning("Failed reading Wiro output url %s: %s", url, exc)
        return None

    async def _extract_task_text(self, task: dict[str, Any]) -> str:
        for field in ("debugoutput", "result", "response", "message"):
            value = task.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for output in task.get("outputs") or []:
            if isinstance(output, dict):
                for field in ("text", "content", "message"):
                    value = output.get(field)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

        text_from_url = await self._extract_text_from_output_urls(task)
        if text_from_url:
            return text_from_url

        raise RuntimeError(f"Wiro task completed but no textual output found. task={task}")

    @staticmethod
    def _strip_markdown_code_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
        return stripped

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            "LLM call failed, retrying (%s/3)...", retry_state.attempt_number
        ),
    )
    async def chat(
        self,
        system: str,
        user: str,
        response_format: str = "json",
        temperature: Optional[float] = None,
    ) -> str:
        """Send a request to Wiro and return response content string."""
        _ = temperature  # Wiro endpoint currently controls style via reasoning/verbosity settings.
        prompt = self._build_prompt(system=system, user=user, response_format=response_format)
        task_token = await self._run_task(prompt)
        task = await self._wait_for_task_completion(task_token)
        content = await self._extract_task_text(task)

        if not content:
            raise ValueError("Empty response from LLM")

        return self._strip_markdown_code_fence(content)

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
    ) -> dict:
        """Send a chat request and parse the JSON response."""
        content = await self.chat(
            system=system,
            user=user,
            response_format="json",
            temperature=temperature,
        )
        candidates = [content]
        extracted = self._extract_json_block(content)
        if extracted and extracted not in candidates:
            candidates.append(extracted)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        try:
            parsed = ast.literal_eval(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON response: %s", content[:400])
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
        raise ValueError("LLM returned JSON value, but not a JSON object.")

    @staticmethod
    def _extract_json_block(text: str) -> Optional[str]:
        stripped = text.strip()
        if not stripped:
            return None

        obj_start = stripped.find("{")
        obj_end = stripped.rfind("}")
        if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            return stripped[obj_start : obj_end + 1]

        arr_start = stripped.find("[")
        arr_end = stripped.rfind("]")
        if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
            return stripped[arr_start : arr_end + 1]
        return None


# Singleton instance
llm_client = LLMClient()
