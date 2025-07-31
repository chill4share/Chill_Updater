import os
import sys
import json

def get_data_dir():
    """
    Lấy đường dẫn đến thư mục 'Data' một cách an toàn.
    Thư mục này nằm cùng cấp với file thực thi hoặc file main.py.
    """
    if hasattr(sys, '_MEIPASS'):
        # Chạy từ file .exe đã được đóng gói bằng PyInstaller
        base_path = os.path.dirname(sys.executable)
    else:
        # Chạy từ mã nguồn .py
        # Giả định rằng file main.py nằm ở thư mục gốc của dự án
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, 'Data')

def load_user_cookies():
    """
    Tải cookies của người dùng từ file Data/cookies.json.
    Trả về một dictionary, có thể rỗng nếu file không tồn tại hoặc lỗi.
    """
    data_dir = get_data_dir()
    cookie_path = os.path.join(data_dir, 'cookies.json')

    if not os.path.exists(cookie_path):
        return {}
    
    try:
        with open(cookie_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            # Đảm bảo trả về dict ngay cả khi file json là null
            return cookies if isinstance(cookies, dict) else {}
    except (json.JSONDecodeError, IOError):
        # Nếu file bị lỗi, trả về rỗng để sử dụng fallback
        return {}

def save_user_cookies(cookies_dict):
    """
    Lưu dictionary cookies vào file Data/cookies.json.
    """
    data_dir = get_data_dir()
    cookie_path = os.path.join(data_dir, 'cookies.json')

    try:
        # Tạo thư mục Data nếu chưa có
        os.makedirs(data_dir, exist_ok=True)
        with open(cookie_path, 'w', encoding='utf-8') as f:
            json.dump(cookies_dict, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Lỗi khi lưu cookies: {e}")
        return False
