"""
src/models.py
=============
資料模型定義。

分為兩層：
  1. 列級記錄（Row-level records）
     FareRecord, ExchangeRateRecord, ComfortScoreRecord
     對應 CSV 的單一列，包含型別轉換、基本驗證與 from_dict() 工廠方法。

  2. 分析結果（Analysis results）
     FareAnalysisResult, RateAnalysisResult, ComfortAnalysisResult, ScoreResult
     由 Analyzer / Scorer 產生，以 pandas DataFrame / Series 儲存聚合後的資料。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

VALID_AIRLINES: frozenset[str] = frozenset({"CI", "BR", "JX"})
DATE_PATTERN: re.Pattern[str] = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# 驗證輔助函式
# ---------------------------------------------------------------------------

def _validate_date(value: Any, field_name: str = "date") -> str:
    """確認值符合 YYYY-MM-DD 格式，回傳字串；否則拋出 ValueError。"""
    s = str(value).strip()
    if not DATE_PATTERN.match(s):
        raise ValueError(
            f"{field_name} 格式不符合 YYYY-MM-DD（值：'{s}'）"
        )
    # 進一步確認日期合法（例如 2024-02-30 應拋出錯誤）
    try:
        _date.fromisoformat(s)
    except ValueError:
        raise ValueError(f"{field_name} 不是合法日期（值：'{s}'）")
    return s


def _validate_positive_int(value: Any, field_name: str) -> int:
    """確認值可轉換為正整數；否則拋出 ValueError。"""
    try:
        v = int(float(str(value)))
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} 無法轉換為整數（值：'{value}'）")
    if v <= 0:
        raise ValueError(f"{field_name} 必須為正整數（值：{v}）")
    return v


def _validate_positive_float(value: Any, field_name: str) -> float:
    """確認值可轉換為正浮點數；否則拋出 ValueError。"""
    try:
        v = float(str(value))
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} 無法轉換為浮點數（值：'{value}'）")
    if v <= 0 or v != v:  # v != v 捕捉 NaN
        raise ValueError(f"{field_name} 必須為正浮點數（值：{v}）")
    return v


def _validate_int_range(
    value: Any, field_name: str, min_val: int, max_val: int
) -> int:
    """確認值可轉換為整數且在 [min_val, max_val] 範圍內；否則拋出 ValueError。"""
    try:
        v = int(float(str(value)))
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} 無法轉換為整數（值：'{value}'）")
    if not (min_val <= v <= max_val):
        raise ValueError(
            f"{field_name} 超出範圍 {min_val}–{max_val}（值：{v}）"
        )
    return v


# ---------------------------------------------------------------------------
# 列級記錄（Row-level records）
# ---------------------------------------------------------------------------

@dataclass
class FareRecord:
    """
    對應 fares.csv 的單一列。

    欄位
    ----
    date : str
        票價查詢日期，格式 YYYY-MM-DD。
    airline : str
        航空公司代碼，必須為 CI、BR、JX 之一。
    origin : str
        出發機場 IATA 代碼（例：TPE）。
    destination : str
        目的地城市名稱（例：東京）。
    roundtrip_fare_twd : int
        來回票價（新台幣），必須 > 0。
    """

    date: str
    airline: str
    origin: str
    destination: str
    roundtrip_fare_twd: int

    def __post_init__(self) -> None:
        """建構後執行基本驗證，不合法時拋出 ValueError。"""
        self.date = _validate_date(self.date, "date")
        if self.airline not in VALID_AIRLINES:
            raise ValueError(
                f"airline 值 '{self.airline}' 不在允許清單中（CI/BR/JX）"
            )
        if not str(self.origin).strip():
            raise ValueError("origin 不可為空")
        if not str(self.destination).strip():
            raise ValueError("destination 不可為空")
        self.roundtrip_fare_twd = _validate_positive_int(
            self.roundtrip_fare_twd, "roundtrip_fare_twd"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FareRecord":
        """
        從字典（例如 CSV 列的 dict）建立 FareRecord。

        Parameters
        ----------
        data : dict
            必須包含 date, airline, origin, destination, roundtrip_fare_twd。

        Returns
        -------
        FareRecord

        Raises
        ------
        KeyError
            缺少必要欄位時。
        ValueError
            欄位值不合法時。
        """
        required = {"date", "airline", "origin", "destination", "roundtrip_fare_twd"}
        missing = required - set(data.keys())
        if missing:
            raise KeyError(f"缺少必要欄位：{sorted(missing)}")
        return cls(
            date=data["date"],
            airline=str(data["airline"]).strip().upper(),
            origin=str(data["origin"]).strip().upper(),
            destination=str(data["destination"]).strip(),
            roundtrip_fare_twd=data["roundtrip_fare_twd"],
        )


@dataclass
class ExchangeRateRecord:
    """
    對應 exchange_rates.csv 的單一列。

    欄位
    ----
    date : str
        匯率日期，格式 YYYY-MM-DD。
    jpy_twd_rate : float
        JPY/TWD 匯率（1 日圓 = ? 台幣），必須 > 0。
    """

    date: str
    jpy_twd_rate: float

    def __post_init__(self) -> None:
        """建構後執行基本驗證，不合法時拋出 ValueError。"""
        self.date = _validate_date(self.date, "date")
        self.jpy_twd_rate = _validate_positive_float(
            self.jpy_twd_rate, "jpy_twd_rate"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExchangeRateRecord":
        """
        從字典建立 ExchangeRateRecord。

        Parameters
        ----------
        data : dict
            必須包含 date, jpy_twd_rate。

        Returns
        -------
        ExchangeRateRecord

        Raises
        ------
        KeyError
            缺少必要欄位時。
        ValueError
            欄位值不合法時。
        """
        required = {"date", "jpy_twd_rate"}
        missing = required - set(data.keys())
        if missing:
            raise KeyError(f"缺少必要欄位：{sorted(missing)}")
        return cls(
            date=data["date"],
            jpy_twd_rate=data["jpy_twd_rate"],
        )


@dataclass
class ComfortScoreRecord:
    """
    對應 comfort_scores.csv 的單一列。

    欄位
    ----
    month : int
        月份，範圍 1–12。
    city : str
        目的地城市名稱（例：東京）。
    avg_temp_c : float
        平均氣溫（°C），無範圍限制。
    rain_probability_pct : int
        降雨機率（%），範圍 0–100。
    crowd_index : int
        觀光人潮指數，範圍 1–10（1=人少，10=非常擁擠）。
    """

    month: int
    city: str
    avg_temp_c: float
    rain_probability_pct: int
    crowd_index: int

    def __post_init__(self) -> None:
        """建構後執行基本驗證，不合法時拋出 ValueError。"""
        self.month = _validate_int_range(self.month, "month", 1, 12)
        if not str(self.city).strip():
            raise ValueError("city 不可為空")
        try:
            self.avg_temp_c = float(str(self.avg_temp_c))
        except (ValueError, TypeError):
            raise ValueError(
                f"avg_temp_c 無法轉換為浮點數（值：'{self.avg_temp_c}'）"
            )
        self.rain_probability_pct = _validate_int_range(
            self.rain_probability_pct, "rain_probability_pct", 0, 100
        )
        self.crowd_index = _validate_int_range(
            self.crowd_index, "crowd_index", 1, 10
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComfortScoreRecord":
        """
        從字典建立 ComfortScoreRecord。

        Parameters
        ----------
        data : dict
            必須包含 month, city, avg_temp_c, rain_probability_pct, crowd_index。

        Returns
        -------
        ComfortScoreRecord

        Raises
        ------
        KeyError
            缺少必要欄位時。
        ValueError
            欄位值不合法時。
        """
        required = {"month", "city", "avg_temp_c", "rain_probability_pct", "crowd_index"}
        missing = required - set(data.keys())
        if missing:
            raise KeyError(f"缺少必要欄位：{sorted(missing)}")
        return cls(
            month=data["month"],
            city=str(data["city"]).strip(),
            avg_temp_c=data["avg_temp_c"],
            rain_probability_pct=data["rain_probability_pct"],
            crowd_index=data["crowd_index"],
        )


# ---------------------------------------------------------------------------
# 分析結果（Analysis results）
# ---------------------------------------------------------------------------

@dataclass
class FareAnalysisResult:
    """
    票價分析結果，由 Analyzer.analyze_fares() 產生。

    Attributes
    ----------
    monthly_avg_by_airline : pd.DataFrame
        index: month (int 1–12)
        columns: airline codes (CI, BR, JX)
        values: 月均來回票價（TWD，四捨五入至整數）或 NaN（無資料）
    monthly_min_fare : pd.Series
        index: month (int 1–12)
        values: 該月所有航空公司中的最低票價（int）或 NaN（無資料）
    estimated_by_airline : pd.DataFrame | None
        index: month (int 1–12), columns: airline codes (CI, BR, JX)
        values: bool — True 表示該 (month, airline) 票價為估算值
        若為 None，表示無估算資料（全為實際值）
    """

    monthly_avg_by_airline: pd.DataFrame
    monthly_min_fare: pd.Series
    estimated_by_airline: "pd.DataFrame | None" = None


@dataclass
class RateAnalysisResult:
    """
    匯率分析結果，由 Analyzer.analyze_rates() 產生。

    Attributes
    ----------
    monthly_avg_rate : pd.Series
        index: month (int 1–12)
        values: 月均 JPY/TWD 匯率（float，保留四位小數）或 NaN（無資料）
    annual_avg_rate : float
        全年（所有有資料月份）平均匯率。
    best_months : list[int]
        月均匯率最高的月份清單（可能多個，含並列情況）。
    """

    monthly_avg_rate: pd.Series
    annual_avg_rate: float
    best_months: list[int] = field(default_factory=list)


@dataclass
class ComfortAnalysisResult:
    """
    旅遊舒適度分析結果，由 Analyzer.analyze_comfort() 產生。

    Attributes
    ----------
    monthly_comfort : pd.DataFrame
        MultiIndex: (city, month)
        columns: avg_temp_c (float, 一位小數),
                 rain_probability_pct (int),
                 crowd_index (float, 一位小數)
        缺少資料的 (city, month) 組合填入 NaN。
    """

    monthly_comfort: pd.DataFrame


@dataclass
class ScoreResult:
    """
    綜合評分結果，由 Scorer.calculate_scores() 產生。

    Attributes
    ----------
    fare_score : pd.Series
        index: month (int 1–12)
        values: 票價分數 0–100，或 NaN（該月無票價資料）
    rate_score : pd.Series
        index: month (int 1–12)
        values: 匯率分數 0–100，或 NaN（該月無匯率資料）
    comfort_score : pd.Series
        index: month (int 1–12)
        values: 舒適度分數 0–100
    total_score : pd.Series
        index: month (int 1–12)
        values: 綜合評分 0–100（四捨五入至一位小數），
                或 NaN（票價分數為 NaN 時）
    fare_estimated : pd.Series
        index: month (int 1–12)
        values: bool — True 表示該月票價為跨城市平均估算值，非實際票價
    temp_score : pd.Series | None
        index: month (int 1–12)
        values: 氣溫子分數 0–100（供前端權重調整使用）
    rain_score : pd.Series | None
        index: month (int 1–12)
        values: 降雨子分數 0–100（供前端權重調整使用）
    crowd_score : pd.Series | None
        index: month (int 1–12)
        values: 人潮子分數 0–100（供前端權重調整使用）

    Notes
    -----
    評分公式：
        fare_score(m)    = 100 × (max_min - min_fare(m)) / (max_min - min_min)
                           分母為 0 時全設為 50.0
        rate_score(m)    = 100 × (max_rate - avg_rate(m)) / (max_rate - min_rate)
                           分母為 0 時全設為 50.0
        comfort_score(m) = temp_score×0.4 + rain_score×0.3 + crowd_score×0.3
                           temp_score:  10–25°C=100；低溫非線性扣分；高溫非線性扣分
                           rain_score:  100 − rain_probability_pct
                           crowd_score: 非線性懲罰（1–5輕微，6–7中度，8–10重度二次曲線）
        total_score(m)   = fare × 0.4 + comfort × 0.5 + rate × 0.1
    """

    fare_score: pd.Series
    rate_score: pd.Series
    comfort_score: pd.Series
    total_score: pd.Series
    fare_estimated: pd.Series = field(
        default_factory=lambda: pd.Series(
            [False] * 12,
            index=pd.Index(range(1, 13), name="month"),
            dtype=bool,
        )
    )
    temp_score: "pd.Series | None" = None
    rain_score: "pd.Series | None" = None
    crowd_score: "pd.Series | None" = None
