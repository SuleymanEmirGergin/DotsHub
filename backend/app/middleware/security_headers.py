"""Security headers middleware: HSTS, X-Content-Type-Options, X-Frame-Options. Applied when APP_ENV=production."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers in production."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # Only add strict security headers in production to avoid breaking dev
        env = getattr(request.app.state, "app_env", None) or "development"
        if env != "production":
            return response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS: enable only when serving over HTTPS in production
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response
