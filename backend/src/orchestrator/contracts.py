"""
Contracts (hợp đồng dữ liệu) — các "điểm chuyển dữ liệu" giữa Orchestrator và teammate.

- EmailSummary : Input mà Summarizer đưa cho Orchestrator.
- DraftResult  : Output cuối cùng Orchestrator trả về.
- Drafter      : Interface (khe cắm) để bước "viết email" plug vào.
"""
from typing import Any, Dict, Optional, Protocol
from pydantic import BaseModel, Field


class EmailSummary(BaseModel):
    """Đầu vào từ Summarizer. Đây là hợp đồng để teammate summarizer plug vào."""
    summary_text: str = Field(description="Bản tóm tắt nội dung email của khách.")
    sender: Optional[str] = Field(default=None, description="Người gửi email.")
    subject: Optional[str] = Field(default=None, description="Tiêu đề email gốc.")
    raw_email: Optional[str] = Field(default=None, description="Nội dung email gốc (nếu cần).")


class DraftResult(BaseModel):
    """Kết quả cuối cùng Orchestrator trả về cho caller (API layer / UI)."""
    draft_text: str = Field(description="Bản nháp email hoàn chỉnh để gửi/review.")
    template_id: str = Field(description="Template đã được chọn để định tuyến.")
    confidence_score: float = Field(description="Độ tự tin của quyết định routing.")
    extracted_data: Dict[str, Any] = Field(description="Dữ liệu LLM trích xuất từ summary.")
    provider_used: str = Field(description="Provider đã tạo kết quả: openai | gemini | mock.")
    used_fallback: bool = Field(
        default=False,
        description="True nếu đã degrade về template mặc định (GENERAL_GREETING).",
    )


class Drafter(Protocol):
    """
    Interface cho bước tạo bản nháp.

    Orchestrator chỉ CHUYỂN DỮ LIỆU cho create_draft() — không tự viết mail.
    Teammate (hoặc renderer sẵn có) implement interface này rồi cắm vào Orchestrator.
    """

    def create_draft(
        self,
        template_id: str,
        extracted_data: Dict[str, Any],
        summary: EmailSummary,
    ) -> str:
        ...
