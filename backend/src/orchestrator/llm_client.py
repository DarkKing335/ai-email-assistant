"""
LLM client — provider-agnostic.

Thứ tự thử: OpenAI (primary) -> Gemini (fallback) -> Mock (khi không có key).
Mỗi provider trả về JSON đã parse (dict). Orchestrator sẽ validate bằng Pydantic.
"""
import json
from typing import Any, Dict, List, Tuple

from .config import settings


class LLMRoutingError(Exception):
    """Ném ra khi TẤT CẢ provider đều thất bại."""


def _extract_json(text: str) -> Dict[str, Any]:
    """Tách khối JSON đầu tiên trong text (phòng khi model bọc ```json ... ```)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # bỏ tiền tố 'json' nếu có
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Không tìm thấy JSON trong output: {text[:200]}")
    return json.loads(text[start : end + 1])


class LLMClient:
    """
    Gọi LLM để routing. Trả về (parsed_json, provider_name).

    Dùng response format JSON để đảm bảo output parse được, sau đó validate ở tầng
    Orchestrator bằng EmailRoutingSchema (nguồn chân lý duy nhất về cấu trúc).
    """

    def route(
        self, system_prompt: str, user_content: str, json_schema: dict
    ) -> Tuple[Dict[str, Any], str]:
        errors: List[str] = []

        # Ép model trả JSON theo đúng schema (nhét schema vào system prompt).
        schema_hint = (
            f"{system_prompt}\n\n"
            f"Trả về DUY NHẤT một JSON object hợp lệ theo JSON Schema sau, không thêm text nào khác:\n"
            f"{json.dumps(json_schema, ensure_ascii=False)}"
        )

        if settings.has_openai:
            try:
                return self._route_openai(schema_hint, user_content), "openai"
            except Exception as e:  # noqa: BLE001 - gom lỗi để fallback
                errors.append(f"openai: {e}")

        if settings.has_gemini:
            try:
                return self._route_gemini(schema_hint, user_content), "gemini"
            except Exception as e:  # noqa: BLE001
                errors.append(f"gemini: {e}")

        # Không có key nào (hoặc mọi provider fail nhưng vẫn muốn chạy demo) -> Mock.
        if not settings.has_openai and not settings.has_gemini:
            return self._route_mock(user_content), "mock"

        raise LLMRoutingError("Tất cả provider thất bại -> " + " | ".join(errors))

    # ------------------------------------------------------------------ OpenAI
    def _route_openai(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return _extract_json(resp.choices[0].message.content or "")

    # ------------------------------------------------------------------ Gemini
    def _route_gemini(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system_prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        resp = model.generate_content(user_content)
        return _extract_json(resp.text or "")

    # -------------------------------------------------------------------- Mock
    def _route_mock(self, user_content: str) -> Dict[str, Any]:
        """
        Routing giả lập bằng keyword — để chạy end-to-end khi CHƯA có API key.
        Không thông minh, chỉ đủ để demo luồng.
        """
        text = user_content.lower()
        tech_kw = ["lỗi", "error", "đăng nhập", "login", "không thể", "sự cố", "bug"]
        price_kw = ["giá", "price", "bảng giá", "gói", "package", "thanh toán", "nâng cấp"]

        if any(k in text for k in tech_kw):
            template_id, data = "TECH_SUPPORT", {
                "customer_name": "Quý khách",
                "error_summary": "sự cố được mô tả trong email",
            }
        elif any(k in text for k in price_kw):
            template_id, data = "PRICING_INQUIRY", {
                "customer_name": "Quý khách",
                "package_name": "bạn quan tâm",
            }
        else:
            template_id, data = "GENERAL_GREETING", {"customer_name": "Quý khách"}

        return {
            "template_id": template_id,
            "extracted_data": data,
            # Đủ cao để vượt threshold cho mục đích demo luồng; provider thật sẽ trả confidence thật.
            "confidence_score": 0.85,
        }
