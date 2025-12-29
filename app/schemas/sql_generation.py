from pydantic import BaseModel, Field


class SQLGenerationSchema(BaseModel):
    """Schema dùng cho llm_with_structured để sinh SQL query."""

    sql: str = Field(
        description="SQL query được sinh ra để trả lời câu hỏi của người dùng. Query phải tuân thủ các quy tắc SQL đã được định nghĩa."
    )
    reason: str = Field(
        description="Lý do tại sao viết câu SQL như vậy, giải thích ngắn gọn về cách tiếp cận, các tables/columns được chọn, logic JOIN, WHERE conditions, và các quyết định thiết kế query."
    )

