from enum import Enum

class TemplateID(str, Enum):
    TECH_SUPPORT = "TECH_SUPPORT"
    PRICING_INQUIRY = "PRICING_INQUIRY"
    GENERAL_GREETING = "GENERAL_GREETING"

# Kho lưu trữ đặc trưng và nội dung thô
TEMPLATE_CATALOG = {
    TemplateID.TECH_SUPPORT: {
        "description": "Dùng KHI email của khách hàng báo cáo về lỗi hệ thống, không thể đăng nhập, hoặc các vấn đề kỹ thuật.",
        "content": "Chào {{ customer_name }}, hệ thống đã ghi nhận lỗi '{{ error_summary }}' của bạn. Đội ngũ kỹ thuật đang kiểm tra và sẽ phản hồi sớm nhất."
    },
    TemplateID.PRICING_INQUIRY: {
        "description": "Dùng KHI khách hàng hỏi về giá cả, bảng giá, nâng cấp gói dịch vụ hoặc thắc mắc thanh toán.",
        "content": "Kính gửi {{ customer_name }}, cảm ơn bạn đã quan tâm. Gói dịch vụ {{ package_name }} hiện đang có mức giá cực kỳ ưu đãi..."
    },
    TemplateID.GENERAL_GREETING: {
        "description": "Dùng KHI email chỉ mang tính chất chào hỏi chung chung, hoặc không khớp với các nghiệp vụ trên.",
        "content": "Xin chào {{ customer_name }}, cảm ơn bạn đã liên hệ. Chúng tôi có thể giúp gì cho bạn hôm nay?"
    }
}