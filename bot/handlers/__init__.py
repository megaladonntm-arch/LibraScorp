from aiogram import Router

from .common import router as common_router


def setup_routers() -> Router:
    root_router = Router()
    root_router.include_router(common_router)
    return root_router

