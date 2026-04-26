"""Application wiring split out of main.py.

main.py was a 570-line god file mixing lifespan, middleware setup,
observers, route registration, and the /health endpoint. The split
keeps each concern in its own module so a change to (e.g.) rate-limit
middleware doesn't make engineers scroll through health-probe code.

Public surface:
    lifespan              — async context manager bound to app.state
    register_middlewares  — adds CORS, security, capability gate,
                            request-id, 5xx monitor, rate-limit, admin
                            rate-limit (in registration order — Starlette
                            applies middleware LIFO on the request path)
    register_routes       — include_router() for every router
    register_health       — mounts the /health endpoint with latency
                            probes for Supabase + Redis

main.py now just builds the FastAPI() instance and calls each of
these in order.
"""
from app.setup.health import register_health
from app.setup.lifespan import lifespan
from app.setup.middleware import register_middlewares
from app.setup.routes import register_routes

__all__ = [
    "lifespan",
    "register_health",
    "register_middlewares",
    "register_routes",
]
