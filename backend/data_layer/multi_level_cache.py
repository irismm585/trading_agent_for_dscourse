"""Multi-Level Cache - 多级缓存策略

提供内存缓存、Redis缓存、文件缓存的多级缓存系统，支持缓存预热、智能失效策略。
"""

from __future__ import annotations

import hashlib
import json
import time
import threading
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from collections import OrderedDict
from copy import deepcopy

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    ttl_seconds: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    
    @property
    def is_expired(self) -> bool:
        """是否过期"""
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - self.created_at) > self.ttl_seconds
    
    @property
    def remaining_ttl(self) -> float:
        """剩余 TTL"""
        if self.ttl_seconds <= 0:
            return float('inf')
        return max(0, self.ttl_seconds - (time.time() - self.created_at))


class LRUCache:
    """LRU 内存缓存"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """初始化 LRU 缓存
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认 TTL（秒）
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            entry = self._cache[key]
            
            # 检查过期
            if entry.is_expired:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # 更新访问信息
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            
            return deepcopy(entry.value)
    
    def set(self, key: str, value: Any, ttl_seconds: int = None) -> bool:
        """设置缓存值"""
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            
            # 如果已存在，更新
            if key in self._cache:
                del self._cache[key]
            
            # 检查容量
            if len(self._cache) >= self._max_size:
                # 移除最旧的
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
            
            self._cache[key] = CacheEntry(
                key=key,
                value=deepcopy(value),
                created_at=time.time(),
                ttl_seconds=ttl
            )
            
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": hit_rate,
                "evictions": self._stats["evictions"]
            }


class FileCache:
    """文件缓存"""
    
    def __init__(self, cache_dir: str = "./cache", default_ttl: int = 86400):
        """初始化文件缓存
        
        Args:
            cache_dir: 缓存目录
            default_ttl: 默认 TTL（秒）
        """
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl
        self._stats = {
            "hits": 0,
            "misses": 0
        }
    
    def _get_file_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self._cache_dir / f"{hashed}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        file_path = self._get_file_path(key)
        
        if not file_path.exists():
            self._stats["misses"] += 1
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查过期
            created_at = data.get("created_at", 0)
            ttl = data.get("ttl_seconds", self._default_ttl)
            
            if ttl > 0 and (time.time() - created_at) > ttl:
                file_path.unlink(missing_ok=True)
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return data.get("value")
            
        except Exception:
            self._stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = None) -> bool:
        """设置缓存值"""
        try:
            file_path = self._get_file_path(key)
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            
            data = {
                "key": key,
                "value": value,
                "created_at": time.time(),
                "ttl_seconds": ttl
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            file_path = self._get_file_path(key)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    def clear(self):
        """清空缓存"""
        try:
            for file_path in self._cache_dir.glob("*.json"):
                file_path.unlink()
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        
        return {
            "cache_dir": str(self._cache_dir),
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate
        }


class RedisCache:
    """Redis 缓存"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = None,
        default_ttl: int = 3600
    ):
        """初始化 Redis 缓存"""
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._default_ttl = default_ttl
        self._client = None
        self._stats = {
            "hits": 0,
            "misses": 0
        }
        self._connect()
    
    def _connect(self):
        """连接 Redis"""
        if not HAS_REDIS:
            return
        
        try:
            self._client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                decode_responses=True
            )
            self._client.ping()
        except Exception:
            self._client = None
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self._client is not None
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self.is_available():
            return None
        
        try:
            value = self._client.get(key)
            if value is None:
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return json.loads(value)
        except Exception:
            self._stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = None) -> bool:
        """设置缓存值"""
        if not self.is_available():
            return False
        
        try:
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.is_available():
            return False
        
        try:
            return self._client.delete(key) > 0
        except Exception:
            return False
    
    def clear(self):
        """清空缓存"""
        if not self.is_available():
            return
        
        try:
            self._client.flushdb()
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        
        return {
            "available": self.is_available(),
            "host": self._host,
            "port": self._port,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate
        }


class MultiLevelCache:
    """多级缓存"""
    
    def __init__(
        self,
        memory_max_size: int = 1000,
        memory_ttl: int = 3600,
        file_cache_dir: str = "./cache",
        file_ttl: int = 86400,
        redis_enabled: bool = False,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_ttl: int = 3600
    ):
        """初始化多级缓存"""
        # L1: 内存缓存
        self._memory = LRUCache(max_size=memory_max_size, default_ttl=memory_ttl)
        
        # L2: 文件缓存
        self._file = FileCache(cache_dir=file_cache_dir, default_ttl=file_ttl)
        
        # L3: Redis 缓存
        self._redis = RedisCache(
            host=redis_host,
            port=redis_port,
            default_ttl=redis_ttl
        ) if redis_enabled and HAS_REDIS else None
        
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值（L1 -> L2 -> L3）"""
        with self._lock:
            # L1: 内存
            value = self._memory.get(key)
            if value is not None:
                return value
            
            # L2: 文件
            value = self._file.get(key)
            if value is not None:
                # 回填到内存
                self._memory.set(key, value)
                return value
            
            # L3: Redis
            if self._redis and self._redis.is_available():
                value = self._redis.get(key)
                if value is not None:
                    # 回填到内存和文件
                    self._memory.set(key, value)
                    self._file.set(key, value)
                    return value
            
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = None) -> bool:
        """设置缓存值（写入所有层级）"""
        with self._lock:
            success = True
            
            # L1: 内存
            if not self._memory.set(key, value, ttl_seconds):
                success = False
            
            # L2: 文件
            if not self._file.set(key, value, ttl_seconds):
                success = False
            
            # L3: Redis
            if self._redis and self._redis.is_available():
                if not self._redis.set(key, value, ttl_seconds):
                    success = False
            
            return success
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            success = True
            
            if not self._memory.delete(key):
                success = False
            
            if not self._file.delete(key):
                success = False
            
            if self._redis and self._redis.is_available():
                if not self._redis.delete(key):
                    success = False
            
            return success
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._memory.clear()
            self._file.clear()
            if self._redis:
                self._redis.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "memory": self._memory.get_stats(),
            "file": self._file.get_stats(),
            "redis": self._redis.get_stats() if self._redis else {"available": False}
        }
    
    def get_or_set(
        self,
        key: str,
        loader: Callable[[], Any],
        ttl_seconds: int = None
    ) -> Any:
        """获取或设置缓存（缓存穿透保护）"""
        value = self.get(key)
        if value is not None:
            return value
        
        # 加载数据
        value = loader()
        
        # 设置缓存
        if value is not None:
            self.set(key, value, ttl_seconds)
        
        return value
    
    def warmup(self, keys: Dict[str, Any], ttl_seconds: int = None):
        """缓存预热"""
        for key, value in keys.items():
            self.set(key, value, ttl_seconds)


# 单例
_cache_instance: Optional[MultiLevelCache] = None


def get_cache(
    memory_max_size: int = 1000,
    redis_enabled: bool = False
) -> MultiLevelCache:
    """获取或创建缓存单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MultiLevelCache(
            memory_max_size=memory_max_size,
            redis_enabled=redis_enabled
        )
    return _cache_instance
