from fastapi import APIRouter
from . import langgraph, sessions, api_logs, knowledge_base

api_router = APIRouter()

api_router.include_router(
    langgraph.router, prefix="/graph", tags=["graph"]
)
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(api_logs.router, prefix="/api-logs", tags=["api-logs"])
api_router.include_router(
    knowledge_base.router, prefix="/knowledge", tags=["knowledge-base"]
)

