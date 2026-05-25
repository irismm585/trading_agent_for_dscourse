"""Data Pipeline with Built-in Validation.

This module provides a validated data pipeline that automatically checks data quality
at every step of the data fetch and processing workflow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

import pandas as pd

from backend.utils.data_converters import (
    BatchDataValidator,
    TypeSafeDecorators
)
from backend.data_layer.stock_data import get_stock_ohlcv
from backend.data_layer.unified_data import fetch_all_data


logger = logging.getLogger(__name__)


class DataPipelineValidationError(Exception):
    """Exception raised when data validation fails in the pipeline."""
    
    def __init__(self, message: str, validation_report: Dict[str, Any]):
        self.message = message
        self.validation_report = validation_report
        super().__init__(self.message)


class DataPipeline:
    """Validated data pipeline for fetching and processing market data.
    
    This class wraps data fetching functions with automatic validation
    at each step, ensuring data quality before the data is used.
    
    Configuration Presets:
        - PRODUCTION: 严格模式，最小20行，最多5%无效
        - BACKTEST:   严格模式，最小60行，最多2%无效
        - DEVELOPMENT:宽松模式，最小5行，最多20%无效
    """
    
    # Validation presets
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
    
    # Default to production settings (best practice)
    DEFAULT_CONFIG = PRESETS["PRODUCTION"]
    
    def __init__(
        self,
        strict_validation: bool = None,
        min_ohlcv_rows: int = None,
        max_invalid_ratio: float = None,
        preset: str = None
    ):
        """Initialize the data pipeline.
        
        Args:
            strict_validation: If True, raise exceptions on validation failures
                              rather than just returning warnings
            min_ohlcv_rows: Minimum required OHLCV data rows
            max_invalid_ratio: Maximum allowed invalid row ratio (0.0-1.0)
            preset: Use a preset configuration ("PRODUCTION", "BACKTEST", "DEVELOPMENT")
                   If provided, overrides individual parameters
        """
        # Apply preset if specified
        if preset is not None and preset in self.PRESETS:
            config = self.PRESETS[preset]
            self.strict_validation = config["strict_validation"]
            self.min_ohlcv_rows = config["min_ohlcv_rows"]
            self.max_invalid_ratio = config["max_invalid_ratio"]
        else:
            # Use defaults and allow overrides
            self.strict_validation = strict_validation if strict_validation is not None else self.DEFAULT_CONFIG["strict_validation"]
            self.min_ohlcv_rows = min_ohlcv_rows if min_ohlcv_rows is not None else self.DEFAULT_CONFIG["min_ohlcv_rows"]
            self.max_invalid_ratio = max_invalid_ratio if max_invalid_ratio is not None else self.DEFAULT_CONFIG["max_invalid_ratio"]
        
        self._validation_logs = []
    
    def log_validation(self, step: str, symbol: str, success: bool, 
                       details: Dict[str, Any]):
        """Log validation results for auditing."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "symbol": symbol,
            "success": success,
            "details": details
        }
        self._validation_logs.append(log_entry)
        
        status = "✅" if success else "❌"
        logger.info(f"[数据验证] {status} {step} - {symbol} - {details.get('summary', 'N/A')}")
    
    def validate_ohlcv_data(self, df: Optional[pd.DataFrame], 
                           symbol: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate OHLCV data quality.
        
        Args:
            df: DataFrame to validate
            symbol: Stock symbol for logging
            
        Returns:
            Tuple of (validation_passed, detailed_report)
        """
        report = {
            "valid": False,
            "summary": "",
            "warnings": [],
            "errors": []
        }
        
        # Basic dataframe checks
        if df is None or df.empty:
            report["summary"] = "Empty OHLCV data"
            report["errors"].append("DataFrame is None or empty")
            return False, report
        
        # Use BatchDataValidator for comprehensive checks
        ohlcv_report = BatchDataValidator.validate_ohlcv_data(df, strict=False)
        report["ohlcv_details"] = ohlcv_report
        
        # Check minimum row count
        if len(df) < self.min_ohlcv_rows:
            report["errors"].append(
                f"Data has only {len(df)} rows, below minimum required {self.min_ohlcv_rows}"
            )
        
        # Check invalid row ratio
        if len(ohlcv_report["invalid_rows"]) > 0:
            invalid_ratio = len(ohlcv_report["invalid_rows"]) / len(df)
            if invalid_ratio > self.max_invalid_ratio:
                report["errors"].append(
                    f"Invalid row ratio {invalid_ratio:.1%} exceeds threshold {self.max_invalid_ratio:.1%}"
                )
            else:
                report["warnings"].append(
                    f"Found {len(ohlcv_report['invalid_rows'])} potentially invalid rows"
                )
        
        # Determine overall validity
        report["valid"] = len(report["errors"]) == 0
        report["summary"] = (
            f"OHLCV data {'valid' if report['valid'] else 'invalid'}, "
            f"{len(df)} rows, {len(ohlcv_report['invalid_rows'])} invalid, "
            f"{len(report['warnings'])} warnings"
        )
        
        return report["valid"], report
    
    def validate_financial_metrics(self, financial_data: Dict[str, Any], 
                                  symbol: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate financial metrics data.
        
        Args:
            financial_data: Dictionary of financial metrics
            symbol: Stock symbol for logging
            
        Returns:
            Tuple of (validation_passed, detailed_report)
        """
        report = {
            "valid": False,
            "summary": "",
            "warnings": [],
            "errors": []
        }
        
        finance_report = BatchDataValidator.validate_financial_data(
            financial_data, strict=False
        )
        report["finance_details"] = finance_report
        
        report["valid"] = finance_report["valid"]
        report["summary"] = f"Financial metrics {'valid' if report['valid'] else 'has errors'}"
        
        if not finance_report["valid"]:
            report["errors"].extend(finance_report["errors"])
        if finance_report["warnings"]:
            report["warnings"].extend(finance_report["warnings"])
        
        return report["valid"], report
    
    @TypeSafeDecorators.validate_types(symbol=str, trade_date=str, market=str)
    def fetch_validated_data(self, symbol: str, trade_date: str, 
                           market: str = "cn", 
                           lookback_days: int = 365) -> Dict[str, Any]:
        """Fetch data with automatic validation at each step.
        
        Args:
            symbol: Stock symbol
            trade_date: End date for data
            market: Market (cn or us)
            lookback_days: Number of days to look back
            
        Returns:
            Full data bundle with validation results included
            
        Raises:
            DataPipelineValidationError: If strict validation is enabled and validation fails
        """
        result = {
            "symbol": symbol,
            "market": market,
            "trade_date": trade_date,
            "validation_summary": {},
            "data": None
        }
        
        # Step 1: Fetch the full data bundle
        logger.info(f"[数据流水线] 开始获取数据 - {symbol} ({market})")
        
        try:
            full_data = fetch_all_data(symbol, trade_date, market, lookback_days)
            result["data"] = full_data
        except Exception as e:
            error_msg = f"Data fetch failed for {symbol}: {str(e)}"
            logger.error(f"[数据流水线] {error_msg}")
            result["validation_summary"]["fetch_failed"] = True
            result["validation_summary"]["error"] = error_msg
            
            if self.strict_validation:
                raise DataPipelineValidationError(error_msg, result["validation_summary"])
            return result
        
        # Step 2: Validate OHLCV data
        logger.info(f"[数据流水线] 验证 OHLCV 数据 - {symbol}")
        
        ohlcv_df = full_data.get("ohlcv_df")
        ohlcv_valid, ohlcv_report = self.validate_ohlcv_data(ohlcv_df, symbol)
        
        result["validation_summary"]["ohlcv"] = ohlcv_report
        self.log_validation("OHLCV验证", symbol, ohlcv_valid, ohlcv_report)
        
        if not ohlcv_valid and self.strict_validation:
            raise DataPipelineValidationError(
                f"OHLCV validation failed for {symbol}",
                result["validation_summary"]
            )
        
        # Step 3: Validate financial metrics
        logger.info(f"[数据流水线] 验证财务指标 - {symbol}")
        
        financial_metrics = full_data.get("financial_metrics", {})
        finance_valid, finance_report = self.validate_financial_metrics(
            financial_metrics, symbol
        )
        
        result["validation_summary"]["financial"] = finance_report
        self.log_validation("财务指标验证", symbol, finance_valid, finance_report)
        
        # Step 4: Generate overall data quality report
        if ohlcv_df is not None and not ohlcv_df.empty:
            quality_report = BatchDataValidator.generate_quality_report(ohlcv_df)
            result["validation_summary"]["data_quality"] = quality_report
        
        # Step 5: Overall validation summary
        overall_valid = ohlcv_valid and finance_valid
        result["validation_summary"]["overall_valid"] = overall_valid
        result["validation_summary"]["timestamp"] = datetime.now().isoformat()
        
        logger.info(
            f"[数据流水线] 完成 - {symbol} - "
            f"整体{'通过' if overall_valid else '未通过'}"
        )
        
        return result
    
    def fetch_only_ohlcv(self, symbol: str, start_date: str, 
                        end_date: str, market: str = "cn") -> Dict[str, Any]:
        """Fetch and validate only OHLCV data.
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            market: Market (cn or us)
            
        Returns:
            OHLCV data with validation results
        """
        result = {
            "symbol": symbol,
            "market": market,
            "start_date": start_date,
            "end_date": end_date,
            "validation_summary": {},
            "ohlcv_df": None
        }
        
        # Fetch data
        try:
            df = get_stock_ohlcv(symbol, start_date, end_date, market)
            result["ohlcv_df"] = df
        except Exception as e:
            error_msg = f"OHLCV fetch failed: {str(e)}"
            result["validation_summary"]["error"] = error_msg
            logger.error(f"[数据流水线] {error_msg}")
            
            if self.strict_validation:
                raise DataPipelineValidationError(error_msg, result["validation_summary"])
            return result
        
        # Validate
        valid, report = self.validate_ohlcv_data(df, symbol)
        result["validation_summary"] = report
        self.log_validation("OHLCV验证", symbol, valid, report)
        
        if not valid and self.strict_validation:
            raise DataPipelineValidationError(
                f"OHLCV validation failed",
                result["validation_summary"]
            )
        
        return result
    
    def get_validation_logs(self) -> list:
        """Get all validation logs from this pipeline instance."""
        return self._validation_logs
    
    def clear_validation_logs(self):
        """Clear validation logs."""
        self._validation_logs = []


# Convenience function for quick access
_pipeline_instance: Optional[DataPipeline] = None


def get_pipeline(strict: bool = None, preset: str = None) -> DataPipeline:
    """Get or create a DataPipeline singleton instance.
    
    Args:
        strict: Whether to use strict validation (deprecated, use preset)
        preset: Configuration preset to use ("PRODUCTION", "BACKTEST", "DEVELOPMENT")
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        if preset is not None:
            _pipeline_instance = DataPipeline(preset=preset)
        elif strict is not None:
            _pipeline_instance = DataPipeline(strict_validation=strict)
        else:
            _pipeline_instance = DataPipeline()  # Use production defaults
    return _pipeline_instance


def validated_data_fetch(
    symbol: str,
    trade_date: str,
    market: str = "cn",
    lookback_days: int = 365,
    strict: bool = None,
    preset: str = None
) -> Dict[str, Any]:
    """Convenience function for validated data fetching.
    
    Args:
        symbol: Stock symbol
        trade_date: End date for data
        market: Market (cn or us)
        lookback_days: Number of days to look back
        strict: Deprecated, use preset
        preset: Configuration preset ("PRODUCTION", "BACKTEST", "DEVELOPMENT")
    """
    pipeline = DataPipeline(strict_validation=strict, preset=preset)
    return pipeline.fetch_validated_data(symbol, trade_date, market, lookback_days)


def validated_ohlcv_fetch(
    symbol: str,
    start_date: str,
    end_date: str,
    market: str = "cn",
    strict: bool = None,
    preset: str = None
) -> Dict[str, Any]:
    """Convenience function for validated OHLCV fetching.
    
    Args:
        symbol: Stock symbol
        start_date: Start date
        end_date: End date
        market: Market (cn or us)
        strict: Deprecated, use preset
        preset: Configuration preset ("PRODUCTION", "BACKTEST", "DEVELOPMENT")
    """
    pipeline = DataPipeline(strict_validation=strict, preset=preset)
    return pipeline.fetch_only_ohlcv(symbol, start_date, end_date, market)
