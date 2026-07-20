"""
LLM client — provider-agnostic.

Thứ tự thử: Groq (primary) -> Gemini (fallback) -> Mock (khi không có key).
Giống thứ tự provider của Summarizer để dùng chung cấu hình.
Mỗi provider trả về JSON đã parse (dict). Orchestrator sẽ validate bằng Pydantic.
"""
import json
from typing import Any, Dict, List, Tuple

from src.config import get_settings


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
        settings = get_settings()
        errors: List[str] = []

        # Ép model trả JSON theo đúng schema (nhét schema vào system prompt).
        schema_hint = (
            f"{system_prompt}\n\n"
            f"Trả về DUY NHẤT một JSON object hợp lệ theo JSON Schema sau, không thêm text nào khác:\n"
            f"{json.dumps(json_schema, ensure_ascii=False)}"
        )

        if settings.has_groq:
            try:
                return self._route_groq(schema_hint, user_content), "groq"
            except Exception as e:  # noqa: BLE001 - gom lỗi để fallback
                errors.append(f"groq: {e}")

        if settings.has_gemini:
            try:
                return self._route_gemini(schema_hint, user_content), "gemini"
            except Exception as e:  # noqa: BLE001
                errors.append(f"gemini: {e}")

        # Không có key nào (hoặc mọi provider fail nhưng vẫn muốn chạy demo) -> Mock.
        if not settings.has_groq and not settings.has_gemini:
            return self._route_mock(user_content), "mock"

        raise LLMRoutingError("Tất cả provider thất bại -> " + " | ".join(errors))

    # ----------------------------------------------------------------- Compose
    def compose(
        self, system_prompt: str, user_content: str, temperature: float = 0.3
    ) -> Tuple[str, str]:
        """
        Sinh văn bản tự do (KHÔNG phải JSON) — dùng cho bước viết bản nháp.

        Khác `route()` ở hai điểm: không ép response_format JSON, và temperature
        > 0 để câu chữ tự nhiên thay vì lặp khuôn. Trả về (text, provider_name).

        Không có mock: khi không có provider nào, caller (LLMDrafter) tự lùi về
        template tĩnh — bịa ra một bản nháp giả sẽ tệ hơn là dùng template thật.
        """
        settings = get_settings()
        errors: List[str] = []

        if settings.has_groq:
            try:
                return self._compose_groq(system_prompt, user_content, temperature), "groq"
            except Exception as e:  # noqa: BLE001 - gom lỗi để fallback
                errors.append(f"groq: {e}")

        if settings.has_gemini:
            try:
                return self._compose_gemini(system_prompt, user_content, temperature), "gemini"
            except Exception as e:  # noqa: BLE001
                errors.append(f"gemini: {e}")

        raise LLMRoutingError(
            "Không có provider nào cho việc soạn thảo -> " + (" | ".join(errors) or "chưa cấu hình API key")
        )

    def _compose_groq(self, system_prompt: str, user_content: str, temperature: float) -> str:
        from groq import Groq

        settings = get_settings()
        client = Groq(api_key=settings.groq_api_key.get_secret_value())
        resp = client.chat.completions.create(
            model=settings.groq_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("Groq trả về nội dung rỗng.")
        return text

    def _compose_gemini(self, system_prompt: str, user_content: str, temperature: float) -> str:
        from google import genai
        from google.genai import types

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        resp = client.models.generate_content(
            model=settings.gemini_model or "gemini-2.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        text = (resp.text or "").strip()
        if not text:
            raise ValueError("Gemini trả về nội dung rỗng.")
        return text

    # -------------------------------------------------------------------- Groq
    def _route_groq(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        from groq import Groq

        settings = get_settings()
        client = Groq(api_key=settings.groq_api_key.get_secret_value())
        resp = client.chat.completions.create(
            model=settings.groq_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return _extract_json(resp.choices[0].message.content or "")

    # ------------------------------------------------------------------ Gemini
    def _route_gemini(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        from google import genai
        from google.genai import types

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        resp = client.models.generate_content(
            model=settings.gemini_model or "gemini-2.5-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                response_mime_type="application/json",
            ),
        )
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
