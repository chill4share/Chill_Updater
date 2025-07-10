import asyncio
from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserOfflineError, UserNotFoundError

async def _get_room_id_from_tiktoklive(username):
    client = TikTokLiveClient(unique_id=username)
    try:
        await client.start(fetch_live_check=True, fetch_room_info=False)
        return str(client.room_id)
    except (UserOfflineError, UserNotFoundError):
        return None
    except Exception:
        return None
    finally:
        await client.disconnect()

def get_room_id_with_tiktoklive(username):
    try:
        return asyncio.run(_get_room_id_from_tiktoklive(username))
    except RuntimeError as e:
        # Nếu đang trong một vòng event loop (ví dụ: tkinter + asyncio), thì dùng cách thay thế
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(_get_room_id_from_tiktoklive(username))
