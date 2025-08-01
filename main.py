import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import requests
from packaging.version import parse as parse_version
import hashlib
import tempfile
import subprocess
import pefile

from Utils.logger_setup import LoggerProvider
from Utils.ffmpeg_utils import setup_ffmpeg
from Utils.config import MAX_ACTIVE_USERS
from Recording.app_controller import AppController
from Recording.settings_window import SettingsWindow
from Down_Chanel.down_gui import TikTokDownloaderGUI
from Convert.convert_gui import ConvertGUI
from CutMerge.cut_merge_gui import CutMergeGUI
from AudioTools.audio_tools_gui import AudioToolsGUI
from VideoTools.video_tools_gui import VideoToolsGUI

class MainApplication:
    def __init__(self, root):
        self.root = root
        if hasattr(sys, '_MEIPASS'):
            self.asset_path = sys._MEIPASS
            self.app_path = os.path.dirname(sys.executable)
        else:
            self.asset_path = os.path.abspath(os.path.dirname(__file__))
            self.app_path = self.asset_path
        
        self.setup_window()
        self.main_logger = LoggerProvider.get_logger('main', self.app_path)
        self.main_logger.info(f"Đường dẫn ứng dụng: {self.app_path}")

        self.thread_pool = ThreadPoolExecutor(max_workers=MAX_ACTIVE_USERS + 10)
        try:
            setup_ffmpeg(self.asset_path)
        except (FileNotFoundError, PermissionError) as e:
            self.main_logger.critical(f"Lỗi khởi tạo FFmpeg: {e}")
            messagebox.showerror("Lỗi nghiêm trọng", f"Không thể tìm thấy hoặc sử dụng FFmpeg.\nChi tiết: {e}", parent=self.root)
            self.root.destroy()
            return

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")
        
        # Khởi tạo các tab
        self.recording_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.recording_tab_frame, text="Recording")
        self.recording_controller = AppController(self.recording_tab_frame, self.app_path, self.thread_pool)
        
        self.download_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.download_tab_frame, text="Download")
        self.downloader_gui = TikTokDownloaderGUI(self.download_tab_frame, self.app_path)

        self.convert_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.convert_tab_frame, text="Convert")
        self.convert_gui = ConvertGUI(self.convert_tab_frame, self.app_path, self.thread_pool)

        self.cut_merge_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cut_merge_tab_frame, text="Cut & Merge")
        self.cut_merge_gui = CutMergeGUI(self.cut_merge_tab_frame, self.app_path, self.thread_pool)

        self.audio_tools_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.audio_tools_tab_frame, text="Audio Tools")
        self.audio_tools_gui = AudioToolsGUI(self.audio_tools_tab_frame, self.app_path, self.thread_pool)

        self.video_tools_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.video_tools_tab_frame, text="Video Tools")
        self.video_tools_gui = VideoToolsGUI(self.video_tools_tab_frame, self.app_path, self.thread_pool)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Tự động kiểm tra cập nhật khi khởi động
        self.root.after(1000, lambda: self.check_for_updates(silent=True))

    def setup_window(self):
        self.root.title("Media Tools v1.1.1 What The Heck")
        self.root.geometry("980x750")
        self.root.minsize(980, 750)
        self.root.resizable(False, False)
        
        try:
            icon_path = os.path.join(self.asset_path, 'icon.ico')
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path)
        except Exception as e:
            LoggerProvider.get_logger('main', self.app_path).warning(f"Không thể thiết lập icon: {e}")

        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        # THÊM MỚI
        file_menu.add_command(label="Cài đặt Cookies", command=self.open_recording_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About Recording", command=lambda: self.recording_controller.view.show_about())
        help_menu.add_separator()
        help_menu.add_command(label="Check for Updates", command=lambda: self.check_for_updates(silent=False))

    def open_recording_settings(self):
        """Mở cửa sổ cài đặt cho tab Recording."""
        if hasattr(self, 'recording_controller'):
            # Ủy quyền cho controller của tab Recording hiển thị cửa sổ
            self.recording_controller.show_settings()
        else:
            messagebox.showwarning("Lỗi", "Không thể mở cài đặt. Tab Recording chưa được khởi tạo.", parent=self.root)

    def get_current_version(self):
        if not hasattr(sys, '_MEIPASS'):
            return "0.0.0-dev"
        exe_path = sys.executable
        pe = None
        try:
            pe = pefile.PE(exe_path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
            if hasattr(pe, 'FileInfo') and len(pe.FileInfo) > 0:
                for file_info in pe.FileInfo[0]:
                    if hasattr(file_info, 'StringTable') and len(file_info.StringTable) > 0:
                        for st in file_info.StringTable:
                            entries = {k.decode(errors="ignore"): v.decode(errors="ignore") for k, v in st.entries.items()}
                            if "ProductVersion" in entries and entries["ProductVersion"].strip():
                                return entries["ProductVersion"].strip()
                            elif "FileVersion" in entries and entries["FileVersion"].strip():
                                return ".".join(entries["FileVersion"].strip().split('.')[:3])
            self.main_logger.warning("Không tìm thấy thông tin phiên bản trong metadata.")
            return "0.0.0"
        except Exception as e:
            self.main_logger.error(f"Lỗi khi đọc phiên bản từ .exe: {e}", exc_info=True)
            return "0.0.0"
        finally:
            if pe:
                pe.close()
    
    def _create_progress_window(self, title, message):
        """Tạo và hiển thị một cửa sổ chờ chung."""
        progress_win = tk.Toplevel(self.root)
        progress_win.title(title)
        progress_win.geometry("300x100")
        progress_win.resizable(False, False)
        # Đặt làm cửa sổ con và chặn tương tác với cửa sổ chính
        progress_win.transient(self.root)
        progress_win.grab_set()
        # Căn giữa so với cửa sổ cha
        x = self.root.winfo_x() + (self.root.winfo_width() / 2) - (300 / 2)
        y = self.root.winfo_y() + (self.root.winfo_height() / 2) - (100 / 2)
        progress_win.geometry(f"+{int(x)}+{int(y)}")
        
        ttk.Label(progress_win, text=message, padding=(10, 10)).pack()
        pb = ttk.Progressbar(progress_win, mode='indeterminate', length=280)
        pb.pack(pady=10)
        pb.start(10)
        
        return progress_win

    def check_for_updates(self, silent=False):
        """Kiểm tra cập nhật. Hiển thị cửa sổ chờ nếu không ở chế độ im lặng."""
        if silent:
            threading.Thread(target=self._do_check_updates, args=(True, None), daemon=True).start()
            return

        self.main_logger.info("Bắt đầu kiểm tra cập nhật thủ công...")
        progress_win = self._create_progress_window("Checking for Updates", "Contacting update server...")
        threading.Thread(target=self._do_check_updates, args=(False, progress_win), daemon=True).start()

    def _do_check_updates(self, silent=False, progress_win=None):
        try:
            if not hasattr(sys, '_MEIPASS'):
                if not silent:
                    messagebox.showinfo("Check for Updates", "Tính năng cập nhật chỉ hoạt động trên phiên bản đã build.", parent=self.root)
                return

            current_version_str = self.get_current_version()
            if "-dev" in current_version_str: return
                
            current_version = parse_version(current_version_str)
            
            base_url = "https://raw.githubusercontent.com/chill4share/Chill_Updater/main/latest.json"
            latest_info_url = f"{base_url}?_={int(time.time())}"
            
            response = requests.get(latest_info_url, timeout=15)
            response.raise_for_status()
            latest_info = response.json()
            
            latest_version = parse_version(latest_info.get("version"))

            if latest_version > current_version:
                notes_list = latest_info.get("notes", [])
                notes_formatted = "\n".join([f"  - {line}" for line in notes_list]) if notes_list else "Không có ghi chú."
                msg = f"Đã có phiên bản mới: {latest_version}\n\n" \
                        f"Ghi chú:\n{notes_formatted}\n\nBạn có muốn tải về và cài đặt không?"
                
                if messagebox.askyesno("Cập nhật có sẵn", msg, parent=self.root):
                    self.start_update_process(latest_info, str(latest_version))
            else:
                if not silent:
                    messagebox.showinfo("Kiểm tra cập nhật", f"Bạn đang sử dụng phiên bản mới nhất! (v{current_version})", parent=self.root)

        except requests.RequestException as e:
            if not silent:
                self.main_logger.error(f"Lỗi mạng khi kiểm tra cập nhật: {e}")
                messagebox.showerror("Lỗi", "Không thể kết nối đến server cập nhật.", parent=self.root)
        except Exception as e:
            if not silent:
                self.main_logger.error(f"Lỗi không xác định khi kiểm tra cập nhật: {e}", exc_info=True)
                messagebox.showerror("Lỗi", f"Đã xảy ra lỗi: {e}", parent=self.root)
        finally:
            if progress_win:
                progress_win.destroy()

    def start_update_process(self, latest_info, new_version_str):
        """Hiển thị cửa sổ chờ và bắt đầu tải updater trong luồng riêng."""
        progress_win = self._create_progress_window("Preparing Update", "Downloading updater components...")
        threading.Thread(
            target=self._threaded_start_update,
            args=(latest_info, new_version_str, progress_win),
            daemon=True
        ).start()

    def _threaded_start_update(self, latest_info, new_version_str, progress_win):
        """Tải updater và khởi chạy nó."""
        try:
            platform_info = latest_info["platforms"]["windows-x64"]
            new_app_url = platform_info["url"]
            updater_url = platform_info["updater_url"]
            expected_hash = platform_info["sha256"]
            
            temp_dir = tempfile.gettempdir()
            updater_path = os.path.join(temp_dir, "updater.exe")

            self.main_logger.info(f"Đang tải updater từ URL đã được che giấu")
            res_updater = requests.get(updater_url, stream=True)
            res_updater.raise_for_status()
            with open(updater_path, "wb") as f:
                f.write(res_updater.content)
            self.main_logger.info(f"Đã tải updater về đường dẫn tạm")

            current_app_path = sys.executable
            parent_pid = os.getpid()
            
            subprocess.Popen([updater_path, current_app_path, new_app_url, expected_hash, new_version_str, str(parent_pid)])
            
            # Lên lịch đóng ứng dụng chính trên luồng UI
            self.root.after(0, self.on_closing, True)

        except Exception as e:
            self.main_logger.critical(f"Lỗi nghiêm trọng trong quá trình cập nhật: {e}", exc_info=True)
            messagebox.showerror("Lỗi Cập nhật", f"Không thể hoàn tất quá trình cập nhật.\nChi tiết: {e}", parent=self.root)
        finally:
            # Luôn đóng cửa sổ chờ
            if progress_win:
                progress_win.destroy()

    def on_closing(self, force_close=False):
        if force_close or messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát?", parent=self.root):
            if hasattr(self, 'recording_controller'): self.recording_controller.on_closing()
            if hasattr(self, 'downloader_gui'): self.downloader_gui.on_closing()
            if hasattr(self, 'convert_gui'): self.convert_gui.controller.on_closing()
            if hasattr(self, 'cut_merge_gui'): self.cut_merge_gui.controller.on_closing()
            if hasattr(self, 'audio_tools_gui'): self.audio_tools_gui.controller.on_closing()
            if hasattr(self, 'video_tools_gui'): self.video_tools_gui.controller.on_closing()
            self.thread_pool.shutdown(wait=True, cancel_futures=True)
            if self.root.winfo_exists():
                self.root.destroy()
            self.main_logger.info("Ứng dụng đã đóng.")

def main():
    if hasattr(sys, '_MEIPASS'):
        app_path = os.path.dirname(sys.executable)
    else:
        app_path = os.path.abspath(os.path.dirname(__file__))
    
    root = None
    try:
        LoggerProvider.get_logger('main', app_path).info("--- Bắt đầu phiên làm việc mới ---")
        root = tk.Tk()
        app = MainApplication(root)
        root.mainloop()
    except Exception as e:
        main_logger = LoggerProvider.get_logger('main', app_path)
        main_logger.critical(f"Lỗi không mong muốn ở cấp cao nhất: {e}", exc_info=True)
        if root:
             messagebox.showerror(
                "Lỗi nghiêm trọng",
                f"Ứng dụng đã gặp lỗi không thể phục hồi và sẽ thoát.\n\nLỗi: {e}",
                parent=root
            )
        else:
             messagebox.showerror(
                "Lỗi nghiêm trọng",
                f"Ứng dụng đã gặp lỗi không thể phục hồi và sẽ thoát.\n\nLỗi: {e}"
            )

if __name__ == "__main__":
    main()
