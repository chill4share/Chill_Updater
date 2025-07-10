# CutMerge/cut_merge_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import datetime
import pygame

from .cut_merge_controller import CutMergeController
from Utils.ui_utils import create_tab_title

# --- THÊM LỚP MỚI: THƯỚC KÉO 2 CON TRƯỢT ---
class DualHandleSlider(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.config(height=50, bg='#ECECEC', cursor="hand2") # Thêm con trỏ
        
        self.max_val = 100
        self.start_val = 0
        self.end_val = 100
        
        self._drag_data = {"x": 0, "y": 0, "item": None}
        self.indicator_pos = 0

        self.bind("<Configure>", self._on_resize)
        # Binding cho các con trượt
        self.tag_bind("start_handle", "<ButtonPress-1>", self._on_press)
        self.tag_bind("start_handle", "<ButtonRelease-1>", self._on_release)
        self.tag_bind("start_handle", "<B1-Motion>", self._on_drag)
        self.tag_bind("end_handle", "<ButtonPress-1>", self._on_press)
        self.tag_bind("end_handle", "<ButtonRelease-1>", self._on_release)
        self.tag_bind("end_handle", "<B1-Motion>", self._on_drag)
        
        # --- THÊM MỚI: Binding cho việc click vào track ---
        self.tag_bind("track", "<ButtonPress-1>", self._on_track_click)

        # --- THAY ĐỔI: Thêm callback mới ---
        self.on_change_callback = None
        self.on_seek_callback = None # Callback khi người dùng yêu cầu tua
        
        self._draw_all()

    def _on_resize(self, event=None):
        self._draw_all()

    def _draw_all(self):
        self.delete("all")
        self.track = self.create_rectangle(10, 20, self.winfo_width()-10, 30, fill="#BDBDBD", outline="", tags="track")
        self.selection_rect = self.create_rectangle(0, 20, 0, 30, fill="#0078D7", outline="")
        self.indicator = self.create_line(0, 15, 0, 35, fill="red", width=2)
        
        # --- SỬA ĐỔI: Đổi màu cho hai con trượt ---
        self.start_handle = self.create_rectangle(0, 10, 0, 40, fill="#28a745", outline="", tags="start_handle") # MÀU XANH LÁ
        self.end_handle = self.create_rectangle(0, 10, 0, 40, fill="#fd7e14", outline="", tags="end_handle") # MÀU CAM

        self.update_handles_from_values()
        self.update_indicator(self.indicator_pos)

    def set_range(self, max_val):
        self.max_val = max_val
        self.set_values(0, max_val)

    def set_values(self, start, end):
        # Đảm bảo giá trị nằm trong khoảng 0 -> max_val
        start = max(0, min(start, self.max_val))
        end = max(0, min(end, self.max_val))

        # --- SỬA ĐỔI: Luôn luôn đảm bảo start <= end ---
        # Logic này đảm bảo hai con trượt không bao giờ vượt qua nhau.
        if start > end:
            # Nếu có xung đột, ưu tiên giữ giá trị 'end' và đẩy 'start' về bằng 'end'
            # Điều này hữu ích khi người dùng kéo 'end' về trước 'start'.
            start = end
        
        self.start_val = start
        self.end_val = end
        
        self.update_handles_from_values()
        if self.on_change_callback:
            self.on_change_callback(self.start_val, self.end_val)

    def _val_to_x(self, val):
        slider_width = self.winfo_width() - 20
        return 10 + (val / self.max_val) * slider_width

    def _x_to_val(self, x):
        slider_width = self.winfo_width() - 20
        val = ((x - 10) / slider_width) * self.max_val
        return max(0, min(val, self.max_val))

    def update_handles_from_values(self):
        start_x = self._val_to_x(self.start_val)
        end_x = self._val_to_x(self.end_val)
        self.coords(self.start_handle, start_x - 4, 10, start_x + 4, 40)
        self.coords(self.end_handle, end_x - 4, 10, end_x + 4, 40)
        self.coords(self.selection_rect, start_x, 20, end_x, 30)

    def update_indicator(self, val):
        self.indicator_pos = val
        x = self._val_to_x(val)
        self.coords(self.indicator, x, 15, x, 35)

    def _on_press(self, event):
        self._drag_data["item"] = self.find_closest(event.x, event.y)[0]
        self._drag_data["x"] = event.x

    def _on_release(self, event):
        # --- THAY ĐỔI: Kích hoạt callback khi thả chuột ---
        if self._drag_data["item"] and self.on_seek_callback:
            if self._drag_data["item"] == self.start_handle:
                self.on_seek_callback(self.start_val, 'play')
            elif self._drag_data["item"] == self.end_handle:
                self.on_seek_callback(self.end_val, 'pause')

        self._drag_data["item"] = None
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0

    def _on_track_click(self, event):
        # --- HÀM MỚI: Xử lý click vào track ---
        if self.on_seek_callback:
            clicked_val = self._x_to_val(event.x)
            self.on_seek_callback(clicked_val, 'play')

    def _on_drag(self, event):
        if not self._drag_data["item"]: return
        
        new_val = self._x_to_val(event.x)
        
        if self._drag_data["item"] == self.start_handle:
            if new_val < self.end_val: self.start_val = new_val
        elif self._drag_data["item"] == self.end_handle:
            if new_val > self.start_val: self.end_val = new_val
            
        self.update_handles_from_values()

        if self.on_change_callback:
            self.on_change_callback(self.start_val, self.end_val)

class CutMergeGUI:
    def __init__(self, root_frame, project_root, thread_pool):
        self.root = root_frame
        self.controller = CutMergeController(self, project_root, thread_pool)
        
        # Biến cho tab Cắt
        self.cut_input_var = tk.StringVar()
        self.start_placeholder = "ví dụ: 90"
        self.end_placeholder = "ví dụ: 125.5"

        # Biến cho tab Ghép
        self.merge_mode_var = tk.StringVar(value="slow") # Mặc định là chế độ chậm, an toàn hơn

        self.create_widgets()
        self.validate_button_states()
    
    def create_widgets(self):
        create_tab_title(self.root, "Cắt & Ghép Video/Audio")

        # Tạo Notebook con cho 2 chức năng
        self.sub_notebook = ttk.Notebook(self.root)
        self.sub_notebook.pack(fill="both", expand=True, padx=10, pady=5)

        cut_frame = ttk.Frame(self.sub_notebook)
        merge_frame = ttk.Frame(self.sub_notebook)

        self.sub_notebook.add(cut_frame, text=" Cắt File ")
        self.sub_notebook.add(merge_frame, text=" Ghép Files ")

        self.create_cut_tab(cut_frame)
        self.create_merge_tab(merge_frame)

        # Khu vực log chung
        status_frame = ttk.LabelFrame(self.root, text="Nhật ký", padding=10)
        status_frame.pack(side="bottom", fill="both", expand=True, padx=10, pady=(0, 10))
        status_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=6, font=('Consolas', 9), wrap=tk.WORD, state="disabled")
        self.status_text.grid(row=0, column=0, sticky="nsew")

    def create_cut_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        
        # 1. Khung nhập liệu
        input_frame = ttk.LabelFrame(parent, text="File đầu vào", padding=10)
        input_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        input_frame.columnconfigure(0, weight=1)
        self.cut_input_entry = ttk.Entry(input_frame, textvariable=self.cut_input_var)
        self.cut_input_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(input_frame, text="Duyệt...", command=self.browse_cut_input).grid(row=0, column=1, padx=(5,0))

        # 2. Khung nghe thử
        self.player_frame = ttk.LabelFrame(parent, text="Nghe thử & Chọn khoảng", padding=10)
        self.player_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self._create_player_widgets(self.player_frame)
        self.player_frame.grid_remove() 

        # 3. Khung định nghĩa các đoạn cắt
        def_frame = ttk.LabelFrame(parent, text="Định nghĩa các đoạn cắt", padding=10)
        def_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        def_frame.columnconfigure(1, weight=1)

        self.cut_listbox = tk.Listbox(def_frame, height=5, selectmode="extended")
        self.cut_listbox.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=(0,5))
        
        ttk.Label(def_frame, text="Bắt đầu từ giây thứ:").grid(row=1, column=0, sticky="w")
        self.start_entry = ttk.Entry(def_frame, width=15)
        self.start_entry.grid(row=1, column=1, sticky="w")
        self.start_entry.insert(0, self.start_placeholder)
        self.start_entry.config(foreground="grey")
        self.start_entry.bind("<FocusIn>", self.on_start_focus_in)
        self.start_entry.bind("<FocusOut>", self.on_start_focus_out)
        # --- THÊM MỚI: BINDING CHO TƯƠNG TÁC 2 CHIỀU ---
        self.start_entry.bind("<Return>", self._on_entry_change)

        ttk.Label(def_frame, text="Kết thúc ở giây thứ:").grid(row=2, column=0, sticky="w")
        self.end_entry = ttk.Entry(def_frame, width=15)
        self.end_entry.grid(row=2, column=1, sticky="w")
        self.end_entry.insert(0, self.end_placeholder)
        self.end_entry.config(foreground="grey")
        self.end_entry.bind("<FocusIn>", self.on_end_focus_in)
        self.end_entry.bind("<FocusOut>", self.on_end_focus_out)
        # --- THÊM MỚI: BINDING CHO TƯƠNG TÁC 2 CHIỀU ---
        self.end_entry.bind("<Return>", self._on_entry_change)


        cut_actions_frame = ttk.Frame(def_frame)
        cut_actions_frame.grid(row=1, column=2, rowspan=2, sticky="e", padx=(10,0))
        ttk.Button(cut_actions_frame, text="Thêm", command=self.add_cut).pack(fill="x", pady=2)
        ttk.Button(cut_actions_frame, text="Xóa", command=self.remove_cut).pack(fill="x")

        # 4. Nút bắt đầu
        self.cut_btn = ttk.Button(parent, text="BẮT ĐẦU CẮT", command=self.controller.start_cutting, style="Accent.TButton")
        self.cut_btn.grid(row=3, column=0, pady=10)
    
    def create_merge_tab(self, parent):
        """Xây dựng giao diện cho tab Ghép File."""
        parent.columnconfigure(0, weight=4)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # 1. Khung danh sách file
        list_frame = ttk.LabelFrame(parent, text="Danh sách file cần ghép (theo thứ tự)", padding=10)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.merge_listbox = tk.Listbox(list_frame, height=8, selectmode="extended")
        self.merge_listbox.grid(row=0, column=0, sticky="nsew")
        
        merge_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.merge_listbox.yview)
        merge_scrollbar.grid(row=0, column=1, sticky="ns")
        self.merge_listbox.config(yscrollcommand=merge_scrollbar.set)

        # 2. Khung điều khiển danh sách
        list_actions_frame = ttk.Frame(parent)
        list_actions_frame.grid(row=0, column=1, sticky="ns", padx=(0,5), pady=5)
        ttk.Button(list_actions_frame, text="Thêm Files...", command=self.add_files_to_merge).pack(fill="x", pady=2)
        ttk.Button(list_actions_frame, text="Xóa", command=self.remove_from_merge).pack(fill="x", pady=2)
        ttk.Separator(list_actions_frame).pack(fill="x", pady=5)
        ttk.Button(list_actions_frame, text="Lên", command=lambda: self.move_in_merge("up")).pack(fill="x", pady=2)
        ttk.Button(list_actions_frame, text="Xuống", command=lambda: self.move_in_merge("down")).pack(fill="x", pady=2)

        # 3. Khung tùy chọn và nút bắt đầu
        bottom_frame = ttk.Frame(parent)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        options_frame = ttk.LabelFrame(bottom_frame, text="Chế độ ghép", padding=10)
        options_frame.pack(side="left", fill="x", expand=True)
        ttk.Radiobutton(options_frame, text="Ghép Tương Thích (Chậm, an toàn)", variable=self.merge_mode_var, value="slow").pack(anchor="w")
        ttk.Radiobutton(options_frame, text="Ghép Nhanh (Yêu cầu file cùng thông số)", variable=self.merge_mode_var, value="fast").pack(anchor="w")
        
        self.merge_btn = ttk.Button(bottom_frame, text="BẮT ĐẦU GHÉP", command=self.controller.start_merging, style="Accent.TButton")
        self.merge_btn.pack(side="right", padx=10, pady=10)

    def update_marker_positions(self, start_seconds, end_seconds):
        """Cập nhật cả hai điểm Bắt đầu và Kết thúc trên thước kéo."""
        self.timeline.set_values(start_seconds, end_seconds)

    def update_end_marker_position(self, end_seconds):
        """Chỉ cập nhật điểm Kết thúc trên thước kéo, giữ nguyên điểm Bắt đầu."""
        current_start_val = self.timeline.start_val
        # Giao phó hoàn toàn việc xử lý ràng buộc cho hàm set_values
        self.timeline.set_values(current_start_val, end_seconds)

    def _on_entry_change(self, event=None):
        """Callback khi người dùng thay đổi giá trị trong ô Entry và nhấn Enter/FocusOut."""
        try:
            start_str = self.start_entry.get()
            end_str = self.end_entry.get()

            # Lấy giá trị, coi placeholder hoặc chuỗi rỗng là giá trị hiện tại của slider
            start_val = float(start_str) if start_str and start_str != self.start_placeholder else self.timeline.start_val
            end_val = float(end_str) if end_str and end_str != self.end_placeholder else self.timeline.end_val
            
            # Đảm bảo logic thời gian
            if start_val >= end_val:
                # Nếu người dùng nhập start lớn hơn end, tạm thời không cập nhật để tránh lỗi
                # Hoặc bạn có thể hiển thị một cảnh báo
                return

            self.timeline.set_values(start_val, end_val)
        except ValueError:
            # Bỏ qua nếu người dùng nhập không phải là số
            pass
        except Exception as e:
            self.controller.logger.warning(f"Lỗi khi cập nhật từ Entry: {e}")

    # --- THÊM MỚI: CÁC HÀM QUẢN LÝ GIAO DIỆN PLAYER ---
    def _create_player_widgets(self, parent):
        """Tạo các widget con cho khung nghe thử."""
        parent.columnconfigure(1, weight=1)

        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        self.play_btn = ttk.Button(control_frame, text="▶ Play", command=self.controller.play_pause_audio, width=8)
        self.play_btn.pack(side="top", pady=2)
        stop_btn = ttk.Button(control_frame, text="⏹ Stop", command=self.controller.stop_audio, width=8)
        stop_btn.pack(side="top", pady=2)

        slider_frame = ttk.Frame(parent)
        slider_frame.grid(row=0, column=1, sticky="ew")
        slider_frame.columnconfigure(0, weight=1)

        self.timeline = DualHandleSlider(slider_frame)
        self.timeline.grid(row=0, column=0, sticky="ew")
        
        # --- THAY ĐỔI: Kết nối các callback ---
        self.timeline.on_change_callback = self._on_slider_change
        self.timeline.on_seek_callback = self._on_timeline_seek

        self.time_label = ttk.Label(slider_frame, text="00:00:00 / 00:00:00")
        self.time_label.grid(row=1, column=0, sticky="e")

    def _on_timeline_seek(self, time_seconds, action):
        """
        Hàm callback được gọi từ thước kéo để ra lệnh cho controller.
        action có thể là 'play' hoặc 'pause'.
        """
        if action == 'play':
            self.controller.seek_audio(time_seconds)
        elif action == 'pause':
            self.controller.seek_and_pause(time_seconds)

    def toggle_player_visibility(self, visible):
        """Hiện hoặc ẩn khung nghe thử."""
        if visible:
            self.player_frame.grid()
        else:
            self.player_frame.grid_remove()

    def update_player_ui(self, duration):
        """Cập nhật giao diện nghe thử với thông tin file mới."""
        self.timeline.set_range(duration)
        self.update_timeline_indicator(0)
    
    def update_play_button_state(self, is_playing):
        def _update():
            if self.play_btn.winfo_exists():
                self.play_btn.config(text="❚❚ Pause" if is_playing else "▶ Play")
        
        # Luôn dùng after() để cập nhật UI từ bất kỳ luồng nào một cách an toàn
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(0, _update)

    def update_timeline_indicator(self, current_seconds):
        """Cập nhật con trỏ thời gian và label hiển thị."""
        def _update():
            # --- SỬA LỖI: Kiểm tra self.root thay vì self ---
            # self.root là frame chính của tab, nếu nó không tồn tại, ta không cập nhật nữa.
            if not self.root.winfo_exists(): 
                return
            
            self.timeline.update_indicator(current_seconds)
            
            total_duration_str = self.seconds_to_hhmmss(self.controller.audio_duration)
            current_time_str = self.seconds_to_hhmmss(current_seconds)
            self.time_label.config(text=f"{current_time_str} / {total_duration_str}")

        self.root.after(0, _update)

    def _on_slider_change(self, start_val, end_val):
        """Callback được gọi khi con trượt trên timeline thay đổi."""
        # Cập nhật các ô Entry
        self.start_entry.config(foreground="black")
        self.start_entry.delete(0, tk.END)
        self.start_entry.insert(0, f"{start_val:.3f}")

        self.end_entry.config(foreground="black")
        self.end_entry.delete(0, tk.END)
        self.end_entry.insert(0, f"{end_val:.3f}")

    def validate_button_states(self):
        """Kiểm tra điều kiện và kích hoạt/vô hiệu hóa các nút Bắt đầu."""
        # Nếu đang xử lý, vô hiệu hóa tất cả
        if self.controller.is_processing:
            self.cut_btn.config(state="disabled")
            self.merge_btn.config(state="disabled")
            return

        # Kiểm tra điều kiện cho nút Cắt
        can_cut = self.cut_input_var.get() and self.controller.cut_list
        self.cut_btn.config(state="normal" if can_cut else "disabled")

        # Kiểm tra điều kiện cho nút Ghép
        can_merge = len(self.controller.merge_list) >= 2
        self.merge_btn.config(state="normal" if can_merge else "disabled")

    def browse_cut_input(self):
        # --- SỬA ĐỔI: Dùng lại entry đã tạo, không tạo mới ---
        path = filedialog.askopenfilename(filetypes=[
            ("Audio/Video Files", "*.mp3 *.wav *.m4a *.aac *.flac *.mp4 *.mkv"),
            ("All files", "*.*")
        ])
        if path:
            self.cut_input_var.set(path)
            self.validate_button_states()
            
            # --- THÊM MỚI: Logic xử lý file nghe thử ---
            audio_exts = {'.mp3', '.wav', '.m4a', '.aac', '.flac'}
            file_ext = os.path.splitext(path)[1].lower()
            if file_ext in audio_exts:
                self.controller.load_audio_for_preview(path)
            else:
                self.controller.stop_audio() # Dừng phát nếu đang mở file khác
                self.toggle_player_visibility(False) # Ẩn player nếu không phải audio

    def on_start_focus_in(self, event):
        if self.start_entry.get() == self.start_placeholder:
            self.start_entry.delete(0, tk.END)
            self.start_entry.config(foreground="black")

    def on_start_focus_out(self, event):
        self._on_entry_change(event) # Gọi hàm xử lý chung
        if not self.start_entry.get():
            self.start_entry.insert(0, self.start_placeholder)
            self.start_entry.config(foreground="grey")

    def on_end_focus_in(self, event):
        if self.end_entry.get() == self.end_placeholder:
            self.end_entry.delete(0, tk.END)
            self.end_entry.config(foreground="black")

    def on_end_focus_out(self, event):
        self._on_entry_change(event) # Gọi hàm xử lý chung
        if not self.end_entry.get():
            self.end_entry.insert(0, self.end_placeholder)
            self.end_entry.config(foreground="grey")

    def add_cut(self):
        start_str = self.start_entry.get()
        end_str = self.end_entry.get()

        try:
            # Lấy giá trị, coi placeholder hoặc chuỗi rỗng là None
            start_seconds = float(start_str) if start_str not in [self.start_placeholder, ""] else None
            end_seconds = float(end_str) if end_str not in [self.end_placeholder, ""] else None

            # Kiểm tra nếu thiếu thông tin
            if start_seconds is None or end_seconds is None:
                self.show_message("warning", "Thiếu thông tin", "Vui lòng nhập cả thời gian bắt đầu và kết thúc.")
                return
                
            # Kiểm tra logic thời gian
            if start_seconds >= end_seconds:
                self.show_message("error", "Lỗi", "Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc.")
                return

            # Định dạng lại thời gian sang HH:MM:SS để hiển thị
            start_formatted = self.seconds_to_hhmmss(start_seconds)
            end_formatted = self.seconds_to_hhmmss(end_seconds)

            # Gọi controller để thêm vào danh sách
            self.controller.add_cut_segment(start_formatted, end_formatted)

            # Reset các ô nhập liệu về trạng thái placeholder
            self.start_entry.delete(0, tk.END)
            self.on_start_focus_out(None)
            self.end_entry.delete(0, tk.END)
            self.on_end_focus_out(None)
            
            # Kích hoạt lại việc kiểm tra trạng thái các nút
            self.validate_button_states()
            
        except ValueError:
            self.show_message("error", "Lỗi định dạng", "Vui lòng nhập số giây hợp lệ.")

    def remove_cut(self):
        selected = self.cut_listbox.curselection()
        if selected:
            self.controller.remove_cut_segment(selected)
            self.validate_button_states()
        else:
            self.show_message("warning", "Chưa chọn", "Vui lòng chọn một hoặc nhiều đoạn cắt để xóa.")
    
    def update_cut_listbox(self, cut_list):
        self.cut_listbox.delete(0, tk.END)
        for start, end in cut_list:
            self.cut_listbox.insert(tk.END, f"  [{start}  ->  {end}]")

    def add_files_to_merge(self):
        paths = filedialog.askopenfilenames(title="Chọn các file Video/Audio để ghép")
        if paths:
            self.controller.add_merge_files(paths)
            self.validate_button_states()

    def remove_from_merge(self):
        selected = self.merge_listbox.curselection()
        if selected:
            self.controller.remove_merge_files(selected)
            self.validate_button_states()

    def move_in_merge(self, direction):
        selected = self.merge_listbox.curselection()
        self.controller.move_merge_file(selected, direction)
        
    def update_merge_listbox(self, merge_list, new_selection_index=None):
        self.merge_listbox.delete(0, tk.END)
        for item in merge_list:
            self.merge_listbox.insert(tk.END, f"  {os.path.basename(item)}")
            self.validate_button_states()
        if new_selection_index is not None:
            self.merge_listbox.selection_clear(0, tk.END)
            self.merge_listbox.selection_set(new_selection_index)
            self.merge_listbox.activate(new_selection_index)
            self.merge_listbox.see(new_selection_index)

    def set_ui_state(self, state):
        is_processing = state == "processing"
        ui_state = "disabled" if is_processing else "normal"
        self.cut_btn.config(state=ui_state)
        self.merge_btn.config(state=ui_state)
        self.validate_button_states()

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

    def seconds_to_hhmmss(self, seconds):
        if seconds is None: return None
        if seconds < 0: seconds = 0
        td = datetime.timedelta(seconds=seconds)
        # Định dạng để luôn có dạng HH:MM:SS
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours:02}:{minutes:02}:{seconds:02}'

    def show_mixed_types_dialog(self, video_exts, audio_exts):
        """Hiển thị dialog tùy chỉnh khi phát hiện trộn lẫn video và audio."""
        
        # Tạo một cửa sổ Toplevel mới
        dialog = tk.Toplevel(self.root)
        dialog.title("Phát hiện xung đột loại file")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root) # Gắn dialog vào cửa sổ chính
        dialog.grab_set() # Modal: chặn tương tác với các cửa sổ khác
        
        # Lưu trữ lựa chọn của người dùng
        user_choice = tk.StringVar(value=None)
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill="both", expand=True)

        message = "Bạn không thể ghép lẫn lộn file video và audio.\nVui lòng chọn một hành động:"
        ttk.Label(main_frame, text=message, wraplength=370).pack(pady=(0, 15))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack()

        def set_choice_and_close(choice):
            user_choice.set(choice)
            dialog.destroy()

        # Tạo các nút động
        ttk.Button(
            button_frame, 
            text="Chỉ giữ lại file Video", 
            command=lambda: set_choice_and_close("keep_video")
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame, 
            text="Chỉ giữ lại file Audio", 
            command=lambda: set_choice_and_close("keep_audio")
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame, 
            text="Hủy bỏ", 
            command=dialog.destroy
        ).pack(side="left", padx=5)

        # Chờ cho đến khi dialog được đóng
        self.root.wait_window(dialog)
        
        return user_choice.get()    
