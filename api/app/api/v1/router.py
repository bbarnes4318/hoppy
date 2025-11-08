"""
API v1 router
"""
from fastapi import APIRouter
from app.api.v1 import auth, calls, metrics, partners, websocket

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(partners.router, prefix="/partners", tags=["partners"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])

