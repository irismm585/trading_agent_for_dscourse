# 数据流水线使用指南

## 概述

数据流水线（Data Pipeline）是一个集成了 BatchDataValidator 的数据获取框架，自动在数据获取的每个阶段进行质量验证。

## 快速开始

### 最简单的方式 - 使用便捷函数

```python
from backend.data_layer import validated_data_fetch

# 获取完整的验证数据
result = validated_data_fetch(
    symbol="600519",
    trade_date="2026-05-25",
    market="cn",
    lookback_days=60,
    strict=True
)

# 检查验证结果
if result["validation_summary"]["overall_valid"]:
    print("✅ 数据验证通过！")
    df = result["data"]["ohlcv_df"]
    # 使用数据...
else:
    print("⚠️ 数据有警告或错误")
```

### 直接获取 OHLCV 数据

```python
from backend.data_layer import validated_ohlcv_fetch

result = validated_ohlcv_fetch(
    symbol="600519",
    start_date="2026-03-01",
    end_date="2026-05-25",
    market="cn",
    strict=True
)

if result["validation_summary"]["valid"]:
    df = result["ohlcv_df"]
```

## 使用 DataPipeline 类

```python
from backend.data_layer import DataPipeline

# 创建流水线实例
pipeline = DataPipeline(strict_validation=True)

# 获取完整数据
result = pipeline.fetch_validated_data(
    symbol="600519",
    trade_date="2026-05-25",
    market="cn",
    lookback_days=60
)

# 只获取 OHLCV
ohlcv_result = pipeline.fetch_only_ohlcv(
    symbol="600519",
    start_date="2026-03-01",
    end_date="2026-05-25",
    market="cn"
)
```

## 结果结构

### validated_data_fetch 返回值

```python
{
    "symbol": "600519",
    "market": "cn",
    "trade_date": "2026-05-25",
    "validation_summary": {
        "overall_valid": True,
        "ohlcv": {
            "valid": True,
            "summary": "OHLCV data valid, 60 rows, 0 invalid, 0 warnings",
            "ohlcv_details": {...},
        "financial": {
            "valid": True,
            "summary": "Financial metrics valid"},
        "data_quality": {
            "row_count": 60,
            "column_count": 7,
            "duplicate_rows": 0,
            "missing_values": {},
            "numeric_stats": {}}
    },
    "data": {...}  # 完整的数据包
}
```

### validated_ohlcv_fetch 返回值

```python
{
    "symbol": "600519",
    "market": "cn",
    "start_date": "2026-03-01",
    "end_date": "2026-05-25",
    "validation_summary": {...},
    "ohlcv_df": pd.DataFrame  # OHLCV 数据
}
```

## 验证日志

```python
# 获取验证日志
logs = pipeline.get_validation_logs()
for log in logs:
    print(f"{log['step']} - {log['symbol']}: {log['success']}")

# 清空日志
pipeline.clear_validation_logs()
```

## 错误处理

```python
from backend.data_layer import (
    DataPipeline,
    DataPipelineValidationError
)

pipeline = DataPipeline(strict_validation=True)

try:
    result = pipeline.fetch_validated_data("600519", "2026-05-25", "cn")
except DataPipelineValidationError as e:
    print(f"验证失败: {e}")
    print(f"详细报告: {e.validation_report}")
```

## 真实测试

要查看更多示例，请查看 test_data_pipeline.py。
