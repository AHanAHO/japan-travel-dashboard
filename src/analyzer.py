"""
src/analyzer.py
===============
資料分析模組。

提供三個公開函式：
    analyze_fares(records)          → FareAnalysisResult
    analyze_exchange_rates(records) → RateAnalysisResult
    analyze_comfort(records)        → ComfortAnalysisResult

各函式接收 data_loader 回傳的 record list，
以 pandas 進行月份聚合分析，回傳對應的 result dataclass。
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from .models import (
    ComfortAnalysisResult,
    ComfortScoreRecord,
    ExchangeRateRecord,
    FareAnalysisResult,
    FareRecord,
    RateAnalysisResult,
)

# 完整月份索引，確保即使某月無資料也保留 NaN 佔位
_ALL_MONTHS = pd.Index(range(1, 13), name="month")


# ---------------------------------------------------------------------------
# 票價分析
# ---------------------------------------------------------------------------

def analyze_fares(records: Sequence[FareRecord]) -> FareAnalysisResult:
    """
    分析票價記錄，計算各航空公司月均票價與各月最低票價。

    Parameters
    ----------
    records : Sequence[FareRecord]
        由 load_fares() 回傳的有效票價記錄清單。

    Returns
    -------
    FareAnalysisResult
        - monthly_avg_by_airline : DataFrame
            index=month(1–12), columns=airline(CI/BR/JX)
            值為月均票價（四捨五入至整數），無資料填 NaN。
        - monthly_min_fare : Series
            index=month(1–12)，值為該月所有航空公司最低票價，無資料填 NaN。

    Notes
    -----
    - 空 records 回傳全 NaN 的結果。
    - 月份從 date 欄位的月份部分提取（YYYY-MM-DD → MM）。

    Examples
    --------
    >>> from src.models import FareRecord
    >>> records = [FareRecord("2024-01-05", "CI", "TPE", "東京", 15800)]
    >>> result = analyze_fares(records)
    >>> result.monthly_avg_by_airline.loc[1, "CI"]
    15800
    """
    if not records:
        # 回傳全 NaN 的空結果
        empty_df = pd.DataFrame(
            index=_ALL_MONTHS,
            columns=["CI", "BR", "JX"],
            dtype=float,
        )
        empty_series = pd.Series(index=_ALL_MONTHS, dtype=float, name="min_fare")
        return FareAnalysisResult(
            monthly_avg_by_airline=empty_df,
            monthly_min_fare=empty_series,
        )

    # 建立 DataFrame
    df = pd.DataFrame(
        [
            {
                "month": int(r.date[5:7]),   # YYYY-MM-DD → MM
                "airline": r.airline,
                "fare": r.roundtrip_fare_twd,
            }
            for r in records
        ]
    )

    # --- 各航空公司月均票價 ---
    # groupby → mean → pivot → reindex 確保所有月份與航空公司都存在
    avg_by_airline = (
        df.groupby(["month", "airline"])["fare"]
        .mean()
        .round(0)
        .astype("Int64")          # 可為 NaN 的整數型別
        .unstack("airline")       # airline → columns
        .reindex(index=_ALL_MONTHS, columns=["CI", "BR", "JX"])
    )

    # --- 各月最低票價（所有航空公司合併）---
    monthly_min = (
        df.groupby("month")["fare"]
        .min()
        .reindex(_ALL_MONTHS)
    )
    monthly_min.name = "min_fare"

    return FareAnalysisResult(
        monthly_avg_by_airline=avg_by_airline,
        monthly_min_fare=monthly_min,
    )


# ---------------------------------------------------------------------------
# 目的地票價分析
# ---------------------------------------------------------------------------

def analyze_fares_for_city_with_fallback(
    records: Sequence[FareRecord],
    city: str,
) -> tuple["FareAnalysisResult", "pd.Series"]:
    """
    分析飛往指定目的地城市的票價，缺失月份以跨城市平均估算補值。

    Parameters
    ----------
    records : Sequence[FareRecord]
        由 load_fares() 回傳的有效票價記錄清單（所有目的地）。
    city : str
        目的地城市名稱。

    Returns
    -------
    (FareAnalysisResult, estimated_months)
        FareAnalysisResult.monthly_min_fare：
            有實際資料的月份使用實際值；
            缺失月份使用同月份其他目的地的平均最低票價估算；
            若同月份所有目的地均無資料，仍為 NaN。
        estimated_months : pd.Series[bool]
            index=month(1–12)，True 表示該月票價為估算值。
    """
    # 1. 該城市的實際票價
    city_result = analyze_fares_for_city(records, city)
    actual_min = city_result.monthly_min_fare.copy()

    # 2. 計算所有目的地的月份平均最低票價（排除目標城市）
    other_records = [r for r in records if r.destination != city]
    if other_records:
        df_other = pd.DataFrame(
            [
                {
                    "month": int(r.date[5:7]),
                    "fare": r.roundtrip_fare_twd,
                }
                for r in other_records
            ]
        )
        cross_city_avg = (
            df_other.groupby("month")["fare"]
            .mean()
            .round(0)
            .reindex(_ALL_MONTHS)
        )
    else:
        cross_city_avg = pd.Series(index=_ALL_MONTHS, dtype=float)

    # 3. 標記估算月份並填補
    estimated_months = pd.Series(False, index=_ALL_MONTHS, dtype=bool)
    filled_min = actual_min.copy()

    for m in range(1, 13):
        if pd.isna(actual_min.get(m)) and not pd.isna(cross_city_avg.get(m)):
            filled_min[m] = cross_city_avg[m]
            estimated_months[m] = True

    # 4. 重建 FareAnalysisResult（avg_by_airline 保持原樣，只更新 monthly_min_fare）
    filled_result = FareAnalysisResult(
        monthly_avg_by_airline=city_result.monthly_avg_by_airline,
        monthly_min_fare=filled_min,
    )

    return filled_result, estimated_months


def build_fare_chart_data_for_city(
    records: Sequence[FareRecord],
    city: str,
) -> FareAnalysisResult:
    """
    為票價圖表建立完整的 (airline × month) 票價矩陣，缺失格以估算值補齊。

    補值優先順序（每個缺失的 airline × month 格）：
        1. 同月份、其他目的地、同航空公司的平均票價
        2. 同月份、所有目的地、所有航空公司的平均票價
        3. 仍為 NaN（該月份完全無任何票價資料）

    Parameters
    ----------
    records : Sequence[FareRecord]
        由 load_fares() 回傳的有效票價記錄清單（所有目的地）。
    city : str
        目的地城市名稱。

    Returns
    -------
    FareAnalysisResult
        - monthly_avg_by_airline : DataFrame（已補值，估算格以 estimated_by_airline 標記）
        - monthly_min_fare : Series（已補值，與 analyze_fares_for_city_with_fallback 一致）
        - estimated_by_airline : DataFrame[bool]（True = 估算值）
    """
    airlines = ["CI", "BR", "JX"]

    # --- 1. 該城市的實際票價矩陣 ---
    city_result = analyze_fares_for_city(records, city)
    # 確保使用純整數 index（1–12），避免 named index 對齊問題
    actual_avg = city_result.monthly_avg_by_airline.copy().astype(float)
    actual_avg.index = list(range(1, 13))

    # --- 2. 同航空公司、其他目的地的月均票價（fallback level 1）---
    other_records = [r for r in records if r.destination != city]
    if other_records:
        df_other = pd.DataFrame(
            [
                {
                    "month": int(r.date[5:7]),
                    "airline": r.airline,
                    "fare": r.roundtrip_fare_twd,
                }
                for r in other_records
            ]
        )
        # 同航空公司、其他目的地的月均票價
        airline_fallback = (
            df_other.groupby(["month", "airline"])["fare"]
            .mean()
            .round(0)
            .unstack("airline")
            .reindex(index=list(range(1, 13)), columns=airlines)
        )
        # 所有目的地、所有航空公司的月均票價（fallback level 2）
        global_fallback = (
            df_other.groupby("month")["fare"]
            .mean()
            .round(0)
            .reindex(list(range(1, 13)))
        )
    else:
        airline_fallback = pd.DataFrame(
            index=list(range(1, 13)), columns=airlines, dtype=float
        )
        global_fallback = pd.Series(index=list(range(1, 13)), dtype=float)

    # --- 3. 也把目標城市自己的資料納入 global_fallback ---
    all_records_df = pd.DataFrame(
        [
            {"month": int(r.date[5:7]), "fare": r.roundtrip_fare_twd}
            for r in records
        ]
    )
    if not all_records_df.empty:
        global_fallback_all = (
            all_records_df.groupby("month")["fare"]
            .mean()
            .round(0)
            .reindex(list(range(1, 13)))  # 使用純整數 index，與 filled_avg 一致
        )
    else:
        global_fallback_all = pd.Series(index=list(range(1, 13)), dtype=float)

    # --- 4. 填補缺失格 ---
    filled_avg = actual_avg.copy()
    # estimated_mask 也使用純整數 index，與 filled_avg 保持一致
    estimated_mask = pd.DataFrame(
        False, index=list(range(1, 13)), columns=airlines, dtype=bool
    )

    for m in range(1, 13):
        for airline in airlines:
            if pd.isna(filled_avg.loc[m, airline]):
                # Level 1: 同航空公司、其他目的地
                lvl1 = airline_fallback.loc[m, airline] if airline in airline_fallback.columns else float("nan")
                if not pd.isna(lvl1):
                    filled_avg.loc[m, airline] = lvl1
                    estimated_mask.loc[m, airline] = True
                else:
                    # Level 2: 所有目的地、所有航空公司（排除目標城市）
                    lvl2 = global_fallback.get(m, float("nan"))
                    if not pd.isna(lvl2):
                        filled_avg.loc[m, airline] = lvl2
                        estimated_mask.loc[m, airline] = True
                    else:
                        # Level 3: 包含目標城市的全域平均
                        lvl3 = global_fallback_all.get(m, float("nan"))
                        if not pd.isna(lvl3):
                            filled_avg.loc[m, airline] = lvl3
                            estimated_mask.loc[m, airline] = True

    # --- 5. 更新 monthly_min_fare（取填補後各月最小值）---
    filled_min = filled_avg.min(axis=1)
    filled_min.name = "min_fare"

    return FareAnalysisResult(
        monthly_avg_by_airline=filled_avg,
        monthly_min_fare=filled_min,
        estimated_by_airline=estimated_mask,
    )


def analyze_fares_for_city(
    records: Sequence[FareRecord],
    city: str,
) -> FareAnalysisResult:
    """
    分析飛往指定目的地城市的票價記錄。

    只計算 destination == city 的記錄。
    """
    city_records = [r for r in records if r.destination == city]
    return analyze_fares(city_records)


# ---------------------------------------------------------------------------
# 匯率分析
# ---------------------------------------------------------------------------

def analyze_exchange_rates(
    records: Sequence[ExchangeRateRecord],
) -> RateAnalysisResult:
    """
    分析匯率記錄，計算月均匯率、全年平均匯率與最佳換匯月份。

    Parameters
    ----------
    records : Sequence[ExchangeRateRecord]
        由 load_exchange_rates() 回傳的有效匯率記錄清單。

    Returns
    -------
    RateAnalysisResult
        - monthly_avg_rate : Series
            index=month(1–12)，值為月均 JPY/TWD 匯率（保留四位小數），
            無資料月份填 NaN。
        - annual_avg_rate : float
            所有有資料月份的平均匯率（保留四位小數）。
            若無任何資料，回傳 0.0。
        - best_months : list[int]
            月均匯率最高的月份清單（含並列情況）。
            若無資料，回傳空清單。

    Notes
    -----
    - JPY/TWD 匯率越低，代表 1 日圓需要的台幣越少，即台幣可換到更多日圓，換匯越划算。
    - 因此最佳換匯月份為月均匯率最低的月份。
    - 月份從 date 欄位的月份部分提取。

    Examples
    --------
    >>> from src.models import ExchangeRateRecord
    >>> records = [
    ...     ExchangeRateRecord("2024-04-01", 0.2078),
    ...     ExchangeRateRecord("2024-08-15", 0.2125),
    ... ]
    >>> result = analyze_exchange_rates(records)
    >>> result.best_months  # 匯率最低的月份
    [4]
    """
    if not records:
        empty_series = pd.Series(
            index=_ALL_MONTHS, dtype=float, name="jpy_twd_rate"
        )
        return RateAnalysisResult(
            monthly_avg_rate=empty_series,
            annual_avg_rate=0.0,
            best_months=[],
        )

    df = pd.DataFrame(
        [
            {
                "month": int(r.date[5:7]),
                "rate": r.jpy_twd_rate,
            }
            for r in records
        ]
    )

    # --- 月均匯率（保留四位小數）---
    monthly_avg = (
        df.groupby("month")["rate"]
        .mean()
        .round(4)
        .reindex(_ALL_MONTHS)
    )
    monthly_avg.name = "jpy_twd_rate"

    # --- 全年平均匯率 ---
    annual_avg = round(float(monthly_avg.dropna().mean()), 4) if not monthly_avg.dropna().empty else 0.0

    # --- 最佳換匯月份（匯率最低 = 台幣可換最多日圓，含並列）---
    valid = monthly_avg.dropna()
    if valid.empty:
        best_months: list[int] = []
    else:
        min_rate = valid.min()
        best_months = sorted(int(m) for m in valid[valid == min_rate].index.tolist())

    return RateAnalysisResult(
        monthly_avg_rate=monthly_avg,
        annual_avg_rate=annual_avg,
        best_months=best_months,
    )


# ---------------------------------------------------------------------------
# 舒適度分析
# ---------------------------------------------------------------------------

def analyze_comfort(
    records: Sequence[ComfortScoreRecord],
) -> ComfortAnalysisResult:
    """
    分析舒適度記錄，計算各城市各月份的平均氣溫、降雨機率與人潮指數。

    Parameters
    ----------
    records : Sequence[ComfortScoreRecord]
        由 load_comfort_scores() 回傳的有效舒適度記錄清單。

    Returns
    -------
    ComfortAnalysisResult
        - monthly_comfort : DataFrame
            MultiIndex: (city, month)
            columns: avg_temp_c (float, 一位小數),
                     rain_probability_pct (int),
                     crowd_index (float, 一位小數)
            缺少資料的 (city, month) 組合填入 NaN。

    Notes
    -----
    精度規格：
        avg_temp_c          → 保留一位小數
        rain_probability_pct → 四捨五入至整數
        crowd_index          → 保留一位小數

    Examples
    --------
    >>> from src.models import ComfortScoreRecord
    >>> records = [ComfortScoreRecord(1, "東京", 6.1, 15, 5)]
    >>> result = analyze_comfort(records)
    >>> result.monthly_comfort.loc[("東京", 1), "avg_temp_c"]
    6.1
    """
    if not records:
        empty_df = pd.DataFrame(
            columns=["avg_temp_c", "rain_probability_pct", "crowd_index"]
        )
        empty_df.index = pd.MultiIndex.from_tuples([], names=["city", "month"])
        return ComfortAnalysisResult(monthly_comfort=empty_df)

    df = pd.DataFrame(
        [
            {
                "city": r.city,
                "month": r.month,
                "avg_temp_c": r.avg_temp_c,
                "rain_probability_pct": r.rain_probability_pct,
                "crowd_index": r.crowd_index,
            }
            for r in records
        ]
    )

    # --- 依 (city, month) 分組計算平均值 ---
    grouped = df.groupby(["city", "month"]).agg(
        avg_temp_c=("avg_temp_c", "mean"),
        rain_probability_pct=("rain_probability_pct", "mean"),
        crowd_index=("crowd_index", "mean"),
    )

    # 套用精度規格
    grouped["avg_temp_c"] = grouped["avg_temp_c"].round(1)
    grouped["rain_probability_pct"] = grouped["rain_probability_pct"].round(0).astype("Int64")
    grouped["crowd_index"] = grouped["crowd_index"].round(1)

    # 確保 MultiIndex 名稱正確
    grouped.index.names = ["city", "month"]

    return ComfortAnalysisResult(monthly_comfort=grouped)


# ---------------------------------------------------------------------------
# 便利函式：取得摘要統計（供 main.py 顯示進度用）
# ---------------------------------------------------------------------------

def fare_summary(result: FareAnalysisResult) -> dict:
    """
    回傳票價分析的摘要統計，方便 main.py 顯示。

    Returns
    -------
    dict with keys:
        cheapest_month : int | None   最便宜月份
        cheapest_fare  : int | None   最低票價（TWD）
        priciest_month : int | None   最貴月份
        priciest_fare  : int | None   最高票價（TWD）
        data_months    : int          有票價資料的月份數
    """
    valid = result.monthly_min_fare.dropna()
    if valid.empty:
        return {
            "cheapest_month": None,
            "cheapest_fare": None,
            "priciest_month": None,
            "priciest_fare": None,
            "data_months": 0,
        }
    return {
        "cheapest_month": int(valid.idxmin()),
        "cheapest_fare": int(valid.min()),
        "priciest_month": int(valid.idxmax()),
        "priciest_fare": int(valid.max()),
        "data_months": int(valid.count()),
    }


def rate_summary(result: RateAnalysisResult) -> dict:
    """
    回傳匯率分析的摘要統計，方便 main.py 顯示。

    Returns
    -------
    dict with keys:
        best_months    : list[int]   最佳換匯月份
        annual_avg     : float       全年平均匯率
        data_months    : int         有匯率資料的月份數
    """
    return {
        "best_months": result.best_months,
        "annual_avg": result.annual_avg_rate,
        "data_months": int(result.monthly_avg_rate.dropna().count()),
    }
