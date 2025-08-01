import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, scrolledtext, filedialog
import sys
import os
import webbrowser

from Utils.ui_utils import ToolTip, center_dialog, create_tab_title
from Utils.config import README_CONTENT, MP3_PROFILES, GITHUB_URL 
from Utils.logger_setup import LoggerProvider
logger = LoggerProvider.get_logger('recording')

class GUIView:
    def __init__(self, root, controller, project_root):
        self.root = root
        self.controller = controller
        self.project_root = project_root
        self.active_dialog = None
        self.dialog_result = None
        self.card_frames = {}
        self.detail_cards = {}
        self.setup_ui()

    def setup_ui(self):
        create_tab_title(self.root, "Ghi hình Livestream (TikTok & Douyin)")

        header_frame = ttk.LabelFrame(self.root, text="Cài đặt chung", padding=10)
        header_frame.pack(padx=10, pady=(10, 5), fill="x")
        header_frame.columnconfigure(1, weight=1)

        ttk.Label(header_frame, text="Thư mục lưu:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=(0, 2))
        self.output_dir_entry = ttk.Entry(header_frame)
        default_output_path = os.path.join(self.project_root, 'Rec_Output')
        self.output_dir_entry.insert(0, default_output_path)
        self.output_dir_entry.grid(row=0, column=1, sticky="ew", pady=(0, 2))
        ttk.Button(header_frame, text="Duyệt...", command=self.controller.browse_output_dir).grid(row=0, column=2, padx=(5, 0), pady=(0, 2))

        action_frame = ttk.Frame(header_frame)
        action_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        self.add_user_button = ttk.Button(action_frame, text="➕ Thêm User", command=self.controller.add_user_row, style="Accent.TButton")
        self.add_user_button.pack(side="left")

        self.mp3_button = ttk.Button(action_frame, text="Chuyển đổi sang MP3...", command=self.show_mp3_dialog)
        self.mp3_button.pack(side="left", padx=(10, 0))
        ToolTip(self.mp3_button, "Mở cửa sổ chuyển đổi file video bất kỳ sang MP3")

        canvas_container = ttk.Frame(self.root)
        canvas_container.pack(padx=10, pady=5, fill="both", expand=True)
        canvas = tk.Canvas(canvas_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)

        self.card_container = ttk.Frame(canvas)
        self.card_container.columnconfigure(0, weight=1)
        self.card_container.columnconfigure(1, weight=0)

        self.card_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.card_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer_frame = ttk.LabelFrame(self.root, text="Thống kê", padding=10)
        footer_frame.pack(padx=10, pady=(5, 10), fill="x")
        
        success_frame = ttk.Frame(footer_frame)
        success_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.success_label = ttk.Label(success_frame, text="Thành công: 0", foreground="green")
        self.success_label.pack(side="left")
        
        # --- THAY ĐỔI: Chuyển nút Xem thành nút thường ---
        ttk.Button(success_frame, text="Xem danh sách", command=lambda: self.controller.show_status_details("success")).pack(side="right")
        
        failure_frame = ttk.Frame(footer_frame)
        failure_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.failure_label = ttk.Label(failure_frame, text="Thất bại: 0", foreground="red")
        self.failure_label.pack(side="left")

        failure_menubutton = ttk.Menubutton(failure_frame, text="Xem", style="Outline.TMenubutton")
        failure_menubutton.pack(side="right")
        failure_menu = tk.Menu(failure_menubutton, tearoff=0)
        failure_menu.add_command(label="Xem danh sách", command=lambda: self.controller.show_status_details("failure"))
        failure_menu.add_command(label="Mở file log", command=self.controller.open_log_file)
        failure_menubutton["menu"] = failure_menu

    def add_user_card_to_gui(self, row_id, user_history):
        row_index = len(self.card_frames)
        card_frame = ttk.LabelFrame(self.card_container, text="User", padding=10)
        card_frame.grid(row=row_index, column=0, sticky="new", pady=(0, 5))
        self.card_frames[row_id] = card_frame

        card_frame.columnconfigure(0, weight=1)

        main_controls_frame = ttk.Frame(card_frame)
        main_controls_frame.grid(row=0, column=0, sticky="ew")
        main_controls_frame.columnconfigure(0, weight=1)

        url_combobox = ttk.Combobox(main_controls_frame, width=30, values=user_history)
        url_combobox.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ToolTip(url_combobox, "Nhập username TikTok (@user) hoặc link live Douyin (live.douyin.com/...)")
        
        buttons_frame = ttk.Frame(main_controls_frame)
        buttons_frame.grid(row=0, column=1, sticky="e")
        
        start_button = ttk.Button(buttons_frame, text="▶ Bắt đầu", command=lambda: self.controller.start_recording(row_id))
        start_button.pack(side="left", padx=(5, 5))
        
        stop_button = ttk.Button(buttons_frame, text="■ Dừng", command=lambda: self.controller.stop_recording(row_id), state="disabled")
        stop_button.pack(side="left", padx=(0, 5))
        
        remove_button = ttk.Button(buttons_frame, text="➖ Xóa", command=lambda: self.controller.remove_user_row(row_id))
        remove_button.pack(side="left")

        # --- THAY ĐỔI: Thêm nút mở thư mục vào đây ---
        status_options_frame = ttk.Frame(card_frame)
        status_options_frame.grid(row=1, column=0, sticky="ew", pady=(8,0))
        status_options_frame.columnconfigure(2, weight=1) 

        options_button = ttk.Button(status_options_frame, text="⚙️", width=3, command=lambda: options_var.set(not options_var.get()))
        options_button.grid(row=0, column=0, sticky="w")
        ToolTip(options_button, "Hiển thị/Ẩn tùy chọn nâng cao")
        
        # Nút mở thư mục mới
        folder_button = ttk.Button(status_options_frame, text="📁", width=3, command=lambda: self.controller.open_specific_user_folder(row_id))
        folder_button.grid(row=0, column=1, sticky="w", padx=(5, 0))
        ToolTip(folder_button, "Mở thư mục chứa các bản ghi của user này")

        progressbar = ttk.Progressbar(status_options_frame, orient="horizontal", length=100, mode="determinate")
        progressbar.grid(row=0, column=2, sticky="ew", padx=(5,0))

        status_label = ttk.Label(status_options_frame, text="Chờ", anchor="w", foreground="grey", width=20)
        status_label.grid(row=0, column=3, sticky="w", padx=(5,0))

        options_var = tk.BooleanVar()
        options_frame = ttk.Frame(card_frame, padding=(15, 8))
        options_frame.columnconfigure(0, weight=1)
        options_frame.columnconfigure(1, weight=1)
        
        def toggle_options(*args):
            if options_var.get():
                options_frame.grid(row=2, column=0, sticky="ew", pady=(5,0))
            else:
                options_frame.grid_remove()
        
        options_var.trace_add("write", toggle_options)
        
        left_options = ttk.Frame(options_frame)
        left_options.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_options.columnconfigure(0, weight=1)

        ttk.Label(left_options, text="Tên file tùy chỉnh:").pack(fill="x")
        filename_entry = ttk.Entry(left_options)
        filename_entry.pack(fill="x", pady=(2, 5))
        ToolTip(filename_entry, "Để trống sẽ dùng tên mặc định: user_ngày_giờ")
        
        ttk.Label(left_options, text="Thời gian ghi (giây):").pack(fill="x")
        duration_entry = ttk.Entry(left_options)
        duration_entry.pack(fill="x", pady=(2, 0))

        right_options = ttk.Frame(options_frame)
        right_options.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_options.columnconfigure(0, weight=1)

        mp3_options_frame = ttk.Frame(right_options)
        mp3_options_frame.pack(fill="x", pady=(0,5))
        
        convert_var = tk.BooleanVar(value=True)
        convert_check = ttk.Checkbutton(mp3_options_frame, text="->Mp3", variable=convert_var)
        convert_check.pack(side="left")
        ToolTip(convert_check, "Tick để tự động chuyển video sang MP3 sau khi ghi hình")

        mute_var = tk.BooleanVar(value=False)
        mute_check = ttk.Checkbutton(mp3_options_frame, text="Tắt tiếng Video", variable=mute_var)
        mute_check.pack(side="left", padx=(10, 0))
        ToolTip(mute_check, "Lưu file video không có âm thanh (MP3 vẫn được tạo nếu chọn)")
        
        mp3_display_names = [profile['display'] for profile in MP3_PROFILES.values()]
        mp3_profile_combobox = ttk.Combobox(right_options, values=mp3_display_names, state="readonly")
        mp3_profile_combobox.pack(fill="x")
        mp3_profile_combobox.set(mp3_display_names[0])
        ToolTip(mp3_profile_combobox, "Chọn cấu hình chuyển đổi MP3.")
        
        def toggle_mp3_widgets(*args):
            state = "normal" if convert_var.get() else "disabled"
            if mp3_profile_combobox.winfo_exists():
                mp3_profile_combobox.config(state=state)

        convert_var.trace_add("write", toggle_mp3_widgets)
        toggle_mp3_widgets()

        url_combobox.bind("<FocusOut>", lambda e, rid=row_id: self.controller.handle_url_entry_focus_out(rid, e.widget))
        url_combobox.bind("<<ComboboxSelected>>", lambda e, rid=row_id: self.controller.handle_url_entry_focus_out(rid, e.widget))

        return {
            'card_frame': card_frame, 'url_combobox': url_combobox, 'start_button': start_button, 
            'stop_button': stop_button, 'remove_button': remove_button, 
            'convert_var': convert_var, 'mute_video_var': mute_var,
            'duration_entry': duration_entry, 'status_label': status_label, 'progressbar': progressbar,
            'filename_entry': filename_entry,
            'mp3_profile_combobox': mp3_profile_combobox
        }

    def create_detail_card(self, row_id):
        self.remove_detail_card(row_id)
        card_frame = self.card_frames.get(row_id)
        if not card_frame or not card_frame.winfo_exists(): return
        grid_info = card_frame.grid_info()
        row_index = grid_info.get('row', 0)
        
        model = self.controller.user_rows.get(row_id)
        identifier = self.controller._extract_identifier(model.last_known_input, model.platform)
        display_name = f"Douyin - {identifier}" if model.platform == 'douyin' else f"@{identifier}"

        detail_frame = ttk.LabelFrame(self.card_container, text=f"Chi tiết: {display_name}")
        detail_frame.grid(row=row_index, column=1, sticky="ns", padx=(5,0), pady=(0, 5))

        text_widget = scrolledtext.ScrolledText(detail_frame, height=7, width=50, font=('Consolas', 9), wrap=tk.WORD, relief="flat")
        text_widget.pack(fill="both", expand=True, padx=2, pady=2)
        text_widget.config(state="disabled")
        download_label = ttk.Label(detail_frame, text="...", font=('Consolas', 9, 'italic'), foreground="blue")
        download_label.pack(fill="x", padx=5, pady=(0, 2))
        self.detail_cards[row_id] = {'frame': detail_frame, 'text_widget': text_widget, 'download_label': download_label}

    def update_detail_card(self, row_id, message):
        card_info = self.detail_cards.get(row_id)
        if not (card_info and card_info['frame'].winfo_exists()):
            return

        if "[DOWNLOAD]" in message:
            download_label = card_info.get('download_label')
            if download_label:
                clean_message = message.replace("[DOWNLOAD]", "").strip()
                download_label.config(text=clean_message)
        else:
            text_widget = card_info.get('text_widget')
            if text_widget:
                text_widget.config(state="normal")
                text_widget.insert(tk.END, message + "\n")
                text_widget.see(tk.END)
                text_widget.config(state="disabled")

    def remove_detail_card(self, row_id):
        card_info = self.detail_cards.pop(row_id, None)
        if card_info and card_info['frame'].winfo_exists():
            card_info['frame'].destroy()
        
    def remove_user_card_from_gui(self, row_id):
        card_frame = self.card_frames.pop(row_id, None)
        if card_frame and card_frame.winfo_exists():
            card_frame.destroy()
        
    def update_status_label(self, status_label, text, color):
        if status_label and status_label.winfo_exists():
            status_label.config(text=text, foreground=color)
    
    def update_progressbar(self, progressbar, mode='stop', value=0):
        if not progressbar or not progressbar.winfo_exists(): return
        if mode == 'indeterminate':
            progressbar.config(mode='indeterminate')
            progressbar.start(10)
        elif mode == 'determinate':
            progressbar.stop()
            progressbar.config(mode='determinate', value=value)
        else:
            progressbar.stop()
            progressbar.config(value=0)

    def update_status_labels(self, success_count, failure_count):
        self.success_label.config(text=f"Thành công: {success_count}")
        self.failure_label.config(text=f"Thất bại: {failure_count}")

    def update_output_dir_entry(self, text, color='black'):
        self.output_dir_entry.delete(0, tk.END)
        self.output_dir_entry.insert(0, text)
        self.output_dir_entry.config(foreground=color)

    def set_widget_state(self, widget, state):
        if widget and widget.winfo_exists():
            widget.config(state=state)

    def update_ui_for_state(self, row_id, state):
        model = self.controller.user_rows.get(row_id)
        if not model: return

        widgets = model.widgets
        is_recording = state == 'recording'

        self.set_widget_state(widgets.get('url_combobox'), 'disabled' if is_recording else 'normal')
        self.set_widget_state(widgets.get('start_button'), 'disabled' if is_recording else 'normal')
        self.set_widget_state(widgets.get('stop_button'), 'normal' if is_recording else 'disabled')
        
        remove_btn = widgets.get('remove_button')
        if remove_btn:
            if is_recording:
                remove_btn.config(text="❌ Hủy")
                ToolTip(remove_btn, "Hủy ghi hình (sẽ không lưu file)")
            else:
                remove_btn.config(text="➖ Xóa")
                ToolTip(remove_btn, "Xóa thẻ này")

    def show_messagebox(self, msg_type, title, message):
        parent_window = self.root.winfo_toplevel()
        if self.active_dialog and self.active_dialog.winfo_exists(): return None
        self.dialog_result = None
        self.active_dialog = dialog = tk.Toplevel(parent_window)
        dialog.title(title); dialog.resizable(False, False)
        main_frame = tk.Frame(dialog, padx=15, pady=10); main_frame.pack(expand=True, fill="both")
        msg_frame = tk.Frame(main_frame); msg_frame.pack(fill="x")
        tk.Label(msg_frame, text=message, justify=tk.LEFT, wraplength=400).pack(side="left", anchor="nw", padx=(10,0))
        btn_frame = tk.Frame(main_frame); btn_frame.pack(pady=(15, 5))
        def on_yes(): self.dialog_result = True; self.close_active_dialog()
        def on_no(): self.dialog_result = False; self.close_active_dialog()
        def on_ok(): self.dialog_result = None; self.close_active_dialog()
        if msg_type == 'askyesno':
            tk.Button(btn_frame, text="Yes", width=10, command=on_yes).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="No", width=10, command=on_no).pack(side=tk.LEFT, padx=5)
        else:
            tk.Button(btn_frame, text="OK", width=10, command=on_ok).pack()
        dialog.transient(self.root); dialog.update_idletasks(); center_dialog(dialog); dialog.grab_set()
        self.root.wait_window(dialog)
        return self.dialog_result

    def show_about(self):
        parent_window = self.root.winfo_toplevel()
        if self.active_dialog: return
        about_window = tk.Toplevel(parent_window)
        self.active_dialog = about_window
        about_window.title("About TikTok Live Recorder")
        about_window.resizable(False, False)

        # Frame chính
        main_frame = ttk.Frame(about_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Phần nội dung chính
        text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=70, height=18, font=("Arial", 10))
        text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        text_area.insert(tk.END, README_CONTENT)
        text_area.config(state="disabled")

        # 2. Phần liên kết có thể nhấp
        def open_link(event):
            webbrowser.open_new(GITHUB_URL)

        link_font = tkfont.Font(family="Arial", size=10, underline=True)
        
        link_label = ttk.Label(
            main_frame, 
            text="Tham khảo mã nguồn mở tại: " + GITHUB_URL, 
            font=link_font, 
            foreground="blue", 
            cursor="hand2"
        )
        link_label.pack(pady=(5, 0))
        link_label.bind("<Button-1>", open_link)

        # 3. Nút đóng
        ttk.Button(main_frame, text="Close", command=self.close_active_dialog, style="Accent.TButton").pack(pady=15)
        
        about_window.transient(self.root)
        about_window.grab_set()
        center_dialog(about_window)
        about_window.protocol("WM_DELETE_WINDOW", self.close_active_dialog)
        
    def show_mp3_dialog(self):
        parent_window = self.root.winfo_toplevel()
        if self.active_dialog: return
        dialog = tk.Toplevel(parent_window)
        self.active_dialog = dialog
        dialog.title("Chuyển đổi sang MP3")
        dialog.resizable(False, False) 
        frame = tk.Frame(dialog, padx=10, pady=10); frame.pack()
        tk.Label(frame, text="File MP4:").grid(row=0, column=0, sticky="w", pady=2)
        input_entry = tk.Entry(frame, width=50); input_entry.grid(row=1, column=0, columnspan=2, sticky="ew")
        def browse_input():
            path = filedialog.askopenfilename(title="Chọn file MP4/FLV", filetypes=[("Video files", "*.mp4 *.flv")])
            if path: input_entry.delete(0, tk.END); input_entry.insert(0, path)
        tk.Button(frame, text="Duyệt...", command=browse_input).grid(row=1, column=2, padx=5)
        tk.Label(frame, text="Thư mục lưu (để trống nếu muốn lưu cùng chỗ):").grid(row=2, column=0, sticky="w", pady=2)
        output_entry = tk.Entry(frame, width=50); output_entry.grid(row=3, column=0, columnspan=2, sticky="ew")
        def browse_output():
            path = filedialog.askdirectory(title="Chọn thư mục lưu file MP3")
            if path: output_entry.delete(0, tk.END); output_entry.insert(0, path)
        tk.Button(frame, text="Duyệt...", command=browse_output).grid(row=3, column=2, padx=5)
        button_frame = tk.Frame(frame); button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        self.convert_mp3_btn = tk.Button(button_frame, text="Chuyển đổi", command=lambda: self.controller.convert_to_mp3_manual(input_entry.get(), output_entry.get()))
        self.convert_mp3_btn.pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Đóng", command=self.close_active_dialog).pack(side=tk.LEFT, padx=10)
        dialog.transient(self.root); dialog.grab_set(); center_dialog(dialog)
        dialog.protocol("WM_DELETE_WINDOW", self.close_active_dialog)

    def set_mp3_button_state(self, state):
        if hasattr(self, 'convert_mp3_btn') and self.convert_mp3_btn.winfo_exists():
            self.convert_mp3_btn.config(state=state)

    def show_progress_dialog(self, message="Đang xử lý..."):
        parent_window = self.root.winfo_toplevel()
        if self.active_dialog: self.close_active_dialog()
        dialog = tk.Toplevel(self.root); self.active_dialog = dialog
        dialog.title("Vui lòng chờ"); dialog.resizable(False, False)
        tk.Label(dialog, text=message, pady=10, padx=20).pack()
        progress = ttk.Progressbar(dialog, length=300, mode='indeterminate')
        progress.pack(pady=10, padx=20); progress.start(10)
        dialog.transient(self.root); dialog.grab_set(); center_dialog(dialog)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    def show_details_window(self, title, content):
        parent_window = self.root.winfo_toplevel()
        if self.active_dialog: return
        dialog = tk.Toplevel(parent_window)
        self.active_dialog = dialog
        dialog.title(title)
        dialog.geometry("300x400")
        text_area = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, width=40, height=20)
        text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        text_area.insert(tk.END, content)
        text_area.config(state="disabled")
        tk.Button(dialog, text="Đóng", command=self.close_active_dialog).pack(pady=5)
        dialog.transient(self.root)
        dialog.grab_set()
        center_dialog(dialog)
        dialog.protocol("WM_DELETE_WINDOW", self.close_active_dialog)

    def close_active_dialog(self):
        parent_window = self.root.winfo_toplevel()
        if self.active_dialog and self.active_dialog.winfo_exists():
            self.active_dialog.destroy()
        self.active_dialog = None
