# VideoTools/video_tools_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os

from .video_tools_controller import VideoToolsController
from Utils.ui_utils import create_tab_title

class VideoToolsGUI:
    def __init__(self, root_frame, project_root, thread_pool):
        self.root = root_frame
        self.controller = VideoToolsController(self, project_root, thread_pool)
        
        # Biến cho tab Watermark
        self.watermark_video_var = tk.StringVar()
        self.watermark_logo_var = tk.StringVar()
        self.watermark_pos_var = tk.StringVar(value="Dưới-Phải")
        self.watermark_pad_var = tk.StringVar(value="10")

        # Biến cho tab Phụ đề
        self.sub_video_var = tk.StringVar()
        self.sub_file_var = tk.StringVar()

        # Biến cho tab GIF
        self.gif_video_var = tk.StringVar()
        self.gif_start_var = tk.StringVar(value="0")
        self.gif_duration_var = tk.StringVar(value="3")
        self.gif_fps_var = tk.StringVar(value="15")
        self.gif_width_var = tk.StringVar(value="480")

        # Biến cho tab Resize
        self.resize_video_var = tk.StringVar()
        self.resize_ratio_var = tk.StringVar(value="9:16 (Dọc/Shorts)")
        self.resize_method_var = tk.StringVar(value="Cắt để vừa (Crop)")

        self.create_widgets()

    def create_widgets(self):
        create_tab_title(self.root, "Công cụ Xử lý Video")

        self.sub_notebook = ttk.Notebook(self.root)
        self.sub_notebook.pack(fill="both", expand=True, padx=10, pady=5)

        wm_frame = ttk.Frame(self.sub_notebook, padding=10)
        sub_frame = ttk.Frame(self.sub_notebook, padding=10)
        gif_frame = ttk.Frame(self.sub_notebook, padding=10)
        resize_frame = ttk.Frame(self.sub_notebook, padding=10)

        self.sub_notebook.add(wm_frame, text=" Chèn Logo (Watermark) ")
        self.sub_notebook.add(sub_frame, text=" Gắn Phụ đề (Hardsub) ")
        self.sub_notebook.add(gif_frame, text=" Tạo ảnh GIF ")
        self.sub_notebook.add(resize_frame, text=" Thay đổi kích thước ")

        self.create_watermark_tab(wm_frame)
        self.create_subtitle_tab(sub_frame)
        self.create_gif_tab(gif_frame)
        self.create_resize_tab(resize_frame)

        status_frame = ttk.LabelFrame(self.root, text="Nhật ký", padding=10)
        status_frame.pack(side="bottom", fill="both", expand=True, padx=10, pady=(0, 10))
        status_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=5, font=('Consolas', 9), wrap=tk.WORD, state="disabled")
        self.status_text.grid(row=0, column=0, sticky="nsew")

    def _create_file_input_frame(self, parent, text, var, command):
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=text, width=12).pack(side="left")
        ttk.Entry(frame, textvariable=var).pack(side="left", expand=True, fill="x")
        ttk.Button(frame, text="Duyệt...", command=command).pack(side="left", padx=(5,0))
        return frame

    def create_watermark_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        # Inputs
        video_input_frame = self._create_file_input_frame(parent, "File Video:", self.watermark_video_var, lambda: self.browse_file(self.watermark_video_var, "Chọn file video"))
        video_input_frame.pack(fill="x", pady=5)
        logo_input_frame = self._create_file_input_frame(parent, "File Logo:", self.watermark_logo_var, lambda: self.browse_file(self.watermark_logo_var, "Chọn file logo", [("PNG/Image", "*.png")]))
        logo_input_frame.pack(fill="x", pady=5)
        # Options
        options_frame = ttk.LabelFrame(parent, text="Tùy chọn", padding=10)
        options_frame.pack(fill="x", pady=10)
        ttk.Label(options_frame, text="Vị trí:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Combobox(options_frame, textvariable=self.watermark_pos_var, values=["Dưới-Phải", "Dưới-Trái", "Trên-Phải", "Trên-Trái"], state="readonly").grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(options_frame, text="Khoảng cách lề (px):").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Entry(options_frame, textvariable=self.watermark_pad_var, width=10).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        # Start button
        self.wm_btn = ttk.Button(parent, text="BẮT ĐẦU CHÈN LOGO", style="Accent.TButton", command=self.start_watermark_action)
        self.wm_btn.pack(pady=10)
        
    def create_subtitle_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        video_input_frame = self._create_file_input_frame(parent, "File Video:", self.sub_video_var, lambda: self.browse_file(self.sub_video_var, "Chọn file video"))
        video_input_frame.pack(fill="x", pady=5)
        sub_input_frame = self._create_file_input_frame(parent, "File Phụ đề:", self.sub_file_var, lambda: self.browse_file(self.sub_file_var, "Chọn file phụ đề", [("Subtitle Files", "*.srt *.ass")]))
        sub_input_frame.pack(fill="x", pady=5)
        self.sub_btn = ttk.Button(parent, text="BẮT ĐẦU GẮN PHỤ ĐỀ", style="Accent.TButton", command=self.start_subtitle_action)
        self.sub_btn.pack(pady=20)

    def create_gif_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        video_input_frame = self._create_file_input_frame(parent, "File Video:", self.gif_video_var, lambda: self.browse_file(self.gif_video_var, "Chọn file video"))
        video_input_frame.pack(fill="x", pady=5)
        options_frame = ttk.LabelFrame(parent, text="Tùy chọn", padding=10)
        options_frame.pack(fill="x", pady=10)
        ttk.Label(options_frame, text="Bắt đầu từ (giây):").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(options_frame, textvariable=self.gif_start_var, width=10).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(options_frame, text="Độ dài (giây):").grid(row=0, column=2, sticky="w", padx=10, pady=3)
        ttk.Entry(options_frame, textvariable=self.gif_duration_var, width=10).grid(row=0, column=3, sticky="w", padx=5)
        ttk.Label(options_frame, text="FPS (khung hình/s):").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(options_frame, textvariable=self.gif_fps_var, values=["10", "15", "20", "25"], state="readonly", width=7).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(options_frame, text="Chiều rộng (px):").grid(row=1, column=2, sticky="w", padx=10, pady=3)
        ttk.Entry(options_frame, textvariable=self.gif_width_var, width=10).grid(row=1, column=3, sticky="w", padx=5)
        self.gif_btn = ttk.Button(parent, text="BẮT ĐẦU TẠO GIF", style="Accent.TButton", command=self.start_gif_action)
        self.gif_btn.pack(pady=10)

    def create_resize_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        video_input_frame = self._create_file_input_frame(parent, "File Video:", self.resize_video_var, lambda: self.browse_file(self.resize_video_var, "Chọn file video"))
        video_input_frame.pack(fill="x", pady=5)
        options_frame = ttk.LabelFrame(parent, text="Tùy chọn", padding=10)
        options_frame.pack(fill="x", pady=10)
        ttk.Label(options_frame, text="Tỷ lệ khung hình đích:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Combobox(options_frame, textvariable=self.resize_ratio_var, values=["9:16 (Dọc/Shorts)", "1:1 (Vuông/Instagram)", "4:3 (Cũ)"], state="readonly").grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(options_frame, text="Phương pháp:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Combobox(options_frame, textvariable=self.resize_method_var, values=["Cắt để vừa (Crop)", "Thêm viền đen (Pad)"], state="readonly").grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        self.resize_btn = ttk.Button(parent, text="BẮT ĐẦU THAY ĐỔI KÍCH THƯỚC", style="Accent.TButton", command=self.start_resize_action)
        self.resize_btn.pack(pady=20)

    def browse_file(self, string_var, title, filetypes=None):
        path = filedialog.askopenfilename(title=title, filetypes=filetypes or [])
        if path:
            string_var.set(path)
            
    def start_watermark_action(self):
        self.controller.start_watermarking(
            self.watermark_video_var.get(),
            self.watermark_logo_var.get(),
            self.watermark_pos_var.get(),
            self.watermark_pad_var.get()
        )

    def start_subtitle_action(self):
        self.controller.start_hardsubbing(
            self.sub_video_var.get(),
            self.sub_file_var.get()
        )

    def start_gif_action(self):
        self.controller.start_gif_creation(
            self.gif_video_var.get(),
            self.gif_start_var.get(),
            self.gif_duration_var.get(),
            self.gif_fps_var.get(),
            self.gif_width_var.get()
        )
        
    def start_resize_action(self):
        # Lấy tỷ lệ dạng "9:16" từ chuỗi "9:16 (Dọc/Shorts)"
        ratio_str = self.resize_ratio_var.get().split(' ')[0]
        self.controller.start_resizing(
            self.resize_video_var.get(),
            self.resize_method_var.get(),
            ratio_str
        )

    def set_ui_state(self, state):
        is_processing = state == "processing"
        ui_state = "disabled" if is_processing else "normal"
        # Vô hiệu hóa tất cả các nút bắt đầu
        self.wm_btn.config(state=ui_state)
        self.sub_btn.config(state=ui_state)
        self.gif_btn.config(state=ui_state)
        self.resize_btn.config(state=ui_state)

    def log_status(self, message, level="info"):
        color_map = {"info": "black", "success": "green", "error": "red", "warning": "orange"}
        tag = level
        def _update():
            self.status_text.config(state="normal")
            self.status_text.tag_config(tag, foreground=color_map.get(level, "black"))
            self.status_text.insert(tk.END, f"> {message}\n", tag)
            self.status_text.see(tk.END)
            self.status_text.config(state="disabled")
        self.root.after(0, _update)

    def show_message(self, level, title, message):
        def _show():
            if level == "info": messagebox.showinfo(title, message)
            elif level == "warning": messagebox.showwarning(title, message)
            elif level == "error": messagebox.showerror(title, message)
        self.root.after(0, _show)

    def finalize_processing(self, operation_name):
        self.set_ui_state("idle")
        self.show_message("info", "Hoàn tất", f"Quá trình {operation_name} đã hoàn thành.")