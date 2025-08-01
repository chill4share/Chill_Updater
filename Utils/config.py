# /Utils/config.py (Nội dung hoàn chỉnh)

MAX_ROWS = 15
MAX_ACTIVE_USERS = 5


# --- Các chuỗi cookie của bạn không thay đổi ---
FALLBACK_TIKTOK_COOKIE  = ""
FALLBACK_DOUYIN_COOKIE  = ""

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

README_CONTENT = """
AaBbCc
"""

GITHUB_URL = "https://github.com/chill4share/Chill_Updater"

# === Cấu hình mới cho việc chuyển đổi MP3 ===
MP3_PROFILES = {
    "default": {
        "display": "Giữ nguyên gốc (128kbps)",
        "params": ["-vn", "-acodec", "mp3", "-ab", "128k"]
    },
    "profile1": {
        "display": "Nâng cao 1 (Gốc, 44.1kHz, 0.92x, +0.2p)",
        "params": ["-vn", "-acodec", "mp3", "-ar", "44100", "-af", "atempo=0.92,asetrate=44100*1.2,aresample=44100"]
    },
    "profile2": {
        "display": "Nâng cao 2 (Gốc, 48kHz, 0.93x, +0.3p)",
        "params": ["-vn", "-acodec", "mp3", "-ar", "48000", "-af", "atempo=0.93,asetrate=48000*1.3,aresample=48000"]
    }
}
