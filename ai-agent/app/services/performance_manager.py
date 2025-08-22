"""
Performance Optimization Manager - Connection pooling, caching, and performance optimization
Provides production-grade performance and scalability
"""

import asyncio
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
import structlog
import weakref

logger = structlog.get_logger(__name__)

@dataclass
class CacheItem:
    """Cache item with metadata"""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if cache item is expired"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """Update access information"""
        self.access_count += 1
        self.last_accessed = time.time()

@dataclass
class PerformanceMetrics:
    """Performance metrics tracking"""
    operation_name: str
    total_calls: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    error_count: int = 0
    last_call_time: float = 0.0
    
    @property
    def average_duration_ms(self) -> float:
        return self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        total_cache_requests = self.cache_hits + self.cache_misses
        return self.cache_hits / total_cache_requests if total_cache_requests > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        return (self.total_calls - self.error_count) / self.total_calls if self.total_calls > 0 else 0.0

class IntelligentCache:
    """Intelligent cache with TTL, LRU eviction, and size management"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheItem] = {}
        self.access_order: OrderedDict = OrderedDict()
        self._lock = asyncio.Lock()
        self._size_bytes = 0
        self._max_size_bytes = 100 * 1024 * 1024  # 100MB default
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        
        async with self._lock:
            cache_item = self.cache.get(key)
            
            if cache_item is None:
                return None
            
            if cache_item.is_expired:
                await self._remove_item(key)
                return None
            
            # Update access information
            cache_item.touch()
            self.access_order.move_to_end(key)
            
            return cache_item.value
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set item in cache"""
        
        if ttl is None:
            ttl = self.default_ttl
        
        async with self._lock:
            # Calculate size
            try:
                serialized = json.dumps(value, default=str)
                size_bytes = len(serialized.encode('utf-8'))
            except:
                size_bytes = 1024  # Estimate for non-serializable objects
            
            # Check if we need to make room
            while (len(self.cache) >= self.max_size or 
                   self._size_bytes + size_bytes > self._max_size_bytes):
                if not await self._evict_lru():
                    return False  # Cannot make room
            
            # Remove existing item if updating
            if key in self.cache:
                await self._remove_item(key)
            
            # Create cache item
            expires_at = time.time() + ttl if ttl > 0 else None
            cache_item = CacheItem(
                key=key,
                value=value,
                created_at=time.time(),
                expires_at=expires_at,
                size_bytes=size_bytes
            )
            
            self.cache[key] = cache_item
            self.access_order[key] = True
            self._size_bytes += size_bytes
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete item from cache"""
        
        async with self._lock:
            if key in self.cache:
                await self._remove_item(key)
                return True
            return False
    
    async def clear(self):
        """Clear all cache items"""
        
        async with self._lock:
            self.cache.clear()
            self.access_order.clear()
            self._size_bytes = 0
    
    async def _remove_item(self, key: str):
        """Remove item from cache (internal)"""
        
        if key in self.cache:
            cache_item = self.cache[key]
            del self.cache[key]
            self.access_order.pop(key, None)
            self._size_bytes -= cache_item.size_bytes
    
    async def _evict_lru(self) -> bool:
        """Evict least recently used item"""
        
        if not self.access_order:
            return False
        
        # Get least recently used key
        lru_key = next(iter(self.access_order))
        await self._remove_item(lru_key)
        
        return True
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired items"""
        
        while True:
            try:
                await asyncio.sleep(60)  # Clean every minute
                
                async with self._lock:
                    expired_keys = []
                    for key, cache_item in self.cache.items():
                        if cache_item.is_expired:
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        await self._remove_item(key)
                    
                    if expired_keys:
                        logger.debug("Cleaned expired cache items", count=len(expired_keys))
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cache cleanup", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        
        return {
            "total_items": len(self.cache),
            "max_size": self.max_size,
            "size_bytes": self._size_bytes,
            "max_size_bytes": self._max_size_bytes,
            "utilization_percent": (len(self.cache) / self.max_size) * 100,
            "memory_utilization_percent": (self._size_bytes / self._max_size_bytes) * 100
        }

class ConnectionPool:
    """Async connection pool for MCP servers"""
    
    def __init__(self, server_url: str, max_connections: int = 10, 
                 connection_timeout: float = 30.0):
        self.server_url = server_url
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        
        self._pool: List[Any] = []
        self._used_connections: Set[Any] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        
        # Connection factory
        self._connection_factory: Optional[Callable] = None
    
    def set_connection_factory(self, factory: Callable[[], Any]):
        """Set connection factory function"""
        self._connection_factory = factory
    
    async def acquire(self) -> Any:
        """Acquire connection from pool"""
        
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        async with self._lock:
            # Try to get existing connection from pool
            if self._pool:
                connection = self._pool.pop()
                self._used_connections.add(connection)
                return connection
            
            # Create new connection if under limit
            if len(self._used_connections) < self.max_connections:
                if not self._connection_factory:
                    raise RuntimeError("Connection factory not set")
                
                connection = await asyncio.wait_for(
                    self._connection_factory(),
                    timeout=self.connection_timeout
                )
                self._used_connections.add(connection)
                return connection
            
            # Wait for connection to become available
            # In a real implementation, this would use a condition variable
            raise RuntimeError("Connection pool exhausted")
    
    async def release(self, connection: Any):
        """Release connection back to pool"""
        
        async with self._lock:
            if connection in self._used_connections:
                self._used_connections.remove(connection)
                
                if not self._closed and len(self._pool) < self.max_connections:
                    self._pool.append(connection)
                else:
                    # Close excess connections
                    await self._close_connection(connection)
    
    async def _close_connection(self, connection: Any):
        """Close individual connection"""
        try:
            if hasattr(connection, 'close'):
                await connection.close()
        except Exception as e:
            logger.warning("Error closing connection", error=str(e))
    
    async def close(self):
        """Close connection pool"""
        
        async with self._lock:
            self._closed = True
            
            # Close all connections
            all_connections = list(self._pool) + list(self._used_connections)
            for connection in all_connections:
                await self._close_connection(connection)
            
            self._pool.clear()
            self._used_connections.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        
        return {
            "server_url": self.server_url,
            "max_connections": self.max_connections,
            "available_connections": len(self._pool),
            "used_connections": len(self._used_connections),
            "total_connections": len(self._pool) + len(self._used_connections),
            "closed": self._closed
        }

class PerformanceManager:
    """Performance management and optimization"""
    
    def __init__(self):
        self.cache = IntelligentCache()
        self.connection_pools: Dict[str, ConnectionPool] = {}
        self.metrics: Dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        self._operation_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Request batching
        self._batch_queues: Dict[str, List] = defaultdict(list)
        self._batch_timers: Dict[str, asyncio.Task] = {}
        self._batch_size = 10
        self._batch_timeout = 1.0  # seconds
    
    async def cached_operation(self, key: str, operation: Callable, 
                             ttl: Optional[float] = None, 
                             cache_key_prefix: str = "op") -> Any:
        """Execute operation with caching"""
        
        # Create cache key
        cache_key = f"{cache_key_prefix}:{key}"
        
        # Try cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result is not None:
            self._record_cache_hit(operation.__name__)
            return cached_result
        
        # Execute operation and cache result
        self._record_cache_miss(operation.__name__)
        
        start_time = time.time()
        try:
            result = await operation()
            duration_ms = (time.time() - start_time) * 1000
            
            # Cache successful result
            await self.cache.set(cache_key, result, ttl)
            
            # Record metrics
            self._record_operation_success(operation.__name__, duration_ms)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._record_operation_error(operation.__name__, duration_ms)
            raise
    
    async def with_connection_pool(self, server_url: str, operation: Callable, 
                                 **pool_kwargs) -> Any:
        """Execute operation using connection pool"""
        
        # Get or create connection pool
        if server_url not in self.connection_pools:
            self.connection_pools[server_url] = ConnectionPool(server_url, **pool_kwargs)
        
        pool = self.connection_pools[server_url]
        
        # Acquire connection
        connection = await pool.acquire()
        
        try:
            return await operation(connection)
        finally:
            await pool.release(connection)
    
    async def batched_operation(self, batch_key: str, operation_data: Any,
                              batch_processor: Callable[[List], List],
                              batch_size: Optional[int] = None,
                              batch_timeout: Optional[float] = None) -> Any:
        """Execute operation with request batching"""
        
        batch_size = batch_size or self._batch_size
        batch_timeout = batch_timeout or self._batch_timeout
        
        # Add to batch queue
        future = asyncio.Future()
        batch_item = (operation_data, future)
        
        async with self._operation_locks[batch_key]:
            self._batch_queues[batch_key].append(batch_item)
            
            # Check if batch is full
            if len(self._batch_queues[batch_key]) >= batch_size:
                await self._process_batch(batch_key, batch_processor)
            else:
                # Set timer if not already set
                if batch_key not in self._batch_timers:
                    self._batch_timers[batch_key] = asyncio.create_task(
                        self._batch_timeout_handler(batch_key, batch_processor, batch_timeout)
                    )
        
        return await future
    
    async def _batch_timeout_handler(self, batch_key: str, batch_processor: Callable,
                                   timeout: float):
        """Handle batch timeout"""
        
        await asyncio.sleep(timeout)
        
        async with self._operation_locks[batch_key]:
            if batch_key in self._batch_queues and self._batch_queues[batch_key]:
                await self._process_batch(batch_key, batch_processor)
    
    async def _process_batch(self, batch_key: str, batch_processor: Callable):
        """Process batch of operations"""
        
        if not self._batch_queues[batch_key]:
            return
        
        batch_items = self._batch_queues[batch_key].copy()
        self._batch_queues[batch_key].clear()
        
        # Cancel timer
        if batch_key in self._batch_timers:
            self._batch_timers[batch_key].cancel()
            del self._batch_timers[batch_key]
        
        try:
            # Extract operation data
            batch_data = [item[0] for item in batch_items]
            
            # Process batch
            results = await batch_processor(batch_data)
            
            # Set results
            for i, (_, future) in enumerate(batch_items):
                if i < len(results):
                    future.set_result(results[i])
                else:
                    future.set_exception(IndexError("Batch result missing"))
                    
        except Exception as e:
            # Set error for all futures
            for _, future in batch_items:
                future.set_exception(e)
    
    def _record_cache_hit(self, operation_name: str):
        """Record cache hit"""
        metrics = self.metrics[operation_name]
        metrics.cache_hits += 1
    
    def _record_cache_miss(self, operation_name: str):
        """Record cache miss"""
        metrics = self.metrics[operation_name]
        metrics.cache_misses += 1
    
    def _record_operation_success(self, operation_name: str, duration_ms: float):
        """Record successful operation"""
        metrics = self.metrics[operation_name]
        metrics.total_calls += 1
        metrics.total_duration_ms += duration_ms
        metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
        metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)
        metrics.last_call_time = time.time()
    
    def _record_operation_error(self, operation_name: str, duration_ms: float):
        """Record operation error"""
        metrics = self.metrics[operation_name]
        metrics.total_calls += 1
        metrics.error_count += 1
        metrics.total_duration_ms += duration_ms
        metrics.last_call_time = time.time()
    
    async def optimize_performance(self):
        """Run performance optimization tasks"""
        
        logger.info("Running performance optimization")
        
        # Analyze slow operations
        slow_operations = []
        for name, metrics in self.metrics.items():
            if metrics.average_duration_ms > 1000:  # > 1 second average
                slow_operations.append((name, metrics.average_duration_ms))
        
        if slow_operations:
            slow_operations.sort(key=lambda x: x[1], reverse=True)
            logger.warning("Slow operations detected", 
                          operations=[{op[0]: f"{op[1]:.1f}ms"} for op in slow_operations[:5]])
        
        # Analyze cache performance
        cache_stats = self.cache.get_stats()
        if cache_stats["utilization_percent"] > 90:
            logger.warning("Cache utilization high", utilization=cache_stats["utilization_percent"])
        
        # Optimize connection pools
        for url, pool in self.connection_pools.items():
            pool_stats = pool.get_stats()
            if pool_stats["used_connections"] == pool_stats["max_connections"]:
                logger.warning("Connection pool at capacity", server=url, stats=pool_stats)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        
        # Top operations by call count
        top_operations = sorted(
            [(name, metrics) for name, metrics in self.metrics.items()],
            key=lambda x: x[1].total_calls,
            reverse=True
        )[:10]
        
        # Slow operations
        slow_operations = sorted(
            [(name, metrics) for name, metrics in self.metrics.items()],
            key=lambda x: x[1].average_duration_ms,
            reverse=True
        )[:10]
        
        # Cache performance
        total_cache_hits = sum(m.cache_hits for m in self.metrics.values())
        total_cache_misses = sum(m.cache_misses for m in self.metrics.values())
        overall_cache_hit_rate = (
            total_cache_hits / (total_cache_hits + total_cache_misses)
            if (total_cache_hits + total_cache_misses) > 0 else 0.0
        )
        
        return {
            "cache": {
                "stats": self.cache.get_stats(),
                "hit_rate": overall_cache_hit_rate,
                "total_hits": total_cache_hits,
                "total_misses": total_cache_misses
            },
            "connection_pools": {
                url: pool.get_stats() 
                for url, pool in self.connection_pools.items()
            },
            "operations": {
                "top_by_calls": [
                    {
                        "name": name,
                        "calls": metrics.total_calls,
                        "avg_duration_ms": metrics.average_duration_ms,
                        "success_rate": metrics.success_rate
                    }
                    for name, metrics in top_operations
                ],
                "slowest": [
                    {
                        "name": name,
                        "avg_duration_ms": metrics.average_duration_ms,
                        "calls": metrics.total_calls,
                        "max_duration_ms": metrics.max_duration_ms
                    }
                    for name, metrics in slow_operations
                ]
            },
            "total_operations": len(self.metrics),
            "active_batch_queues": len(self._batch_queues)
        }
    
    async def close(self):
        """Close performance manager and clean up resources"""
        
        # Close connection pools
        for pool in self.connection_pools.values():
            await pool.close()
        
        # Cancel batch timers
        for timer in self._batch_timers.values():
            timer.cancel()
        
        # Close cache cleanup task
        if hasattr(self.cache, '_cleanup_task'):
            self.cache._cleanup_task.cancel()
        
        logger.info("Performance Manager closed")

# Global performance manager instance
performance_manager = PerformanceManager()