from src.email_module.services import EmailTemplateService

# Khởi tạo Service của bạn
service = EmailTemplateService()

# 1. Người làm Orchestrator gọi hàm của bạn để lấy "Vũ khí"
schema_for_llm = service.get_json_schema_for_tools()
prompt_for_llm = service.get_llm_system_prompt_context()

print("--- SCHEMA GỬI CHO LLM ---")
print(schema_for_llm)

# 2. Giả lập kết quả LLM trả về sau khi đọc email
mock_llm_response = {
    "template_id": "TECH_SUPPORT",
    "extracted_data": {
        "customer_name": "Nguyễn Văn A",
        "error_summary": "Lỗi 404 trang chủ"
    },
    "confidence_score": 0.98
}

# 3. Kết xuất email cuối cùng
final_text = service.generate_final_email(
    template_id_str=mock_llm_response["template_id"],
    extracted_data=mock_llm_response["extracted_data"]
)

print("\n--- EMAIL HOÀN CHỈNH ĐỂ GỬI ---")
print(final_text)