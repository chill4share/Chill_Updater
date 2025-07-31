# CutMerge/cut_merge_controller.py

import os
import threading
import subprocess
import time
from datetime import datetime
import psutil
import pygame

from Utils.logger_setup import LoggerProvider
from Utils.ffmpeg_utils import run_ffmpeg, stop_ffmpeg_processes, get_media_duration

class CutMergeController:
    def __init__(self, gui, project_root, thread_pool):
        self.gui = gui
        self.project_root = project_root
        self.thread_pool = thread_pool
        self.logger = LoggerProvider.get_logger('cut_merge')
        
        self.active_ffmpeg_pids = []
        self.is_processing = False
        self.cut_list = []
        self.merge_list = []
        
        self.task_lock = threading.Lock()
        self.active_tasks = 0

        pygame.mixer.init()
        self.audio_duration = 0
        self.is_playing = False
        self.is_paused = False
        
        self.playback_start_offset = 0 # <-- THÊM MỚI
        self.playback_monitor_thread = None
        self.stop_playback_monitor = threading.Event()

    # --- THÊM MỚI: CÁC HÀM ĐIỀU KHIỂN AUDIO ---

    def load_audio_for_preview(self, file_path):
        """Tải file audio, lấy thông tin và cập nhật GUI."""
        self.logger.info(f"Đang tải file nghe thử: {file_path}")
        if pygame.mixer.music.get_busy():
            self.stop_audio()

        duration = get_media_duration(file_path)
        if duration is None:
            self.gui.show_message("error", "Lỗi", "Không thể đọc thông tin file. File có thể bị lỗi hoặc không được hỗ trợ.")
            self.gui.toggle_player_visibility(False)
            return

        self.audio_duration = duration
        
        self.is_paused = False
        self.is_playing = False
        self.playback_start_offset = 0 # <-- THÊM MỚI: Reset offset
        
        try:
            pygame.mixer.music.load(file_path)
            self.gui.update_player_ui(self.audio_duration)
            self.gui.toggle_player_visibility(True)
            self.logger.info("Tải file nghe thử thành công.")
        except pygame.error as e:
            self.logger.error(f"Lỗi Pygame khi tải file: {e}")
            self.gui.show_message("error", "Lỗi Pygame", f"Không thể tải file audio:\n{e}")
            self.gui.toggle_player_visibility(False)

    def play_pause_audio(self):
        """
        Phát, tạm dừng, hoặc tiếp tục phát audio với logic được làm rõ.
        - Luôn tiếp tục từ vị trí đã tạm dừng.
        - Luôn bắt đầu phát mới từ vị trí của thanh Start.
        """
        # 1. Nếu đang chạy -> Tạm dừng
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            pygame.mixer.music.pause()
            
            paused_time_ms = pygame.mixer.music.get_pos()
            if paused_time_ms != -1:
                current_pause_sec = self.playback_start_offset + (paused_time_ms / 1000.0)
                self.gui.update_end_marker_position(current_pause_sec)

        # 2. Nếu đang tạm dừng -> Tiếp tục phát
        elif self.is_paused:
            self.is_playing = True
            self.is_paused = False
            pygame.mixer.music.unpause()

        # 3. Nếu đang dừng hẳn -> Bắt đầu phát mới từ vị trí của thanh Start
        else:
            self.is_playing = True
            self.is_paused = False
            
            # Lấy vị trí bắt đầu từ chính GUI
            start_from_seconds = self.gui.timeline.start_val
            self.playback_start_offset = start_from_seconds
            
            pygame.mixer.music.play(start=start_from_seconds)
            self.gui.update_timeline_indicator(start_from_seconds) # Cập nhật vạch đỏ ngay
            
            if self.playback_monitor_thread is None or not self.playback_monitor_thread.is_alive():
                self.stop_playback_monitor.clear()
                self.playback_monitor_thread = threading.Thread(target=self._monitor_playback, daemon=True)
                self.playback_monitor_thread.start()
        
        self.gui.update_play_button_state(self.is_playing)

    def stop_audio(self):
        """Dừng hẳn việc phát audio và reset trạng thái."""
        self.is_playing = False
        self.is_paused = False
         
        self.playback_start_offset = 0 # <-- THÊM MỚI: Reset offset
        pygame.mixer.music.stop()
        self.stop_playback_monitor.set() 
        self.gui.update_play_button_state(False)
        self.gui.update_timeline_indicator(0)
        self.gui.update_marker_positions(0, self.audio_duration)

    def seek_audio(self, time_seconds):
        """Tua audio đến một vị trí nhất định và bắt đầu phát."""
        self.is_playing = True
        self.is_paused = False
        self.playback_start_offset = time_seconds # <-- SỬA ĐỔI: Set offset
        pygame.mixer.music.play(start=time_seconds)
        self.gui.update_play_button_state(True)
        self.gui.update_timeline_indicator(time_seconds) # Cập nhật vạch đỏ ngay lập tức
        if self.playback_monitor_thread is None or not self.playback_monitor_thread.is_alive():
            self.stop_playback_monitor.clear()
            self.playback_monitor_thread = threading.Thread(target=self._monitor_playback, daemon=True)
            self.playback_monitor_thread.start()

    def seek_and_pause(self, time_seconds):
        """Tua audio đến một vị trí nhất định và tạm dừng ngay lập tức."""
        self.is_playing = False
        self.is_paused = True
        self.playback_start_offset = time_seconds # <-- SỬA ĐỔI: Set offset
        pygame.mixer.music.play(start=time_seconds)
        pygame.mixer.music.pause()
        self.gui.update_play_button_state(False)
        self.gui.update_timeline_indicator(time_seconds)

    def _monitor_playback(self):
        """Luồng nền để liên tục cập nhật vị trí con trỏ trên GUI."""
        while pygame.mixer.music.get_busy() and not self.stop_playback_monitor.is_set():
            current_pos_ms = pygame.mixer.music.get_pos()
            if current_pos_ms == -1: break
            
            # --- SỬA ĐỔI: Tính toán thời gian thực tế dựa trên offset ---
            real_current_pos_sec = self.playback_start_offset + (current_pos_ms / 1000.0)
            
            # Đảm bảo không vượt quá tổng thời lượng do sai số
            real_current_pos_sec = min(real_current_pos_sec, self.audio_duration)

            self.gui.update_timeline_indicator(real_current_pos_sec)
            time.sleep(0.1)
        
        # Khi nhạc kết thúc tự nhiên
        if self.is_playing:
             self.gui.update_timeline_indicator(self.audio_duration)
        self.is_playing = False
        self.is_paused = False
        self.gui.update_play_button_state(False)

    def on_closing(self):
        """Dọn dẹp khi đóng chương trình."""
        self.logger.info("Bắt đầu dọn dẹp cho tab Cắt & Ghép...")
        # Dừng các tiến trình ffmpeg
        if self.active_ffmpeg_pids:
            self.logger.warning(f"Đang dừng {len(self.active_ffmpeg_pids)} tiến trình FFmpeg đang chạy...")
            stop_ffmpeg_processes(self.active_ffmpeg_pids)
            self.logger.info("Đã dừng các tiến trình FFmpeg.")
        # --- THÊM MỚI: Dọn dẹp Pygame ---
        pygame.mixer.quit()
        self.logger.info("Đã đóng pygame mixer.")
    
    # --- CÁC HÀM CHO VIỆC CẮT FILE ---
    def add_cut_segment(self, start_time, end_time):
        """Thêm một đoạn cắt vào danh sách."""
        self.cut_list.append((start_time, end_time))
        self.gui.update_cut_listbox(self.cut_list)
        self.logger.info(f"Đã thêm đoạn cắt: {start_time} -> {end_time}")

    def remove_cut_segment(self, selected_indices):
        """Xóa các đoạn cắt đã chọn khỏi danh sách."""
        for i in sorted(selected_indices, reverse=True):
            del self.cut_list[i]
        self.gui.update_cut_listbox(self.cut_list)

    def start_cutting(self):
        """Bắt đầu quá trình cắt file theo danh sách."""
        if self.is_processing: return
        input_file = self.gui.cut_input_var.get()
        if not input_file or not os.path.exists(input_file):
            self.gui.show_message("error", "Lỗi", "Vui lòng chọn file đầu vào.")
            return
        if not self.cut_list:
            self.gui.show_message("error", "Lỗi", "Vui lòng thêm ít nhất một đoạn cắt.")
            return

        self.is_processing = True
        self.gui.set_ui_state("processing")
        
        session_folder_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Split"
        output_session_dir = os.path.join(self.project_root, "Mer_Split_Output", session_folder_name)
        os.makedirs(output_session_dir, exist_ok=True)
        self.gui.log_status(f"Các file sẽ được lưu tại: {output_session_dir}")

        # --- THAY ĐỔI: Sử dụng bộ đếm tác vụ ---
        with self.task_lock:
            self.active_tasks = len(self.cut_list)
        
        for i, (start, end) in enumerate(self.cut_list, 1):
            self.thread_pool.submit(self.run_cut_task, i, input_file, start, end, output_session_dir)
        
        # --- XÓA: Lời gọi hàm không tồn tại ---
        # self.thread_pool.submit(self.wait_for_all_tasks_to_finish)

    def run_cut_task(self, index, input_file, start_time, end_time, output_dir):
        """Chạy một tác vụ cắt trong luồng nền."""
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        ext = os.path.splitext(input_file)[1]
        output_file = os.path.join(output_dir, f"{base_name}_part{index}{ext}")
        
        try:
            self.gui.log_status(f"Bắt đầu cắt đoạn {index} ({start_time} -> {end_time})...")
            args = ["-ss", start_time, "-to", end_time, "-c", "copy"]
            pid = run_ffmpeg(input_file, output_file, args)
            self.active_ffmpeg_pids.append(pid)
            self.active_ffmpeg_pids.remove(pid)
            self.gui.log_status(f"Cắt thành công đoạn {index} -> {os.path.basename(output_file)}", "success")
        except Exception as e:
            self.logger.error(f"Lỗi khi cắt đoạn {index}: {e}", exc_info=True)
            self.gui.log_status(f"LỖI khi cắt đoạn {index}: {e}", "error")
        finally:
            # --- THÊM MỚI: Báo cáo tác vụ hoàn thành ---
            self.task_finished("cắt")
            
    # --- THÊM MỚI: Hàm xử lý khi một tác vụ hoàn tất ---
    def task_finished(self, operation_name):
        """Giảm bộ đếm và kiểm tra nếu tất cả tác vụ đã xong."""
        with self.task_lock:
            self.active_tasks -= 1
            if self.active_tasks == 0:
                self.is_processing = False
                # Dùng after để đảm bảo hàm này chạy trên luồng chính của UI
                self.gui.root.after(100, self.finalize_processing, operation_name)

    def finalize_processing(self, operation_name):
        """Reset giao diện và trạng thái controller sau khi tất cả tác vụ đã hoàn thành."""
        # --- THÊM MỚI: Reset lại trạng thái của controller ---
        self.is_processing = False
        
        self.gui.set_ui_state("idle")
        self.gui.show_message("info", "Hoàn tất", f"Quá trình {operation_name} đã hoàn thành.")

    # --- CÁC HÀM CHO VIỆC GHÉP FILE ---
    def add_merge_files(self, file_paths):
        self.merge_list.extend(file_paths)
        self.gui.update_merge_listbox(self.merge_list)
        self.logger.info(f"Đã thêm {len(file_paths)} file vào danh sách ghép.")

    def remove_merge_files(self, selected_indices):
        for i in sorted(selected_indices, reverse=True):
            del self.merge_list[i]
        self.gui.update_merge_listbox(self.merge_list)
    
    def move_merge_file(self, selected_indices, direction):
        if not selected_indices: return
        idx = selected_indices[0]
        if direction == "up" and idx > 0:
            self.merge_list[idx], self.merge_list[idx-1] = self.merge_list[idx-1], self.merge_list[idx]
            self.gui.update_merge_listbox(self.merge_list, new_selection_index=idx-1)
        elif direction == "down" and idx < len(self.merge_list) - 1:
            self.merge_list[idx], self.merge_list[idx+1] = self.merge_list[idx+1], self.merge_list[idx]
            self.gui.update_merge_listbox(self.merge_list, new_selection_index=idx+1)

    def start_merging(self):
        if self.is_processing: return
        if len(self.merge_list) < 2:
            self.gui.show_message("error", "Lỗi", "Vui lòng thêm ít nhất hai file để ghép.")
            return

        video_files = []
        audio_files = []
        video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv'}
        audio_exts = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}

        for f in self.merge_list:
            ext = os.path.splitext(f)[1].lower()
            if ext in video_exts: video_files.append(f)
            elif ext in audio_exts: audio_files.append(f)
        
        if video_files and audio_files:
            choice = self.gui.show_mixed_types_dialog(video_exts, audio_exts)
            
            if choice == "keep_video":
                self.logger.info("Người dùng chọn chỉ giữ lại file video.")
                self.merge_list = video_files
                self.gui.update_merge_listbox(self.merge_list)
                # --- THAY ĐỔI: Gọi lại hàm start_merging để tiếp tục ---
                self.gui.root.after(100, self.start_merging)
                return
            elif choice == "keep_audio":
                self.logger.info("Người dùng chọn chỉ giữ lại file audio.")
                self.merge_list = audio_files
                self.gui.update_merge_listbox(self.merge_list)
                # --- THAY ĐỔI: Gọi lại hàm start_merging để tiếp tục ---
                self.gui.root.after(100, self.start_merging)
                return
            else:
                self.logger.info("Người dùng đã hủy thao tác ghép.")
                return
        
        self.is_processing = True
        self.gui.set_ui_state("processing")
        
        session_folder_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Merge"
        output_session_dir = os.path.join(self.project_root, "Mer_Split_Output", session_folder_name)
        os.makedirs(output_session_dir, exist_ok=True)
        self.gui.log_status(f"File ghép sẽ được lưu tại: {output_session_dir}")

        with self.task_lock:
            self.active_tasks = 1
        
        merge_mode = self.gui.merge_mode_var.get()
        self.thread_pool.submit(self.run_merge_task, self.merge_list.copy(), merge_mode, output_session_dir)

    def run_merge_task(self, file_list, mode, output_dir):
        ext = os.path.splitext(file_list[0])[1].lower() # Lấy đuôi file và chuyển thành chữ thường
        output_file = os.path.join(output_dir, f"merged_output{ext}")
        
        try:
            if mode == "fast":
                self.gui.log_status("Bắt đầu ghép nhanh (yêu cầu file cùng thông số)...")
                list_file_path = os.path.join(output_dir, "mylist.txt")
                with open(list_file_path, 'w', encoding='utf-8') as f:
                    for file_path in file_list:
                        escaped_path = file_path.replace("'", "'\\''")
                        f.write(f"file '{escaped_path}'\n")
                
                args = ["-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy"]
                pid = run_ffmpeg("", output_file, args)
                self.active_ffmpeg_pids.append(pid)
                self.active_ffmpeg_pids.remove(pid)
                os.remove(list_file_path)

            elif mode == "slow":
                self.gui.log_status("Bắt đầu ghép tương thích (chậm, mã hóa lại)...")
                inputs = []
                for file_path in file_list:
                    inputs.extend(["-i", file_path])
                
                filter_complex_parts = []
                # Kiểm tra xem có luồng video nào không để quyết định loại filter
                has_video = any(os.path.splitext(f)[1].lower() in ['.mp4', '.mkv', '.avi', '.mov'] for f in file_list)
                
                if has_video:
                    # Ghép cả video và audio
                    for i in range(len(file_list)):
                        # Sử dụng stream video và audio đầu tiên của mỗi file, bỏ qua nếu không có
                        filter_complex_parts.append(f"[{i}:v:0]?")
                        filter_complex_parts.append(f"[{i}:a:0]?")
                    filter_complex = "".join(filter_complex_parts) + f"concat=n={len(file_list)}:v=1:a=1[v][a]"
                    map_args = ["-map", "[v]", "-map", "[a]"]
                else:
                    # Chỉ ghép audio
                    for i in range(len(file_list)):
                        filter_complex_parts.append(f"[{i}:a:0]")
                    filter_complex = "".join(filter_complex_parts) + f"concat=n={len(file_list)}:v=0:a=1[a]"
                    map_args = ["-map", "[a]"]

                args = inputs + ["-filter_complex", filter_complex] + map_args
                
                # --- THÊM MỚI: Chỉ định codec cho file đầu ra ---
                if ext == '.wav':
                    args.extend(['-acodec', 'pcm_s16le']) # Codec chuẩn cho WAV 16-bit
                elif ext == '.mp3':
                    args.extend(['-acodec', 'libmp3lame']) # Codec chuẩn cho MP3
                elif ext == '.mp4':
                    args.extend(['-vcodec', 'libx264', '-acodec', 'aac']) # Codec video và audio phổ biến cho MP4
                
                pid = run_ffmpeg("", output_file, args)
                self.active_ffmpeg_pids.append(pid)
                self.active_ffmpeg_pids.remove(pid)

            self.gui.log_status(f"GHÉP THÀNH CÔNG -> {os.path.basename(output_file)}", "success")
        
        except Exception as e:
            self.logger.error(f"Lỗi khi ghép file: {e}", exc_info=True)
            self.gui.log_status(f"LỖI khi ghép file: {e}", "error")
        finally:
            self.task_finished("ghép")
