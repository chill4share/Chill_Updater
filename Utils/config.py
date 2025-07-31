MAX_ROWS = 15
MAX_ACTIVE_USERS = 5

COOKIES = {}

TIKTOK_RECORDER_COOKIE_STRING = ""

DOUYIN_COOKIE = ""

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

"""
