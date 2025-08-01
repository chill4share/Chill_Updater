# VideoTools/video_tools_controller.py

import os
import threading
from datetime import datetime

from Utils.logger_setup import LoggerProvider
from Utils.ffmpeg_utils import run_ffmpeg, stop_ffmpeg_processes

class VideoToolsController:
    def __init__(self, gui, project_root, thread_pool):
        self.gui = gui
        self.project_root = project_root
        self.thread_pool = thread_pool
        self.logger = LoggerProvider.get_logger('video_tools')
        
        self.is_processing = False
        self.task_lock = threading.Lock()
        self.active_tasks = 0

    def on_closing(self):
        # This method is good practice if you need to clean up ffmpeg on exit
        pass

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

    # --- LOGIC XỬ LÝ VIDEO TỔNG HỢP ---
    def start_combined_processing(self, params):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        with self.task_lock: self.active_tasks = 1

        session_folder = self.create_session_folder("Processed_Video")
        output_file = self.get_output_path(params["video_path"], session_folder, "_processed")

        self.thread_pool.submit(self.run_combined_task, output_file, params)

    def run_combined_task(self, output_file, params):
        try:
            input_files = []
            video_filters = []
            map_args = []
            log_messages = []

            # --- Xây dựng danh sách Input và Map cơ bản ---
            # Input 0: Video chính
            input_files.extend(["-i", params["video_path"]])
            video_stream_label = "[0:v]"
            audio_stream_label = "[0:a]"

            # --- Xử lý Transform (Xoay/Lật & Thu phóng) ---
            transform_filters = []
            if params.get("rotate_enabled"):
                option = params["rotate_option"]
                log_messages.append(f"xoay/lật ({option})")
                filter_map = {
                    "Xoay 90° theo chiều kim đồng hồ": "transpose=1",
                    "Xoay 90° ngược chiều kim đồng hồ": "transpose=2",
                    "Lật video theo chiều ngang": "hflip",
                    "Lật video theo chiều dọc": "vflip"
                }
                transform_filters.append(filter_map[option])

            if params.get("scale_enabled"):
                factor = params["scale_factor"]
                log_messages.append(f"thu phóng ({factor}x)")
                transform_filters.append(f"crop=iw/{factor}:ih/{factor}")
            
            if transform_filters:
                # Nối các filter transform và gán nhãn tạm thời
                video_filters.append(f"{video_stream_label}{','.join(transform_filters)}[v_transformed]")
                video_stream_label = "[v_transformed]" # Cập nhật nhãn cho bước tiếp theo

            # --- Xử lý Watermark (Chèn Logo) ---
            if params.get("watermark_enabled"):
                logo_path = params["logo_path"]
                pos = params["watermark_pos"]
                pad = params["watermark_pad"]
                log_messages.append("chèn logo")

                # Input 1: Logo
                input_files.extend(["-i", logo_path])
                pos_map = {
                    "Trên-Trái": f"overlay={pad}:{pad}", "Trên-Phải": f"overlay=W-w-{pad}:{pad}",
                    "Dưới-Trái": f"overlay={pad}:H-h-{pad}", "Dưới-Phải": f"overlay=W-w-{pad}:H-h-{pad}"
                }
                # Nối filter watermark và gán nhãn tạm thời
                video_filters.append(f"{video_stream_label}[1:v]{pos_map[pos]}[v_watermarked]")
                video_stream_label = "[v_watermarked]" # Cập nhật nhãn

            # --- Xử lý Audio (Ghép âm thanh mới) ---
            if params.get("audio_enabled"):
                audio_path = params["audio_path"]
                log_messages.append("ghép âm thanh mới")
                
                # Input tiếp theo: Audio
                input_files.extend(["-i", audio_path])
                audio_input_index = len(input_files) // 2 - 1 # Tìm chỉ số của input audio
                audio_stream_label = f"[{audio_input_index}:a]"

            # --- Finalize và chạy FFmpeg ---
            final_args = list(input_files)
            if video_filters:
                final_args.extend(["-filter_complex", ";".join(video_filters)])
            
            # Map video và audio cuối cùng
            map_args.extend(["-map", video_stream_label, "-map", audio_stream_label])
            final_args.extend(map_args)
            
            # Thêm codec và flag -shortest để đảm bảo video kết thúc cùng âm thanh
            final_args.extend(["-c:v", "libx264", "-c:a", "aac", "-shortest"])

            log_string = " và ".join(log_messages) if log_messages else "xử lý"
            self.gui.log_status(f"Bắt đầu {log_string}...")
            
            run_ffmpeg(None, output_file, final_args, use_input_path_as_first_arg=False)
            
            self.gui.log_status(f"Xử lý video thành công -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi xử lý video: {e}", exc_info=True)
            self.gui.log_status(f"LỖI: {e}", "error")
        finally:
            self.task_finished("xử lý video")