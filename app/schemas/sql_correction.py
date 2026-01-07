from pydantic import BaseModel, Field


class SQLCorrectionSchema(BaseModel):
    """Schema dùng cho llm_with_structured để sửa SQL bị lỗi."""

    sql: str = Field(
        description=(
            "Phiên bản SQL đã được sửa để khắc phục lỗi khi thực thi, "
            "vẫn tuân thủ các quy tắc an toàn (chỉ SELECT, không thay đổi dữ liệu)."
        )
    )
    reason: str = Field(
        description=(
            "Giải thích ngắn gọn cách sửa: bảng/cột nào được đổi, "
            "cách điều chỉnh JOIN/WHERE/kiểu dữ liệu để tránh lỗi."
        )
    )


