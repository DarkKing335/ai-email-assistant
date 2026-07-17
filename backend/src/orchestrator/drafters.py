"""
Drafters — các implementation cho bước "viết bản nháp".

TemplateRenderDrafter là mặc định: bọc lại generate_final_email() sẵn có
(render Jinja2 deterministic). Đây là stub để luồng chạy được ngay.

Khi teammate làm Drafter bằng LLM, chỉ cần tạo class mới implement interface
`Drafter` (contracts.py) rồi truyền vào EmailOrchestrator — KHÔNG sửa code orchestrator.
"""
from typing import Any, Dict

from src.email_module.services import EmailTemplateService
from src.summarization.models import SummarizationResult


class TemplateRenderDrafter:
    """Drafter mặc định: render template Jinja2 với dữ liệu đã trích xuất."""

    def __init__(self, template_service: EmailTemplateService | None = None):
        self._service = template_service or EmailTemplateService()

    def create_draft(
        self,
        template_id: str,
        extracted_data: Dict[str, Any],
        summary: SummarizationResult,  # noqa: ARG002 - renderer deterministic không cần summary
    ) -> str:
        return self._service.generate_final_email(template_id, extracted_data)
