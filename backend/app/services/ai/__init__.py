"""Wiro.ai-backed AI service wrappers.

Each module in this package is a thin domain wrapper over
``wiro_client.run()``. The pattern matches the existing
``procedure_intent_llm`` integration:
    - feature flag (default off)
    - PII redaction on user-supplied text
    - retry / timeout policy via the generic client
    - structured failure modes that return None instead of raising

Modules:
    wiro_client       — generic submit + poll + output fetch primitives
    qwen_llm          — Qwen3.6-27B text generation
    whisper_stt       — Whisper speech-to-text (multilingual, TR-tuned)
    cogvlm_caption    — CogVLM2 video-to-text caption
"""
