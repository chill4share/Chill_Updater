# logic.py
import requests
import os
import logging
import asyncio

def extract_video_id_from_url(url, headers={}, proxy=None):
    """
    Trích xuất ID video từ URL.
    Hàm này giờ đây sẽ ghi log chi tiết hơn để chẩn đoán lỗi.
    """
    logger = logging.getLogger(__name__)
    try:
        logger.debug(f"Thực hiện HEAD request tới URL: {url}")
        response = requests.head(url=url, allow_redirects=True, headers=headers, proxies=proxy, timeout=10)
        response.raise_for_status() # Gây lỗi nếu status code là 4xx hoặc 5xx
        
        final_url = response.url
        logger.debug(f"URL cuối cùng sau khi chuyển hướng là: {final_url}")

        if "@" in final_url and "/video/" in final_url:
            video_id = final_url.split("/video/")[1].split("?")[0]
            logger.debug(f"Trích xuất thành công video_id: {video_id} từ {final_url}")
            return video_id
        else:
            # Đây là điểm có thể gây lỗi. Ghi log lại URL không hợp lệ.
            logger.error(f"URL cuối cùng '{final_url}' không có định dạng '@.../video/...' như mong đợi.")
            raise TypeError(f"Định dạng URL cuối cùng không được hỗ trợ: {final_url}")
            
    except requests.RequestException as e:
        logger.error(f"Lỗi mạng trong khi thực hiện HEAD request tới {url}: {e}", exc_info=True)
        # Ném lại lỗi để khối try-except bên ngoài (trong standardize_url) có thể bắt được
        raise
    except TypeError as e:
        # Ném lại lỗi TypeError để khối try-except bên ngoài bắt được
        raise


def retry_api(session, url, params=None, max_attempts=3, delay=2):
    """Thử lại API tối đa max_attempts lần nếu thất bại."""
    logger = logging.getLogger(__name__)
    for attempt in range(max_attempts):
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Thử {attempt + 1} thất bại: {str(e)}")
            if attempt == max_attempts - 1:
                raise Exception(f"API thất bại sau {max_attempts} lần thử: {str(e)}")
            asyncio.sleep(delay)

def handle_partial_file(file_path, min_size=1024):
    """Xóa file tải dở nếu kích thước nhỏ hơn min_size."""
    logger = logging.getLogger(__name__)
    if os.path.exists(file_path) and os.path.getsize(file_path) < min_size:
        try:
            os.remove(file_path)
            logger.info(f"Xóa file tải dở: {file_path}")
        except Exception as e:
            logger.error(f"Lỗi xóa file tải dở {file_path}: {str(e)}")

class TikTokException(Exception):
    def __init__(self, raw_response, message, error_code=None):
        self.error_code = error_code
        self.raw_response = raw_response
        self.message = message
        super().__init__(self.message)

class EmptyResponseException(TikTokException):
    pass

class InvalidJSONException(TikTokException):
    pass

class InvalidResponseException(TikTokException):
    pass
