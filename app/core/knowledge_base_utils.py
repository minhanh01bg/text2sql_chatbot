"""
Helper functions để xử lý knowledge base documents:
- Load DOCX files sử dụng LangChain loaders
- Convert DOCX -> Markdown để giữ format (tables, headers, lists)
- Split markdown thành chunks với strategy đặc biệt cho tables
- Tạo embeddings và lưu vào MongoDB
"""
import logging
import tempfile
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document
from langchain_community.document_transformers import MarkdownifyTransformer

logger = logging.getLogger(__name__)


# Khởi tạo MarkdownifyTransformer để convert DOCX -> Markdown
md_transformer = MarkdownifyTransformer()

# Khởi tạo text splitter với config chuẩn cho project
# Separators được tối ưu cho markdown: giữ nguyên table blocks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    add_start_index=True,
    separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],  # Thêm "\n\n\n" để tách sections lớn
)

# Header splitter để split theo markdown headers trước
header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
)


def load_docx_file(file_path: str) -> List[Document]:
    """
    Load DOCX file sử dụng LangChain Docx2txtLoader.
    
    Args:
        file_path: Đường dẫn đến file DOCX
        
    Returns:
        List LangChain Document objects từ file DOCX
        
    Raises:
        FileNotFoundError: Nếu file không tồn tại
        Exception: Nếu không thể load file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        loader = Docx2txtLoader(file_path=file_path)
        documents = loader.load()
        
        logger.info(f"Loaded DOCX file: {len(documents)} documents from {file_path}")
        
        return documents
    except Exception as e:
        logger.error(f"Error loading DOCX file {file_path}: {e}", exc_info=True)
        raise


def load_docx_from_bytes(file_content: bytes, filename: str = "temp.docx") -> List[Document]:
    """
    Load DOCX từ bytes content (từ file upload) và convert sang Markdown.
    
    Args:
        file_content: Bytes content của file DOCX
        filename: Tên file tạm (chỉ để debug)
        
    Returns:
        List LangChain Document objects đã được convert sang Markdown
        
    Raises:
        Exception: Nếu không thể load file
    """
    # Tạo temporary file để Docx2txtLoader có thể đọc
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
        tmp_file.write(file_content)
        tmp_file_path = tmp_file.name
    
    try:
        # Load DOCX
        documents = load_docx_file(tmp_file_path)
        
        # Convert sang Markdown để giữ format (tables, headers, lists)
        markdown_documents = md_transformer.transform_documents(documents)
        
        logger.info(
            f"Converted DOCX to Markdown: {len(documents)} -> {len(markdown_documents)} documents"
        )
        
        return markdown_documents
    finally:
        # Xóa temporary file
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def detect_table_blocks(text: str) -> List[Tuple[int, int]]:
    """
    Detect các markdown table blocks trong text.
    
    Args:
        text: Markdown text
        
    Returns:
        List of tuples (start_index, end_index) cho mỗi table block
    """
    table_pattern = r'\|[^\n]*\|(?:\n\|[^\n]*\|)+'
    tables = []
    
    for match in re.finditer(table_pattern, text):
        start = match.start()
        end = match.end()
        tables.append((start, end))
    
    return tables


def split_markdown_with_table_awareness(
    documents: List[Document],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Document]:
    """
    Split markdown documents với awareness về tables:
    - Split theo headers trước (section-level)
    - Trong mỗi section, split text nhưng giữ nguyên table blocks
    - Nếu table quá lớn, giữ nguyên và đánh dấu trong metadata
    
    Args:
        documents: List LangChain Document objects (đã là markdown)
        metadata: Metadata bổ sung cho mỗi chunk
        
    Returns:
        List LangChain Document objects đã được split
    """
    if not documents:
        logger.warning("Empty documents list provided for splitting")
        return []
    
    # Merge metadata vào documents trước khi split
    if metadata:
        for doc in documents:
            if doc.metadata:
                doc.metadata.update(metadata)
            else:
                doc.metadata = metadata.copy()
    
    all_chunks = []
    
    for doc in documents:
        text = doc.page_content
        doc_metadata = doc.metadata.copy() if doc.metadata else {}
        
        # Detect tables trong document
        table_blocks = detect_table_blocks(text)
        logger.debug(f"Found {len(table_blocks)} table blocks in document")
        
        # Strategy 1: Split theo headers trước (nếu có headers)
        try:
            header_splits = header_splitter.split_text(text)
            if len(header_splits) > 1:
                logger.info(f"Split document into {len(header_splits)} sections by headers")
                # Mỗi header split là một section, tiếp tục split nhỏ hơn
                for header_doc in header_splits:
                    section_text = header_doc.page_content
                    section_metadata = {**doc_metadata, **(header_doc.metadata or {})}
                    
                    # Split section thành chunks nhỏ hơn (nhưng giữ tables)
                    section_chunks = _split_section_preserving_tables(
                        section_text, section_metadata
                    )
                    all_chunks.extend(section_chunks)
            else:
                # Không có headers, split trực tiếp
                chunks = _split_section_preserving_tables(text, doc_metadata)
                all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Header splitting failed, falling back to direct split: {e}")
            # Fallback: split trực tiếp
            chunks = _split_section_preserving_tables(text, doc_metadata)
            all_chunks.extend(chunks)
    
    logger.info(f"Split {len(documents)} documents into {len(all_chunks)} chunks")
    return all_chunks


def _split_section_preserving_tables(
    text: str, metadata: Dict[str, Any]
) -> List[Document]:
    """
    Split một section markdown thành chunks, giữ nguyên table blocks.
    
    Strategy:
    - Detect table blocks
    - Split text giữa các tables
    - Mỗi chunk có thể chứa: text trước table + table + text sau table
    - Nếu table quá lớn (> chunk_size), giữ nguyên và đánh dấu
    """
    table_blocks = detect_table_blocks(text)
    
    if not table_blocks:
        # Không có tables, split bình thường
        chunks = text_splitter.create_documents([text], metadatas=[metadata])
        return chunks
    
    # Có tables, cần xử lý đặc biệt
    chunks = []
    last_end = 0
    
    for table_start, table_end in table_blocks:
        # Text trước table
        text_before = text[last_end:table_start].strip()
        # Table block
        table_text = text[table_start:table_end]
        
        if text_before:
            # Split text trước table
            before_chunks = text_splitter.create_documents(
                [text_before], metadatas=[metadata]
            )
            chunks.extend(before_chunks)
        
        # Table block: giữ nguyên (không split)
        # Nếu table quá lớn, vẫn giữ nguyên và đánh dấu
        table_metadata = metadata.copy()
        table_metadata["has_table"] = True
        table_metadata["table_size"] = len(table_text)
        
        table_chunk = Document(page_content=table_text, metadata=table_metadata)
        chunks.append(table_chunk)
        
        last_end = table_end
    
    # Text sau table cuối cùng
    text_after = text[last_end:].strip()
    if text_after:
        after_chunks = text_splitter.create_documents(
            [text_after], metadatas=[metadata]
        )
        chunks.extend(after_chunks)
    
    return chunks


def split_documents_into_chunks(
    documents: List[Document],
    metadata: Optional[Dict[str, Any]] = None,
    use_markdown_splitting: bool = True,
) -> List[Document]:
    """
    Split documents thành chunks.
    
    Nếu documents đã là markdown (từ MarkdownifyTransformer), sẽ dùng
    table-aware splitting để giữ nguyên table blocks.
    
    Args:
        documents: List LangChain Document objects cần split
        metadata: Metadata bổ sung cho mỗi chunk
        use_markdown_splitting: Nếu True, dùng markdown-aware splitting (giữ tables)
        
    Returns:
        List LangChain Document objects đã được split thành chunks
    """
    if not documents:
        logger.warning("Empty documents list provided for splitting")
        return []
    
    if use_markdown_splitting:
        # Dùng markdown-aware splitting (giữ tables)
        return split_markdown_with_table_awareness(documents, metadata)
    else:
        # Split bình thường (fallback)
        if metadata:
            for doc in documents:
                if doc.metadata:
                    doc.metadata.update(metadata)
                else:
                    doc.metadata = metadata.copy()
        
        try:
            chunked_docs = text_splitter.split_documents(documents)
            logger.info(
                f"Split {len(documents)} documents into {len(chunked_docs)} chunks "
                f"(chunk_size={text_splitter._chunk_size}, overlap={text_splitter._chunk_overlap})"
            )
            return chunked_docs
        except Exception as e:
            logger.error(f"Error splitting documents: {e}", exc_info=True)
            raise


def prepare_chunks_for_embedding(
    chunked_documents: List[Document],
    document_id: str,
    source_id: str,
) -> List[Document]:
    """
    Chuẩn bị chunks với metadata đầy đủ để embedding và lưu vào MongoDB.
    
    Args:
        chunked_documents: List Document đã được split
        document_id: ID của KnowledgeBaseDocument
        source_id: Source ID (file_id)
        
    Returns:
        List Document với metadata đầy đủ
    """
    prepared_docs = []
    
    for idx, doc in enumerate(chunked_documents):
        # Đảm bảo metadata có đầy đủ thông tin
        doc.metadata = doc.metadata or {}
        doc.metadata.update({
            "document_id": document_id,
            "source_id": source_id,
            "chunk_index": idx,
        })
        
        prepared_docs.append(doc)
    
    logger.info(f"Prepared {len(prepared_docs)} chunks for embedding")
    
    return prepared_docs
