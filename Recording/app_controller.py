# Recording/app_controller.py

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

from Utils.config import MAX_ROWS, MAX_ACTIVE_USERS, COOKIES
from .rec_logic import (
    TikTokRecorder, TikTokException, UserLiveException,
    LiveNotFound, RecordingException
)
from .gui_view import GUIView
from Utils.logger_setup import LoggerProvider
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

class AppController:
    def __init__(self, root_frame, project_root, thread_pool):
        logger.debug("Bắt đầu khởi tạo AppController cho tab Recording")
        self.root = root_frame
        self.project_root = project_root
        
        self.user_history = []
        self.history_file_path = os.path.join(self.project_root, 'Data', 'user_history.json')
        self._load_user_history()
        
        self.is_running = True
        self.user_rows = {}
        self.rows_lock = threading.RLock()
        self.thread_pool = thread_pool
        self.custom_output_dir = None
        self.cookies = COOKIES
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

    # --- HÀM MỚI ---
    def detail_log_update(self, row_id, message):
        """Đưa tác vụ cập nhật log chi tiết vào hàng đợi của UI."""
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
        username = self.extract_username(current_text)
        
        card_frame = model.widgets.get('card_frame')
        if card_frame and card_frame.winfo_exists():
            card_frame.config(text=f"User: @{username}" if username else "User")

        if username and current_text != f"@{username}":
            widget.set(f"@{username}")
        
        model.last_known_input = widget.get()

    def update_row_status(self, row_id, text, color, is_countdown=False):
        model = self.user_rows.get(row_id)
        if not model: return

        # Chỉ cập nhật trạng thái logic nếu không phải là đếm ngược
        if not is_countdown:
            model.status = text

        status_label = model.widgets.get('status_label')
        progressbar = model.widgets.get('progressbar')

        self.update_queue.put(lambda: self.view.update_status_label(status_label, text, color))

        # Không thay đổi progressbar khi đang đếm ngược
        if not is_countdown:
            if "Đang ghi hình" in text or "Đang khởi động" in text:
                self.update_queue.put(lambda: self.view.update_progressbar(progressbar, mode='indeterminate'))
            elif "Chờ" in text or "Lỗi" in text or "Đã hủy" in text:
                self.update_queue.put(lambda: self.view.update_progressbar(progressbar, mode='stop'))
            elif "Hoàn tất" in text or "Live kết thúc" in text or "Đã dừng" in text:
                self.update_queue.put(lambda: self.view.update_progressbar(progressbar, mode='determinate', value=100))

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
            if response:
                self.stop_recording(row_id, is_cancelling=True)
        else:
            self.view.remove_detail_card(row_id)
            self.view.remove_user_card_from_gui(row_id)
            with self.rows_lock:
                if row_id in self.user_rows: del self.user_rows[row_id]
            logger.info(f"Đã xóa thẻ với row_id: {row_id}")
            self._update_add_button_state()

    def cleanup_ui_and_data(self, row_id, username):
        logger.debug(f"Bắt đầu dọn dẹp cho hàng {row_id}")
        self.active_users.discard(username)
        with self.rows_lock:
            model = self.user_rows.get(row_id)
            if model:
                model.recorder = None
                model.future = None
                model.is_stopping = False
                self.view.update_ui_for_state(row_id, 'stopped')
                self.update_row_status(row_id, "Chờ", "grey")
                # Xóa thẻ chi tiết khi dọn dẹp
                self.view.remove_detail_card(row_id) 
        self.view.update_status_labels(len(self.successful_users), len(self.failed_users))
        logger.info(f"Hoàn tất dọn dẹp cho user {username}")

    def report_recording_success(self, row_id, username):
        logger.info(f"Nhận báo cáo ghi hình thành công cho user: {username}")
        if username not in self.successful_users: self.successful_users.append(username)
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
        username = self.extract_username(url_input)

        if not username:
            self.view.show_messagebox("error", "Lỗi", "Tên người dùng không hợp lệ.")
            return

        self.handle_url_entry_focus_out(row_id, model.widgets['url_combobox'])

        for r_id, r_model in self.user_rows.items():
            if r_id != row_id and r_model.recorder and r_model.recorder.user == username:
                self.view.show_messagebox("warning", "Trùng lặp", f"User {username} đã đang được ghi hình ở thẻ khác.")
                return

        if username in self.user_history: self.user_history.remove(username)
        self.user_history.insert(0, username)
        self._save_user_history()
        self._update_all_history_suggestions()

        def record_in_thread():
            try:
                custom_filename = model.widgets['filename_entry'].get().strip()
                duration_str = model.widgets['duration_entry'].get()
                duration = int(duration_str) if duration_str.isdigit() else None

                recorder = TikTokRecorder(
                    user=username, cookies=self.cookies, duration=duration,
                    convert_to_mp3=model.widgets['convert_var'].get(),
                    recording_id=row_id, custom_output_dir=self.custom_output_dir,
                    status_callback=self.update_row_status,
                    success_callback=self.report_recording_success,
                    project_root=self.project_root,
                    custom_filename=custom_filename,
                    detail_log_callback=self.detail_log_update
                )

                with self.rows_lock: model.recorder = recorder
                self.active_users.add(recorder.user)
                recorder.run()

                if recorder.cancellation_requested:
                    if username not in self.failed_users: self.failed_users.append(username)
                    self.update_row_status(row_id, "Đã hủy", "red")
                elif recorder.manual_stop_requested:
                    self.update_row_status(row_id, "Đã dừng & Lưu", "grey")
                else:
                    self.update_row_status(row_id, "Live kết thúc, theo dõi lại...", "orange")

            except (TikTokException, UserLiveException, LiveNotFound, RecordingException) as e:
                logger.error(f"Lỗi ghi hình cho {username}: {e}")
                if username not in self.failed_users: self.failed_users.append(username)
                self.update_row_status(row_id, f"Lỗi: {e}", "red")
            except Exception as e:
                logger.critical(f"Lỗi không mong muốn khi ghi hình {username}: {e}", exc_info=True)
                if username not in self.failed_users: self.failed_users.append(username)
                self.update_row_status(row_id, "Lỗi nghiêm trọng", "red")

        future = self.thread_pool.submit(record_in_thread)
        with self.rows_lock: model.future = future

        self.view.create_detail_card(row_id)
        self.view.update_ui_for_state(row_id, 'recording')
        self.update_row_status(row_id, "Đang khởi động...", "blue")

    def stop_recording(self, row_id, is_cancelling=False):
        with self.rows_lock:
            model = self.user_rows.get(row_id)
            if not model or not model.recorder: return

        self.view.remove_detail_card(row_id)

        if is_cancelling:
            logger.info(f"Đã gửi tín hiệu Hủy cho recorder của user {model.recorder.user}.")
            self.update_row_status(row_id, "Đang hủy...", "orange")
            model.recorder.cancel()
        else:
            logger.info(f"Đã gửi tín hiệu Dừng cho recorder của user {model.recorder.user}.")
            self.update_row_status(row_id, "Đang dừng...", "orange")
            model.recorder.stop()

    def extract_username(self, text_input):
        if not text_input or not isinstance(text_input, str): return ""
        text_input = text_input.strip()
        match = re.search(r"@([a-zA-Z0-9_.-]+)", text_input)
        if match: return match.group(1)
        if re.match(r'^[a-zA-Z0-9_.-]+$', text_input): return text_input
        logger.warning(f"Không thể trích xuất username từ đầu vào: '{text_input}'")
        return ""

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
                        username = recorder.user
                        if future.exception():
                            logger.error(f"Luồng cho user '{username}' đã kết thúc với một exception: {future.exception()}", exc_info=future.exception())
                        else:
                            logger.info(f"Luồng cho user '{username}' đã hoàn thành, chuẩn bị dọn dẹp.")
                        model.is_stopping = True
                        self.update_queue.put(lambda rid=row_id, u=username: self.cleanup_ui_and_data(rid, u))

    def on_closing(self):
        logger.info("Bắt đầu quy trình đóng tab Recording")
        self.is_running = False

        # Dừng tất cả recorder nếu còn đang chạy
        for model in self.user_rows.values():
            if model.recorder:
                model.recorder.cancel()

        logger.info("Đã gửi tín hiệu dừng cho tất cả các luồng.")
        
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
