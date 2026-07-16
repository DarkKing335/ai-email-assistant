# Orchestrator — Design & Plan

> Phần việc: **Orchestrator** (người điều phối / "nhạc trưởng").
> Nhiệm vụ chính là **điều phối** các phần khác và **luân chuyển dữ liệu** giữa chúng,
> cộng với **một quyết định** cốt lõi: chọn template nào cho email.

## 1. Orchestrator làm gì (và KHÔNG làm gì)

Orchestrator **không** tự viết summarizer, cũng **không** bắt buộc tự viết drafter.
Nó là người điều phối:

1. **Nhận** `EmailSummary` từ Summarizer (teammate khác làm).
2. **Routing call (LLM)** — "email này hợp template nào?" + trích xuất dữ liệu
   → trả về `EmailRoutingSchema` (`template_id`, `extracted_data`, `confidence_score`).
   Đây chính là việc mà `email_module` đã dọn sẵn cho Orchestrator
   (`get_llm_system_prompt_context()`, `get_json_schema_for_tools()`).
3. **Validate / fallback** — nếu `confidence_score` thấp, hoặc thiếu dữ liệu bắt buộc
   → degrade về `GENERAL_GREETING`.
4. **Ủy quyền (delegate)** việc tạo bản nháp cho một `Drafter` (interface).
   Việc "viết email" thực sự có thể do teammate làm, hoặc dùng bản render sẵn có.
   Orchestrator chỉ **chuyển dữ liệu** cho Drafter — không tự nhúng logic viết mail.
5. **Trả về** `DraftResult`.

## 2. Provider LLM

- Provider-agnostic client: **OpenAI primary → Gemini fallback**.
- Fallback kích hoạt khi OpenAI lỗi/timeout.
- Nếu **không có API key nào** → dùng **Mock provider** (deterministic keyword routing)
  để cả luồng chạy được ngay mà không tốn tiền / chưa cần key.

## 3. Cấu trúc thư mục

```
backend/src/orchestrator/
├── __init__.py
├── config.py         # đọc API key, model name, confidence threshold từ .env
├── contracts.py      # EmailSummary (input), DraftResult (output), Drafter protocol
├── llm_client.py     # OpenAI → Gemini → Mock; trả JSON đã parse
├── drafters.py       # TemplateRenderDrafter (mặc định, bọc generate_final_email)
└── orchestrator.py   # EmailOrchestrator.run(summary) -> DraftResult
```

## 4. Luồng end-to-end

```
summarizer ──EmailSummary──► [ORCHESTRATOR]
    1. build routing prompt (system prompt catalog + json schema)
    2. LLM routing call  (OpenAI → Gemini → Mock)
         → EmailRoutingSchema {template_id, extracted_data, confidence}
    3. validate: confidence < threshold? thiếu key? → fallback GENERAL_GREETING
    4. delegate → Drafter.create_draft(template_id, extracted_data, summary)
    5. return DraftResult {draft_text, template_id, confidence, extracted_data, provider_used}
```

## 5. Các "điểm chuyển dữ liệu" (contracts)

- **Input `EmailSummary`** (hợp đồng với Summarizer): `summary_text`, `sender`,
  `subject`, `raw_email` (optional).
- **Output `DraftResult`**: `draft_text`, `template_id`, `confidence_score`,
  `extracted_data`, `provider_used`.
- **`Drafter` interface**: `create_draft(template_id, extracted_data, summary) -> str`.
  Đây là "khe cắm" để teammate (hoặc renderer sẵn có) plug vào.

## 6. Edge cases

- Confidence thấp → `GENERAL_GREETING`.
- LLM trả JSON sai/thiếu field → validate lại bằng `EmailRoutingSchema`; fail → fallback.
- OpenAI lỗi → tự động fallback Gemini → Mock.
- `generate_final_email` raise `ValueError` (thiếu key) → catch → degrade `GENERAL_GREETING`.

## 7. Việc cần chốt với team

**Ai sở hữu Drafter** (bước LLM "viết email")? Plan chạy được cả 2 hướng vì Drafter
chỉ là một interface: hoặc ship drafter LLM thật, hoặc chỉ interface + stub render.
