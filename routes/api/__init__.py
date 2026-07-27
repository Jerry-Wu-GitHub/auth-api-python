from typing import Callable

from fastapi import APIRouter

from .v1 import (
    API_VERSION as API_VERSION_V1,
    get_router as get_v1_router
)


def _wrapper(get_router: Callable[..., APIRouter]) -> Callable[..., APIRouter]:
    def get_api_router(*args, **kwargs) -> APIRouter:
        # 添加 /api 前缀
        router = APIRouter(prefix=f"/api", tags=["API"])
        router.include_router(get_router(*args, **kwargs))
        return router
    return get_api_router


get_v1_router = _wrapper(get_v1_router)


router_getters = {
    API_VERSION_V1: get_v1_router
}
