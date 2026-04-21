"""Entry point: start uvicorn with the Starlette ASGI app."""

import logging
import uvicorn

from gateway.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

uvicorn.run(
    "gateway.server:app",
    host="0.0.0.0",
    port=settings.port,
    log_level=settings.log_level.lower(),
)
