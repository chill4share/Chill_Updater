# Convert/convert_controller.py

import os
import threading

from Utils.logger_setup import LoggerProvider
from Utils.ffmpeg_utils import run_ffmpeg, stop_ffmpeg_processes

# Hằng số cho các đuôi file video
VIDEO_EXTENSIONS = {'.mp4', '.flv', '.mkv', '.mov', '.avi', '.wmv'}

class ConvertController:
    def __init__(self, gui, project_root, thread_pool, options_map):
        self.gui = gui
        self.project_root = project_root
        self.thread_pool = thread_pool
        self.logger = LoggerProvider.get_logger('convert')
        
        self.options = options_map
        
        self.active_ffmpeg_pids = []
        self.is_converting = False
        
        self.task_lock = threading.Lock()
        self.active_tasks = 0

    def on_closing(self):
        if self.active_ffmpeg_pids:
            self.logger.warning(f"Đang dừng {len(self.active_ffmpeg_pids)} tiến trình FFmpeg đang chạy...")
            stop_ffmpeg_processes(self.active_ffmpeg_pids)
            self.logger.info("Đã dừng các tiến trình FFmpeg.")

    def _add_channel_args(self, channel_display_value, args_list):
        """Thêm tham số kênh audio vào danh sách args nếu cần."""
        channel_value = self.options["channels"].get(channel_display_value)
        if channel_value not in [None, "keep"]:
            args_list.extend(["-ac", channel_value])
            
    def build_ffmpeg_args(self, input_file, output_ext):
        args = []
        
        # Xử lý hiệu ứng Tốc độ và Cao độ
        speed = self.gui.speed_var.get()
        pitch_semitones = self.gui.pitch_var.get()
        audio_filters = []
        
        if speed != 1.0:
            audio_filters.append(f"atempo={speed}")
            
        # --- SỬA LỖI TẠI ĐÂY ---
        # Chỉ kích hoạt bộ lọc pitch khi giá trị đủ lớn, tránh sai số float
        if abs(pitch_semitones) > 0.01:
            pitch_multiplier = pow(2, pitch_semitones / 12.0)
            original_rate = 44100
            new_rate = int(original_rate * pitch_multiplier)
            audio_filters.append(f"asetrate={new_rate},aresample={original_rate}")
            
        if audio_filters:
            args.extend(["-af", ",".join(audio_filters)])
            
        # Lấy giá trị từ dict
        if output_ext == 'mp3':
            rate_display = self.gui.mp3_sample_rate_var.get()
            bitrate_display = self.gui.mp3_bitrate_var.get()
            channel_display = self.gui.mp3_channels_var.get()

            sample_rate = self.options["sample_rates"].get(rate_display)
            bitrate = self.options["mp3_bitrates"].get(bitrate_display)
            
            args.extend(["-ar", sample_rate, "-ab", bitrate])
            self._add_channel_args(channel_display, args)
            
        elif output_ext == 'wav':
            rate_display = self.gui.wav_sample_rate_var.get()
            depth_display = self.gui.wav_bit_depth_var.get()
            channel_display = self.gui.wav_channels_var.get()
            
            sample_rate = self.options["sample_rates"].get(rate_display)
            bit_depth_codec = self.options["wav_bit_depths"].get(depth_display)

            args.extend(["-ar", sample_rate, "-acodec", bit_depth_codec])
            self._add_channel_args(channel_display, args)
            
        return args

    def start_conversion(self):
        if self.is_converting:
            self.gui.show_message("warning", "Đang xử lý", "Một tác vụ chuyển đổi đang chạy, vui lòng chờ.")
            return

        input_file = self.gui.input_path_var.get()
        output_dir = self.gui.output_path_var.get()

        if not input_file or not os.path.exists(input_file):
            self.gui.show_message("error", "Lỗi", "Vui lòng chọn file đầu vào hợp lệ.")
            return

        if not output_dir or not os.path.isdir(output_dir):
            output_dir = os.path.join(self.project_root, "Convert_Output")
            os.makedirs(output_dir, exist_ok=True)
            self.gui.output_path_var.set(output_dir)

        targets = []
        if self.gui.to_mp3_var.get(): targets.append("mp3")
        if self.gui.to_wav_var.get(): targets.append("wav")
        
        if not targets:
            self.gui.show_message("error", "Lỗi", "Vui lòng chọn ít nhất một định dạng đầu ra.")
            return
            
        self.is_converting = True
        self.gui.set_ui_state("converting")
        self.gui.log_status(f"Bắt đầu chuyển đổi file: {os.path.basename(input_file)}")
        
        with self.task_lock:
            self.active_tasks = len(targets)

        for ext in targets:
            self.thread_pool.submit(self.run_conversion_task, input_file, output_dir, ext)

    def run_conversion_task(self, input_file, output_dir, output_ext):
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}.{output_ext}")
        
        try:
            self.gui.log_status(f"Đang chuẩn bị chuyển đổi sang {output_ext.upper()}...")
            args = self.build_ffmpeg_args(input_file, output_ext)
            
            input_ext = os.path.splitext(input_file)[1].lower()
            if input_ext in VIDEO_EXTENSIONS:
                args.insert(0, "-vn")
            
            self.gui.log_status(f"Lệnh FFmpeg cho {output_ext.upper()}: ffmpeg -i ... {' '.join(args)} ...")
            
            pid = run_ffmpeg(input_file, output_file, args)
            self.active_ffmpeg_pids.append(pid)
            self.active_ffmpeg_pids.remove(pid) 
            
            self.gui.log_status(f"CHUYỂN ĐỔI THÀNH CÔNG -> {os.path.basename(output_file)}", "success")

        except Exception as e:
            self.logger.error(f"Lỗi khi chuyển đổi sang {output_ext.upper()}: {e}", exc_info=True)
            self.gui.log_status(f"LỖI khi chuyển đổi sang {output_ext.upper()}: {e}", "error")
        finally:
            self.task_finished()

    def task_finished(self):
        with self.task_lock:
            self.active_tasks -= 1
            if self.active_tasks == 0:
                self.gui.root.after(100, self.finalize_processing)

    def finalize_processing(self):
        self.is_converting = False
        self.gui.set_ui_state("idle")
        self.gui.show_message("info", "Hoàn tất", "Tất cả các tác vụ chuyển đổi đã hoàn thành.")
