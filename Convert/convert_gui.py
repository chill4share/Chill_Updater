# Convert/convert_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from .convert_controller import ConvertController

# --- Dữ liệu tùy chọn, không thay đổi ---
MP3_BITRATE_OPTIONS = {"128 kbps": "128k", "192 kbps": "192k", "256 kbps": "256k", "320 kbps": "320k"}
WAV_BIT_DEPTH_OPTIONS = {"16-bit PCM": "pcm_s16le", "24-bit PCM": "pcm_s24le"}
SAMPLE_RATE_OPTIONS = {"22050 Hz": "22050", "44100 Hz": "44100", "48000 Hz": "48000", "96000 Hz": "96000"}
CHANNEL_OPTIONS = {"Giữ nguyên": "keep", "Mono": "1", "Stereo": "2"}


class ConvertGUI:
    def __init__(self, root_frame, project_root, thread_pool):
        self.root = root_frame
        self.controller = ConvertController(self, project_root, thread_pool, {
            "mp3_bitrates": MP3_BITRATE_OPTIONS,
            "wav_bit_depths": WAV_BIT_DEPTH_OPTIONS,
            "sample_rates": SAMPLE_RATE_OPTIONS,
            "channels": CHANNEL_OPTIONS
        })

        self.output_placeholder = "Để trống sẽ lưu vào thư mục Convert_Output"

        # Biến điều khiển
        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.to_mp3_var = tk.BooleanVar(value=True)
        self.to_wav_var = tk.BooleanVar(value=False)

        # Biến tùy chọn
        self.mp3_sample_rate_var = tk.StringVar(value='44100 Hz')
        self.mp3_bitrate_var = tk.StringVar(value='192 kbps')
        self.mp3_channels_var = tk.StringVar(value='Giữ nguyên')

        self.wav_sample_rate_var = tk.StringVar(value='44100 Hz')
        self.wav_bit_depth_var = tk.StringVar(value='16-bit PCM')
        self.wav_channels_var = tk.StringVar(value='Giữ nguyên')

        self.speed_var = tk.DoubleVar(value=1.0)
        self.pitch_var = tk.DoubleVar(value=0.0)

        self.create_widgets()
        self.toggle_options_ui()

    # --- HÀM MỚI: Xử lý việc reset hiệu ứng ---
    def reset_effects(self):
        """Đặt lại giá trị của Tốc độ và Cao độ về mặc định."""
        self.speed_var.set(1.0)
        self.pitch_var.set(0.0)
        # Cập nhật lại cả label hiển thị
        self.speed_label.config(text="1.00x")
        self.pitch_label.config(text="0.0x")

    def _create_format_options_frame(self, parent, text, rate_var, rate_vals,
                                     quality_var, quality_map, quality_label,
                                     channel_var, channel_map):
        frame = ttk.LabelFrame(parent, text=text, padding=5)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Tần số:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(frame, textvariable=rate_var, values=rate_vals, state="readonly").grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(frame, text=quality_label).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(frame, textvariable=quality_var, values=list(quality_map.keys()), state="readonly").grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(frame, text="Kênh:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(frame, textvariable=channel_var, values=list(channel_map.keys()), state="readonly").grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        return frame

    def create_widgets(self):
        from Utils.ui_utils import create_tab_title
        create_tab_title(self.root, "Chuyển đổi định dạng Video & Audio")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(4, weight=1)

        input_frame = ttk.LabelFrame(self.root, text="1. Chọn File Đầu vào", padding=10)
        input_frame.pack(side="top", fill="x", padx=10, pady=5)
        input_frame.columnconfigure(0, weight=1)
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_path_var)
        self.input_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(input_frame, text="Duyệt...", command=self.browse_input).grid(row=0, column=1, padx=(5, 0))

        settings_frame = ttk.LabelFrame(self.root, text="2. Cài đặt Chuyển đổi", padding=10)
        settings_frame.pack(side="top", fill="x", padx=10, pady=5)
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)

        target_frame = ttk.Frame(settings_frame)
        target_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Label(target_frame, text="Mục tiêu:").pack(side="left")
        self.mp3_check = ttk.Checkbutton(target_frame, text="MP3", variable=self.to_mp3_var, command=self.toggle_options_ui)
        self.mp3_check.pack(side="left", padx=10)
        self.wav_check = ttk.Checkbutton(target_frame, text="WAV", variable=self.to_wav_var, command=self.toggle_options_ui)
        self.wav_check.pack(side="left")

        mp3_sample_rates = [k for k, v in SAMPLE_RATE_OPTIONS.items() if v in ["22050", "44100", "48000"]]
        self.mp3_options_frame = self._create_format_options_frame(
            settings_frame, "Tùy chọn MP3",
            self.mp3_sample_rate_var, mp3_sample_rates,
            self.mp3_bitrate_var, MP3_BITRATE_OPTIONS, "Bitrate:",
            self.mp3_channels_var, CHANNEL_OPTIONS
        )
        self.mp3_options_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))

        wav_sample_rates = [k for k, v in SAMPLE_RATE_OPTIONS.items() if v in ["44100", "48000", "96000"]]
        self.wav_options_frame = self._create_format_options_frame(
            settings_frame, "Tùy chọn WAV",
            self.wav_sample_rate_var, wav_sample_rates,
            self.wav_bit_depth_var, WAV_BIT_DEPTH_OPTIONS, "Bit Depth:",
            self.wav_channels_var, CHANNEL_OPTIONS
        )
        self.wav_options_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        # --- CẬP NHẬT KHUNG HIỆU ỨNG ---
        effects_frame = ttk.LabelFrame(settings_frame, text="Hiệu ứng Audio", padding=5)
        effects_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        effects_frame.columnconfigure(1, weight=1) # Cột chứa thanh trượt co giãn

        ttk.Label(effects_frame, text="Tốc độ:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Scale(effects_frame, from_=0.5, to=2.0, variable=self.speed_var, orient="horizontal", command=lambda v: self.speed_label.config(text=f"{float(v):.2f}x")).grid(row=0, column=1, sticky="ew", padx=5)
        self.speed_label = ttk.Label(effects_frame, text="1.00x", width=10)
        self.speed_label.grid(row=0, column=2, padx=5)

        ttk.Label(effects_frame, text="Cao độ:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Scale(effects_frame, from_=-6, to=6, variable=self.pitch_var, orient="horizontal", command=lambda v: self.pitch_label.config(text=f"{float(v):.1f}x")).grid(row=1, column=1, sticky="ew", padx=5)
        self.pitch_label = ttk.Label(effects_frame, text="0.0x", width=10)
        self.pitch_label.grid(row=1, column=2, padx=5)

        # --- THÊM NÚT RESET ---
        reset_button = ttk.Button(effects_frame, text="Reset", command=self.reset_effects, width=7)
        reset_button.grid(row=0, column=3, rowspan=2, sticky="ns", padx=(10, 5), pady=2)


        # --- Khung Đầu ra ---
        output_frame = ttk.LabelFrame(self.root, text="3. Chọn Nơi lưu", padding=10)
        output_frame.pack(side="top", fill="x", padx=10, pady=5)
        output_frame.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_path_var)
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_entry.insert(0, self.output_placeholder)
        self.output_entry.config(foreground="grey")
        self.output_entry.bind("<FocusIn>", self.on_output_focus_in)
        self.output_entry.bind("<FocusOut>", self.on_output_focus_out)
        ttk.Button(output_frame, text="Duyệt...", command=self.browse_output).grid(row=0, column=1, padx=(5, 0))

        # --- Khung điều khiển và trạng thái ---
        action_frame = ttk.Frame(self.root)
        action_frame.pack(side="top", pady=10)
        self.convert_btn = ttk.Button(action_frame, text="BẮT ĐẦU CHUYỂN ĐỔI", command=self.controller.start_conversion, style="Accent.TButton")
        self.convert_btn.pack()

        status_frame = ttk.LabelFrame(self.root, text="Nhật ký", padding=10)
        status_frame.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        status_frame.rowconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=8, font=('Consolas', 9), wrap=tk.WORD, state="disabled")
        self.status_text.grid(row=0, column=0, sticky="nsew")

    def on_output_focus_in(self, event):
        if self.output_entry.get() == self.output_placeholder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.config(foreground="black")

    def on_output_focus_out(self, event):
        if not self.output_entry.get():
            self.output_entry.insert(0, self.output_placeholder)
            self.output_entry.config(foreground="grey")

    def browse_input(self):
        file_path = filedialog.askopenfilename(title="Chọn file Video hoặc Audio", filetypes=[
            ("Media Files", "*.mp4 *.flv *.mkv *.mov *.avi *.wmv *.mp3 *.wav"),
            ("All Files", "*.*")
        ])
        if file_path:
            self.input_path_var.set(file_path)

    def browse_output(self):
        dir_path = filedialog.askdirectory(title="Chọn thư mục lưu file")
        if dir_path:
            self.output_path_var.set(dir_path)

    def toggle_options_ui(self):
        self.mp3_options_frame.grid() if self.to_mp3_var.get() else self.mp3_options_frame.grid_remove()
        self.wav_options_frame.grid() if self.to_wav_var.get() else self.wav_options_frame.grid_remove()

    def set_ui_state(self, state):
        if state == "converting":
            self.convert_btn.config(state="disabled", text="ĐANG CHUYỂN ĐỔI...")
        else:
            self.convert_btn.config(state="normal", text="BẮT ĐẦU CHUYỂN ĐỔI")

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
