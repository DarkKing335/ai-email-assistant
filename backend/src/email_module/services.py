import json
from jinja2 import Environment, BaseLoader, StrictUndefined
from jinja2.exceptions import UndefinedError

from .schemas import EmailRoutingSchema
from .templates import TEMPLATE_CATALOG, TemplateID

class EmailTemplateService:
    def __init__(self):
        # Sử dụng StrictUndefined: Nếu thiếu biến truyền vào template, Jinja2 sẽ quăng Exception thay vì để trống
        self.jinja_env = Environment(loader=BaseLoader(), undefined=StrictUndefined)

    # ==========================================
    # CÁC HÀM DÀNH CHO ORCHESTRATOR (LLM)
    # ==========================================
    def get_llm_system_prompt_context(self) -> str:
        """
        Xuất danh sách đặc trưng template để người làm Orchestrator nhét vào System Prompt.
        """
        context_lines = ["Danh sách các Template ID và điều kiện sử dụng:"]
        for t_id, data in TEMPLATE_CATALOG.items():
            context_lines.append(f"- {t_id.value}: {data['description']}")
        return "\n".join(context_lines)

    def get_json_schema_for_tools(self) -> dict:
        """
        Xuất cấu trúc JSON Schema chuẩn từ Pydantic để đẩy vào API của OpenAI/Gemini.
        """
        return EmailRoutingSchema.model_json_schema()

    # ==========================================
    # HÀM KẾT XUẤT SAU KHI LLM TRẢ KẾT QUẢ
    # ==========================================
    def generate_final_email(self, template_id_str: str, extracted_data: dict) -> str:
        """
        Hàm nhận kết quả từ LLM, tìm template và bơm dữ liệu.
        """
        try:
            # Ép kiểu an toàn từ chuỗi sang Enum
            template_id = TemplateID(template_id_str)
        except ValueError:
            raise ValueError(f"Mã template '{template_id_str}' không tồn tại trong hệ thống.")

        # Lấy nội dung template thô
        raw_content = TEMPLATE_CATALOG[template_id]["content"]
        
        # Load template vào Jinja2 Engine
        template = self.jinja_env.from_string(raw_content)

        try:
            # Bơm dữ liệu (Hydration)
            final_email = template.render(**extracted_data)
            return final_email
        except UndefinedError as e:
            raise ValueError(f"LLM trích xuất thiếu dữ liệu cho template {template_id.value}: {e}")