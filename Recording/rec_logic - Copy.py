import os
import sys
import time
import re
import asyncio
import nest_asyncio
import shutil
from contextlib import suppress
import threading
import json
import subprocess
from requests import RequestException, Session

from TikTokLive.client.client import TikTokLiveClient
from TikTokLive.client.errors import UserOfflineError, AgeRestrictedError, UserNotFoundError

from Utils.ffmpeg_utils import run_ffmpeg
from Utils.logger_setup import LoggerProvider
from Utils.constants import Status, Colors
from Utils.config import DOUYIN_CONFIG, MP3_PROFILES

logger = LoggerProvider.get_logger('recording')
class RecordingException(Exception): pass
nest_asyncio.apply()

class VideoManagement:
    @staticmethod
    def convert_flv_to_mp4(file, recording_id='N/A'):
        file = os.path.normpath(file)
        logger.info(f"Bắt đầu chuyển đổi FLV sang MP4: {os.path.basename(file)}", extra={'recording_id': recording_id})
        try:
            output_file = os.path.splitext(file)[0] + '.mp4'
            run_ffmpeg(file, output_file, ["-c", "copy"], recording_id=recording_id)
            os.remove(file)
            return output_file
        except Exception as e:
            logger.error(f"Lỗi chuyển đổi MP4: {e}", extra={'recording_id': recording_id})
            return None

    @staticmethod
    def convert_mp4_to_mp3(file, output_file=None, recording_id='N/A', profile_key='default'):
        file = os.path.normpath(file)
        profile = MP3_PROFILES.get(profile_key, MP3_PROFILES['default'])
        logger.info(f"Bắt đầu chuyển đổi MP4 sang MP3: {os.path.basename(file)} với profile: {profile['display']}")
        try:
            if output_file is None:
                output_file = os.path.splitext(file)[0] + '.mp3'
            
            run_ffmpeg(file, output_file, profile['params'], recording_id=recording_id)
        except Exception as e:
            logger.error(f"Lỗi chuyển đổi MP3: {e}")
            raise

    @staticmethod
    def create_muted_video(input_file, output_file, recording_id='N/A'):
        logger.info(f"Tạo video không tiếng: {os.path.basename(output_file)}", extra={'recording_id': recording_id})
        try:
            # Cũ:
            #run_ffmpeg(input_file, output_file, ["-c:v", "copy", "-an"], recording_id=recording_id)
            # Mới:
            run_ffmpeg(input_file, output_file, ["-c:v", "copy", "-map", "0:v"], recording_id=recording_id)
            return output_file
        except Exception as e:
            logger.error(f"Lỗi khi tạo video không tiếng: {e}", extra={'recording_id': recording_id})
            return None

class BaseRecorder:
    def __init__(self, **kwargs):
        self.user = kwargs.get('user', 'N/A')
        for key, value in kwargs.items(): setattr(self, key, value)

        # Trích xuất các callback và tùy chọn
        self.failure_callback = kwargs.get('failure_callback')
        self.success_callback = kwargs.get('success_callback')
        self.close_card_callback = kwargs.get('close_card_callback')
        self.status_callback = kwargs.get('status_callback')
        self.detail_log_callback = kwargs.get('detail_log_callback')
        self.mp3_options = kwargs.get('mp3_options', {'convert': False})
        self.mute_video = kwargs.get('mute_video', False)

        # Trạng thái nội bộ
        self.stop_event = threading.Event()
        self.cancellation_requested = False
        self.manual_stop_requested = False
        self.output_filepath = None
        self.process = None

    def _update_status(self, message, color, is_countdown=False):
        if callable(self.status_callback):
            self.status_callback(self.recording_id, message, color, is_countdown)

    def _detail_log(self, message):
        if callable(self.detail_log_callback):
            self.detail_log_callback(self.recording_id, f"[{time.strftime('%H:%M:%S')}] {message}")

    def stop(self):
        self._update_status(Status.STOPPING, Colors.ORANGE)
        self.manual_stop_requested = True
        self.stop_event.set()

    def cancel(self):
        self._update_status(Status.CANCELLING, Colors.ORANGE)
        self.cancellation_requested = True
        self.stop_event.set()

    def get_user_dir(self):
        base_path = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else self.project_root
        output_dir = self.custom_output_dir or os.path.join(base_path, 'Rec_Output')
        user_dir = os.path.join(output_dir, re.sub(r'[\\/*?:"<>|]', "", self.user))
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def run(self):
        raise NotImplementedError("Lớp con phải triển khai phương thức run()")

    def _process_output_file(self, original_video_path):
        """
        Xử lý file video sau khi ghi xong với logic chống xung đột cuối cùng.
        """
        self._update_status("Đang xử lý file...", Colors.BLUE)

        # Kiểm tra các tùy chọn
        do_mp3_conversion = self.mp3_options.get('convert')
        do_video_muting = self.mute_video

        # Trường hợp 1: Không làm gì cả
        if not do_mp3_conversion and not do_video_muting:
            self._detail_log("Không có tác vụ xử lý file nào được chọn.")
            return original_video_path

        # Trường hợp 2: Chỉ chuyển MP3
        if do_mp3_conversion and not do_video_muting:
            self._detail_log("[MP3] Bắt đầu chuyển đổi (chỉ MP3)...")
            try:
                VideoManagement.convert_mp4_to_mp3(file=original_video_path, recording_id=self.recording_id, profile_key=self.mp3_options.get('profile_key'))
                self._detail_log("[MP3] Chuyển đổi thành công.")
            except Exception as e:
                self._detail_log(f"[MP3] Lỗi: {e}")
            return original_video_path

        # Trường hợp 3: Chỉ tắt tiếng video
        if not do_mp3_conversion and do_video_muting:
            self._detail_log("Bắt đầu tắt tiếng video (chỉ tắt tiếng)...")
            path_parts = os.path.splitext(original_video_path)
            muted_output_path = f"{path_parts[0]}_muted_temp{path_parts[1]}"
            result_path = VideoManagement.create_muted_video(original_video_path, muted_output_path, self.recording_id)
            if result_path and os.path.exists(result_path):
                try:
                    os.replace(result_path, original_video_path)
                    self._detail_log("Tắt tiếng video thành công.")
                    return original_video_path
                except OSError as e:
                    self._detail_log(f"Lỗi thay thế file đã tắt tiếng: {e}")
                    return result_path # Trả về file tạm nếu không thay thế được
            else:
                self._detail_log("Lỗi tạo file không tiếng.")
                return original_video_path

        # --- TRƯỜNG HỢP 4: LÀM CẢ HAI (LOGIC AN TOÀN NHẤT) ---
        if do_mp3_conversion and do_video_muting:
            self._detail_log("Bắt đầu xử lý MP3 và Tắt tiếng...")
            
            # Bước 1: Tạo file MP3 từ file gốc
            self._detail_log("[MP3] Tạo file MP3 từ file gốc...")
            try:
                VideoManagement.convert_mp4_to_mp3(file=original_video_path, recording_id=self.recording_id, profile_key=self.mp3_options.get('profile_key'))
                self._detail_log("[MP3] Tạo MP3 thành công.")
            except Exception as e:
                self._detail_log(f"[MP3] Lỗi: {e}")
            
            # Bước 2: Tạo một file video MỚI (đã tắt tiếng) từ file gốc
            self._detail_log("Tạo file video mới không có âm thanh...")
            path_parts = os.path.splitext(original_video_path)
            muted_final_path = f"{path_parts[0]}_muted.mp4" # Đặt tên rõ ràng
            
            result_path = VideoManagement.create_muted_video(original_video_path, muted_final_path, self.recording_id)
            
            # Bước 3: Xóa file video gốc (có âm thanh)
            if result_path and os.path.exists(result_path):
                self._detail_log(f"Tạo video không tiếng thành công: {os.path.basename(result_path)}")
                try:
                    os.remove(original_video_path)
                    self._detail_log("Đã xóa file video gốc (có âm thanh).")
                    return result_path # Trả về đường dẫn của file mới đã tắt tiếng
                except OSError as e:
                    self._detail_log(f"Lỗi xóa file video gốc: {e}")
                    return result_path # Vẫn trả về file đã tắt tiếng dù không xóa được file gốc
            else:
                self._detail_log("Lỗi tạo file không tiếng, giữ lại file gốc.")
                return original_video_path
        
        return original_video_path
        
    def _handle_post_recording(self):
        if self.manual_stop_requested and not self.output_filepath:
            self._update_status(Status.DONE_MONITORING_STOPPED, Colors.GREY)
            return {'status': 'monitoring_stopped', 'filepath': None}

        if self.cancellation_requested:
            self._update_status(Status.DONE_CANCELLED, Colors.ORANGE)
            if self.output_filepath and os.path.exists(self.output_filepath):
                with suppress(OSError): os.remove(self.output_filepath)
            return {'status': 'cancelled', 'filepath': None}

        if not self.output_filepath or not os.path.exists(self.output_filepath) or os.path.getsize(self.output_filepath) <= 1024:
            reason = Status.ERROR_ON_STOP if self.manual_stop_requested else Status.ERROR_RECORDING_FAILED
            self._update_status(reason, Colors.RED)
            if callable(self.failure_callback): self.failure_callback(self.recording_id, self.user)
            return {'status': 'failed', 'filepath': self.output_filepath}

        # Xử lý file (MP3/Mute)
        final_video_path = self._process_output_file(self.output_filepath)

        # Cập nhật trạng thái cuối cùng
        status_msg = Status.DONE_STOPPED if self.manual_stop_requested else Status.DONE_SUCCESS
        color = Colors.DARK_BLUE if self.manual_stop_requested else Colors.GREEN
        self._update_status(status_msg, color)
        
        if callable(self.success_callback): self.success_callback(self.recording_id, self.user)
        return {'status': 'success', 'filepath': final_video_path}

class TikTokRecorder(BaseRecorder):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = TikTokLiveClient(unique_id=self.user)
        if self.cookies and isinstance(self.cookies, str):
            cookie_jar = {k.strip(): v for k, v in (item.split('=', 1) for item in self.cookies.split(';') if '=' in item)}
            if cookie_jar: self.client.web.cookies.update(cookie_jar)
        
        self.last_gui_log_time = 0
        self.INITIAL_WAIT_TIME = 180
        self.MAX_WAIT_TIME = 1800
        self.current_wait_time = self.INITIAL_WAIT_TIME
        logger.info(f"Khởi tạo TikTok recorder cho user: {self.user}")

    def _log_subprocess_output(self, pipe):
        try:
            for line in iter(pipe.readline, ''):
                clean_line = line.strip()
                if not clean_line: continue
                is_progress_line = "frame=" in clean_line and "time=" in clean_line
                if is_progress_line:
                    current_time = time.time()
                    if current_time - self.last_gui_log_time >= 10.0:
                        self._detail_log(f"[FFMPEG] {clean_line}")
                        self.last_gui_log_time = current_time
            pipe.close()
        except Exception as e:
            logger.warning(f"Lỗi khi đang đọc log từ subprocess: {e}")

    def run(self):
        self._detail_log("Bắt đầu vòng lặp theo dõi.")
        loop = asyncio.get_event_loop()
        final_status = None
        
        try:
            while not self.stop_event.is_set():
                try:
                    self._update_status(Status.MONITORING, Colors.BLUE)
                    self._detail_log(f"Đang kiểm tra trạng thái của @{self.user}...")

                    room_id = loop.run_until_complete(self.client.web.fetch_room_id_from_api(self.user))
                    if not room_id: raise UserOfflineError("API không trả về Room ID.")
                    
                    room_info = loop.run_until_complete(self.client.web.fetch_room_info(room_id))
                    if room_info.get("status", 4) == 4: raise UserOfflineError("User offline.")

                    logger.info(f"Xác nhận user @{self.user} đang live. Bắt đầu ghi hình.")
                    self._detail_log("Xác nhận user đang live. Bắt đầu ghi hình.")
                    self.current_wait_time = self.INITIAL_WAIT_TIME
                    
                    self._record_stream(room_info)

                    if not self.manual_stop_requested and not self.cancellation_requested:
                        self._update_status(Status.INFO_LIVESTREAM_ENDED, Colors.GREY)
                        self._detail_log("Live đã kết thúc. Quay lại chế độ theo dõi.")

                except UserOfflineError:
                    wait_duration = self.current_wait_time
                    self._detail_log(f"User không live, bắt đầu chờ {wait_duration // 60} phút...")
                    for i in range(wait_duration, 0, -1):
                        if self.stop_event.is_set(): break
                        mins, secs = divmod(i, 60)
                        self._update_status(Status.WAITING_COUNTDOWN.format(mins=mins, secs=secs), Colors.GREY, is_countdown=True)
                        time.sleep(1)
                    if self.stop_event.is_set(): break
                    self.current_wait_time = min(self.current_wait_time * 2, self.MAX_WAIT_TIME)
                    
                except (UserNotFoundError, AgeRestrictedError) as e:
                    error_map = {UserNotFoundError: Status.ERROR_USER_NOT_FOUND, AgeRestrictedError: Status.ERROR_AGE_RESTRICTED}
                    status_msg = error_map.get(type(e), Status.ERROR_UNKNOWN)
                    self._update_status(status_msg, Colors.RED)
                    self._detail_log(f"{status_msg}. Dừng theo dõi.")
                    logger.warning(f"Dừng theo dõi @{self.user} do: {status_msg}")
                    break
                except Exception as e:
                    logger.critical(f"Lỗi không mong muốn với @{self.user}: {e}", exc_info=True)
                    self._update_status(Status.ERROR_UNKNOWN, Colors.RED)
                    self._detail_log(f"Lỗi không xác định: {e}. Chờ 60 giây.")
                    self.stop_event.wait(timeout=60)
            
            final_status = self._handle_post_recording()
        
        finally:
            if callable(self.close_card_callback):
                self.close_card_callback(self.recording_id)
            try:
                if hasattr(self.client, 'web') and hasattr(self.client.web, '_session') and not self.client.web._session.is_closed:
                        loop.run_until_complete(self.client.web.close())
            except Exception as e:
                logger.warning(f"Lỗi khi dọn dẹp event loop cho @{self.user}: {e}")

        return final_status

    def _get_best_stream_url(self, room_info) -> str | None:
        try:
            stream_data = json.loads(room_info['stream_url']['live_core_sdk_data']['pull_data']['stream_data'])
            available_qualities = stream_data.get("data", {})
            for quality in ["origin", "uhd", "hd", "sd", "ld"]:
                if quality in available_qualities and available_qualities[quality]['main'].get('flv'):
                    self._detail_log(f"Đã chọn chất lượng tốt nhất: {quality.upper()}")
                    return available_qualities[quality]['main']['flv']
            self._detail_log("Không tìm thấy link stream FLV.")
            return None
        except Exception as e:
            self._detail_log(f"Lỗi khi lấy link stream: {e}.")
            return None

    def _record_stream(self, room_info):
        stream_url = self._get_best_stream_url(room_info)
        if not stream_url:
            self._update_status(Status.ERROR_NO_STREAM_URL, Colors.RED)
            return

        self._update_status(Status.RECORDING, Colors.RED)
        base_name = re.sub(r'[\\/*?:"<>|]', "", self.custom_filename) if self.custom_filename else f"TT_{self.user}_{time.strftime('%Y%m%d_%H%M%S')}"
        self.output_filepath = os.path.join(self.get_user_dir(), f"{base_name}.mp4")
        
        self._detail_log(f"URL Stream: ...{stream_url[-50:]}")
        self._detail_log(f"Tên file: {os.path.basename(self.output_filepath)}")
        
        ffmpeg_path = os.environ.get("FFMPEG_PATH")
        if not ffmpeg_path:
            self._update_status("Lỗi: Không tìm thấy FFmpeg", Colors.RED)
            return
            
        command = [ffmpeg_path, '-i', stream_url, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-y', self.output_filepath]

        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='ignore',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            
            log_thread = threading.Thread(target=self._log_subprocess_output, args=(self.process.stderr,), daemon=True)
            log_thread.start()
            
            last_check_time = time.time()
            while self.process.poll() is None and not self.stop_event.is_set():
                if time.time() - last_check_time >= 10:
                    try:
                        if os.path.exists(self.output_filepath):
                            size_mb = os.path.getsize(self.output_filepath) / (1024 * 1024)
                            self._detail_log(f"[DOWNLOAD] Đã ghi: {size_mb:.2f} MB")
                    except OSError as e: logger.warning(f"Không thể kiểm tra kích thước file: {e}")
                    last_check_time = time.time()
                time.sleep(1)

            if self.stop_event.is_set():
                if self.manual_stop_requested and not self.cancellation_requested:
                    self._detail_log("Đã nhận tín hiệu Dừng. Yêu cầu FFmpeg kết thúc an toàn...")
                    with suppress(OSError, subprocess.TimeoutExpired):
                        self.process.stdin.write('q'); self.process.stdin.flush()
                        self.process.wait(timeout=10)
                self.process.kill()

        except Exception as e:
            logger.error(f"Lỗi khi chạy ffmpeg cho @{self.user}: {e}", exc_info=True)
            self._update_status(f"Lỗi ghi hình: {e}", Colors.RED)
        finally:
            self._detail_log("Tiến trình ghi hình FFmpeg đã kết thúc.")
            self.process = None

# --- Douyin Section ---

class DouyinHttpClient:
    def __init__(self, cookies=None, custom_headers=None):
        self.session = Session(); self.session.trust_env = False
        default_headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", "Referer": "https://live.douyin.com/" }
        if custom_headers: default_headers.update(custom_headers)
        self.session.headers.update(default_headers)
        if cookies: self.session.headers['Cookie'] = cookies

class DouyinAPI:
    def __init__(self, cookies):
        self.config = DOUYIN_CONFIG
        self.http_client = DouyinHttpClient(cookies=cookies)

    def get_live_info(self, web_rid: str):
        params = self.config['api_params'].copy(); params['web_rid'] = web_rid
        try:
            response = self.http_client.session.get(self.config['api_endpoints']['web_enter'], params=params, timeout=15)
            if "<title>验证</title>" in response.text: raise RecordingException("Yêu cầu bị chặn bởi CAPTCHA.")
            response.raise_for_status(); data = response.json()
            room_data = data.get("data", {}).get("data", [{}])[0]
            user_data = data.get("data", {}).get("user", {})
            status = room_data.get("status", 4)
            live_url = None
            if status == 2:
                flv_map = room_data.get("stream_url", {}).get("flv_pull_url", {})
                live_url = flv_map.get("ORIGIN") or flv_map.get("FULL_HD1") or next(iter(flv_map.values()), None)
            return {"author_name": user_data.get("nickname", "Không rõ"), "status": status, "live_url": live_url}
        except RequestException as e: raise RecordingException(f"Lỗi mạng: {e}")
        except (ValueError, KeyError) as e: raise RecordingException(f"Lỗi phân tích dữ liệu API: {e}")

class DouyinRecorder(BaseRecorder):
    def __init__(self, live_url, **kwargs):
        self.live_url = live_url
        self.web_rid = self.live_url.split('?')[0].rstrip('/').rsplit('/', 1)[-1]
        super().__init__(user=f"Douyin_{self.web_rid}", **kwargs)
        self.douyin_api = DouyinAPI(self.cookies)
        logger.info(f"Khởi tạo Douyin recorder cho RID: {self.web_rid}")

    def run(self):
        final_status = None
        try:
            self._update_status(Status.MONITORING, Colors.BLUE)
            live_info = self.douyin_api.get_live_info(self.web_rid)
            if live_info.get("status") == 2:
                self.user = live_info.get("author_name", self.user)
                logger.info(f"Xác nhận user Douyin '{self.user}' đang live. Bắt đầu ghi hình.")
                self._detail_log(f"Xác nhận user '{self.user}' đang live. Bắt đầu ghi hình.")
                self._record_stream(live_info.get("live_url"))
                final_status = self._handle_douyin_post_recording()
            else:
                self._update_status("Offline", Colors.GREY)
                self._detail_log("User hiện không livestream.")
                final_status = {'status': 'offline', 'filepath': None}
        except RecordingException as e:
            self._update_status(f"Lỗi: {e}", Colors.RED)
            logger.error(f"Lỗi khi ghi hình Douyin '{self.user}': {e}")
            if callable(self.failure_callback): self.failure_callback(self.recording_id, self.user)
            final_status = {'status': 'failed', 'filepath': None}
        except Exception as e:
            logger.critical(f"Lỗi không mong muốn với Douyin RID {self.web_rid}: {e}", exc_info=True)
            self._update_status("Lỗi nghiêm trọng", Colors.RED)
            if callable(self.failure_callback): self.failure_callback(self.recording_id, self.user)
            final_status = {'status': 'failed', 'filepath': None}
        finally:
            if callable(self.close_card_callback):
                self.close_card_callback(self.recording_id)
        return final_status
    
    def _handle_douyin_post_recording(self):
        """Xử lý riêng cho Douyin để chuyển đổi FLV sang MP4 trước."""
        if self.cancellation_requested or (self.manual_stop_requested and not self.output_filepath):
            return self._handle_post_recording() # Gọi base handler cho các trường hợp này
        
        if not self.output_filepath or not os.path.exists(self.output_filepath) or os.path.getsize(self.output_filepath) <= 1024:
            return self._handle_post_recording() # Để base handler xử lý lỗi file
        
        self._detail_log("Chuyển đổi file FLV sang MP4...")
        mp4_file = VideoManagement.convert_flv_to_mp4(self.output_filepath, self.recording_id)

        if not mp4_file:
            self._update_status(Status.ERROR_RECORDING_FAILED, Colors.RED)
            self._detail_log("Lỗi khi chuyển đổi từ FLV sang MP4.")
            if callable(self.failure_callback): self.failure_callback(self.recording_id, self.user)
            return {'status': 'failed', 'filepath': self.output_filepath}

        self._detail_log("Chuyển đổi sang MP4 thành công.")
        self.output_filepath = mp4_file # Cập nhật filepath để base handler sử dụng
        return self._handle_post_recording() # Gọi base handler để xử lý MP3/Mute

    def _record_stream(self, live_url):
        if not live_url:
            self._detail_log("Không tìm thấy URL stream.")
            return

        self._update_status(Status.RECORDING, Colors.RED)
        base_name = re.sub(r'[\\/*?:"<>|]', "", self.custom_filename) if self.custom_filename else f"DY_{self.user}_{time.strftime('%Y%m%d_%H%M%S')}"
        self.output_filepath = os.path.join(self.get_user_dir(), f"{base_name}.flv")
        self._detail_log(f"Bắt đầu tải stream vào: {os.path.basename(self.output_filepath)}")

        start_time = time.time()
        last_check_time = start_time
        try:
            with self.douyin_api.http_client.session.get(live_url, stream=True, timeout=15) as response:
                response.raise_for_status()
                with open(self.output_filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.stop_event.is_set():
                            self._detail_log("Đã nhận tín hiệu dừng, ngưng tải.")
                            break
                        f.write(chunk)
                        current_time = time.time()
                        if current_time - last_check_time >= 10:
                            with suppress(OSError):
                                size_mb = os.path.getsize(self.output_filepath) / (1024 * 1024)
                                self._detail_log(f"[DOWNLOAD] Đã ghi: {size_mb:.2f} MB")
                            last_check_time = current_time
                        if self.duration and (current_time - start_time) > self.duration:
                            self._detail_log(f"Đã đạt thời lượng tối đa ({self.duration}s).")
                            break
        except RequestException as e:
            self._detail_log(f"Lỗi kết nối khi tải stream: {e}")
