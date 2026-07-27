from fastapi import APIRouter

from ._common import API_VERSION
from .sessions import get_router as get_session_router


def get_router(*args, **kwargs) -> APIRouter:
    router = APIRouter(prefix=f"/{API_VERSION}")
    router.include_router(get_session_router(*args, **kwargs))
    return router


__all__ = ["get_router"]
