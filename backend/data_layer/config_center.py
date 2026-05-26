"""Config Center - 配置中心化管理

提供统一配置中心、环境隔离、热更新、版本管理和变更审计功能。
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from copy import deepcopy


@dataclass
class ConfigVersion:
    """配置版本"""
    version: int
    timestamp: datetime
    changes: Dict[str, Any]
    author: str = "system"
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "changes": self.changes,
            "author": self.author,
            "message": self.message
        }


@dataclass
class ConfigAuditLog:
    """配置审计日志"""
    action: str  # create, update, delete
    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime
    author: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "key": self.key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat(),
            "author": self.author
        }


class ConfigCenter:
    """配置中心"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        "environment": {
            "name": "development",
            "debug": True,
            "log_level": "INFO"
        },
        "data_pipeline": {
            "preset": "PRODUCTION",
            "strict_validation": True,
            "min_ohlcv_rows": 20,
            "max_invalid_ratio": 0.05
        },
        "data_sources": {
            "cn": {
                "primary": "pytdx",
                "fallback": ["akshare", "yfinance"],
                "timeout": 30
            },
            "us": {
                "primary": "yfinance",
                "fallback": ["alpha_vantage", "polygon"],
                "timeout": 30
            }
        },
        "cache": {
            "enabled": True,
            "ttl_seconds": 3600,
            "max_size": 1000
        },
        "validation": {
            "ohlcv": {
                "min_rows": 20,
                "max_invalid_ratio": 0.05
            },
            "financial": {
                "required_fields": ["pe_ratio", "pb_ratio", "market_cap"]
            }
        },
        "monitoring": {
            "enabled": True,
            "alert_thresholds": {
                "error_rate": 0.05,
                "latency_ms": 5000
            }
        },
        "rate_limit": {
            "enabled": True,
            "requests_per_second": 10,
            "burst": 20
        }
    }
    
    # 环境配置覆盖
    ENVIRONMENT_OVERRIDES = {
        "development": {
            "environment": {"debug": True, "log_level": "DEBUG"},
            "data_pipeline": {"preset": "DEVELOPMENT"}
        },
        "testing": {
            "environment": {"debug": True, "log_level": "INFO"},
            "data_pipeline": {"preset": "PRODUCTION"}
        },
        "production": {
            "environment": {"debug": False, "log_level": "WARNING"},
            "data_pipeline": {"preset": "PRODUCTION", "strict_validation": True}
        }
    }
    
    def __init__(
        self,
        environment: str = None,
        config_file: str = None,
        auto_reload: bool = True
    ):
        """初始化配置中心
        
        Args:
            environment: 环境名称 (development/testing/production)
            config_file: 配置文件路径
            auto_reload: 是否自动重载配置
        """
        self._environment = environment or os.getenv("APP_ENV", "development")
        self._config_file = Path(config_file) if config_file else None
        self._auto_reload = auto_reload
        
        # 初始化配置
        self._config = deepcopy(self.DEFAULT_CONFIG)
        self._apply_environment_overrides()
        self._load_from_file()
        
        # 版本管理
        self._versions: List[ConfigVersion] = [
            ConfigVersion(
                version=1,
                timestamp=datetime.now(),
                changes={},
                message="Initial configuration"
            )
        ]
        self._current_version = 1
        
        # 审计日志
        self._audit_logs: List[ConfigAuditLog] = []
        
        # 回调
        self._change_callbacks: Dict[str, List[Callable]] = {}
        
        # 锁
        self._lock = threading.RLock()
        
        # 自动重载
        self._last_modified = 0
        if auto_reload and self._config_file:
            self._start_auto_reload()
    
    def _apply_environment_overrides(self):
        """应用环境覆盖"""
        if self._environment in self.ENVIRONMENT_OVERRIDES:
            overrides = self.ENVIRONMENT_OVERRIDES[self._environment]
            self._deep_update(self._config, overrides)
    
    def _deep_update(self, base: Dict, updates: Dict):
        """深度更新字典"""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value
    
    def _load_from_file(self):
        """从文件加载配置"""
        if self._config_file and self._config_file.exists():
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    self._deep_update(self._config, file_config)
            except Exception as e:
                print(f"[ConfigCenter] Failed to load config file: {e}")
    
    def _save_to_file(self):
        """保存配置到文件"""
        if self._config_file:
            try:
                self._config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._config_file, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[ConfigCenter] Failed to save config file: {e}")
    
    def _start_auto_reload(self):
        """启动自动重载"""
        def check_and_reload():
            while self._auto_reload:
                try:
                    if self._config_file and self._config_file.exists():
                        mtime = self._config_file.stat().st_mtime
                        if mtime > self._last_modified:
                            self._last_modified = mtime
                            old_config = deepcopy(self._config)
                            self._load_from_file()
                            self._notify_changes(old_config, self._config)
                except Exception:
                    pass
                time.sleep(5)
        
        import time
        thread = threading.Thread(target=check_and_reload, daemon=True)
        thread.start()
    
    def _notify_changes(self, old_config: Dict, new_config: Dict):
        """通知配置变更"""
        changes = self._find_changes(old_config, new_config)
        for key in changes:
            if key in self._change_callbacks:
                for callback in self._change_callbacks[key]:
                    try:
                        callback(changes[key])
                    except Exception:
                        pass
    
    def _find_changes(self, old: Dict, new: Dict, prefix: str = "") -> Dict[str, Any]:
        """查找配置变更"""
        changes = {}
        all_keys = set(old.keys()) | set(new.keys())
        
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            
            if key not in old:
                changes[full_key] = {"action": "add", "new": new[key]}
            elif key not in new:
                changes[full_key] = {"action": "delete", "old": old[key]}
            elif isinstance(old[key], dict) and isinstance(new[key], dict):
                nested_changes = self._find_changes(old[key], new[key], full_key)
                changes.update(nested_changes)
            elif old[key] != new[key]:
                changes[full_key] = {
                    "action": "update",
                    "old": old[key],
                    "new": new[key]
                }
        
        return changes
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键（支持点分隔，如 "data_pipeline.preset"）
            default: 默认值
            
        Returns:
            配置值
        """
        with self._lock:
            parts = key.split(".")
            value = self._config
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            return deepcopy(value)
    
    def set(self, key: str, value: Any, author: str = "system", message: str = ""):
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            author: 修改者
            message: 修改说明
        """
        with self._lock:
            old_config = deepcopy(self._config)
            parts = key.split(".")
            config = self._config
            
            # 导航到目标位置
            for part in parts[:-1]:
                if part not in config:
                    config[part] = {}
                config = config[part]
            
            # 获取旧值
            old_value = config.get(parts[-1])
            
            # 设置新值
            config[parts[-1]] = value
            
            # 记录审计日志
            self._audit_logs.append(ConfigAuditLog(
                action="update" if old_value is not None else "create",
                key=key,
                old_value=old_value,
                new_value=value,
                timestamp=datetime.now(),
                author=author
            ))
            
            # 创建新版本
            self._current_version += 1
            self._versions.append(ConfigVersion(
                version=self._current_version,
                timestamp=datetime.now(),
                changes={key: {"old": old_value, "new": value}},
                author=author,
                message=message
            ))
            
            # 保存到文件
            self._save_to_file()
            
            # 通知回调
            if key in self._change_callbacks:
                for callback in self._change_callbacks[key]:
                    try:
                        callback({"old": old_value, "new": value})
                    except Exception:
                        pass
    
    def on_change(self, key: str, callback: Callable):
        """注册配置变更回调
        
        Args:
            key: 监听的配置键
            callback: 回调函数
        """
        if key not in self._change_callbacks:
            self._change_callbacks[key] = []
        self._change_callbacks[key].append(callback)
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        with self._lock:
            return deepcopy(self._config)
    
    def get_environment(self) -> str:
        """获取当前环境"""
        return self._environment
    
    def get_versions(self) -> List[Dict[str, Any]]:
        """获取版本历史"""
        return [v.to_dict() for v in self._versions]
    
    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志"""
        return [log.to_dict() for log in self._audit_logs[-limit:]]
    
    def rollback(self, version: int) -> bool:
        """回滚到指定版本
        
        Args:
            version: 目标版本号
            
        Returns:
            是否成功
        """
        with self._lock:
            # 找到目标版本
            target_version = None
            for v in self._versions:
                if v.version == version:
                    target_version = v
                    break
            
            if not target_version:
                return False
            
            # 应用变更的反向操作
            old_config = deepcopy(self._config)
            
            for key, change in target_version.changes.items():
                if "old" in change:
                    self.set(key, change["old"], author="rollback", message=f"Rollback to version {version}")
            
            return True
    
    def export(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "environment": self._environment,
            "config": self.get_all(),
            "version": self._current_version,
            "timestamp": datetime.now().isoformat()
        }


# 单例
_config_center_instance: Optional[ConfigCenter] = None


def get_config_center(
    environment: str = None,
    config_file: str = None
) -> ConfigCenter:
    """获取或创建配置中心单例"""
    global _config_center_instance
    if _config_center_instance is None:
        _config_center_instance = ConfigCenter(
            environment=environment,
            config_file=config_file
        )
    return _config_center_instance


def get_config(key: str, default: Any = None) -> Any:
    """便捷函数：获取配置"""
    return get_config_center().get(key, default)


def set_config(key: str, value: Any, author: str = "system"):
    """便捷函数：设置配置"""
    return get_config_center().set(key, value, author=author)
