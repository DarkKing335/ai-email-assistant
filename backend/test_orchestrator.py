"""
Demo luồng Orchestrator end-to-end.

Chạy từ thư mục backend/:   python test_orchestrator.py

- Nếu CHƯA điền API key trong .env  -> dùng Mock provider (keyword routing).
- Nếu đã điền OPENAI_API_KEY        -> gọi OpenAI thật (fallback Gemini nếu lỗi).
"""
import sys

# Console Windows mặc định cp1252 -> ép UTF-8 để in được tiếng Việt.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.orchestrator import EmailOrchestrator, EmailSummary

orchestrator = EmailOrchestrator()

samples = [
    EmailSummary(
        summary_text="Khách báo không thể đăng nhập, gặp lỗi 404 ở trang chủ.",
        sender="an.nguyen@example.com",
        subject="Không vào được hệ thống",
    ),
    EmailSummary(
        summary_text="Khách hỏi về bảng giá và muốn nâng cấp gói Premium.",
        sender="binh.tran@example.com",
        subject="Hỏi giá dịch vụ",
    ),
    EmailSummary(
        summary_text="Khách chỉ chào hỏi và cảm ơn đội ngũ.",
        sender="chi.le@example.com",
    ),
]

for i, s in enumerate(samples, 1):
    result = orchestrator.run(s)
    print(f"\n===== EMAIL #{i} =====")
    print(f"Provider     : {result.provider_used}")
    print(f"Template     : {result.template_id}  (confidence={result.confidence_score}, fallback={result.used_fallback})")
    print(f"Extracted    : {result.extracted_data}")
    print(f"--- DRAFT ---\n{result.draft_text}")
