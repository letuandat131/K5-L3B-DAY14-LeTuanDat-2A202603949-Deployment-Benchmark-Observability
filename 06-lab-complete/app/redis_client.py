"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""

"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""
import redis
from app.config import settings

_client = None
_client_url = None


def get_redis():
    global _client, _client_url
    url = settings.redis_url
    if not url:
        return None
    if _client is None or _client_url != url:
        try:
            _client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            _client_url = url
        except Exception:
            return None
    return _client


class RedisProxy:
    def __getattr__(self, name):
        client = get_redis()
        if client is None:
            raise redis.ConnectionError("Redis not available")
        return getattr(client, name)


r = RedisProxy()


def redis_healthy() -> bool:
    try:
        url = settings.redis_url
        if not url:
            return False
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1)
        return bool(client.ping())
    except Exception:
        return False
