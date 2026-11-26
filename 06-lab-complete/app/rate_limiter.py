"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""


"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r, redis_healthy


def check_rate_limit(key: str) -> None:
    limit = settings.rate_limit_per_minute
    window = 60
    now = time.time()
    rate_key = f"rate_limit:{key}"

    if redis_healthy():
        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(rate_key, 0, now - window)
            pipe.zcard(rate_key)
            pipe.zadd(rate_key, {f"{now}:{time.time_ns()}": now})
            pipe.expire(rate_key, window)
            results = pipe.execute()
            count = results[1]
            if count >= limit:
                r.zremrangebyscore(rate_key, now, now)
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(window)}
                )
            return
        except HTTPException:
            raise
        except Exception:
            pass
