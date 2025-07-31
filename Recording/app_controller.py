import tkinter as tk
from tkinter import filedialog
import threading
import os
import sys
import json
import time
import queue
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

from Utils.cookie_loader import load_user_cookies, save_user_cookies
from .settings_window import SettingsWindow
from Utils.config import MAX_ROWS, MAX_ACTIVE_USERS, MP3_PROFILES, FALLBACK_TIKTOK_COOKIE, FALLBACK_DOUYIN_COOKIE
from .rec_logic import (
    TikTokRecorder, DouyinRecorder,
    RecordingException, VideoManagement
)
from .gui_view import GUIView
from Utils.ffmpeg_utils import setup_ffmpeg
from Utils.logger_setup import LoggerProvider
from Utils.constants import Status, Colors

logger = LoggerProvider.get_logger('recording')

class UserRowModel:
    def __init__(self, row_id):
        self.id = row_id
        self.status = "Chờ"
        self.recorder = None
        self.future = None
        self.is_stopping = False
        self.widgets = {}
        self.last_known_input = ""
        self.platform = "tiktok"

class AppController:
    def __init__(self, root_frame, project_root, thread_pool):
        logger.debug("Bắt đầu khởi tạo AppController cho tab Recording")
        self.root = root_frame
        self.project_root = project_root

        try:
            setup_ffmpeg(self.project_root)
        except (FileNotFoundError, PermissionError) as e:
            logger.critical(f"KHỞI TẠO FFMPEG THẤT BẠI: {e}")
        
        self.user_history = []
        self.history_file_path = os.path.join(self.project_root, 'Data', 'user_history.json')
        self._load_user_history()
        
        self.is_running = True
        self.user_rows = {}
        self.rows_lock = threading.RLock()
        self.thread_pool = thread_pool
        self.custom_output_dir = None
        
        # Tải cookie do người dùng cung cấp
        self.user_cookies = load_user_cookies() 
        # Giữ lại cookie hardcode làm phương án dự phòng
        self.fallback_cookies = {
            'tiktok': FALLBACK_TIKTOK_COOKIE,
            'douyin': FALLBACK_DOUYIN_COOKIE
        }
        
        self.successful_users = []
        self.failed_users = []
        self.active_users = set()

        self.view = GUIView(self.root, self, self.project_root)
        self.add_user_row()

        self.update_queue = queue.Queue()
        self.process_queue()

        self.monitor_thread = threading.Thread(target=self.monitor_threads, daemon=True)
        self.monitor_thread.start()
        logger.debug("Hoàn tất khởi tạo AppController")

    def open_specific_user_folder(self, row_id):
        """Mở thư mục con của một user cụ thể trong thư mục Output."""
        model = self.user_rows.get(row_id)
        if not model: return

        user_folder_path = None
        # Nếu recorder đã được tạo, nó là nguồn tin cậy nhất cho đường dẫn
        if model.recorder:
            user_folder_path = model.recorder.get_user_dir()
        else:
            # Nếu chưa, tạo đường dẫn dự đoán từ thông tin nhập vào
            identifier = self._extract_identifier(model.last_known_input, model.platform)
            if not identifier:
                self.view.show_messagebox("info", "Thông báo", "Vui lòng nhập ID user để xác định thư mục.")
                return
            
            # Phải khớp với logic tạo tên trong rec_logic
            # Douyin ban đầu sẽ có tên thư mục là "Douyin_{RID}"
            user_for_folder = f"Douyin_{identifier}" if model.platform == 'douyin' else identifier
            sanitized_foldername = re.sub(r'[\\/*?:"<>|]', "", user_for_folder)
            
            base_output_dir = self.custom_output_dir or os.path.join(self.project_root, 'Rec_Output')
            user_folder_path = os.path.join(base_output_dir, sanitized_foldername)

        if os.path.isdir(user_folder_path):
            try:
                os.startfile(user_folder_path)
                logger.info(f"Đang mở thư mục của user: {user_folder_path}")
            except Exception as e:
                logger.error(f"Không thể mở thư mục user: {e}")
                self.view.show_messagebox("error", "Lỗi", f"Không thể mở thư mục:\n{user_folder_path}")
        else:
            self.view.show_messagebox("info", "Thông báo", f"Thư mục của user chưa tồn tại.\n(Có thể chưa có bản ghi nào được lưu).\nĐường dẫn mong muốn: {user_folder_path}")

    def open_log_file(self):
        """Mở file log của tab Recording."""
        try:
            # Lấy đường dẫn file log từ LoggerProvider
            log_filepath = LoggerProvider.get_log_filepath('recording')
            if log_filepath and os.path.exists(log_filepath):
                os.startfile(log_filepath)
                logger.info(f"Đang mở file log: {log_filepath}")
            else:
                logger.warning("Không tìm thấy file log của tab Recording.")
                self.view.show_messagebox("warning", "Không tìm thấy", "Không tìm thấy file log.")
        except Exception as e:
            logger.error(f"Không thể mở file log: {e}")
            self.view.show_messagebox("error", "Lỗi", f"Không thể mở file log.")

    def get_active_cookies(self, platform):
        """
        Ưu tiên cookie của người dùng. Nếu không có, dùng cookie dự phòng.
        platform: 'tiktok' hoặc 'douyin'
        """
        user_cookie = self.user_cookies.get(platform, "").strip()
        if user_cookie:
            logger.info(f"Sử dụng cookie do người dùng cung cấp cho {platform}.")
            return user_cookie
        
        logger.warning(f"Không có cookie người dùng, sử dụng cookie dự phòng cho {platform}.")
        return self.fallback_cookies.get(platform)

    def show_settings(self):
        """Hiển thị cửa sổ cài đặt cookies."""
        SettingsWindow(self.root, self.user_cookies, self.save_settings)

    def save_settings(self, new_cookies):
        """Callback để lưu cookies từ cửa sổ cài đặt."""
        if save_user_cookies(new_cookies):
            self.user_cookies = new_cookies # Cập nhật trạng thái cookies trong controller
            return True
        return False

    def get_current_mp3_options(self, row_id):
        model = self.user_rows.get(row_id)
        if not model or not model.widgets:
            return {'convert': False, 'profile_key': None}

        widgets = model.widgets
        convert = widgets.get('convert_var').get() if 'convert_var' in widgets else False
        
        selected_display_name = widgets.get('mp3_profile_combobox').get() if 'mp3_profile_combobox' in widgets else ''
        
        # Tìm key tương ứng với display name
        profile_key = None
        for key, profile in MP3_PROFILES.items():
            if profile['display'] == selected_display_name:
                profile_key = key
                break

        return {'convert': convert, 'profile_key': profile_key}

    def _detect_platform(self, input_str):
        if "live.douyin.com/" in input_str:
            return "douyin"
        return "tiktok"

    def _extract_identifier(self, text_input, platform):
        if not text_input or not isinstance(text_input, str): return ""
        text_input = text_input.strip()
        
        if platform == "douyin":
            match = re.search(r'live\.douyin\.com/(\d+)', text_input)
            return match.group(1) if match else ""
        else:
            match = re.search(r"@([a-zA-Z0-9_.-]+)", text_input)
            if match: return match.group(1)
            if re.match(r'^[a-zA-Z0-9_.-]+$', text_input): return text_input
            return ""

    def detail_log_update(self, row_id, message):
        self.update_queue.put(lambda: self.view.update_detail_card(row_id, message))

    def _load_user_history(self):
        try:
            os.makedirs(os.path.dirname(self.history_file_path), exist_ok=True)
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list): self.user_history = data
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Không thể đọc file lịch sử: {e}")
            self.user_history = []

    def _save_user_history(self):
        try:
            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Lỗi khi ghi file lịch sử: {e}")

    def _update_all_history_suggestions(self):
        for row_id, model in self.user_rows.items():
            combobox = model.widgets.get('url_combobox')
            if combobox and combobox.winfo_exists():
                combobox['values'] = self.user_history
    
    def handle_url_entry_focus_out(self, row_id, widget):
        model = self.user_rows.get(row_id)
        if not model: return
        
        current_text = widget.get().strip()
        platform = self._detect_platform(current_text)
        identifier = self._extract_identifier(current_text, platform)
        
        model.platform = platform
        
        card_frame = model.widgets.get('card_frame')
        if card_frame and card_frame.winfo_exists():
            display_name = f"Douyin - {identifier}" if platform == 'douyin' else f"@{identifier}"
            card_frame.config(text=f"User: {display_name}" if identifier else "User")

        if platform == 'tiktok' and identifier and current_text != f"@{identifier}":
            widget.set(f"@{identifier}")
        
        model.last_known_input = widget.get()

    def update_row_status(self, row_id, text, color, is_countdown=False):
        model = self.user_rows.get(row_id)
        if not model: return
        if not is_countdown: model.status = text
        status_label = model.widgets.get('status_label')
        progressbar = model.widgets.get('progressbar')
        self.update_queue.put(lambda: self.view.update_status_label(status_label, text, color))
        
        if not is_countdown:
            if "Đang ghi hình" in text or "Đang khởi động" in text or "Đang theo dõi" in text:
                self.update_queue.put(lambda: self.view.update_progressbar(progressbar, mode='indeterminate'))
            elif "Hoàn tất" in text or "Đã dừng" in text:
                self.update_queue.put(lambda: self.view.update_progressbar(progressbar, mode='determinate', value=100))
            else:
                self.update_queue.put(lambda: self.view.update_progressbar(progressbar, mode='stop'))

    def process_queue(self):
        try:
            while not self.update_queue.empty():
                callback = self.update_queue.get_nowait()
                if callable(callback): callback()
        except queue.Empty: pass
        finally:
            if self.is_running: self.root.after(100, self.process_queue)

    def _update_add_button_state(self):
        at_max_rows = len(self.user_rows) >= MAX_ROWS
        self.view.set_widget_state(self.view.add_user_button, 'disabled' if at_max_rows else 'normal')

    def add_user_row(self):
        with self.rows_lock:
            if len(self.user_rows) >= MAX_ROWS:
                self.view.show_messagebox("warning", "Cảnh báo", f"Đã đạt tối đa {MAX_ROWS} thẻ user.")
                return None
            row_id = str(uuid.uuid4())
            new_row_widgets = self.view.add_user_card_to_gui(row_id, self.user_history)
            new_model = UserRowModel(row_id)
            new_model.widgets = new_row_widgets
            self.user_rows[row_id] = new_model
            logger.debug(f"Đã thêm thẻ mới với row_id: {row_id}")
            self._update_add_button_state()
            return row_id

    def remove_user_row(self, row_id):
        model = self.user_rows.get(row_id)
        if not model: return
        if model.recorder is not None:
            msg = "User đang ghi hình/chờ.\nThao tác này sẽ HỦY và KHÔNG LƯU file.\nBạn có chắc không?"
            response = self.view.show_messagebox("askyesno", "Xác nhận Hủy", msg)
            if response: self.stop_recording(row_id, is_cancelling=True)
        else:
            self.view.remove_detail_card(row_id)
            self.view.remove_user_card_from_gui(row_id)
            with self.rows_lock:
                if row_id in self.user_rows: del self.user_rows[row_id]
            logger.info(f"Đã xóa thẻ với row_id: {row_id}")
            self._update_add_button_state()

    def cleanup_ui_and_data(self, row_id, identifier):
        logger.debug(f"Bắt đầu dọn dẹp cho hàng {row_id}")
        self.active_users.discard(identifier)
        with self.rows_lock:
            model = self.user_rows.get(row_id)
            if model:
                model.recorder = None
                model.future = None
                model.is_stopping = False
                self.update_queue.put(lambda: self.view.update_ui_for_state(row_id, 'stopped'))
        
        self.update_queue.put(lambda: self.view.update_status_labels(len(self.successful_users), len(self.failed_users)))
        logger.info(f"Hoàn tất dọn dẹp cho user {identifier}")

    def close_detail_card_for_row(self, row_id):
        self.update_queue.put(lambda: self.view.remove_detail_card(row_id))

    def report_recording_success(self, row_id, identifier):
        logger.info(f"Nhận báo cáo ghi hình thành công cho user: {identifier}")
        if identifier not in self.successful_users: self.successful_users.append(identifier)
        if identifier in self.failed_users: self.failed_users.remove(identifier)
        self.update_queue.put(lambda: self.view.update_status_labels(len(self.successful_users), len(self.failed_users)))

    def report_recording_failure(self, row_id, identifier):
        logger.warning(f"Nhận báo cáo ghi hình thất bại cho user: {identifier}")
        if identifier not in self.failed_users: self.failed_users.append(identifier)
        if identifier in self.successful_users: self.successful_users.remove(identifier)
        self.update_queue.put(lambda: self.view.update_status_labels(len(self.successful_users), len(self.failed_users)))
    
    def browse_output_dir(self):
        path = filedialog.askdirectory(title="Chọn thư mục đầu ra")
        if path:
            self.custom_output_dir = os.path.normpath(path)
            self.view.update_output_dir_entry(self.custom_output_dir)
            logger.info(f"Đã chọn thư mục đầu ra tùy chỉnh: {self.custom_output_dir}")

    def start_recording(self, row_id):
        model = self.user_rows.get(row_id)
        if not model or model.recorder: return

        if len(self.active_users) >= MAX_ACTIVE_USERS:
            self.view.show_messagebox("warning", "Quá tải", f"Đã đạt tối đa {MAX_ACTIVE_USERS} user ghi hình cùng lúc.")
            return

        url_input = model.widgets['url_combobox'].get()
        platform = self._detect_platform(url_input)
        identifier = self._extract_identifier(url_input, platform)

        if not identifier:
            self.view.show_messagebox("error", "Lỗi", "Đầu vào không hợp lệ (username TikTok hoặc link Douyin).")
            return

        self.handle_url_entry_focus_out(row_id, model.widgets['url_combobox'])

        for r_id, r_model in self.user_rows.items():
            if r_id != row_id and r_model.recorder:
                recorder_id = r_model.recorder.web_rid if hasattr(r_model.recorder, 'web_rid') else r_model.recorder.user
                if recorder_id == identifier and r_model.platform == platform:
                    self.view.show_messagebox("warning", "Trùng lặp", f"Định danh '{identifier}' đã đang được xử lý.")
                    return

        history_item = identifier if platform == 'tiktok' else url_input
        if history_item in self.user_history:
            self.user_history.remove(history_item)
        self.user_history.insert(0, history_item)
        self._save_user_history()
        self._update_all_history_suggestions()
        
        def record_in_thread():
            try:
                # Lấy tất cả tùy chọn từ giao diện
                custom_filename = model.widgets['filename_entry'].get().strip()
                duration_str = model.widgets['duration_entry'].get()
                duration = int(duration_str) if duration_str.isdigit() else None
                mp3_options = self.get_current_mp3_options(row_id)
                mute_video = model.widgets['mute_video_var'].get()
                
                # Lấy cookie đang hoạt động
                active_cookie = self.get_active_cookies(platform)
                
                recorder_class = DouyinRecorder if platform == 'douyin' else TikTokRecorder
                recorder_args = {
                    'cookies': active_cookie,
                    'duration': duration,
                    'recording_id': row_id,
                    'custom_output_dir': self.custom_output_dir,
                    'status_callback': self.update_row_status,
                    'success_callback': self.report_recording_success,
                    'failure_callback': self.report_recording_failure,
                    'close_card_callback': self.close_detail_card_for_row,
                    'project_root': self.project_root,
                    'custom_filename': custom_filename,
                    'detail_log_callback': self.detail_log_update,
                    'mp3_options': mp3_options,
                    'mute_video': mute_video,
                }
                if platform == 'douyin':
                    recorder_args['live_url'] = url_input
                else:
                    recorder_args['user'] = identifier

                recorder = recorder_class(**recorder_args)
                with self.rows_lock:
                    model.recorder = recorder
                self.active_users.add(identifier)
                
                recorder.run()

            except RecordingException as e:
                logger.error(f"Lỗi ghi hình cho {identifier}: {e}")
                if identifier not in self.failed_users:
                    self.failed_users.append(identifier)
                self.update_row_status(row_id, f"Lỗi: {e}", "red")
            except Exception as e:
                logger.critical(f"Lỗi không mong muốn khi ghi hình {identifier}: {e}", exc_info=True)
                if identifier and identifier not in self.failed_users:
                    self.report_recording_failure(row_id, identifier)
                self.update_row_status(row_id, "Lỗi nghiêm trọng", "red")
            
            finally:
                identifier_to_clean = identifier
                self.update_queue.put(lambda: self.cleanup_ui_and_data(row_id, identifier_to_clean))

        self.thread_pool.submit(record_in_thread)
        with self.rows_lock: model.future = None

        self.view.create_detail_card(row_id)
        self.view.update_ui_for_state(row_id, 'recording')
        self.update_row_status(row_id, Status.STARTING, Colors.BLUE)

    def stop_recording(self, row_id, is_cancelling=False):
        with self.rows_lock:
            model = self.user_rows.get(row_id)
            if not model or not model.recorder: return
        self.view.remove_detail_card(row_id)
        identifier = model.recorder.web_rid if hasattr(model.recorder, 'web_rid') else model.recorder.user
        if is_cancelling:
            logger.info(f"Đã gửi tín hiệu Hủy cho recorder của {identifier}.")
            self.update_row_status(row_id, Status.CANCELLING, Colors.ORANGE)
            model.recorder.cancel()
        else:
            logger.info(f"Đã gửi tín hiệu Dừng cho recorder của {identifier}.")
            self.update_row_status(row_id, Status.STOPPING, Colors.ORANGE)
            model.recorder.stop()

    def monitor_threads(self):
        while self.is_running:
            time.sleep(1)
            with self.rows_lock:
                for row_id in list(self.user_rows.keys()):
                    model = self.user_rows.get(row_id)
                    if not model or model.is_stopping: continue
                    future = model.future
                    if future and future.done():
                        recorder = model.recorder
                        if not recorder: continue
                        identifier = recorder.web_rid if hasattr(recorder, 'web_rid') else recorder.user
                        if future.exception():
                            logger.error(f"Luồng cho '{identifier}' đã kết thúc với một exception: {future.exception()}", exc_info=future.exception())
                        else:
                            logger.info(f"Luồng cho '{identifier}' đã hoàn thành, chuẩn bị dọn dẹp.")
                        model.is_stopping = True
                        self.update_queue.put(lambda rid=row_id, u=identifier: self.cleanup_ui_and_data(rid, u))

    def on_closing(self):
        logger.info("Bắt đầu quy trình đóng tab Recording")
        self.is_running = False

        self.view.show_progress_dialog("Đang dừng và lưu các bản ghi...")

        def shutdown_worker():
            active_recorders = []
            for model in self.user_rows.values():
                if model.recorder:
                    active_recorders.append(model.recorder)
            
            for recorder in active_recorders:
                recorder.stop()

            logger.info(f"Đang chờ {len(self.thread_pool._threads)} luồng hoàn thành...")
            self.thread_pool.shutdown(wait=True)
            
            logger.info("Tất cả luồng đã dừng. Đóng cửa sổ chờ.")
            self.update_queue.put(self.view.close_active_dialog)
            
        shutdown_thread = threading.Thread(target=shutdown_worker)
        shutdown_thread.start()
        
        logger.info("Đã gửi yêu cầu đóng, giao diện chính có thể tiếp tục.")
        
    def convert_to_mp3_manual(self, input_file, output_dir):
        if not input_file or not os.path.exists(input_file):
            self.view.show_messagebox("error", "Lỗi", "Vui lòng chọn file đầu vào hợp lệ.")
            return
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = os.path.dirname(input_file)
        base_filename = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_filename}.mp3")
        logger.info(f"Bắt đầu chuyển đổi thủ công sang MP3: {os.path.basename(input_file)}")
        self.view.set_mp3_button_state('disabled')
        def conversion_thread():
            from .rec_logic import VideoManagement
            try:
                VideoManagement.convert_mp4_to_mp3(file=input_file, output_file=output_file)
                self.update_queue.put(lambda: self.view.show_messagebox("info", "Thành công", f"Đã chuyển đổi thành công file:\n{os.path.basename(output_file)}"))
            except Exception as e:
                logger.error(f"Lỗi khi chuyển đổi MP3 thủ công: {e}")
                self.update_queue.put(lambda: self.view.show_messagebox("error", "Lỗi", f"Chuyển đổi thất bại: {e}"))
            finally:
                self.update_queue.put(lambda: self.view.set_mp3_button_state('normal'))
                self.update_queue.put(self.view.close_active_dialog)
        self.thread_pool.submit(conversion_thread)

    def show_status_details(self, status_type):
        if status_type == "success":
            events = self.successful_users
            title = "Lịch sử Thành công"
        else:
            events = self.failed_users
            title = "Lịch sử Thất bại"
        if not events:
            self.view.show_messagebox("info", title, "Không có sự kiện nào trong danh sách này.")
            return
        unique_users = sorted(list(set(events)))
        user_list_str = "\n".join(unique_users)
        self.view.show_details_window(title, user_list_str)
