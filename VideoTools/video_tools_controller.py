# VideoTools/video_tools_controller.py

import os
import threading
from datetime import datetime
import re

from Utils.logger_setup import LoggerProvider
from Utils.ffmpeg_utils import run_ffmpeg, stop_ffmpeg_processes

class VideoToolsController:
    def __init__(self, gui, project_root, thread_pool):
        self.gui = gui
        self.project_root = project_root
        self.thread_pool = thread_pool
        self.logger = LoggerProvider.get_logger('video_tools')
        
        self.active_ffmpeg_pids = []
        self.is_processing = False
        self.task_lock = threading.Lock()
        self.active_tasks = 0

    def on_closing(self):
        if self.active_ffmpeg_pids:
            self.logger.warning(f"Đang dừng {len(self.active_ffmpeg_pids)} tiến trình FFmpeg...")
            stop_ffmpeg_processes(self.active_ffmpeg_pids)

    def task_finished(self, operation_name):
        with self.task_lock:
            self.active_tasks -= 1
            if self.active_tasks == 0:
                self.is_processing = False
                self.gui.root.after(100, self.gui.finalize_processing, operation_name)

    def get_output_path(self, input_path, session_folder, suffix, new_ext=None):
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        ext = new_ext or os.path.splitext(input_path)[1]
        return os.path.join(session_folder, f"{base_name}{suffix}{ext}")

    def create_session_folder(self, base_name):
        session_folder_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + f"_{base_name}"
        output_session_dir = os.path.join(self.project_root, "Video_Output", session_folder_name)
        os.makedirs(output_session_dir, exist_ok=True)
        self.gui.log_status(f"Các file sẽ được lưu tại: {output_session_dir}")
        return output_session_dir

    # --- LOGIC CHO WATERMARK ---
    def start_watermarking(self, video_path, logo_path, position, padding):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        with self.task_lock: self.active_tasks = 1
        
        session_folder = self.create_session_folder("Watermarked")
        output_file = self.get_output_path(video_path, session_folder, "_watermarked")
        
        self.thread_pool.submit(self.run_watermark_task, video_path, logo_path, position, padding, output_file)

    def run_watermark_task(self, video_path, logo_path, position, padding, output_file):
        try:
            self.gui.log_status(f"Bắt đầu chèn logo vào {os.path.basename(video_path)}...")
            pos_map = {
                "Trên-Trái": f"overlay={padding}:{padding}",
                "Trên-Phải": f"overlay=W-w-{padding}:{padding}",
                "Dưới-Trái": f"overlay={padding}:H-h-{padding}",
                "Dưới-Phải": f"overlay=W-w-{padding}:H-h-{padding}"
            }
            filter_complex = f"[0:v][1:v]{pos_map[position]}"
            args = ["-i", logo_path, "-filter_complex", filter_complex]
            run_ffmpeg(video_path, output_file, args)
            self.gui.log_status(f"Chèn logo thành công -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi chèn logo: {e}", exc_info=True)
            self.gui.log_status(f"LỖI: {e}", "error")
        finally:
            self.task_finished("chèn logo")

    # --- LOGIC CHO GẮN PHỤ ĐỀ ---
    def start_hardsubbing(self, video_path, subtitle_path):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        with self.task_lock: self.active_tasks = 1

        session_folder = self.create_session_folder("Hardsubbed")
        output_file = self.get_output_path(video_path, session_folder, "_subbed")

        self.thread_pool.submit(self.run_hardsub_task, video_path, subtitle_path, output_file)

    def run_hardsub_task(self, video_path, subtitle_path, output_file):
        try:
            self.gui.log_status(f"Bắt đầu gắn phụ đề vào {os.path.basename(video_path)}...")
            # FFmpeg yêu cầu đường dẫn file phụ đề phải được escape đúng cách
            escaped_sub_path = subtitle_path.replace('\\', '/').replace(':', '\\:')
            filter_vf = f"subtitles='{escaped_sub_path}'"
            args = ["-vf", filter_vf]
            run_ffmpeg(video_path, output_file, args)
            self.gui.log_status(f"Gắn phụ đề thành công -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi gắn phụ đề: {e}", exc_info=True)
            self.gui.log_status(f"LỖI: {e}", "error")
        finally:
            self.task_finished("gắn phụ đề")

    # --- LOGIC CHO TẠO GIF ---
    def start_gif_creation(self, video_path, start_time, duration, fps, width):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        with self.task_lock: self.active_tasks = 1

        session_folder = self.create_session_folder("GIF_Creation")
        output_file = self.get_output_path(video_path, session_folder, "", new_ext=".gif")
        
        self.thread_pool.submit(self.run_gif_creation_task, video_path, start_time, duration, fps, width, session_folder, output_file)

    def run_gif_creation_task(self, video_path, start_time, duration, fps, width, session_folder, output_file):
        try:
            self.gui.log_status("Bắt đầu tạo ảnh GIF (2 bước)...")
            palette_file = os.path.join(session_folder, "palette.png")
            
            # Bước 1: Tạo bảng màu (palette) để GIF đẹp hơn
            self.gui.log_status("Bước 1/2: Đang tạo bảng màu tối ưu...")
            palette_filter = f"fps={fps},scale={width}:-1:flags=lanczos,palettegen"
            palette_args = ["-ss", start_time, "-t", duration, "-vf", palette_filter]
            run_ffmpeg(video_path, palette_file, palette_args)
            
            # Bước 2: Sử dụng bảng màu để tạo GIF
            self.gui.log_status("Bước 2/2: Đang tạo file GIF...")
            gif_filter = f"fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse"
            gif_args = ["-ss", start_time, "-t", duration, "-i", palette_file, "-filter_complex", gif_filter]
            run_ffmpeg(video_path, output_file, gif_args)

            os.remove(palette_file) # Dọn dẹp file palette
            self.gui.log_status(f"Tạo GIF thành công -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi tạo GIF: {e}", exc_info=True)
            self.gui.log_status(f"LỖI: {e}", "error")
        finally:
            self.task_finished("tạo GIF")

    # --- LOGIC CHO THAY ĐỔI KÍCH THƯỚC ---
    def start_resizing(self, video_path, method, target_ratio_str):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        with self.task_lock: self.active_tasks = 1

        session_folder = self.create_session_folder("Resized")
        output_file = self.get_output_path(video_path, session_folder, f"_resized_{target_ratio_str.replace(':', 'x')}")

        self.thread_pool.submit(self.run_resize_task, video_path, method, target_ratio_str, output_file)

    def run_resize_task(self, video_path, method, target_ratio_str, output_file):
        try:
            self.gui.log_status(f"Bắt đầu thay đổi kích thước sang {target_ratio_str}...")
            w, h = map(int, target_ratio_str.split(':'))
            
            if method == "Cắt để vừa (Crop)":
                # Cắt phần thừa hai bên hoặc trên dưới
                filter_vf = f"scale=iw*max({w}/iw\\,{h}/ih):ih*max({w}/iw\\,{h}/ih),crop={w}*iw/{w}:{h}*ih/{h}"
            else: # Thêm viền đen (Pad)
                # Thu nhỏ video để vừa khung hình, sau đó thêm viền đen
                filter_vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"

            args = ["-vf", filter_vf, "-c:a", "copy"]
            run_ffmpeg(video_path, output_file, args)
            self.gui.log_status(f"Thay đổi kích thước thành công -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi thay đổi kích thước: {e}", exc_info=True)
            self.gui.log_status(f"LỖI: {e}", "error")
        finally:
            self.task_finished("thay đổi kích thước")