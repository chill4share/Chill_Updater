# Utils/logger_setup.py

import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import re

class SensitiveInfoFilter(logging.Filter):
    def __init__(self):
        super().__init__()

    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = re.sub(r'Output/[^/]+/', '', record.msg)
            record.msg = re.sub(r'sessionid giống mặc định|số lượng mục: \d+', '', record.msg)
            record.msg = re.sub(r'\(PID: \d+\)', '', record.msg)
            record.msg = re.sub(r'mã trạng thái: \d+', '', record.msg)
            record.msg = re.sub(r'Khởi tạo [^\s]+|Đã đọc file [^\s]+|API TikTok|Cấu trúc API|icon\.ico|biểu tượng', '', record.msg)
        return True

class MaxLevelFilter(logging.Filter):
    def __init__(self, max_level):
        super().__init__()
        self.max_level = max_level
    def filter(self, record):
        return record.levelno <= self.max_level

class PathShortenerFilter(logging.Filter):
    def __init__(self, base_path):
        super().__init__()
        self.base_path = os.path.normpath(base_path)

    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            normalized_msg = os.path.normpath(record.msg)
            if self.base_path in normalized_msg:
                record.msg = normalized_msg.replace(self.base_path, '').lstrip(os.sep).lstrip('/').replace('\\', '/')
            else:
                record.msg = normalized_msg.lstrip('/').lstrip(os.sep).replace('\\', '/')
        return True

class ProductionFilter(logging.Filter):
    def __init__(self, logged_messages):
        super().__init__()
        self.logged_messages = logged_messages
        self.allowed_keywords = [
            'FFmpeg', 'ghi hình', 'dừng', 'Hoàn tất', 'chuyển đổi', 'thành công',
            'Lỗi', 'lỗi', 'thất bại', 'Không thể', 'không tìm thấy', 'Cảnh báo',
            'bị chặn', 'hết thời gian', 'quá tải', 'rỗng', 'xóa', 'đóng'
        ]

    def filter(self, record):
        if record.levelno < logging.INFO:
            return False
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            if not any(keyword in record.msg for keyword in self.allowed_keywords):
                return False
            message_key = (record.msg, record.levelno)
            if message_key in self.logged_messages:
                return False
            self.logged_messages.add(message_key)
        return True

class LoggerManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance.loggers = {}
            # --- CẢI TIẾN: Thêm biến để lưu đường dẫn cơ sở ---
            cls._instance.base_path = None
            cls._instance.is_production = hasattr(sys, '_MEIPASS')
        return cls._instance

    def get_logger(self, name='application', base_path=None):
        if name in self.loggers:
            return self.loggers[name]

        # --- CẢI TIẾN: Logic "thông minh" để lưu và sử dụng base_path ---
        # 1. Nếu base_path của Manager chưa được set, và lần gọi này có cung cấp, hãy lưu lại.
        if self.base_path is None and base_path is not None:
            self.base_path = base_path
            # Log lần đầu tiên để xác nhận
            # (Phải tạo logger tạm thời để log, vì logger hiện tại chưa hoàn thành)
            temp_logger = logging.getLogger('setup')
            if not temp_logger.handlers:
                temp_handler = logging.StreamHandler()
                temp_logger.addHandler(temp_handler)
            temp_logger.info(f"[LoggerManager] Đường dẫn log cơ sở được thiết lập: {self.base_path}")

        # 2. Sử dụng đường dẫn đã lưu nếu lần gọi này không cung cấp
        effective_base_path = self.base_path if base_path is None else base_path

        # 3. Fallback cuối cùng nếu vẫn không có đường dẫn nào (trường hợp an toàn)
        if effective_base_path is None:
            if self.is_production:
                effective_base_path = os.path.dirname(sys.executable)
            else:
                # Trỏ về thư mục cha của thư mục chứa file này (ví dụ: Utils -> Project Root)
                effective_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            self.base_path = effective_base_path # Lưu lại cho các lần sau

        # --- Từ đây, sử dụng `effective_base_path` để đảm bảo tính nhất quán ---
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        log_dir = os.path.join(effective_base_path, 'Logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.normpath(os.path.join(log_dir, f'{name}.txt'))

        if os.path.exists(log_path):
            try:
                os.remove(log_path)
            except Exception as e:
                print(f"[ERROR] Không thể xóa file log cũ '{log_path}': {e}")

        # File Handler
        try:
            file_handler = RotatingFileHandler(
                log_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = '%(asctime)s [%(levelname)s] %(message)s'
            file_datefmt = '%Y-%m-%d %H:%M:%S'
            file_formatter = logging.Formatter(file_format, file_datefmt)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"[ERROR] Không thể tạo file log '{log_path}': {e}")

        # Console Handler (Chỉ cho môi trường dev)
        if not self.is_production and not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_format = f'\033[1;35m[{name.upper()}]\033[0m \033[1;34m%(asctime)s \033[1;32m[%(levelname)s]\033[0m %(message)s'
            console_formatter = logging.Formatter(console_format, '%H:%M:%S')
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        self.loggers[name] = logger
        return logger

LoggerProvider = LoggerManager()
