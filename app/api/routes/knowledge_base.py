"""
API routes cho knowledge base: upload và quản lý documents.
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.services.knowledge_base_service import process_and_save_docx_file

logger = logging.getLogger(__name__)

router = APIRouter()


class UploadDocxResponse(BaseModel):
    """Response model cho upload DOCX endpoint."""
    success: bool
    document_id: str
    source_id: str
    chunk_count: int
    embedding_ids: list[str]
    filename: str
    message: str


@router.post("/upload-docx", response_model=UploadDocxResponse)
async def upload_docx_file(
    file: UploadFile = File(..., description="DOCX file to upload"),
    title: Optional[str] = Form(None, description="Title of the document"),
    description: Optional[str] = Form(None, description="Description of the document"),
    source_id: Optional[str] = Form(None, description="Source ID (auto-generated if not provided)"),
):
    """
    Upload DOCX file và xử lý:
    - Parse DOCX và convert sang Markdown
    - Split thành chunks với table awareness
    - Tạo embeddings và lưu vào MongoDB
    
    Returns:
        UploadDocxResponse với thông tin document và chunks đã được lưu
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    if not file.filename.endswith(('.docx', '.DOCX')):
        raise HTTPException(
            status_code=400,
            detail="Only .docx files are supported"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(status_code=400, detail="File is empty")
        
        logger.info(f"Received DOCX upload: {file.filename} ({len(file_content)} bytes)")
        
        # Process file: load -> convert markdown -> split -> embed -> save
        result = await process_and_save_docx_file(
            file_content=file_content,
            filename=file.filename,
            source_id=source_id,
            title=title,
            description=description,
        )
        
        return UploadDocxResponse(
            success=True,
            document_id=result["document_id"],
            source_id=result["source_id"],
            chunk_count=result["chunk_count"],
            embedding_ids=result["embedding_ids"],
            filename=result["filename"],
            message=f"Successfully processed {result['chunk_count']} chunks from {file.filename}",
        )
        
    except ValueError as e:
        logger.error(f"Validation error processing DOCX: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing DOCX file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

