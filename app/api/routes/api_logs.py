from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.api_log import ApiLogResponse
from app.services.api_log_service import api_log_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[ApiLogResponse])
async def get_all_api_logs(skip: int = 0, limit: int = 100):
    """Get all API logs"""
    try:
        results = await api_log_service.get_all(skip=skip, limit=limit)
        return [ApiLogResponse(**log) for log in results]
    except Exception as e:
        logger.error(f"Error getting API logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{log_id}", response_model=ApiLogResponse)
async def get_api_log(log_id: str):
    """Get API log by ID"""
    try:
        log = await api_log_service.get_by_id(log_id)
        if not log:
            raise HTTPException(status_code=404, detail="API log not found")
        return ApiLogResponse(**log)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/path/{path:path}", response_model=List[ApiLogResponse])
async def get_api_logs_by_path(path: str, skip: int = 0, limit: int = 100):
    """Get API logs by path"""
    try:
        results = await api_log_service.get_by_path(path, skip=skip, limit=limit)
        return [ApiLogResponse(**log) for log in results]
    except Exception as e:
        logger.error(f"Error getting API logs by path: {e}")
        raise HTTPException(status_code=500, detail=str(e))

