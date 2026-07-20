"""
Drafters — các implementation cho bước "viết bản nháp".

- TemplateRenderDrafter : render Jinja2 deterministic (1 câu cố định / template).
- LLMDrafter            : gọi LLM viết thư thật, tự lùi về template khi lỗi.

Cả hai đều implement interface `Drafter` (contracts.py) nên EmailOrchestrator
không cần biết đang dùng cái nào.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from src.config import get_settings
from src.email_module.services import EmailTemplateService
from src.email_module.templates import TEMPLATE_CATALOG, TemplateID
from src.summarization.models import SummarizationResult

from .llm_client import LLMClient

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# LLM drafter
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Bạn là trợ lý soạn email chuyên nghiệp. Nhiệm vụ: viết BẢN NHÁP THƯ TRẢ LỜI cho email đến, dựa trên bản tóm tắt được cung cấp.

QUY TẮC BẮT BUỘC:
1. Viết bằng ngôn ngữ có mã "{language}". Toàn bộ thư phải cùng một ngôn ngữ.
2. CHỈ trả về phần thân thư. Không dòng tiêu đề, không "Subject:", không markdown, không giải thích, không đặt thư trong dấu ngoặc kép.
3. TUYỆT ĐỐI KHÔNG bịa thông tin cụ thể: không tự đặt giá, con số, ngày giờ, tên người, mã đơn hàng hay cam kết mà bản tóm tắt không nêu. Nếu cần thông tin chưa có, hãy hỏi lại người gửi.
4. Phản hồi đúng những điểm chính và việc cần làm trong tóm tắt.
5. Giữ giọng văn lịch sự, chuyên nghiệp, ngắn gọn — thường 3 đến 6 câu.
6. Đây là bản nháp cho người dùng xem lại rồi mới gửi, nên không hứa hẹn thay mặt họ những điều vượt quá nội dung tóm tắt.
7. KHÔNG ký tên cuối thư. Dừng lại sau câu cuối cùng của nội dung. Không viết "Trân trọng," kèm tên, không để chỗ trống dạng [Tên của bạn] hay [Your name] — người dùng tự thêm chữ ký của họ.

Ý ĐỊNH CỦA THƯ TRẢ LỜI (đã được phân loại): {intent}"""


class LLMDrafter:
    """
    Drafter dùng LLM để viết thư thật thay vì render một câu cố định.

    Vì sao cần: `TEMPLATE_CATALOG` chỉ có đúng một câu cho mỗi template, nên mọi
    email cùng loại đều nhận y hệt một câu trả lời. Đây là bước biến sản phẩm từ
    "chạy được" thành "dùng được".

    An toàn khi hỏng: mọi lỗi (không có API key, provider chết, output rỗng) đều
    lùi về `TemplateRenderDrafter`. Có bản nháp cứng vẫn tốt hơn là ném lỗi làm
    cả email bị đánh dấu FAILED — người dùng luôn có thứ gì đó để sửa.
    """

    def __init__(
        self,
        fallback: TemplateRenderDrafter | None = None,
        llm_client: LLMClient | None = None,
    ):
        self._fallback = fallback or TemplateRenderDrafter()
        self._llm = llm_client or LLMClient()

    def create_draft(
        self,
        template_id: str,
        extracted_data: Dict[str, Any],
        summary: SummarizationResult,
    ) -> str:
        try:
            system_prompt = _SYSTEM_PROMPT.format(
                language=summary.language or "vi",
                intent=self._intent_for(template_id),
            )
            text, provider = self._llm.compose(
                system_prompt, self._build_user_content(extracted_data, summary)
            )
            draft = _clean(text)
            if not draft:
                raise ValueError("LLM trả về bản nháp rỗng sau khi làm sạch.")

            logger.info(
                "llm_drafter_ok template=%s provider=%s chars=%d",
                template_id,
                provider,
                len(draft),
            )
            return draft

        except Exception as exc:  # noqa: BLE001 - luôn phải có bản nháp
            logger.warning(
                "llm_drafter_fallback template=%s error=%s", template_id, exc
            )
            return self._fallback.create_draft(template_id, extracted_data, summary)

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _intent_for(template_id: str) -> str:
        """Mô tả nghiệp vụ của template đã chọn, lấy từ catalog dùng chung."""
        try:
            return TEMPLATE_CATALOG[TemplateID(template_id)]["description"]
        except (KeyError, ValueError):
            return "Phản hồi chung, lịch sự."

    @staticmethod
    def _build_user_content(
        extracted_data: Dict[str, Any], summary: SummarizationResult
    ) -> str:
        parts = [f"TÓM TẮT EMAIL ĐẾN:\n{summary.overview}"]

        if summary.key_points:
            parts.append("ĐIỂM CHÍNH:")
            parts.extend(f"- {p.text}" for p in summary.key_points)

        if summary.action_items:
            parts.append("VIỆC CẦN LÀM:")
            for item in summary.action_items:
                owner = f" (phụ trách: {item.owner})" if item.owner else ""
                deadline = f" [hạn: {item.deadline}]" if item.deadline else ""
                parts.append(f"- {item.task}{owner}{deadline}")

        # Dữ liệu router trích xuất (tên khách, tên gói...) để xưng hô cho đúng.
        known = {k: v for k, v in extracted_data.items() if v}
        if known:
            parts.append("THÔNG TIN ĐÃ BIẾT:")
            parts.extend(f"- {k}: {v}" for k, v in known.items())

        if summary.truncated:
            parts.append(
                "(Lưu ý: nội dung gốc đã bị cắt bớt — tránh khẳng định chắc chắn "
                "về những phần không có trong tóm tắt.)"
            )

        parts.append("\nViết bản nháp thư trả lời:")
        return "\n".join(parts)


# Model hay bọc kết quả trong ```...``` hoặc mở đầu bằng "Chắc chắn rồi, đây là...".
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n?|\n?```$")
_PREAMBLE_RE = re.compile(
    r"^\s*(?:(?:đây là|dưới đây là|chắc chắn|tất nhiên|sure|here(?:'s| is))[^\n]*:\s*\n)",
    re.IGNORECASE,
)
_SUBJECT_RE = re.compile(r"^\s*(?:subject|tiêu đề|chủ đề)\s*:[^\n]*\n+", re.IGNORECASE)
# Model vẫn hay ký tên dù đã dặn, và để lại chỗ trống kiểu "[Tên của bạn]".
# Chữ ký thật do người dùng tự thêm, nên cắt phần đuôi này đi.
_SIGNATURE_RE = re.compile(
    r"\n+(?:trân trọng|thân mến|best regards|kind regards|regards|sincerely|thanks)\s*,?\s*"
    r"(?:\n+\[[^\]]*\]|\n+\{\{[^}]*\}\})?\s*$",
    re.IGNORECASE,
)
_PLACEHOLDER_TAIL_RE = re.compile(r"\n+\[[^\]]*\]\s*$")


def _clean(text: str) -> str:
    """Bỏ những thứ model hay thêm vào dù đã dặn: fence, lời dẫn, Subject, chữ ký."""
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    cleaned = _PREAMBLE_RE.sub("", cleaned)
    cleaned = _SUBJECT_RE.sub("", cleaned)
    cleaned = _SIGNATURE_RE.sub("", cleaned)
    cleaned = _PLACEHOLDER_TAIL_RE.sub("", cleaned)
    return cleaned.strip()


def build_default_drafter(
    template_service: EmailTemplateService | None = None,
) -> TemplateRenderDrafter | LLMDrafter:
    """
    Chọn drafter theo cấu hình hiện có.

    Có API key -> LLMDrafter (viết thư thật). Không có -> template tĩnh, để
    `uv run` vẫn chạy end-to-end mà không cần key nào.
    """
    fallback = TemplateRenderDrafter(template_service)
    settings = get_settings()
    if settings.has_groq or settings.has_gemini:
        return LLMDrafter(fallback=fallback)
    return fallback
