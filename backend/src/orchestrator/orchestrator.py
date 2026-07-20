"""
EmailOrchestrator — nhạc trưởng của luồng.

run(summary):
    1. build routing prompt (catalog + json schema)  [từ email_module]
    2. LLM routing call (Groq -> Gemini -> Mock)
    3. validate + confidence/fallback
    4. delegate cho Drafter (chỉ chuyển dữ liệu)
    5. trả DraftResult
"""
from pydantic import ValidationError

from src.config import get_settings
from src.email_module.schemas import EmailRoutingSchema
from src.email_module.services import EmailTemplateService
from src.email_module.templates import TemplateID
from src.summarization.models import SummarizationResult

from .contracts import Drafter, DraftResult
from .drafters import build_default_drafter
from .llm_client import LLMClient

# Template an toàn khi mọi thứ khác thất bại.
_FALLBACK_TEMPLATE = TemplateID.GENERAL_GREETING.value


class EmailOrchestrator:
    def __init__(
        self,
        template_service: EmailTemplateService | None = None,
        llm_client: LLMClient | None = None,
        drafter: Drafter | None = None,
    ):
        self.template_service = template_service or EmailTemplateService()
        self.llm_client = llm_client or LLMClient()
        # Drafter mặc định = LLM khi có API key, ngược lại render deterministic.
        # Truyền `drafter=` để ép dùng một implementation cụ thể (test, so sánh).
        self.drafter: Drafter = drafter or build_default_drafter(self.template_service)

    def run(self, summary: SummarizationResult) -> DraftResult:
        # 1. Chuẩn bị "vũ khí" cho LLM (email_module đã dọn sẵn).
        system_prompt = self.template_service.get_llm_system_prompt_context()
        json_schema = self.template_service.get_json_schema_for_tools()
        user_content = self._build_user_content(summary)

        # 2. Gọi LLM để routing.
        raw, provider = self.llm_client.route(system_prompt, user_content, json_schema)

        # 3. Validate output bằng schema chuẩn của email_module.
        try:
            routing = EmailRoutingSchema.model_validate(raw)
            template_id = routing.template_id.value
            extracted_data = dict(routing.extracted_data)
            confidence = routing.confidence_score
            used_fallback = False
        except ValidationError:
            template_id, extracted_data, confidence, used_fallback = (
                _FALLBACK_TEMPLATE, {"customer_name": "Quý khách"}, 0.0, True,
            )

        # 3b. Confidence thấp -> degrade an toàn.
        if confidence < get_settings().confidence_threshold and template_id != _FALLBACK_TEMPLATE:
            template_id, used_fallback = _FALLBACK_TEMPLATE, True
            extracted_data.setdefault("customer_name", "Quý khách")

        # 4. Ủy quyền tạo bản nháp (chỉ chuyển dữ liệu).
        try:
            draft_text = self.drafter.create_draft(template_id, extracted_data, summary)
        except ValueError:
            # Thiếu dữ liệu cho template đã chọn -> degrade về template chào hỏi.
            template_id, used_fallback = _FALLBACK_TEMPLATE, True
            extracted_data.setdefault("customer_name", "Quý khách")
            draft_text = self.drafter.create_draft(template_id, extracted_data, summary)

        # 5. Trả kết quả.
        return DraftResult(
            draft_text=draft_text,
            template_id=template_id,
            confidence_score=confidence,
            extracted_data=extracted_data,
            provider_used=provider,
            used_fallback=used_fallback,
        )

    @staticmethod
    def _build_user_content(summary: SummarizationResult) -> str:
        # Dùng trực tiếp output có cấu trúc của Summarizer làm ngữ cảnh routing.
        parts = [f"Tóm tắt email: {summary.overview}"]

        if summary.key_points:
            parts.append("Điểm chính:")
            parts.extend(f"- {point.text}" for point in summary.key_points)

        if summary.action_items:
            parts.append("Hành động cần làm:")
            for item in summary.action_items:
                owner = f" (phụ trách: {item.owner})" if item.owner else ""
                deadline = f" [hạn: {item.deadline}]" if item.deadline else ""
                parts.append(f"- {item.task}{owner}{deadline}")

        return "\n".join(parts)
