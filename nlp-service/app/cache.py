import hashlib
import os
import logging
from typing import Optional
import redis

logger = logging.getLogger("nlp-service")

_redis_client: Optional[redis.Redis] = None

def _get_redis() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/1")
        try:
            _redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3)
            _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis connection failed, caching disabled: {e}")
            _redis_client = None
    return _redis_client

def get_cache_key(task: str, text: str, tone_target: Optional[str] = None, max_length: Optional[int] = None) -> str:
    key_base = f"{task}:{tone_target}:{max_length}:{text}"
    return hashlib.sha256(key_base.encode()).hexdigest()

def get_cached(key: str) -> Optional[str]:
    try:
        client = _get_redis()
        if client is None:
            return None
        return client.get(key)
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")
        return None

def set_cached(key: str, value: str, ttl: int = 3600) -> None:
    try:
        client = _get_redis()
        if client is None:
            return
        client.setex(key, ttl, value)
    except Exception as e:
        logger.warning(f"Redis set failed: {e}")
