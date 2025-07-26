# Recording/rec_logic.py

import os
import sys
import time
import json
import re
import logging
import subprocess
import psutil
import threading
from enum import Enum, IntEnum
from contextlib import contextmanager, nullcontext, suppress
from requests import RequestException, Session
from tenacity import retry, stop_after_attempt, wait_exponential
from Recording.tiktoklive_fallback import get_room_id_with_tiktoklive

# --- THAY ĐỔI IMPORT ---
from Utils.config import TIKTOK_CONFIG, DOUYIN_CONFIG
from Utils.ffmpeg_utils import run_ffmpeg, stop_ffmpeg_processes
from Utils.logger_setup import LoggerProvider
logger = LoggerProvider.get_logger('recording')

class TimeOut(IntEnum):
    ONE_MINUTE = 60
    AUTOMATIC_MODE = 5
    CONNECTION_CLOSED = 2

class StatusCode(IntEnum):
    OK = 200
    REDIRECT = 302
    MOVED = 301

class Mode(IntEnum):
    MANUAL = 0
    AUTOMATIC = 1

class TikTokError(Enum):
    def __str__(self):
        return str(self.value)
    COUNTRY_BLACKLISTED = "Quốc gia bị chặn, vui lòng dùng VPN hoặc cookies."
    ACCOUNT_PRIVATE = "Tài khoản riêng tư, cần đăng nhập."
    LIVE_RESTRICTION = "Livestream bị giới hạn, cần đăng nhập."
    ROOM_ID_ERROR = "Không lấy được RoomID từ API."
    USER_NOT_CURRENTLY_LIVE = "Người dùng hiện không livestream."
    RETRIEVE_LIVE_URL = "Không lấy được URL livestream."
    API_CHANGED = "Cấu trúc API TikTok đã thay đổi, vui lòng cập nhật ứng dụng."
    USERNAME_NOT_FOUND = "Không tìm thấy người dùng."


class TikTokException(Exception): pass
class UserLiveException(Exception): pass
class LiveNotFound(Exception): pass
class RecordingException(Exception): pass


class VideoManagement:
    @staticmethod
    def convert_flv_to_mp4(file, ffmpeg_lock=None, ffmpeg_pids=None, recording_id='N/A'):
        file = os.path.normpath(file)
        logger.info(f"Bắt đầu chuyển đổi FLV sang MP4: {os.path.basename(file)}", extra={'recording_id': recording_id})
        try:
            output_file = os.path.normpath(file.replace('_flv.mp4', '.mp4'))
            with ffmpeg_lock if ffmpeg_lock else nullcontext():
                pid = run_ffmpeg(file, output_file, ["-c", "copy"], recording_id=recording_id)
                if ffmpeg_pids is not None:
                    with threading.Lock():
                        ffmpeg_pids.append(pid)
            os.remove(file)
        except Exception as e:
            logger.error(f"Lỗi chuyển đổi MP4: {e}", extra={'recording_id': recording_id})
        finally:
            if ffmpeg_pids:
                stop_ffmpeg_processes(ffmpeg_pids)

    @staticmethod
    def convert_mp4_to_mp3(file, output_file=None, ffmpeg_lock=None, ffmpeg_pids=None, recording_id='N/A', mp3_profile=None):
        file = os.path.normpath(file)
        logger.info(f"Bắt đầu chuyển đổi MP4 sang MP3: {os.path.basename(file)} với profile: {mp3_profile}")
        try:
            if output_file is None:
                output_file = os.path.normpath(file.replace('.mp4', '.mp3'))

            # Xây dựng tham số FFmpeg dựa trên profile
            ffmpeg_params = ["-vn", "-acodec", "mp3"]
            if mp3_profile and "Nâng cao 1" in mp3_profile:
                # Bitrate gốc, 44.1kHz, tốc độ 0.92, cao độ 0.2
                # FFmpeg không có tham số bitrate gốc, bỏ trống -ab sẽ dùng VBR mặc định
                audio_filter = "atempo=0.92,asetrate=44100*1.2,aresample=44100" # Pitch +0.2 tương đương nhân tần số với ~1.2
                ffmpeg_params.extend(["-ar", "44100", "-af", audio_filter])
                logger.info("Sử dụng profile MP3 nâng cao 1")
            elif mp3_profile and "Nâng cao 2" in mp3_profile:
                # Bitrate gốc, 48kHz, tốc độ 0.93, cao độ 0.3
                audio_filter = "atempo=0.93,asetrate=48000*1.3,aresample=48000" # Pitch +0.3 tương đương nhân tần số với ~1.3
                ffmpeg_params.extend(["-ar", "48000", "-af", audio_filter])
                logger.info("Sử dụng profile MP3 nâng cao 2")
            else: # Mặc định hoặc "Giữ nguyên gốc"
                ffmpeg_params.extend(["-ab", "128k"])
                logger.info("Sử dụng profile MP3 mặc định (128kbps)")


            with ffmpeg_lock if ffmpeg_lock else nullcontext():
                pid = run_ffmpeg(file, output_file, ffmpeg_params, recording_id=recording_id)
                if ffmpeg_pids is not None:
                    with threading.Lock():
                        ffmpeg_pids.append(pid)
        except Exception as e:
            logger.error(f"Lỗi chuyển đổi MP3: {e}")
        finally:
            if ffmpeg_pids:
                stop_ffmpeg_processes(ffmpeg_pids)

class HttpClient:
    def __init__(self, cookies=None, custom_headers=None):
        self.session = Session()
        self.session.trust_env = False
        
        # Thiết lập headers mặc định
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Referer": "https://www.tiktok.com/",
        }

        # Nếu có custom_headers, cập nhật vào bộ mặc định
        if custom_headers:
            default_headers.update(custom_headers)
        
        self.session.headers.update(default_headers)
        
        if cookies:
            # Dùng headers['Cookie'] thay vì session.cookies.update để đảm bảo tính nhất quán
            self.session.headers['Cookie'] = cookies

    def close_session(self):
        if self.session:
            self.session.close()

class TikTokAPI:
    def __init__(self, cookies):
        self.config = TIKTOK_CONFIG
        self.http_client = HttpClient(cookies)

    def get_room_id_from_user(self, user: str) -> str:
        try:
            url = f"{self.config['api_endpoints']['base_url']}/@{user}/live"
            response = self.http_client.session.get(url, timeout=10)
            response.raise_for_status()

            content = response.text
            match = re.search(r'<script id="SIGI_STATE" type="application/json">(.*?)</script>', content)
            if not match:
                raise UserLiveException(TikTokError.API_CHANGED)

            sigi_state = json.loads(match.group(1)) or {}

            # Cách 1: LiveRoom phổ biến
            room_id = sigi_state.get('LiveRoom', {}).get('liveRoomUserInfo', {}).get('user', {}).get('roomId')

            # Cách 2: RoomFeed
            if not room_id:
                room_id = sigi_state.get('RoomFeed', {}).get('detail', {}).get('liveRoom', {}).get('roomId')
            
            # Cách 3: UserModule
            if not room_id:
                user_module = sigi_state.get('UserModule', {}).get('users', {})
                if user_module and user in user_module:
                    room_id = user_module[user].get('roomId')

            # --- Fallback: dùng TikTokLive nếu không có room_id ---
            if not room_id:
                logger.warning(f"Không tìm thấy RoomID cho {user} trong SIGI_STATE. Thử TikTokLive fallback...")
                room_id = get_room_id_with_tiktoklive(user)
                if room_id:
                    logger.info(f"RoomID fallback từ TikTokLive thành công: {room_id}")
                else:
                    raise UserLiveException(TikTokError.ROOM_ID_ERROR)

            logger.info(f"Lấy RoomID thành công cho {user}: {room_id}")
            return str(room_id)
        
        except RequestException as e:
            if e.response and e.response.status_code == 404:
                raise UserLiveException(TikTokError.USERNAME_NOT_FOUND)
            logger.error(f"Lỗi mạng khi lấy RoomID từ {user}: {e}")
            raise TikTokException(f"Lỗi mạng: {e}")

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Lỗi phân tích cú pháp JSON hoặc Key cho {user}: {e}")
            raise UserLiveException(TikTokError.API_CHANGED)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    def is_room_alive(self, room_id: str):
        if not room_id: return False
        try:
            url = f"{self.config['api_endpoints']['webcast_url']}{self.config['api_endpoints']['room_info'].format(room_id=room_id)}"
            response = self.http_client.session.get(url, timeout=5)
            if response.status_code != 200: return False
            data = response.json()
            return data.get('data', {}).get('status', 0) == 2
        except Exception:
            return False

    def get_live_url(self, room_id: str):
        try:
            url = f"{self.config['api_endpoints']['webcast_url']}{self.config['api_endpoints']['room_info'].format(room_id=room_id)}"
            response = self.http_client.session.get(url, timeout=10)
            data = response.json().get('data', {})

            if data.get('status', 0) != 2:
                raise LiveNotFound(TikTokError.USER_NOT_CURRENTLY_LIVE)

            stream_data = data.get('stream_url', {}).get('flv_pull_url', {})
            live_url = stream_data.get('FULL_HD1') or stream_data.get('HD1') or stream_data.get('SD1') or stream_data.get('SD2')
            
            if not live_url:
                raise LiveNotFound(TikTokError.RETRIEVE_LIVE_URL)
            return live_url
        except (RequestException, json.JSONDecodeError):
            raise LiveNotFound(TikTokError.RETRIEVE_LIVE_URL)

class TikTokRecorder:
    
    def __init__(self, user, cookies=None, duration=None, convert_to_mp3=False, recording_id='N/A', 
                 custom_output_dir=None, status_callback=None, success_callback=None, 
                 project_root=None, custom_filename=None, detail_log_callback=None, mp3_profile=None):
        from Utils.config import COOKIES
        self.user = user
        self.cookies = cookies or COOKIES
        self.duration = duration
        self.convert_to_mp3 = convert_to_mp3
        self.recording_id = recording_id
        self.custom_output_dir = custom_output_dir
        self.status_callback = status_callback
        self.success_callback = success_callback
        self.project_root = project_root
        self.custom_filename = custom_filename

        self.mp3_profile = mp3_profile
        self.detail_log_callback = detail_log_callback
        
        self.tiktok = TikTokAPI(self.cookies)
        self.room_id = None
        self.stop_event = threading.Event()
        self.cancellation_requested = False
        self.manual_stop_requested = False
        self.output_filepath = None
        self.final_video_path = None

        logger.info(f"Khởi tạo recorder cho user: {self.user}")

    def _update_status(self, message, color, is_countdown=False):
        if self.status_callback:
            # Thêm 'is_countdown' vào lời gọi callback
            self.status_callback(self.recording_id, message, color, is_countdown)

    def _detail_log(self, message):
        if self.detail_log_callback:
            self.detail_log_callback(self.recording_id, f"[{time.strftime('%H:%M:%S')}] {message}")

    def run(self):
        # THAY ĐỔI 1: Giảm thời gian chờ tối đa xuống 10 phút (600s)
        wait_intervals = [120, 300, 600]
        interval_index = 0

        while not self.stop_event.is_set():
            try:
                self._detail_log("Kiểm tra trạng thái livestream...")
                self._update_status("Kiểm tra live...", "blue")
                self.room_id = self.tiktok.get_room_id_from_user(self.user)
                self._detail_log(f"Lấy RoomID thành công: {self.room_id}")

                is_live = self.tiktok.is_room_alive(self.room_id)
                if is_live:
                    self._detail_log("Xác nhận user đang live. Bắt đầu ghi hình.")
                    logger.info(f"User {self.user} đang livestream. Bắt đầu ghi hình.")
                    self._update_status("Đang ghi hình...", "green")
                    self.start_recording()

                    if self.manual_stop_requested or self.cancellation_requested:
                        logger.info(f"Luồng cho {self.user} kết thúc do người dùng yêu cầu.")
                        break
                    else:
                        logger.info(f"Livestream của {self.user} đã kết thúc. Quay lại chế độ theo dõi.")
                        self._update_status("Live kết thúc, theo dõi lại...", "orange")
                        interval_index = 0
                else:
                    raise LiveNotFound(TikTokError.USER_NOT_CURRENTLY_LIVE)

            except (UserLiveException, TikTokException, LiveNotFound) as e:
                fatal_errors = [
                    TikTokError.USERNAME_NOT_FOUND,
                    TikTokError.ACCOUNT_PRIVATE,
                    TikTokError.LIVE_RESTRICTION
                ]
                if any(str(fatal_error) == str(e) for fatal_error in fatal_errors):
                    logger.error(f"Lỗi nghiêm trọng, không thể theo dõi {self.user}: {e}")
                    self._update_status(f"Lỗi: {e}", "red")
                    self._detail_log(f"Lỗi nghiêm trọng, dừng theo dõi: {e}")
                    return

                # THAY ĐỔI 2: Sửa đổi logic để lặp lại chu kỳ chờ
                # Lấy thời gian chờ dựa trên index hiện tại
                wait_time = wait_intervals[interval_index]
                logger.info(f"User {self.user} không live, chờ {wait_time} giây. (Lý do: {e})")
                self._detail_log(f"User không live, sẽ kiểm tra lại sau {wait_time / 60:.1f} phút.")
                # Cập nhật index cho lần lặp tiếp theo, sử dụng toán tử modulo (%) để quay vòng
                interval_index = (interval_index + 1) % len(wait_intervals)

                # --- VÒNG LẶP ĐẾM NGƯỢC ---
                for i in range(wait_time, 0, -1):
                    if self.stop_event.is_set():
                        break # Thoát nếu có yêu cầu dừng
                    minutes, seconds = divmod(i, 60)
                    countdown_text = f"{minutes:02d}:{seconds:02d}"
                    # Gửi trạng thái đếm ngược
                    self._update_status(f"Chờ live ({countdown_text})", "orange", is_countdown=True)
                    time.sleep(1)
                # --- KẾT THÚC ĐẾM NGƯỢC ---

                if self.stop_event.is_set():
                    break

            except Exception as e:
                logger.critical(f"Lỗi không mong muốn trong vòng lặp chính của {self.user}: {e}", exc_info=True)
                self._update_status("Lỗi, đang thử lại...", "red")
                self._detail_log(f"Lỗi không xác định: {e}")
                self.stop_event.wait(300)

    def start_recording(self):
        try:
            self._detail_log("Lấy URL của luồng FLV...")
            live_url = self.tiktok.get_live_url(self.room_id)
            self._detail_log("Lấy URL thành công.")

            if self.custom_filename:
                safe_filename = re.sub(r'[\\/*?:"<>|]', "", self.custom_filename)
                base_name = safe_filename
                logger.info(f"Sử dụng tên file tùy chỉnh: '{base_name}'")
            else:
                base_name = f"TK_{self.user}_{time.strftime('%Y%m%d_%H%M%S')}"

            self.output_filepath = os.path.join(
                self.get_user_dir(),
                f"{base_name}_flv.mp4"
            )

            logger.info(f"Bắt đầu ghi hình @{self.user}. Lưu vào: {os.path.basename(self.output_filepath)}")
            self._detail_log(f"Bắt đầu tải stream...")
            self.fetch_stream(live_url, self.output_filepath)
        except LiveNotFound as e:
            logger.warning(f"Không thể bắt đầu ghi hình cho {self.user}: {e}")
        finally:
            if self.cancellation_requested:
                logger.warning(f"Hủy bỏ được yêu cầu, xóa file tạm cho {self.user}.")
                if self.output_filepath and os.path.exists(self.output_filepath):
                    with suppress(OSError):
                        os.remove(self.output_filepath)
                        logger.info(f"Đã xóa thành công file tạm.")
            else:
                self.process_recorded_file(self.output_filepath)

    def fetch_stream(self, live_url, output_file):
        start_time = time.time()
        total_bytes = 0
        last_update_time = time.time()
        try:
            with self.tiktok.http_client.session.get(live_url, stream=True, timeout=10) as response:
                response.raise_for_status()
                self._detail_log("Kết nối stream thành công.")
                with open(output_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.stop_event.is_set():
                            self._detail_log("Nhận tín hiệu dừng, ngừng tải.")
                            break
                        f.write(chunk)
                        total_bytes += len(chunk)

                        current_time = time.time()
                        # --- THAY ĐỔI TẠI ĐÂY: Cập nhật mỗi 10 giây ---
                        if current_time - last_update_time > 10:
                            # Gửi thẻ [DOWNLOAD] và đổi đơn vị sang MB
                            self._detail_log(f"[DOWNLOAD]Đã nhận: {total_bytes / (1024*1024):.2f} MB")
                            last_update_time = current_time

                        if self.duration and (current_time - start_time) > self.duration:
                            logger.info(f"Đã đạt thời gian ghi hình {self.duration}s. Dừng lại.")
                            self._detail_log(f"Đạt thời gian ghi hình tối đa.")
                            break
            # Thông báo cuối cùng
            self._detail_log(f"Tải stream hoàn tất, tổng dung lượng: {total_bytes / (1024*1024):.2f} MB.")
        except RequestException as e:
            self._detail_log(f"Lỗi kết nối: {e}")
            raise RecordingException(f"Lỗi kết nối khi tải stream: {e}")

    def process_recorded_file(self, file_path):
        if file_path and os.path.exists(file_path):
            if os.path.getsize(file_path) > 1024:
                mp4_file = file_path.replace('_flv.mp4', '.mp4')
                self._detail_log("Bắt đầu chuyển đổi FLV -> MP4...")
                VideoManagement.convert_flv_to_mp4(file_path, recording_id=self.recording_id)
                self.final_video_path = mp4_file
                self._detail_log("Chuyển đổi MP4 thành công.")

                if self.success_callback and os.path.exists(mp4_file):
                    self.success_callback(self.recording_id, self.user)

                if self.convert_to_mp3 and os.path.exists(mp4_file):
                    self._detail_log("Bắt đầu chuyển đổi MP4 sang MP3...")
                    VideoManagement.convert_mp4_to_mp3(mp4_file, recording_id=self.recording_id, mp3_profile=self.mp3_profile)
                    self._detail_log("Chuyển đổi MP3 thành công.")
            else:
                os.remove(file_path)
                self._detail_log("File ghi hình quá nhỏ, đã xóa.")
                logger.warning(f"File ghi hình của @{self.user} rỗng hoặc quá nhỏ, đã xóa.")
        
    def stop(self):
        logger.info(f"Đã gửi tín hiệu Dừng & Lưu cho recorder của {self.user}")
        self.manual_stop_requested = True
        self.stop_event.set()

    def cancel(self):
        logger.warning(f"Đã gửi tín hiệu Hủy & Xóa cho recorder của {self.user}")
        self.cancellation_requested = True
        self.stop_event.set()

    def get_user_dir(self):
        base_path = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else self.project_root
        output_dir_base = self.custom_output_dir or os.path.join(base_path, 'Rec_Output')
        
        # --- THAY ĐỔI: Sử dụng tên tác giả cho thư mục ---
        # self.user ban đầu là Douyin_{rid}, sau khi có thông tin live sẽ được cập nhật thành tên thật
        safe_user_name = re.sub(r'[\\/*?:"<>|]', "", self.user)
        user_dir = os.path.normpath(os.path.join(output_dir_base, safe_user_name))
        # --- KẾT THÚC THAY ĐỔI ---

        os.makedirs(user_dir, exist_ok=True)
        return user_dir

#=================================================================
# LỚP MỚI: DOUYIN API
#=================================================================
class DouyinAPI:
    def __init__(self, cookies):
        self.config = DOUYIN_CONFIG
        # Douyin cần headers và referer cụ thể
        douyin_headers = {
            "Referer": "https://live.douyin.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        }
        self.http_client = HttpClient(cookies=cookies, custom_headers=douyin_headers)

    def get_live_info(self, web_rid: str):
        """Lấy thông tin chi tiết của livestream từ web_rid."""
        params = self.config['api_params'].copy()
        params['web_rid'] = web_rid
        
        try:
            response = self.http_client.session.get(self.config['api_endpoints']['web_enter'], params=params, timeout=15)
            
            # Xử lý các trường hợp bị chặn
            if "<title>验证</title>" in response.text:
                raise RecordingException("Yêu cầu bị chặn bởi CAPTCHA.")
            
            response.raise_for_status()
            data = response.json()

            # Chuẩn hóa dữ liệu trả về
            normalized_data = {}
            room_data = data.get("data", {}).get("data", [{}])[0]
            user_data = data.get("data", {}).get("user", {})
            
            normalized_data["author_name"] = user_data.get("nickname", "Không rõ")
            normalized_data["live_title"] = room_data.get("title", "Không có tiêu đề")
            normalized_data["status"] = room_data.get("status", 4)
            
            if normalized_data["status"] == 2: # Đang live
                stream_data = room_data.get("stream_url", {})
                flv_map = stream_data.get("flv_pull_url", {})
                # Ưu tiên chất lượng gốc
                live_url = flv_map.get("ORIGIN") or flv_map.get("FULL_HD1") or next(iter(flv_map.values()), None)
                normalized_data["live_url"] = live_url
            
            return normalized_data

        except RequestException as e:
            logger.error(f"Lỗi mạng khi lấy thông tin Douyin cho RID {web_rid}: {e}")
            raise RecordingException(f"Lỗi mạng: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Lỗi phân tích dữ liệu Douyin cho RID {web_rid}: {e}")
            raise RecordingException("Lỗi phân tích dữ liệu API.")

#=================================================================
# LỚP MỚI: DOUYIN RECORDER
#=================================================================
class DouyinRecorder:
    def __init__(self, live_url, cookies=None, duration=None, convert_to_mp3=False, recording_id='N/A', 
                 custom_output_dir=None, status_callback=None, success_callback=None, 
                 project_root=None, custom_filename=None, detail_log_callback=None, mp3_profile=None):
        
        self.live_url = live_url
        self.web_rid = self.live_url.split('?')[0].rstrip('/').rsplit('/', 1)[-1]
        self.cookies = cookies
        self.duration = duration
        self.convert_to_mp3 = convert_to_mp3
        self.recording_id = recording_id
        self.custom_output_dir = custom_output_dir
        self.status_callback = status_callback
        self.success_callback = success_callback
        self.project_root = project_root
        self.custom_filename = custom_filename
        self.mp3_profile = mp3_profile
        self.detail_log_callback = detail_log_callback
        
        self.douyin_api = DouyinAPI(self.cookies)
        self.stop_event = threading.Event()
        self.cancellation_requested = False
        self.manual_stop_requested = False
        self.output_filepath = None
        self.final_video_path = None
        self.user = f"Douyin_{self.web_rid}" # Tên định danh nội bộ

        logger.info(f"Khởi tạo Douyin recorder cho RID: {self.web_rid}")

    def _update_status(self, message, color, is_countdown=False):
        if self.status_callback:
            self.status_callback(self.recording_id, message, color, is_countdown)

    def _detail_log(self, message):
        if self.detail_log_callback:
            self.detail_log_callback(self.recording_id, f"[{time.strftime('%H:%M:%S')}] {message}")

    def run(self):
        """Vòng lặp chính cho Douyin, đơn giản hơn TikTok vì không cần theo dõi."""
        try:
            self._detail_log("Kiểm tra trạng thái livestream Douyin...")
            self._update_status("Kiểm tra live...", "blue")
            
            live_info = self.douyin_api.get_live_info(self.web_rid)
            
            if live_info.get("status") == 2:
                self.user = live_info.get("author_name", self.user) # Cập nhật tên thật
                self._detail_log(f"Xác nhận user '{self.user}' đang live. Bắt đầu ghi hình.")
                logger.info(f"User Douyin {self.user} (RID: {self.web_rid}) đang livestream.")
                self._update_status("Đang ghi hình...", "green")
                self.start_recording(live_info)
            else:
                self._detail_log("User hiện không livestream.")
                self._update_status("Offline", "grey")
                logger.info(f"User Douyin (RID: {self.web_rid}) không live.")

        except RecordingException as e:
            logger.error(f"Lỗi khi ghi hình Douyin (RID: {self.web_rid}): {e}")
            self._update_status(f"Lỗi: {e}", "red")
            self._detail_log(f"Lỗi nghiêm trọng, dừng lại: {e}")
        except Exception as e:
            logger.critical(f"Lỗi không mong muốn với Douyin (RID: {self.web_rid}): {e}", exc_info=True)
            self._update_status("Lỗi nghiêm trọng", "red")
            self._detail_log(f"Lỗi không xác định: {e}")

    def start_recording(self, live_info):
        try:
            live_url = live_info.get("live_url")
            if not live_url:
                raise RecordingException("Không tìm thấy URL stream hợp lệ.")
            
            self._detail_log("Lấy URL của luồng FLV thành công.")

            if self.custom_filename:
                safe_filename = re.sub(r'[\\/*?:"<>|]', "", self.custom_filename)
                base_name = safe_filename
            else:
                base_name = f"DY_{self.user}_{time.strftime('%Y%m%d_%H%M%S')}"

            self.output_filepath = os.path.join(self.get_user_dir(), f"{base_name}_flv.mp4")

            logger.info(f"Bắt đầu ghi hình Douyin @{self.user}. Lưu vào: {os.path.basename(self.output_filepath)}")
            self._detail_log(f"Bắt đầu tải stream...")
            self.fetch_stream(live_url, self.output_filepath)
        finally:
            if self.cancellation_requested:
                logger.warning(f"Hủy bỏ, xóa file tạm cho Douyin {self.user}.")
                if self.output_filepath and os.path.exists(self.output_filepath):
                    with suppress(OSError): os.remove(self.output_filepath)
            else:
                self.process_recorded_file(self.output_filepath)

    def fetch_stream(self, live_url, output_file):
        start_time = time.time()
        total_bytes = 0
        last_update_time = time.time()
        try:
            # Douyin cần headers khi tải stream
            headers = self.douyin_api.http_client.session.headers
            with self.douyin_api.http_client.session.get(live_url, stream=True, timeout=15, headers=headers) as response:
                response.raise_for_status()
                self._detail_log("Kết nối stream thành công.")
                with open(output_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.stop_event.is_set():
                            self._detail_log("Nhận tín hiệu dừng, ngừng tải.")
                            break
                        f.write(chunk)
                        total_bytes += len(chunk)

                        current_time = time.time()
                        if current_time - last_update_time > 10:
                            self._detail_log(f"[DOWNLOAD]Đã nhận: {total_bytes / (1024*1024):.2f} MB")
                            last_update_time = current_time

                        if self.duration and (current_time - start_time) > self.duration:
                            self._detail_log(f"Đạt thời gian ghi hình tối đa.")
                            break
            self._detail_log(f"Tải stream hoàn tất, tổng dung lượng: {total_bytes / (1024*1024):.2f} MB.")
        except RequestException as e:
            self._detail_log(f"Lỗi kết nối: {e}")
            raise RecordingException(f"Lỗi kết nối khi tải stream: {e}")

    def process_recorded_file(self, file_path):
        # Hàm này giống hệt TikTokRecorder
        if file_path and os.path.exists(file_path):
            if os.path.getsize(file_path) > 1024:
                mp4_file = file_path.replace('_flv.mp4', '.mp4')
                self._detail_log("Bắt đầu chuyển đổi FLV -> MP4...")
                VideoManagement.convert_flv_to_mp4(file_path, recording_id=self.recording_id)
                self.final_video_path = mp4_file
                self._detail_log("Chuyển đổi MP4 thành công.")

                if self.success_callback and os.path.exists(mp4_file):
                    self.success_callback(self.recording_id, self.user)

                if self.convert_to_mp3 and os.path.exists(mp4_file):
                    self._detail_log("Bắt đầu chuyển đổi MP4 sang MP3...")
                    VideoManagement.convert_mp4_to_mp3(mp4_file, recording_id=self.recording_id, mp3_profile=self.mp3_profile)
                    self._detail_log("Chuyển đổi MP3 thành công.")
            else:
                os.remove(file_path)
                self._detail_log("File ghi hình quá nhỏ, đã xóa.")
                logger.warning(f"File ghi hình của Douyin @{self.user} rỗng hoặc quá nhỏ, đã xóa.")

    def stop(self):
        logger.info(f"Đã gửi tín hiệu Dừng & Lưu cho Douyin recorder của {self.user}")
        self.manual_stop_requested = True
        self.stop_event.set()

    def cancel(self):
        logger.warning(f"Đã gửi tín hiệu Hủy & Xóa cho Douyin recorder của {self.user}")
        self.cancellation_requested = True
        self.stop_event.set()

    def get_user_dir(self):
        # Hàm này giống hệt TikTokRecorder
        if not self.project_root:
            base_path = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.abspath(__file__))
        else:
            base_path = self.project_root
        output_dir_base = self.custom_output_dir or os.path.join(base_path, 'Rec_Output')
        user_dir = os.path.normpath(os.path.join(output_dir_base, self.user))
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
