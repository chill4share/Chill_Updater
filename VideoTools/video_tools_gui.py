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
        self.widgets_to_disable = []

        # --- Biến cho tất cả các tính năng ---
        self.video_path_var = tk.StringVar()
        
        # Biến Transform
        self.rotate_enabled_var = tk.BooleanVar(value=False)
        self.rotate_option_var = tk.StringVar(value="Xoay 90° theo chiều kim đồng hồ")
        self.scale_enabled_var = tk.BooleanVar(value=False)
        self.scale_factor_var = tk.StringVar(value="1.5")
        
        # Biến Watermark
        self.watermark_enabled_var = tk.BooleanVar(value=False)
        self.watermark_logo_var = tk.StringVar()
        self.watermark_pos_var = tk.StringVar(value="Dưới-Phải")
        self.watermark_pad_var = tk.StringVar(value="10")

        # Biến Audio
        self.audio_enabled_var = tk.BooleanVar(value=False)
        self.audio_path_var = tk.StringVar()
        
        self.create_widgets()

    def create_widgets(self):
        create_tab_title(self.root, "Công cụ Xử lý Video Tổng hợp")

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)

        # --- 1. Input Video chính ---
        video_input_frame = self._create_file_input_frame(main_frame, "File Video:", self.video_path_var, "Chọn file video")
        video_input_frame.pack(fill="x", pady=(5, 15))
        self.widgets_to_disable.extend(video_input_frame.winfo_children())

        # --- 2. Khung Biến đổi ---
        self.create_transform_frame(main_frame)

        # --- 3. Khung Chèn Logo ---
        self.create_watermark_frame(main_frame)

        # --- 4. Khung Ghép Âm thanh ---
        self.create_audio_frame(main_frame)

        # --- 5. Nút Bắt đầu ---
        self.process_btn = ttk.Button(main_frame, text="BẮT ĐẦU XỬ LÝ", style="Accent.TButton", command=self.start_processing_action)
        self.process_btn.pack(pady=20, ipady=5)
        self.widgets_to_disable.append(self.process_btn)

        # --- 6. Khung Nhật ký ---
        status_frame = ttk.LabelFrame(main_frame, text="Nhật ký", padding=10)
        status_frame.pack(side="bottom", fill="both", expand=True, padx=0, pady=(10, 0))
        status_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=6, font=('Consolas', 9), wrap=tk.WORD, state="disabled")
        self.status_text.grid(row=0, column=0, sticky="nsew")

        # Cập nhật trạng thái ban đầu của các widget
        self.toggle_all_options()
        
    def _create_file_input_frame(self, parent, text, var, title, filetypes=None):
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=text, width=12).pack(side="left")
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side="left", expand=True, fill="x")
        button = ttk.Button(frame, text="Duyệt...", command=lambda: self.browse_file(var, title, filetypes))
        button.pack(side="left", padx=(5, 0))
        return frame
        
    def create_transform_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="1. Biến đổi (Xoay/Lật & Thu phóng)", padding=10)
        frame.pack(fill="x", pady=5)
        check = ttk.Checkbutton(frame, text="Bật Xoay/Lật", variable=self.rotate_enabled_var, command=self.toggle_all_options)
        check.grid(row=0, column=0, sticky="w", padx=5)
        self.widgets_to_disable.append(check)
        
        opts = ["Xoay 90°...", "Xoay 90° ngược...", "Lật ngang", "Lật dọc"]
        self.rotate_combo = ttk.Combobox(frame, textvariable=self.rotate_option_var, values=[
            "Xoay 90° theo chiều kim đồng hồ", "Xoay 90° ngược chiều kim đồng hồ",
            "Lật video theo chiều ngang", "Lật video theo chiều dọc"
        ])
        self.rotate_combo.grid(row=0, column=1, sticky="ew", padx=5)
        frame.columnconfigure(1, weight=1)
        
        check2 = ttk.Checkbutton(frame, text="Bật Thu phóng", variable=self.scale_enabled_var, command=self.toggle_all_options)
        check2.grid(row=1, column=0, sticky="w", padx=5, pady=(5,0))
        self.widgets_to_disable.append(check2)
        
        self.scale_entry = ttk.Entry(frame, textvariable=self.scale_factor_var, width=10)
        self.scale_entry.grid(row=1, column=1, sticky="w", padx=5, pady=(5,0))

    def create_watermark_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="2. Chèn Logo (Watermark)", padding=10)
        frame.pack(fill="x", pady=5)
        check = ttk.Checkbutton(frame, text="Bật", variable=self.watermark_enabled_var, command=self.toggle_all_options)
        check.pack(side="left", padx=5)
        self.widgets_to_disable.append(check)
        
        self.wm_file_input = self._create_file_input_frame(frame, "File Logo:", self.watermark_logo_var, "Chọn file logo", [("PNG/Image", "*.png")])
        self.wm_file_input.pack(side="left", fill="x", expand=True, padx=10)
        
        pos_frame = ttk.Frame(frame)
        pos_frame.pack(side="left")
        ttk.Label(pos_frame, text="Vị trí:").pack(side="left")
        self.wm_pos_combo = ttk.Combobox(pos_frame, textvariable=self.watermark_pos_var, values=["Dưới-Phải", "Dưới-Trái", "Trên-Phải", "Trên-Trái"], width=10)
        self.wm_pos_combo.pack(side="left", padx=5)
        
        ttk.Label(pos_frame, text="Lề:").pack(side="left")
        self.wm_pad_entry = ttk.Entry(pos_frame, textvariable=self.watermark_pad_var, width=5)
        self.wm_pad_entry.pack(side="left", padx=5)

    def create_audio_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="3. Ghép Âm thanh", padding=10)
        frame.pack(fill="x", pady=5)
        check = ttk.Checkbutton(frame, text="Bật (sẽ thay thế âm thanh gốc)", variable=self.audio_enabled_var, command=self.toggle_all_options)
        check.pack(side="left", padx=5)
        self.widgets_to_disable.append(check)
        
        self.audio_file_input = self._create_file_input_frame(frame, "File Audio:", self.audio_path_var, "Chọn file âm thanh", [("Audio Files", "*.mp3 *.wav *.aac")])
        self.audio_file_input.pack(side="left", fill="x", expand=True, padx=10)

    def toggle_all_options(self):
        # Kích hoạt/Vô hiệu hóa các widget con dựa trên checkbox của chúng
        self.rotate_combo.config(state="readonly" if self.rotate_enabled_var.get() else "disabled")
        self.scale_entry.config(state="normal" if self.scale_enabled_var.get() else "disabled")
        
        for w in self.wm_file_input.winfo_children(): w.config(state="normal" if self.watermark_enabled_var.get() else "disabled")
        self.wm_pos_combo.config(state="readonly" if self.watermark_enabled_var.get() else "disabled")
        self.wm_pad_entry.config(state="normal" if self.watermark_enabled_var.get() else "disabled")

        for w in self.audio_file_input.winfo_children(): w.config(state="normal" if self.audio_enabled_var.get() else "disabled")

    def browse_file(self, string_var, title, filetypes=None):
        path = filedialog.askopenfilename(title=title, filetypes=filetypes or [])
        if path:
            string_var.set(path)

    def start_processing_action(self):
        # 1. Thu thập và xác thực dữ liệu
        params = {"video_path": self.video_path_var.get()}
        if not params["video_path"]:
            self.show_message("error", "Lỗi", "Vui lòng chọn file video chính.")
            return

        params["rotate_enabled"] = self.rotate_enabled_var.get()
        params["scale_enabled"] = self.scale_enabled_var.get()
        params["watermark_enabled"] = self.watermark_enabled_var.get()
        params["audio_enabled"] = self.audio_enabled_var.get()

        if not any([params["rotate_enabled"], params["scale_enabled"], params["watermark_enabled"], params["audio_enabled"]]):
            self.show_message("warning", "Thiếu thao tác", "Vui lòng bật ít nhất một tùy chọn xử lý.")
            return

        # 2. Xác thực các tham số phụ
        try:
            if params["rotate_enabled"]: params["rotate_option"] = self.rotate_option_var.get()
            if params["scale_enabled"]:
                params["scale_factor"] = float(self.scale_factor_var.get())
                if params["scale_factor"] <= 0: raise ValueError("Hệ số thu phóng phải > 0")
            if params["watermark_enabled"]:
                params["logo_path"] = self.watermark_logo_var.get()
                params["watermark_pos"] = self.watermark_pos_var.get()
                params["watermark_pad"] = int(self.watermark_pad_var.get())
                if not params["logo_path"]: raise ValueError("Chưa chọn file logo")
            if params["audio_enabled"]:
                params["audio_path"] = self.audio_path_var.get()
                if not params["audio_path"]: raise ValueError("Chưa chọn file âm thanh")
        except ValueError as e:
            self.show_message("error", "Giá trị không hợp lệ", f"Lỗi: {e}. Vui lòng kiểm tra lại các giá trị đã nhập.")
            return
        
        # 3. Gọi controller
        self.controller.start_combined_processing(params)

    def set_ui_state(self, state):
        ui_state = "disabled" if state == "processing" else "normal"
        # Vô hiệu hóa tất cả các widget đã đăng ký
        for w in self.widgets_to_disable:
            # Cần xử lý riêng cho Combobox vì nó có state 'readonly'
            if isinstance(w, ttk.Combobox):
                w.config(state="disabled" if ui_state == "disabled" else "readonly")
            else:
                w.config(state=ui_state)
        
        # Sau khi set state chung, gọi lại hàm toggle để giữ logic bật/tắt của các mục con
        if state != "processing":
            self.toggle_all_options()
        else: # Nếu đang xử lý, tắt tất cả các mục con không cần quan tâm đến checkbox
             self.rotate_combo.config(state="disabled")
             self.scale_entry.config(state="disabled")
             for w in self.wm_file_input.winfo_children(): w.config(state="disabled")
             self.wm_pos_combo.config(state="disabled")
             self.wm_pad_entry.config(state="disabled")
             for w in self.audio_file_input.winfo_children(): w.config(state="disabled")

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