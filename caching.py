"""
Caching System
==============

Cache expensive operations to improve performance.

Benefits:
- Faster repeated queries
- Reduced database load
- Lower CPU usage
- Better responsiveness
- Configurable TTL
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   caching.py
#
# Connected modules (direct imports):
#   error_handling
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only.
# ============================================================================

import time
import threading
from typing import Any, Optional, Callable, Dict, Tuple, TypeVar
from dataclasses import dataclass
from functools import wraps
import hashlib
import json

from error_handling import ErrorHandler


# ============================================================================
# CONFIGURATION / CONSTANTS
# ============================================================================

T = TypeVar('T')


@dataclass
class CacheEntry:
    """A single cache entry"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: float


class Cache:
    """
    Thread-safe cache with TTL (Time To Live)
    
    Features:
    - Automatic expiration
    - Access tracking
    - Thread-safe operations
    - Size limits
    - Statistics
    """
    
    def __init__(
        self,
        name: str,
        default_ttl: float = 60.0,
        max_size: int = 1000,
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Initialize cache
        
        Args:
            name: Cache name (for logging)
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of entries
            error_handler: Error handler (optional)
        """
        self.name = name
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.error_handler = error_handler
        
        # Storage
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            # Check if expired
            if self._is_expired(entry):
                del self._cache[key]
                self._misses += 1
                return None
            
            # Update access stats
            entry.last_accessed = time.time()
            entry.access_count += 1
            self._hits += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live (None = use default)
        """
        with self._lock:
            # Evict if at capacity
            if key not in self._cache and len(self._cache) >= self.max_size:
                self._evict_lru()
            
            now = time.time()
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                last_accessed=now,
                access_count=0,
                ttl=ttl or self.default_ttl
            )
            
            self._cache[key] = entry
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry is expired"""
        age = time.time() - entry.created_at
        return age > entry.ttl
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self._cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )
        
        del self._cache[lru_key]
        self._evictions += 1
    
    def cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            expired = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]
            
            for key in expired:
                del self._cache[key]
            
            return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "name": self.name,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": hit_rate,
                "total_requests": total_requests
            }


class CacheManager:
    """
    Manages multiple caches
    
    Provides centralized cache management with automatic cleanup.
    """
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        """
        Initialize cache manager
        
        Args:
            error_handler: Error handler
        """
        self.error_handler = error_handler
        self.caches: Dict[str, Cache] = {}
        self._lock = threading.Lock()
        
        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
    
    def create_cache(
        self,
        name: str,
        default_ttl: float = 60.0,
        max_size: int = 1000
    ) -> Cache:
        """
        Create a new cache
        
        Args:
            name: Cache name
            default_ttl: Default TTL
            max_size: Maximum size
            
        Returns:
            Cache instance
        """
        with self._lock:
            if name in self.caches:
                return self.caches[name]
            
            cache = Cache(name, default_ttl, max_size, self.error_handler)
            self.caches[name] = cache
            
            return cache
    
    def get_cache(self, name: str) -> Optional[Cache]:
        """Get cache by name"""
        with self._lock:
            return self.caches.get(name)
    
    def start_cleanup_thread(self, interval: float = 60.0):
        """
        Start automatic cleanup thread
        
        Args:
            interval: Cleanup interval in seconds
        """
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                time.sleep(interval)
                
                if self._stop_cleanup.is_set():
                    break
                
                # Cleanup expired entries
                total_cleaned = 0
                with self._lock:
                    for cache in self.caches.values():
                        cleaned = cache.cleanup_expired()
                        total_cleaned += cleaned
                
                if total_cleaned > 0 and self.error_handler:
                    self.error_handler.logger.info(
                        f"Cache cleanup: removed {total_cleaned} expired entries"
                    )
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            name="cache-cleanup",
            daemon=True
        )
        self._cleanup_thread.start()
    
    def stop_cleanup_thread(self):
        """Stop cleanup thread"""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2.0)
    
    def clear_all(self):
        """Clear all caches"""
        with self._lock:
            for cache in self.caches.values():
                cache.clear()
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches"""
        with self._lock:
            return {
                name: cache.get_stats()
                for name, cache in self.caches.items()
            }


# ============================================================================
# FUNCTIONS
# ============================================================================

# ============================================================================
# CACHING DECORATORS
# ============================================================================

def cached(
    cache: Cache,
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None
):
    """
    Decorator to cache function results
    
    Args:
        cache: Cache instance
        ttl: Time-to-live (None = use cache default)
        key_func: Function to generate cache key (None = use args)
    
    Usage:
        @cached(my_cache, ttl=300)
        def expensive_function(arg1, arg2):
            # ... expensive operation ...
            return result
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _generate_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def _generate_key(func_name: str, args: Tuple, kwargs: Dict) -> str:
    """
    Generate cache key from function name and arguments
    
    Args:
        func_name: Function name
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        Cache key string
    """
    # Create deterministic representation
    key_data = {
        "func": func_name,
        "args": args,
        "kwargs": sorted(kwargs.items())
    }
    
    # Serialize to JSON
    try:
        key_str = json.dumps(key_data, sort_keys=True)
    except TypeError:
        # Fallback for non-serializable objects
        key_str = f"{func_name}:{str(args)}:{str(kwargs)}"
    
    # Hash for consistent length
    return hashlib.md5(key_str.encode()).hexdigest()


# ============================================================================
# SPECIALIZED CACHES
# ============================================================================

class QueryCache(Cache):
    """Cache for database queries"""
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        super().__init__(
            name="query_cache",
            default_ttl=60.0,  # 1 minute
            max_size=500,
            error_handler=error_handler
        )


class CalculationCache(Cache):
    """Cache for expensive calculations"""
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        super().__init__(
            name="calculation_cache",
            default_ttl=300.0,  # 5 minutes
            max_size=1000,
            error_handler=error_handler
        )


class StatsCache(Cache):
    """Cache for statistics"""
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        super().__init__(
            name="stats_cache",
            default_ttl=30.0,  # 30 seconds
            max_size=100,
            error_handler=error_handler
        )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """Example of using the caching system"""
    
    # Create cache manager
    cache_manager = CacheManager()
    
    # Create caches
    query_cache = cache_manager.create_cache("queries", ttl=60.0)
    stats_cache = cache_manager.create_cache("stats", ttl=30.0)
    
    # Start automatic cleanup
    cache_manager.start_cleanup_thread(interval=60.0)
    
    # Use cache decorator
    @cached(query_cache, ttl=120.0)
    def get_top_systems(limit: int):
        """Expensive database query"""
        print(f"Executing query for top {limit} systems...")
        # ... database query ...
        return ["System A", "System B", "System C"]
    
    # First call - cache miss, executes function
    result1 = get_top_systems(10)
    print(f"Result 1: {result1}")
    
    # Second call - cache hit, returns cached value
    result2 = get_top_systems(10)
    print(f"Result 2: {result2}")
    
# ============================================================================
# ENTRYPOINT
# ============================================================================

    # Get statistics
    stats = query_cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Cleanup
    cache_manager.stop_cleanup_thread()


if __name__ == "__main__":
    example_usage()
