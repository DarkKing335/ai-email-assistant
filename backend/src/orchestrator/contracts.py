"""
Contracts (hợp đồng dữ liệu) — các "điểm chuyển dữ liệu" giữa Orchestrator và teammate.

- SummarizationResult : Input mà Summarizer đưa cho Orchestrator (định nghĩa trong
  src.summarization.models — Orchestrator dùng trực tiếp, không qua adapter).
- DraftResult         : Output cuối cùng Orchestrator trả về.
- Drafter             : Interface (khe cắm) để bước "viết email" plug vào.
"""
from typing import Any, Dict, Protocol
from pydantic import BaseModel, Field

from src.summarization.models import SummarizationResult


class DraftResult(BaseModel):
    """Kết quả cuối cùng Orchestrator trả về cho caller (API layer / UI)."""
    draft_text: str = Field(description="Bản nháp email hoàn chỉnh để gửi/review.")
    template_id: str = Field(description="Template đã được chọn để định tuyến.")
    confidence_score: float = Field(description="Độ tự tin của quyết định routing.")
    extracted_data: Dict[str, Any] = Field(description="Dữ liệu LLM trích xuất từ summary.")
    provider_used: str = Field(description="Provider đã tạo kết quả: groq | gemini | mock.")
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
        summary: SummarizationResult,
    ) -> str:
        ...
