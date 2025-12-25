from typing import Literal
from pydantic import BaseModel, Field


class IntentClassifierSchema(BaseModel):
    """Schema dùng cho llm_with_structured để phân loại intent."""

    intent: Literal["consultation", "course_registration", "general"] = Field(
        description="Intent của người dùng."
    )




