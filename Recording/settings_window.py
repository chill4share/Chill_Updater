import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from Utils.ui_utils import center_dialog

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, current_cookies, save_callback):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        
        self.title("Cài đặt Cookies")
        self.resizable(False, False)

        self.save_callback = save_callback
        self.result = None
        
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # --- Phần nhập liệu Cookies ---
        cookies_frame = ttk.Frame(main_frame)
        cookies_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(cookies_frame, text="Cookie cho TikTok:", font=("-weight", "bold")).pack(fill="x")
        self.tiktok_cookie_text = scrolledtext.ScrolledText(cookies_frame, height=4, width=80, wrap=tk.WORD)
        self.tiktok_cookie_text.pack(fill="x", pady=(5, 10))
        if current_cookies.get("tiktok"):
            self.tiktok_cookie_text.insert("1.0", current_cookies["tiktok"])

        ttk.Label(cookies_frame, text="Cookie cho Douyin:", font=("-weight", "bold")).pack(fill="x")
        self.douyin_cookie_text = scrolledtext.ScrolledText(cookies_frame, height=4, width=80, wrap=tk.WORD)
        self.douyin_cookie_text.pack(fill="x", pady=5)
        if current_cookies.get("douyin"):
            self.douyin_cookie_text.insert("1.0", current_cookies["douyin"])

        # --- Phần hướng dẫn ---
        instructions_frame = ttk.LabelFrame(main_frame, text="Hướng dẫn lấy Cookie", padding=10)
        instructions_frame.pack(fill="x")

        instructions_text = """
1. Mở trang chủ TikTok hoặc Douyin trên trình duyệt (Chrome, Firefox...).
2. Đăng nhập vào tài khoản của bạn.
3. Nhấn phím F12 để mở Công cụ cho nhà phát triển (Developer Tools).
4. Chuyển sang tab "Network" (Mạng).
5. Trong tab Network, tìm và chọn mục "Fetch/XHR".
6. Tải lại trang (F5) hoặc thực hiện một hành động bất kỳ (vd: lướt xem video).
7. Một danh sách các yêu cầu mạng sẽ hiện ra. Chọn một yêu cầu bất kỳ (thường là các file có tên `check_alive/?aid=1988&app_language`, `webcast`, `live`, `aweme`...).
8. Trong cửa sổ chi tiết của yêu cầu đó, tìm mục "Request Headers" (Tiêu đề yêu cầu).
9. Tìm dòng có tên "cookie:", sao chép TOÀN BỘ giá trị của nó và dán vào ô tương ứng ở trên.
"""
        
        info_label = ttk.Label(instructions_frame, text=instructions_text, justify=tk.LEFT)
        info_label.pack(fill="x")

        # --- Các nút điều khiển ---
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill="x", pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Lưu & Đóng", command=self.save_and_close, style="Accent.TButton").pack(side="right")
        ttk.Button(buttons_frame, text="Hủy", command=self.destroy).pack(side="right", padx=10)

        center_dialog(self)
        self.wait_window()

    def save_and_close(self):
        new_cookies = {
            "tiktok": self.tiktok_cookie_text.get("1.0", tk.END).strip(),
            "douyin": self.douyin_cookie_text.get("1.0", tk.END).strip()
        }
        
        if self.save_callback:
            if self.save_callback(new_cookies):
                messagebox.showinfo("Thành công", "Đã lưu cài đặt cookies thành công.", parent=self)
                self.destroy()
            else:
                messagebox.showerror("Lỗi", "Không thể lưu file cookies. Vui lòng kiểm tra lại.", parent=self)
        else:
            self.destroy()
