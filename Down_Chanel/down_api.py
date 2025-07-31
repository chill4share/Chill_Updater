import asyncio
import requests
import logging
import json
import re
import os

from .down_logic import retry_api
from Utils.logger_setup import LoggerProvider
logger = LoggerProvider.get_logger('download')

class TikTokDownloader:
    def __init__(self, cookies_str=None):
        """
        Khởi tạo downloader với chuỗi cookie được cung cấp.
        """
        self.logger = logger
        self.session = requests.Session()
        # Gọi hàm khởi tạo session với cookie được truyền vào
        self.initialize_session(cookies_str)

    def initialize_session(self, cookies_str):
        """
        Thiết lập header và cookie cho session.
        """
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,vi-VN;q=0.8",
            "Referer": "https://www.tiktok.com/",
        })
        
        # Chuyển đổi chuỗi cookie thành dictionary và cập nhật vào session
        if cookies_str:
            try:
                # Tách chuỗi cookie thành các cặp key=value
                cookies_dict = {k.strip(): v for k, v in (item.split('=', 1) for item in cookies_str.split(';') if '=' in item)}
                self.session.cookies.update(cookies_dict)
                self.logger.info("Khởi tạo session cho tab Download với cookie được cung cấp.")
            except Exception as e:
                self.logger.error(f"Lỗi định dạng cookie cho tab Download: {e}. Session sẽ không có cookie.")
        else:
            self.logger.warning("Không có cookie nào được cung cấp cho tab Download.")

    def extract_username_and_video_id(self, url_or_id):
        """
        Trích xuất username và video_id từ một URL đầy đủ.
        Rất quan trọng để tạo thư mục lưu trữ.
        """
        url_or_id = url_or_id.replace('\n', '').replace('%0A', '').strip()
        if "tiktok.com" in url_or_id and "/video/" in url_or_id:
            clean_url = url_or_id.split("?")[0]
            try:
                video_id = self.extract_video_id(clean_url)
                username_match = re.search(r'/@([^/]+)', clean_url)
                username = username_match.group(1) if username_match else "unknown"
                return username, video_id
            except Exception as e:
                self.logger.error(f"Lỗi trích xuất username/video_id từ {clean_url}: {e}")
                return "unknown", self.extract_video_id(url_or_id)
        # Nếu đầu vào không phải URL đầy đủ, trả về mặc định
        return "unknown", self.extract_video_id(url_or_id)
    
    def extract_video_id(self, url_or_id):
        url_or_id = url_or_id.replace('\n', '').replace('%0A', '').strip()
        match = re.search(r'/video/(\d+)', url_or_id)
        if match: return match.group(1)
        if url_or_id.isdigit(): return url_or_id
        return url_or_id

    async def download_video(self, url_or_id):
        video_id = self.extract_video_id(url_or_id)
        self.logger.info(f"Bắt đầu tải video {video_id}")
        video_info = await self.get_video_info(url_or_id)
        if not video_info:
             raise Exception(f"Không thể lấy thông tin cho video {video_id}")
        download_addr = None
        if 'video' in video_info:
            video_data = video_info['video']
            download_addr = video_data.get('playAddr') or video_data.get('downloadAddr')
        if not download_addr:
            self.logger.error(f"Thất bại: Không tìm thấy địa chỉ tải hợp lệ cho video {video_id}.")
            raise Exception(f"Video này được bảo vệ hoặc không có link tải công khai.")
        self.logger.info(f"Đã tìm thấy URL tải cho {video_id}. Bắt đầu tải xuống...")
        for attempt in range(3):
            try:
                response = self.session.get(download_addr, stream=True, timeout=30)
                response.raise_for_status()
                video_bytes = response.content
                if len(video_bytes) < 50 * 1024:
                    raise Exception(f"Kích thước video tải về quá nhỏ, có thể đây là video được bảo vệ.")
                self.logger.info(f"Tải video {video_id} thành công, kích thước={len(video_bytes)} bytes")
                return video_bytes
            except requests.RequestException as e:
                self.logger.error(f"Thử {attempt + 1}/3 thất bại khi tải {video_id}: {e}")
                if attempt == 2: raise Exception(f"Tải video {video_id} thất bại sau 3 lần thử")
                await asyncio.sleep(2)
        return None

    async def get_video_info(self, url_or_id):
        video_url = url_or_id
        if "tiktok.com" not in video_url: video_url = f"https://www.tiktok.com/t/{video_url}"
        self.logger.info(f"Phân tích trực tiếp trang video: {video_url}")
        try:
            r = self.session.get(video_url, allow_redirects=True)
            r.raise_for_status()
            html_content = r.text
            match = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>', html_content)
            if not match: match = re.search(r'<script id="SIGI_STATE" type="application/json">(.*?)</script>', html_content)
            if not match:
                self.logger.error("Không tìm thấy thẻ script chứa JSON trong trang.")
                return None
            json_data = json.loads(match.group(1))
            video_info = None
            if "webapp.video-detail" in json_data.get("__DEFAULT_SCOPE__", {}):
                video_info = json_data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
            elif "ItemModule" in json_data:
                video_id = self.extract_video_id(url_or_id)
                if video_id in json_data["ItemModule"]: video_info = json_data["ItemModule"][video_id]
            if video_info:
                self.logger.info("Phân tích trang và trích xuất thông tin video thành công.")
                return video_info
            else:
                self.logger.error("Đã tìm thấy JSON nhưng không có cấu trúc video hợp lệ.")
                return None
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Lỗi khi phân tích trang video: {e}", exc_info=True)
            return None

    async def get_user_videos(self, username_or_url):
        self.logger.warning("Chức năng tải toàn bộ kênh đang tạm thời không khả dụng do thay đổi từ TikTok.")
        return []
