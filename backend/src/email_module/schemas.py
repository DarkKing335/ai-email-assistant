from pydantic import BaseModel, Field
from typing import Dict, Any
from .templates import TemplateID

class EmailRoutingSchema(BaseModel):
    template_id: TemplateID = Field(
        description="Mã template định tuyến. Phải chọn chính xác 1 trong các giá trị Enum được cung cấp."
    )
    
    extracted_data: Dict[str, Any] = Field(
        description="Dữ liệu trích xuất từ email. BẮT BUỘC CÓ key 'customer_name'. NẾU template_id là TECH_SUPPORT, PHẢI CÓ key 'error_summary'. NẾU template_id là PRICING_INQUIRY, PHẢI CÓ key 'package_name'."
    )
    
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Mức độ tự tin của quyết định định tuyến, giá trị từ 0.0 đến 1.0."
    )