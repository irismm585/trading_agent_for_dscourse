# 数据验证集成技术文档

## 概述

本文档详细介绍数据验证系统的架构、集成方式、配置预设和使用方法。

---

## 目录

1. [架构概览](#架构概览)
2. [核心组件](#核心组件)
3. [配置预设](#配置预设)
4. [集成方式](#集成方式)
5. [使用示例](#使用示例)
6. [验证报告结构](#验证报告结构)
7. [故障排查](#故障排查)

---

## 架构概览

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    数据获取层 (Data Layer)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────────┐                  │
│  │ unified_data │───▶│ BatchDataValidator │                  │
│  │ fetch_all_data│    │ (数据验证器)      │                  │
│  └──────────────┘    └──────────────────┘                  │
│         │                        │                          │
│         ▼                        ▼                          │
│  ┌──────────────┐    ┌──────────────────┐                  │
│  │ data_pipeline│───▶│ 验证报告生成      │                  │
│  │ (流水线)      │    │ validation_report│                  │
│  └──────────────┘    └──────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户请求
    │
    ▼
┌──────────────┐
│ fetch_all_data │ ──▶ 自动集成验证 (CN/US 市场)
└──────────────┘
    │
    ├──▶ OHLCV 数据验证
    ├──▶ 财务指标验证
    └──▶ 生成 validation_report
    │
    ▼
返回数据 + 验证报告
```

---

## 核心组件

### 1. BatchDataValidator

**位置**: [`backend/utils/data_converters.py`](../backend/utils/data_converters.py)

**功能**: 提供底层数据验证能力

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `validate_ohlcv_data(df, strict)` | `Dict` | 验证 OHLCV 数据完整性和逻辑 |
| `validate_financial_data(data, strict)` | `Dict` | 验证财务数据格式和范围 |
| `validate_dataframe_schema(df, schema, strict)` | `Dict` | 验证 DataFrame 模式 |
| `generate_quality_report(df)` | `Dict` | 生成数据质量报告 |

**注意**: 所有方法只返回一个字典，不是元组！

### 2. DataPipeline

**位置**: [`backend/data_layer/data_pipeline.py`](../backend/data_layer/data_pipeline.py)

**功能**: 高级数据流水线，支持配置预设

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `fetch_validated_data(...)` | `Dict` | 获取完整数据包 + 验证 |
| `fetch_only_ohlcv(...)` | `Dict` | 仅获取 OHLCV + 验证 |
| `validate_ohlcv_data(df, symbol)` | `Tuple[bool, Dict]` | 验证 OHLCV (返回元组) |
| `validate_financial_metrics(data, symbol)` | `Tuple[bool, Dict]` | 验证财务指标 (返回元组) |

**注意**: DataPipeline 内部的验证方法返回 `(valid, report)` 元组！

### 3. unified_data 集成

**位置**: [`backend/data_layer/unified_data.py`](../backend/data_layer/unified_data.py)

**功能**: 在 `fetch_all_data` 中自动集成验证

**修改点**:
- CN 市场: 第 389-428 行
- US 市场: 第 525-564 行

---

## 配置预设

### 预设定义

```python
PRESETS = {
    "PRODUCTION": {
        "min_ohlcv_rows": 20,
        "max_invalid_ratio": 0.05,
        "strict_validation": True
    },
    "BACKTEST": {
        "min_ohlcv_rows": 60,
        "max_invalid_ratio": 0.02,
        "strict_validation": True
    },
    "DEVELOPMENT": {
        "min_ohlcv_rows": 5,
        "max_invalid_ratio": 0.20,
        "strict_validation": False
    }
}
```

### 预设对比

| 预设 | 严格模式 | 最小行数 | 最大无效比例 | 适用场景 |
|------|---------|---------|-------------|---------|
| **PRODUCTION** | ✅ True | 20 | 5% | 生产环境、正式交易 |
| **BACKTEST** | ✅ True | 60 | 2% | 回测系统、历史分析 |
| **DEVELOPMENT** | ❌ False | 5 | 20% | 开发调试、快速原型 |

### 预设选择建议

```
生产环境 ──▶ PRODUCTION (严格，20行，5%)
    │
    ├── 数据量足够 (≥20行) ──▶ ✅ 通过
    └── 数据量不足 (<20行) ──▶ ❌ 拒绝 (需要更多历史数据)

回测系统 ──▶ BACKTEST (最严格，60行，2%)
    │
    ├── 数据量足够 (≥60行) ──▶ ✅ 通过
    └── 数据量不足 (<60行) ──▶ ❌ 拒绝 (回测需要更多历史)

开发环境 ──▶ DEVELOPMENT (宽松，5行，20%)
    │
    └── 几乎所有数据 ──▶ ✅ 通过 (方便调试)
```

---

## 集成方式

### 方式1: 使用 fetch_all_data (推荐)

`fetch_all_data` 已自动集成验证，无需额外代码。

**代码示例**:

```python
from backend.data_layer import fetch_all_data

# 获取数据，自动包含验证报告
result = fetch_all_data("600519", "2026-05-26", "cn", lookback_days=60)

# 检查验证结果
validation = result["validation_report"]
print(f"OHLCV 有效: {validation['ohlcv_valid']}")
print(f"财务有效: {validation['financial_valid']}")
print(f"警告数: {len(validation['warnings'])}")
print(f"错误数: {len(validation['errors'])}")

# 使用数据
df = result["ohlcv_df"]
profile = result["profile"]
```

**优点**:
- 零代码集成
- 向后兼容（不影响现有代码）
- 同时支持 CN 和 US 市场

### 方式2: 使用 DataPipeline

适用于需要更细粒度控制的场景。

**代码示例**:

```python
from backend.data_layer import DataPipeline

# 使用预设
pipeline = DataPipeline(preset="PRODUCTION")

# 或者自定义配置
pipeline = DataPipeline(
    strict_validation=True,
    min_ohlcv_rows=30,
    max_invalid_ratio=0.03
)

# 获取完整数据
result = pipeline.fetch_validated_data(
    symbol="600519",
    trade_date="2026-05-26",
    market="cn",
    lookback_days=60
)

# 或者只获取 OHLCV
ohlcv_result = pipeline.fetch_only_ohlcv(
    symbol="600519",
    start_date="2026-03-01",
    end_date="2026-05-26",
    market="cn"
)
```

### 方式3: 使用便捷函数

适用于快速调用。

**代码示例**:

```python
from backend.data_layer import validated_data_fetch, validated_ohlcv_fetch

# 完整数据
result = validated_data_fetch(
    "600519", "2026-05-26", "cn",
    preset="PRODUCTION"
)

# 仅 OHLCV
ohlcv = validated_ohlcv_fetch(
    "600519", "2026-03-01", "2026-05-26", "cn",
    preset="DEVELOPMENT"
)
```

---

## 使用示例

### 示例1: 生产环境数据获取

```python
"""生产环境 - 使用 PRODUCTION 预设"""

from backend.data_layer import DataPipeline, DataPipelineValidationError

def get_production_data(symbol, date):
    """获取生产环境数据，严格验证"""
    
    pipeline = DataPipeline(preset="PRODUCTION")
    
    try:
        result = pipeline.fetch_validated_data(symbol, date, "cn", lookback_days=60)
        
        # 只有完全通过验证才会到这里
        return {
            "success": True,
            "data": result["data"],
            "validation": result["validation_summary"]
        }
        
    except DataPipelineValidationError as e:
        # 验证失败，记录日志
        print(f"数据验证失败: {e}")
        print(f"详细报告: {e.validation_report}")
        return {
            "success": False,
            "error": str(e),
            "validation_report": e.validation_report
        }
```

### 示例2: 回测数据获取

```python
"""回测系统 - 使用 BACKTEST 预设"""

from backend.data_layer import DataPipeline

def get_backtest_data(symbol, start_date, end_date):
    """获取回测数据，最严格验证"""
    
    pipeline = DataPipeline(preset="BACKTEST")
    
    try:
        result = pipeline.fetch_only_ohlcv(symbol, start_date, end_date, "cn")
        return result["ohlcv_df"]
        
    except Exception as e:
        print(f"回测数据获取失败: {e}")
        # 回测系统可能需要抛出异常
        raise
```

### 示例3: 开发调试

```python
"""开发环境 - 使用 DEVELOPMENT 预设"""

from backend.data_layer import DataPipeline

def debug_data_quality(symbol, date):
    """调试数据质量问题"""
    
    pipeline = DataPipeline(preset="DEVELOPMENT")
    
    result = pipeline.fetch_validated_data(symbol, date, "cn", lookback_days=60)
    summary = result["validation_summary"]
    
    print(f"=== {symbol} 数据质量分析 ===")
    print(f"整体状态: {'✅ 正常' if summary['overall_valid'] else '⚠️ 有问题'}")
    
    # 检查 OHLCV
    if "ohlcv" in summary:
        ohlcv = summary["ohlcv"]
        print(f"\nOHLCV: {'✅' if ohlcv['valid'] else '❌'} {ohlcv['summary']}")
        
        if "ohlcv_details" in ohlcv:
            details = ohlcv["ohlcv_details"]
            print(f"  有效行数: {details.get('valid_rows')}")
            print(f"  无效行数: {len(details.get('invalid_rows', []))}")
            
            if details.get("invalid_rows"):
                print("\n  问题行:")
                for row in details["invalid_rows"][:5]:
                    print(f"    行 {row['index']}: {row['errors']}")
    
    # 检查质量报告
    if "data_quality" in summary:
        quality = summary["data_quality"]
        print(f"\n数据质量:")
        print(f"  总行数: {quality['row_count']}")
        print(f"  重复行: {quality['duplicate_rows']}")
        
        print(f"\n  缺失值:")
        for col, info in quality["missing_values"].items():
            status = "✅" if info["percentage"] == 0 else "⚠️"
            print(f"    {status} {col}: {info['count']} ({info['percentage']:.1f}%)")
    
    return result
```

### 示例4: 批量处理

```python
"""批量处理股票数据"""

from backend.data_layer import DataPipeline

def process_portfolio(symbols, date):
    """处理一篮子股票，只保留高质量数据"""
    
    pipeline = DataPipeline(preset="PRODUCTION")
    results = []
    
    for symbol in symbols:
        try:
            result = pipeline.fetch_validated_data(symbol, date, "cn")
            summary = result["validation_summary"]
            
            if summary["overall_valid"]:
                results.append({
                    "symbol": symbol,
                    "status": "success",
                    "data": result["data"]
                })
            else:
                results.append({
                    "symbol": symbol,
                    "status": "warning",
                    "issues": summary
                })
                
        except Exception as e:
            results.append({
                "symbol": symbol,
                "status": "failed",
                "error": str(e)
            })
    
    # 统计
    success = sum(1 for r in results if r["status"] == "success")
    print(f"批量处理完成: {success}/{len(results)} 成功")
    
    return results
```

---

## 验证报告结构

### fetch_all_data 返回的 validation_report

```python
{
    "ohlcv_valid": True,           # OHLCV 数据是否有效
    "financial_valid": True,       # 财务指标是否有效
    "warnings": [],                # 警告列表
    "errors": [],                  # 错误列表
    "ohlcv_report": {              # OHLCV 详细报告
        "total_rows": 60,
        "valid_rows": 60,
        "invalid_rows": [],
        "errors": [],
        "warnings": []
    },
    "financial_report": {          # 财务指标详细报告
        "valid": True,
        "errors": [],
        "warnings": []
    }
}
```

### DataPipeline 返回的 validation_summary

```python
{
    "overall_valid": True,
    "ohlcv": {
        "valid": True,
        "summary": "OHLCV data valid, 60 rows, 0 invalid, 0 warnings",
        "ohlcv_details": {...},
        "warnings": [],
        "errors": []
    },
    "financial": {
        "valid": True,
        "summary": "Financial metrics valid",
        "financial_report": {...},
        "warnings": [],
        "errors": []
    },
    "data_quality": {
        "row_count": 60,
        "column_count": 7,
        "duplicate_rows": 0,
        "missing_values": {
            "date": {"count": 0, "percentage": 0.0},
            "open": {"count": 0, "percentage": 0.0},
            ...
        },
        "numeric_stats": {
            "open": {"mean": 100.0, "min": 90.0, "max": 110.0, ...},
            ...
        }
    },
    "timestamp": "2026-05-26T10:00:00"
}
```

---

## 故障排查

### 常见问题

#### 问题1: "too many values to unpack (expected 2)"

**原因**: 错误地将返回一个字典的方法当成返回元组来使用。

**错误代码**:
```python
# ❌ 错误
ohlcv_valid, ohlcv_report = BatchDataValidator.validate_ohlcv_data(df, symbol)
```

**正确代码**:
```python
# ✅ 正确 - BatchDataValidator 只返回一个字典
ohlcv_report = BatchDataValidator.validate_ohlcv_data(df, strict=False)
ohlcv_valid = len(ohlcv_report.get("errors", [])) == 0

# ✅ 正确 - DataPipeline 内部方法返回元组
ohlcv_valid, ohlcv_report = pipeline.validate_ohlcv_data(df, symbol)
```

#### 问题2: 生产环境数据被拒绝

**原因**: 数据量不足或质量不达标。

**排查**:
```python
# 使用 DEVELOPMENT 预设查看详细问题
pipeline = DataPipeline(preset="DEVELOPMENT")
result = pipeline.fetch_validated_data(symbol, date, "cn")

# 检查验证报告
summary = result["validation_summary"]
print(f"OHLCV 报告: {summary['ohlcv']}")
print(f"质量报告: {summary['data_quality']}")
```

**解决方案**:
- 增加 `lookback_days` 参数获取更多历史数据
- 检查数据源是否正常
- 如果是临时数据不足，考虑使用 DEVELOPMENT 预设

#### 问题3: 验证报告为空

**原因**: 可能使用了旧版本代码，或者验证逻辑未正确集成。

**检查**:
```python
result = fetch_all_data("600519", "2026-05-26", "cn")

if "validation_report" in result:
    print("✅ 验证报告已集成")
else:
    print("❌ 验证报告缺失，请检查代码版本")
```

### 调试技巧

#### 技巧1: 查看验证日志

```python
pipeline = DataPipeline(preset="DEVELOPMENT")
# ... 执行一些操作 ...

# 获取所有日志
logs = pipeline.get_validation_logs()
for log in logs:
    print(f"{log['step']} - {log['symbol']}: {log['success']}")
    print(f"  详情: {log['details']}")
```

#### 技巧2: 分步验证

```python
from backend.utils.data_converters import BatchDataValidator

# 已有数据框
df = get_some_data()

# 单独验证 OHLCV
ohlcv_report = BatchDataValidator.validate_ohlcv_data(df, strict=False)
print(f"OHLCV 有效: {len(ohlcv_report['errors']) == 0}")
print(f"无效行数: {len(ohlcv_report['invalid_rows'])}")

# 生成质量报告
quality = BatchDataValidator.generate_quality_report(df)
print(f"缺失值: {quality['missing_values']}")
```

#### 技巧3: 对比不同预设

```python
from backend.data_layer import DataPipeline

symbol = "600519"
date = "2026-05-26"

for preset in ["DEVELOPMENT", "PRODUCTION", "BACKTEST"]:
    pipeline = DataPipeline(preset=preset)
    try:
        result = pipeline.fetch_only_ohlcv(symbol, "2026-04-01", date, "cn")
        print(f"{preset}: ✅ 通过")
    except Exception as e:
        print(f"{preset}: ❌ 失败 - {e}")
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| [`backend/utils/data_converters.py`](../backend/utils/data_converters.py) | BatchDataValidator 实现 |
| [`backend/data_layer/data_pipeline.py`](../backend/data_layer/data_pipeline.py) | DataPipeline 实现 |
| [`backend/data_layer/unified_data.py`](../backend/data_layer/unified_data.py) | fetch_all_data 集成验证 |
| [`backend/data_layer/mock_data.py`](../backend/data_layer/mock_data.py) | Mock 数据也包含验证报告 |
| [`docs/VALIDATION_STRICT_MODE.md`](./VALIDATION_STRICT_MODE.md) | 严格模式详细文档 |
| [`docs/PIPELINE_USAGE.md`](./PIPELINE_USAGE.md) | 流水线使用指南 |

---

## 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-26 | 1.0 | 初始版本，完整的验证集成文档 |
| 2026-05-26 | 1.1 | 修复返回值解包问题，统一验证接口 |

---

## 最佳实践检查清单

- [ ] 生产环境使用 `PRODUCTION` 预设
- [ ] 回测系统使用 `BACKTEST` 预设
- [ ] 开发调试使用 `DEVELOPMENT` 预设
- [ ] 捕获 `DataPipelineValidationError` 异常
- [ ] 记录验证失败的详细日志
- [ ] 定期审查验证日志
- [ ] 确保 `fetch_all_data` 返回包含 `validation_report`
