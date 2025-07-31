# AudioTools/audio_tools_controller.py

import os
import threading
import subprocess
import json
import re
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE1, TIT2, TALB, TDRC, TCON
from PIL import Image

from Utils.logger_setup import LoggerProvider
from Utils.ffmpeg_utils import run_ffmpeg, stop_ffmpeg_processes

class AudioToolsController:
    def __init__(self, gui, project_root, thread_pool):
        self.gui = gui
        self.project_root = project_root
        self.thread_pool = thread_pool
        self.logger = LoggerProvider.get_logger('audio_tools')
        
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
    
    # --- LOGIC CHO CHUẨN HÓA ÂM LƯỢNG ---
    def start_normalization(self, file_list, target_lufs):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        self.gui.log_status(f"Bắt đầu quá trình chuẩn hóa âm lượng cho {len(file_list)} file...")
        
        with self.task_lock:
            self.active_tasks = len(file_list)
            
        for file_path in file_list:
            self.thread_pool.submit(self.run_normalization_task, file_path, target_lufs)
            
    def run_normalization_task(self, file_path, target_lufs):
        """Thực hiện chuẩn hóa 2-pass cho một file."""
        try:
            self.gui.log_status(f"Phân tích (Pass 1/2): {os.path.basename(file_path)}")
            # Pass 1: Phân tích và lấy thông số
            pass1_args = ["-af", f"loudnorm=I={target_lufs}:tp=-1.5:LRA=7:print_format=json", "-f", "null", "-"]
            _, stderr = run_ffmpeg(file_path, "", pass1_args, get_output=True)
            
            # Trích xuất dữ liệu JSON từ output của FFmpeg
            json_str = stderr[stderr.rfind('{'):stderr.rfind('}')+1]
            stats = json.loads(json_str)
            
            self.gui.log_status(f"Áp dụng (Pass 2/2): {os.path.basename(file_path)}")
            # Pass 2: Áp dụng các thông số đã đo
            pass2_filter = (
                f"loudnorm=I={target_lufs}:tp=-1.5:LRA=7:"
                f"measured_I={stats['input_i']}:"
                f"measured_LRA={stats['input_lra']}:"
                f"measured_tp={stats['input_tp']}:"
                f"measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}"
            )
            
            output_file = self.get_output_path(file_path, "_normalized")
            pass2_args = ["-af", pass2_filter, "-ar", "44100", "-b:a", "192k"]
            
            run_ffmpeg(file_path, output_file, pass2_args)
            self.gui.log_status(f"Chuẩn hóa thành công -> {os.path.basename(output_file)}", "success")

        except Exception as e:
            self.logger.error(f"Lỗi khi chuẩn hóa {os.path.basename(file_path)}: {e}", exc_info=True)
            self.gui.log_status(f"LỖI chuẩn hóa {os.path.basename(file_path)}: {e}", "error")
        finally:
            self.task_finished("chuẩn hóa âm lượng")

    # --- LOGIC CHO CHỈNH SỬA METADATA ---
    def load_metadata(self, file_path):
        try:
            audio = MP3(file_path, ID3=ID3)
            tags = {
                'title': audio.get('TIT2', [''])[0],
                'artist': audio.get('TPE1', [''])[0],
                'album': audio.get('TALB', [''])[0],
                'year': str(audio.get('TDRC', [''])[0]),
                'genre': str(audio.get('TCON', [''])[0]),
            }
            # Lấy ảnh bìa
            cover_data = None
            if 'APIC:' in audio:
                cover_data = audio['APIC:'].data
            return tags, cover_data
        except Exception as e:
            self.logger.error(f"Không thể đọc metadata từ {file_path}: {e}")
            return None, None

    def save_metadata(self, file_path, tags_to_save, new_cover_path):
        if not file_path: return
        try:
            self.gui.log_status("Bắt đầu lưu thông tin...")
            audio = MP3(file_path, ID3=ID3)
            # Add new tags
            audio['TIT2'] = TIT2(encoding=3, text=tags_to_save['title'])
            audio['TPE1'] = TPE1(encoding=3, text=tags_to_save['artist'])
            audio['TALB'] = TALB(encoding=3, text=tags_to_save['album'])
            audio['TDRC'] = TDRC(encoding=3, text=tags_to_save['year'])
            audio['TCON'] = TCON(encoding=3, text=tags_to_save['genre'])
            
            # Add cover art
            if new_cover_path:
                with open(new_cover_path, 'rb') as art:
                    audio['APIC'] = APIC(
                        encoding=3, # 3 is for utf-8
                        mime='image/jpeg', # or image/png
                        type=3, # 3 is for the cover (front)
                        desc='Cover',
                        data=art.read()
                    )
            audio.save()
            self.gui.log_status("Lưu thông tin thành công!", "success")
            self.gui.show_message("info", "Thành công", "Đã cập nhật thông tin cho file.")
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu metadata: {e}", exc_info=True)
            self.gui.show_message("error", "Lỗi", f"Không thể lưu thông tin: {e}")


    # --- LOGIC CHO GIẢM TẠP ÂM ---
    def start_noise_reduction(self, file_list, strength):
        if self.is_processing: return
        self.is_processing = True
        self.gui.set_ui_state("processing")
        self.gui.log_status(f"Bắt đầu giảm tạp âm cho {len(file_list)} file...")
        
        with self.task_lock:
            self.active_tasks = len(file_list)
        
        for file_path in file_list:
            self.thread_pool.submit(self.run_noise_reduction_task, file_path, strength)

    def run_noise_reduction_task(self, file_path, strength):
        """Áp dụng bộ lọc anlmdn của FFmpeg."""
        try:
            self.gui.log_status(f"Đang xử lý: {os.path.basename(file_path)}")
            output_file = self.get_output_path(file_path, "_denoised")
            args = ["-af", f"anlmdn=s={strength}"]
            
            run_ffmpeg(file_path, output_file, args)
            self.gui.log_status(f"Giảm tạp âm thành công -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi giảm tạp âm {os.path.basename(file_path)}: {e}", exc_info=True)
            self.gui.log_status(f"LỖI giảm tạp âm {os.path.basename(file_path)}: {e}", "error")
        finally:
            self.task_finished("giảm tạp âm")
            
    def get_output_path(self, input_path, suffix):
        """Tạo đường dẫn file output với hậu tố."""
        dir_name = os.path.dirname(input_path)
        base_name, ext = os.path.splitext(os.path.basename(input_path))
        return os.path.join(dir_name, f"{base_name}{suffix}{ext}")
