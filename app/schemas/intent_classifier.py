from typing import Literal
from pydantic import BaseModel, Field


class IntentClassifierSchema(BaseModel):
    """Schema dùng cho llm_with_structured để phân loại intent."""

    intent: Literal["text2sql", "out_of_scope"] = Field(
        description="Intent của người dùng: text2sql nếu câu hỏi hướng đến truy vấn database, out_of_scope nếu nằm ngoài lĩnh vực chuyên môn."
    )
    reason: str = Field(
        description="Lý do tại sao phân loại intent như vậy, giải thích ngắn gọn và rõ ràng."
    )




 