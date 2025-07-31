# Utils/constants.py

class Colors:
    """Định nghĩa các mã màu để sử dụng thống nhất trong ứng dụng."""
    BLUE = "blue"
    GREY = "grey"
    RED = "red"
    ORANGE = "orange"
    GREEN = "green"
    DARK_BLUE = "#0078D4"

class Status:
    """Định nghĩa các chuỗi thông báo trạng thái."""
    # Trạng thái chờ và theo dõi
    STARTING = "Đang khởi động..."
    MONITORING = "🔍 Đang theo dõi..."
    WAITING_COUNTDOWN = "⏳ Chờ {mins:02d}:{secs:02d}"

    # Trạng thái hoạt động
    RECORDING = "🔴 Đang ghi hình..."
    STOPPING = "⏳ Đang dừng..."
    CANCELLING = "⏳ Đang hủy..."

    # Trạng thái kết thúc
    DONE_SUCCESS = "✔️ Hoàn tất"
    DONE_STOPPED = "✅ Đã dừng ghi hình"
    DONE_MONITORING_STOPPED = "✅ Đã dừng theo dõi"
    DONE_CANCELLED = "❌ Đã hủy"

    # Trạng thái lỗi
    ERROR_LIVESTREAM_ENDED = "Live kết thúc"
    ERROR_USER_NOT_FOUND = "⚠️ Lỗi: Không tìm thấy user"
    ERROR_AGE_RESTRICTED = "⚠️ Lỗi: Live giới hạn tuổi"
    ERROR_UNKNOWN = "⚠️ Lỗi: Thử lại..."
    ERROR_NO_STREAM_URL = "⚠️ Lỗi: Không lấy được link stream"
    ERROR_ON_STOP = "⚠️ Lỗi khi dừng"
    ERROR_RECORDING_FAILED = "🔥 Lỗi ghi hình"
