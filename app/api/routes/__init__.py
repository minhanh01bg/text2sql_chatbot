from fastapi import APIRouter
from . import langgraph, sessions, api_logs

api_router = APIRouter()

api_router.include_router(
    langgraph.router, prefix="/graph", tags=["graph"]
)
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(api_logs.router, prefix="/api-logs", tags=["api-logs"])

