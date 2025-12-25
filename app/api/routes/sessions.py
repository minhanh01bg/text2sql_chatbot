from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.session import SessionResponse
from app.services.chat_session_service import chat_session_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[SessionResponse])
async def get_all_sessions(skip: int = 0, limit: int = 100):
    """Get all chat sessions"""
    try:
        results = await chat_session_service.get_all(skip=skip, limit=limit)
        return [SessionResponse(**session) for session in results]
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_by_id(session_id: str):
    """Get session by document ID"""
    try:
        session = await chat_session_service.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session by id: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session-id/{session_id}", response_model=SessionResponse)
async def get_session_by_session_id(session_id: str):
    """Get session by session_id"""
    try:
        session = await chat_session_service.get_by_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session by session_id: {e}")
        raise HTTPException(status_code=500, detail=str(e))

