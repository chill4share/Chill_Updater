# Utils/config.py

# =================================================
# CẤU HÌNH DÙNG CHUNG
# =================================================
MAX_ROWS = 15
MAX_ACTIVE_USERS = 5

# --- Cookie cho TikTok (bản quốc tế) ---
COOKIES = {
    # Dán cookie TikTok của bạn vào đây nếu cần
}

# --- THÊM MỚI: Cookie cho Douyin (bản Trung Quốc) ---
# !!! BẮT BUỘC: Dán cookie Douyin hợp lệ của bạn vào đây
DOUYIN_COOKIE = "SEARCH_RESULT_LIST_TYPE=%22single%22; enter_pc_once=1; UIFID=4be83ecefa579a300714166db9e569bafd8689fc248d1e190e384db8df203b813bdac59fe2520b65d6008303abb0511c79db5985945991b7cadac8dff16b422e878ef583b94be16fbb0dd703cba46891915e04e8e5bfdcbe83d802dd884def05ea1da08b81bbeee598f7a89732151a2b31dc7c63addbe93fe1b738015ddcfc73000f2f8bd9d3e958bac6b0a90e17362a55dfebbaf00c51ecd47421f26520b424; passport_csrf_token=9d6be2e3e71ab352d112733feaeccb04; passport_csrf_token_default=9d6be2e3e71ab352d112733feaeccb04; odin_tt=f08418ee748161d83f247da89aa44b249a8614c90c959bae598abfd482aa25a6f751b658f861ee6c24b2d85dc8afb7376cc2ca4ccc1f2912a554a5d81de6d98ea84af7c141255323bdc6f760a0c40e34; __security_mc_1_s_sdk_cert_key=a9ac1a04-4473-ae0f; __security_mc_1_s_sdk_sign_data_key_web_protect=bdd19137-4e5e-ac7c; __security_mc_1_s_sdk_crypt_sdk=40bffb56-4378-86ea; bd_ticket_guard_client_web_domain=2; x-web-secsdk-uid=96b70174-e93a-455f-90ff-dfc32250058d; xgplayer_device_id=80433848314; xgplayer_user_id=879732455788; has_avx2=null; device_web_cpu_core=4; device_web_memory_size=8; live_use_vvc=%22false%22; csrf_session_id=f1aa19d34a5d637d22ef4640dc6b7c4f; fpk1=U2FsdGVkX19tS3vqj+P0QTGgQZoiq4r/UDCLBQehxMdbVPbkm29TAOq3tJqIXNU+pZ5mWhaLVjb9pLj6dMnhGg==; fpk2=7ddeda88d0c599cc494da0dece6554d5; my_rd=2; download_guide=%223%2F20250725%2F1%22; webcast_leading_last_show_time=1753428823036; webcast_leading_total_show_times=1; webcast_local_quality=sd; stream_recommend_feed_params=%22%7B%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22screen_width%5C%22%3A1920%2C%5C%22screen_height%5C%22%3A1080%2C%5C%22browser_online%5C%22%3Atrue%2C%5C%22cpu_core_num%5C%22%3A4%2C%5C%22device_memory%5C%22%3A8%2C%5C%22downlink%5C%22%3A3.35%2C%5C%22effective_type%5C%22%3A%5C%224g%5C%22%2C%5C%22round_trip_time%5C%22%3A100%7D%22; strategyABtestKey=%221753493843.335%22; ttwid=1%7CLcDY2htAKmQSdMhc7WddNF6eDoqSgZdOlAjm9tvazd8%7C1753493853%7Ca5ebf3d7ffe1a166dc00fec0ca065fb361be91f5c7ef64c86165c66c2e6890d9; volume_info=%7B%22volume%22%3A0.6%2C%22isMute%22%3Atrue%7D; home_can_add_dy_2_desktop=%221%22; biz_trace_id=82449019; bd_ticket_guard_client_data=eyJiZC10aWNrZXQtZ3VhcmQtdmVyc2lvbiI6MiwiYmQtdGlja2V0LWd1YXJkLWl0ZXJhdGlvbi12ZXJzaW9uIjoxLCJiZC10aWNrZXQtZ3VhcmQtcmVlLXB1YmxpYy1rZXkiOiJCSTV0UlhMWDFMeGF2TUVFTVRYcmwrYTd2eXp3amFMZzFHdE9BRlNqM055RDVBSFg5VjBNeDRBK2NRK0VaSC96WWRxSTQ5QlQ2UTBPZzMzL0lISVJQcDA9IiwiYmQtdGlja2V0LWd1YXJkLXdlYi12ZXJzaW9uIjoyfQ%3D%3D; WallpaperGuide=%7B%22showTime%22%3A1753428627549%2C%22closeTime%22%3A0%2C%22showCount%22%3A1%2C%22cursor1%22%3A23%2C%22cursor2%22%3A6%2C%22hoverTime%22%3A1753428729195%7D; stream_player_status_params=%22%7B%5C%22is_auto_play%5C%22%3A0%2C%5C%22is_full_screen%5C%22%3A0%2C%5C%22is_full_webscreen%5C%22%3A0%2C%5C%22is_mute%5C%22%3A1%2C%5C%22is_speed%5C%22%3A1%2C%5C%22is_visible%5C%22%3A0%7D%22; __ac_signature=_02B4Z6wo00f01MoKIwwAAIDAuddhrs-7p7DKKieAAFoM0f; __live_version__=%221.1.3.6365%22; xg_device_score=6.904764705882353; live_can_add_dy_2_desktop=%221%22; IsDouyinActive=false; INVISIBLE_QUERY=%22action_type%3Dclick%26enter_from_merge%3Dweb_search%26enter_method%3Dweb_video_head%26enter_method_temai%3Dweb_video_head%26group_id%3Dundefined%26is_livehead_preview_mini_window_show%3D%26live_position%3Dundefined%26mini_window_show_type%3D%26request_id%3D202507260938298A207007041181CA2EC0%26room_id%3D7531178974266018596%26search_tab%3Daweme_live%22"


# =================================================
# CẤU HÌNH API RIÊNG CHO TỪNG NỀN TẢNG
# =================================================

# --- Cấu hình cho Douyin ---
DOUYIN_CONFIG = {
    'api_endpoints': {
        'web_enter': "https://live.douyin.com/webcast/room/web/enter/"
    },
    'api_params': {
        "aid": "6383", "app_name": "douyin_web", "live_id": "1",
        "device_platform": "web", "language": "zh-CN", "enter_from_merge": "web_live",
        "cookie_enabled": "true", "screen_width": "1920", "screen_height": "1080",
        "browser_language": "en-US", "browser_platform": "Win32", "browser_name": "Chrome",
        "browser_version": "125.0.0.0",
    }
}
#=================================================

# --- Cấu hình cho tab Recording ---
MAX_ROWS = 10
MAX_ACTIVE_USERS = 10

TIKTOK_CONFIG = {
    "api_endpoints": {
        "base_url": "https://www.tiktok.com",
        "webcast_url": "https://webcast.tiktok.com",
        "live_detail": "/api/live/detail/?aid=1988&roomID={room_id}",
        "room_info": "/webcast/room/info/?aid=1988&room_id={room_id}",
        "check_alive": "/webcast/room/check_alive/?aid=1988&room_ids={room_id}",
        "user_live": "/@{user}/live",
        "user_detail": "/api/user/detail/?uniqueId={user}&aid=1988"
    }
}

# Nội dung README cho cửa sổ "About"
README_CONTENT = """
TikTok Live Recorder - Hướng Dẫn Sử Dụng

1. Mô tả

TikTok Live Recorder giúp bạn ghi hình livestream TikTok, lưu thành file MP4 và chuyển sang MP3 nếu cần.
Chương trình hỗ trợ ghi nhiều user (tối đa 10) cùng lúc và có chế độ tự động kiểm tra, ghi hình khi user livestream.
Sử dụng File -> Exit để thoát khẩn cấp nếu chương trình quá tải (chú ý: sẽ không có dữ liệu nào được lưu lại).

2. Yêu cầu

Windows 10 64-bit (build 19041 trở lên)
CPU: Tối thiểu: Intel Core i7-8700 hoặc AMD Ryzen 5 5600X.
RAM: Tối thiểu: 8 GB DDR4.
Ổ Cứng: SSD với tốc độ ghi tốt (~500 MB/s).
Mạng: Kết nối ổn định, băng thông tải xuống > 40 Mbps.

3. Hướng dẫn sử dụng

Bước 1: Chạy chương trình

Nhấp đúp vào file thực thi của chương trình để mở.

Bước 2: Ghi hình

Ở một hàng trống, nhập username TikTok (ví dụ: @abc) vào ô "Nhập tên người dùng...".
Chọn chế độ:
    - Thủ công: Ghi ngay lập tức nếu user đang livestream.
    - Tự động: Tự động kiểm tra và sẽ bắt đầu ghi hình ngay khi user livestream.
Tùy chọn:
    - Tích "🎵" để tự động chuyển file video sang MP3 sau khi ghi xong.
    - Nhập thời gian ghi (tính bằng giây) vào ô "Thời gian (s)" nếu muốn giới hạn thời gian ghi, hoặc để trống để ghi không giới hạn.
Nhấn "▶" để bắt đầu.
Nhấn "■" để dừng và lưu file.
Nhấn "➖" để hủy ghi hình (không lưu file) và xóa hàng.
Nhấn "➕" để thêm một hàng mới.

Bước 3: Chuyển đổi MP3 thủ công

Nhấn nút "Convert to MP3".
Trong cửa sổ mới, chọn file MP4/FLV cần chuyển, chọn thư mục lưu (nếu để trống sẽ lưu cùng thư mục với file gốc), và nhấn "Chuyển đổi".

4. Lưu ý

File video và audio được lưu trong thư mục Output/<username> (thư mục này được tạo cùng cấp với file chạy chương trình).
Nếu gặp lỗi "Quốc gia bị chặn" hoặc "Tài khoản riêng tư", có thể cần cập nhật cookies.
File recording.txt lưu lại nhật ký hoạt động, hãy gửi file này nếu cần báo lỗi.

5. Hỗ trợ

Gặp vấn đề? Liên hệ người hỗ trợ và gửi file recording.txt.
"""
