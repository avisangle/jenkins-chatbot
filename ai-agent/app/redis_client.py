"""
Redis client configuration and management
Handles Redis connection for session storage and caching
"""

import redis.asyncio as redis
from urllib.parse import urlparse
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Global Redis connection
redis_client = None

async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    
    try:
        # Parse Redis URL
        parsed_url = urlparse(settings.REDIS_URL)
        
        # Create Redis client
        redis_client = redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True,  # Automatically decode responses to strings
            retry_on_timeout=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test connection
        await redis_client.ping()
        
        logger.info("Redis initialized successfully",
                   host=parsed_url.hostname,
                   port=parsed_url.port,
                   db=parsed_url.path.lstrip('/') if parsed_url.path else '0')
        
    except Exception as e:
        logger.error("Redis initialization failed", error=str(e))
        raise

async def close_redis():
    """Close Redis connection"""
    global redis_client
    
    try:
        if redis_client:
            await redis_client.aclose()
            redis_client = None
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error("Error closing Redis connection", error=str(e))

async def get_redis() -> redis.Redis:
    """Get Redis connection"""
    if not redis_client:
        await init_redis()
    return redis_client

async def health_check() -> bool:
    """Check Redis health"""
    try:
        client = await get_redis()
        await client.ping()
        return True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False

# Redis utility functions
async def set_with_ttl(key: str, value: str, ttl_seconds: int) -> bool:
    """Set a key with TTL"""
    try:
        client = await get_redis()
        await client.setex(key, ttl_seconds, value)
        return True
    except Exception as e:
        logger.error("Error setting Redis key with TTL",
                    error=str(e),
                    key=key,
                    ttl=ttl_seconds)
        return False

async def get_key(key: str) -> str:
    """Get a key value"""
    try:
        client = await get_redis()
        return await client.get(key)
    except Exception as e:
        logger.error("Error getting Redis key",
                    error=str(e),
                    key=key)
        return None

async def delete_key(key: str) -> bool:
    """Delete a key"""
    try:
        client = await get_redis()
        result = await client.delete(key)
        return result > 0
    except Exception as e:
        logger.error("Error deleting Redis key",
                    error=str(e),
                    key=key)
        return False

async def exists_key(key: str) -> bool:
    """Check if key exists"""
    try:
        client = await get_redis()
        result = await client.exists(key)
        return result > 0
    except Exception as e:
        logger.error("Error checking Redis key existence",
                    error=str(e),
                    key=key)
        return False

async def get_ttl(key: str) -> int:
    """Get TTL for a key"""
    try:
        client = await get_redis()
        return await client.ttl(key)
    except Exception as e:
        logger.error("Error getting Redis key TTL",
                    error=str(e),
                    key=key)
        return -1

async def increment_counter(key: str, ttl_seconds: int = 3600) -> int:
    """Increment a counter with optional TTL"""
    try:
        client = await get_redis()
        
        # Use pipeline for atomic operation
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds)
        
        results = await pipe.execute()
        return results[0]  # Return the incremented value
        
    except Exception as e:
        logger.error("Error incrementing Redis counter",
                    error=str(e),
                    key=key)
        return 0

async def add_to_set(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    """Add value to a Redis set with TTL"""
    try:
        client = await get_redis()
        
        pipe = client.pipeline()
        pipe.sadd(key, value)
        pipe.expire(key, ttl_seconds)
        
        await pipe.execute()
        return True
        
    except Exception as e:
        logger.error("Error adding to Redis set",
                    error=str(e),
                    key=key,
                    value=value)
        return False

async def get_set_members(key: str) -> set:
    """Get all members of a Redis set"""
    try:
        client = await get_redis()
        return await client.smembers(key)
    except Exception as e:
        logger.error("Error getting Redis set members",
                    error=str(e),
                    key=key)
        return set()

async def cleanup_expired_keys(pattern: str) -> int:
    """Clean up expired keys matching pattern"""
    try:
        client = await get_redis()
        count = 0
        
        async for key in client.scan_iter(match=pattern):
            ttl = await client.ttl(key)
            if ttl == -1:  # Key exists but has no expiry
                # Set a default expiry
                await client.expire(key, 3600)  # 1 hour default
                count += 1
        
        if count > 0:
            logger.info("Set expiry for keys without TTL",
                       pattern=pattern,
                       count=count)
        
        return count
        
    except Exception as e:
        logger.error("Error cleaning up Redis keys",
                    error=str(e),
                    pattern=pattern)
        return 0