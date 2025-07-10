# AudioTools/audio_tools_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
from PIL import Image, ImageTk
from io import BytesIO

from .audio_tools_controller import AudioToolsController
from Utils.ui_utils import create_tab_title

class AudioToolsGUI:
    def __init__(self, root_frame, project_root, thread_pool):
        self.root = root_frame
        self.controller = AudioToolsController(self, project_root, thread_pool)
        
        # Biến lưu trữ danh sách file
        self.file_list_norm = []
        self.file_list_denoise = []
        
        # Biến cho tab Metadata
        self.current_metadata_file = None
        self.current_cover_path = None
        
        # Biến cho các tùy chọn
        self.norm_lufs_var = tk.DoubleVar(value=-14.0)
        self.denoise_strength_var = tk.DoubleVar(value=5.0)

        self.create_widgets()

    def create_widgets(self):
        create_tab_title(self.root, "Công cụ Xử lý & Cải thiện Âm thanh")

        self.sub_notebook = ttk.Notebook(self.root)
        self.sub_notebook.pack(fill="both", expand=True, padx=10, pady=5)

        norm_frame = ttk.Frame(self.sub_notebook, padding=10)
        meta_frame = ttk.Frame(self.sub_notebook, padding=10)
        denoise_frame = ttk.Frame(self.sub_notebook, padding=10)

        self.sub_notebook.add(norm_frame, text=" Chuẩn hóa Âm lượng ")
        self.sub_notebook.add(meta_frame, text=" Chỉnh sửa Thông tin ")
        self.sub_notebook.add(denoise_frame, text=" Giảm Tạp âm ")

        self.create_normalization_tab(norm_frame)
        self.create_metadata_tab(meta_frame)
        self.create_denoise_tab(denoise_frame)
        
        # Log chung
        status_frame = ttk.LabelFrame(self.root, text="Nhật ký", padding=10)
        status_frame.pack(side="bottom", fill="both", expand=True, padx=10, pady=(0, 10))
        status_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=5, font=('Consolas', 9), wrap=tk.WORD, state="disabled")
        self.status_text.grid(row=0, column=0, sticky="nsew")

    def create_normalization_tab(self, parent):
        parent.columnconfigure(0, weight=1)

        # Khung danh sách file
        list_frame = ttk.LabelFrame(parent, text="Danh sách file cần chuẩn hóa", padding=10)
        list_frame.grid(row=0, column=0, sticky="ew")
        list_frame.columnconfigure(0, weight=1)
        self.norm_listbox = tk.Listbox(list_frame, height=8, selectmode="extended")
        self.norm_listbox.grid(row=0, column=0, sticky="nsew")
        norm_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.norm_listbox.yview)
        norm_scrollbar.grid(row=0, column=1, sticky="ns")
        self.norm_listbox.config(yscrollcommand=norm_scrollbar.set)
        
        list_actions = ttk.Frame(list_frame)
        list_actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        ttk.Button(list_actions, text="Thêm Files...", command=self.browse_norm_files).pack(side="left")
        ttk.Button(list_actions, text="Xóa", command=self.remove_norm_files).pack(side="left", padx=5)

        # Khung tùy chọn
        options_frame = ttk.LabelFrame(parent, text="Tùy chọn", padding=10)
        options_frame.grid(row=1, column=0, sticky="ew", pady=10)
        options_frame.columnconfigure(1, weight=1)
        ttk.Label(options_frame, text="Mức âm lượng mục tiêu (LUFS):").grid(row=0, column=0, padx=5)
        ttk.Scale(options_frame, from_=-24, to=-9, variable=self.norm_lufs_var, orient="horizontal", command=lambda v: self.norm_lufs_label.config(text=f"{float(v):.1f}")).grid(row=0, column=1, sticky="ew")
        self.norm_lufs_label = ttk.Label(options_frame, text=f"{self.norm_lufs_var.get():.1f}")
        self.norm_lufs_label.grid(row=0, column=2, padx=5)

        # Nút bắt đầu
        self.norm_btn = ttk.Button(parent, text="BẮT ĐẦU CHUẨN HÓA", style="Accent.TButton", command=lambda: self.controller.start_normalization(self.file_list_norm, self.norm_lufs_var.get()))
        self.norm_btn.grid(row=2, column=0, pady=10)
    
    def create_metadata_tab(self, parent):
        parent.columnconfigure(1, weight=1)

        # File selection
        file_frame = ttk.LabelFrame(parent, text="Chọn file Audio", padding=10)
        file_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        file_frame.columnconfigure(0, weight=1)
        self.meta_file_entry = ttk.Entry(file_frame, state="readonly")
        self.meta_file_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(file_frame, text="Duyệt...", command=self.browse_meta_file).grid(row=0, column=1, padx=(5,0))

        # Metadata fields
        tags_frame = ttk.LabelFrame(parent, text="Thông tin", padding=10)
        tags_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        tags_frame.columnconfigure(1, weight=1)
        
        self.tag_entries = {}
        fields = ["Tiêu đề:", "Nghệ sĩ:", "Album:", "Năm:", "Thể loại:"]
        for i, field in enumerate(fields):
            key = field.replace(":", "").lower().replace(" ", "_")
            ttk.Label(tags_frame, text=field).grid(row=i, column=0, sticky="w", padx=5, pady=3)
            entry = ttk.Entry(tags_frame)
            entry.grid(row=i, column=1, sticky="ew", padx=5, pady=3)
            self.tag_entries[key] = entry

        # Cover art
        art_frame = ttk.LabelFrame(parent, text="Ảnh bìa", padding=10)
        art_frame.grid(row=1, column=0, sticky="ns", padx=5, pady=5)
        
        # --- THAY ĐỔI TẠI ĐÂY ---
        # 1. Tạo một Frame container có kích thước cố định
        image_container = tk.Frame(art_frame, width=150, height=150, relief="solid", borderwidth=1)
        image_container.pack(expand=True)
        # 2. Ngăn Frame co lại để vừa với nội dung bên trong
        image_container.pack_propagate(False)

        # 3. Tạo Label bên trong Frame container
        self.art_label = ttk.Label(image_container, text="Chưa có ảnh", anchor="center")
        self.art_label.pack(expand=True, fill="both")
        
        # 4. Xóa dòng .config() gây lỗi
        # self.art_label.config(width=25, height=13) -> Dòng này đã được xóa

        ttk.Button(art_frame, text="Chọn ảnh...", command=self.browse_cover_art).pack(pady=5)
        
        # Save button
        self.meta_save_btn = ttk.Button(parent, text="LƯU THAY ĐỔI", style="Accent.TButton", command=self.save_metadata)
        self.meta_save_btn.grid(row=2, column=0, columnspan=2, pady=10)

    def create_denoise_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        list_frame = ttk.LabelFrame(parent, text="Danh sách file cần giảm tạp âm", padding=10)
        list_frame.grid(row=0, column=0, sticky="ew")
        list_frame.columnconfigure(0, weight=1)
        self.denoise_listbox = tk.Listbox(list_frame, height=8, selectmode="extended")
        self.denoise_listbox.grid(row=0, column=0, sticky="nsew")
        denoise_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.denoise_listbox.yview)
        denoise_scrollbar.grid(row=0, column=1, sticky="ns")
        self.denoise_listbox.config(yscrollcommand=denoise_scrollbar.set)
        list_actions = ttk.Frame(list_frame)
        list_actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        ttk.Button(list_actions, text="Thêm Files...", command=self.browse_denoise_files).pack(side="left")
        ttk.Button(list_actions, text="Xóa", command=self.remove_denoise_files).pack(side="left", padx=5)
        options_frame = ttk.LabelFrame(parent, text="Tùy chọn", padding=10)
        options_frame.grid(row=1, column=0, sticky="ew", pady=10)
        options_frame.columnconfigure(1, weight=1)
        ttk.Label(options_frame, text="Mức độ giảm tạp âm:").grid(row=0, column=0, padx=5)
        ttk.Scale(options_frame, from_=1.0, to=21.0, variable=self.denoise_strength_var, orient="horizontal", command=lambda v: self.denoise_strength_label.config(text=f"{float(v):.1f}")).grid(row=0, column=1, sticky="ew")
        self.denoise_strength_label = ttk.Label(options_frame, text=f"{self.denoise_strength_var.get():.1f}")
        self.denoise_strength_label.grid(row=0, column=2, padx=5)
        self.denoise_btn = ttk.Button(parent, text="BẮT ĐẦU GIẢM TẠP ÂM", style="Accent.TButton", command=lambda: self.controller.start_noise_reduction(self.file_list_denoise, self.denoise_strength_var.get()))
        self.denoise_btn.grid(row=2, column=0, pady=10)

    def browse_norm_files(self):
        paths = filedialog.askopenfilenames(title="Chọn file Audio")
        if paths:
            self.file_list_norm.extend(paths)
            self.update_listbox(self.norm_listbox, self.file_list_norm)

    def remove_norm_files(self):
        selected = self.norm_listbox.curselection()
        for i in sorted(selected, reverse=True):
            del self.file_list_norm[i]
        self.update_listbox(self.norm_listbox, self.file_list_norm)
        
    def browse_denoise_files(self):
        paths = filedialog.askopenfilenames(title="Chọn file Audio")
        if paths:
            self.file_list_denoise.extend(paths)
            self.update_listbox(self.denoise_listbox, self.file_list_denoise)

    def remove_denoise_files(self):
        selected = self.denoise_listbox.curselection()
        for i in sorted(selected, reverse=True):
            del self.file_list_denoise[i]
        self.update_listbox(self.denoise_listbox, self.file_list_denoise)

    def update_listbox(self, listbox, file_list):
        listbox.delete(0, tk.END)
        for item in file_list:
            listbox.insert(tk.END, f"  {os.path.basename(item)}")

    def browse_meta_file(self):
        path = filedialog.askopenfilename(title="Chọn file MP3/FLAC", filetypes=[("Audio Files", "*.mp3 *.flac"), ("All files", "*.*")])
        if not path: return
        self.current_metadata_file = path
        self.current_cover_path = None
        self.meta_file_entry.config(state="normal")
        self.meta_file_entry.delete(0, tk.END)
        self.meta_file_entry.insert(0, path)
        self.meta_file_entry.config(state="readonly")
        tags, cover_data = self.controller.load_metadata(path)
        if tags:
            self.tag_entries['tiêu_đề'].delete(0, tk.END); self.tag_entries['tiêu_đề'].insert(0, tags.get('title', ''))
            self.tag_entries['nghệ_sĩ'].delete(0, tk.END); self.tag_entries['nghệ_sĩ'].insert(0, tags.get('artist', ''))
            self.tag_entries['album'].delete(0, tk.END); self.tag_entries['album'].insert(0, tags.get('album', ''))
            self.tag_entries['năm'].delete(0, tk.END); self.tag_entries['năm'].insert(0, tags.get('year', ''))
            self.tag_entries['thể_loại'].delete(0, tk.END); self.tag_entries['thể_loại'].insert(0, tags.get('genre', ''))
        self.display_cover_art(cover_data)

    def display_cover_art(self, data):
        if data:
            try:
                img = Image.open(BytesIO(data))
                img.thumbnail((150, 150))
                self.cover_photo = ImageTk.PhotoImage(img)
                self.art_label.config(image=self.cover_photo, text="")
            except Exception as e:
                self.art_label.config(image='', text="Lỗi ảnh")
                self.controller.logger.error(f"Lỗi hiển thị ảnh bìa: {e}")
        else:
            self.art_label.config(image='', text="Chưa có ảnh")

    def browse_cover_art(self):
        path = filedialog.askopenfilename(title="Chọn ảnh bìa", filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if path:
            self.current_cover_path = path
            self.display_cover_art(open(path, 'rb').read())

    def save_metadata(self):
        tags = {
            'title': self.tag_entries['tiêu_đề'].get(),
            'artist': self.tag_entries['nghệ_sĩ'].get(),
            'album': self.tag_entries['album'].get(),
            'year': self.tag_entries['năm'].get(),
            'genre': self.tag_entries['thể_loại'].get()
        }
        self.controller.save_metadata(self.current_metadata_file, tags, self.current_cover_path)
        self.current_cover_path = None

    def set_ui_state(self, state):
        is_processing = state == "processing"
        ui_state = "disabled" if is_processing else "normal"
        self.norm_btn.config(state=ui_state)
        self.meta_save_btn.config(state=ui_state)
        self.denoise_btn.config(state=ui_state)

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
