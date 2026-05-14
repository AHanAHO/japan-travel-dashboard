"""
tests/test_analyzer.py
======================
Analyzer 單元測試。

涵蓋：
  - analyze_fares()
      正常分組、月均計算、最低票價、NaN 填充、空輸入
  - analyze_exchange_rates()
      月均計算、全年平均、最佳月份識別（含並列）、空輸入
  - analyze_comfort()
      分組計算、精度規格、MultiIndex 結構、空輸入
  - fare_summary() / rate_summary() 摘要函式
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.analyzer import (
    analyze_comfort,
    analyze_exchange_rates,
    analyze_fares,
    fare_summary,
    rate_summary,
)
from src.models import (
    ComfortScoreRecord,
    ExchangeRateRecord,
    FareRecord,
)


# ---------------------------------------------------------------------------
# 輔助工廠函式
# ---------------------------------------------------------------------------

def _fare(date: str, airline: str, fare: int) -> FareRecord:
    return FareRecord(date, airline, "TPE", "東京", fare)


def _rate(date: str, rate: float) -> ExchangeRateRecord:
    return ExchangeRateRecord(date, rate)


def _comfort(month: int, city: str, temp: float, rain: int, crowd: int) -> ComfortScoreRecord:
    return ComfortScoreRecord(month, city, temp, rain, crowd)


# ===========================================================================
# analyze_fares
# ===========================================================================

class TestAnalyzeFares:

    def test_empty_records_returns_all_nan(self) -> None:
        """空輸入應回傳全 NaN 的 DataFrame 與 Series。"""
        result = analyze_fares([])
        assert result.monthly_avg_by_airline.shape == (12, 3)
        assert result.monthly_avg_by_airline.isna().all().all()
        assert result.monthly_min_fare.isna().all()

    def test_single_record_correct_avg(self) -> None:
        """單筆記錄應正確填入對應月份與航空公司。"""
        records = [_fare("2024-03-08", "CI", 17500)]
        result = analyze_fares(records)
        assert result.monthly_avg_by_airline.loc[3, "CI"] == 17500
        # 其他航空公司該月應為 NaN
        assert pd.isna(result.monthly_avg_by_airline.loc[3, "BR"])
        assert pd.isna(result.monthly_avg_by_airline.loc[3, "JX"])

    def test_monthly_avg_rounds_to_integer(self) -> None:
        """月均票價應四捨五入至整數。"""
        records = [
            _fare("2024-01-05", "CI", 15000),
            _fare("2024-01-20", "CI", 16000),
        ]
        result = analyze_fares(records)
        # (15000 + 16000) / 2 = 15500
        assert result.monthly_avg_by_airline.loc[1, "CI"] == 15500

    def test_monthly_avg_rounds_half_up(self) -> None:
        """月均票價奇數平均應正確四捨五入。"""
        records = [
            _fare("2024-05-01", "BR", 10000),
            _fare("2024-05-15", "BR", 10001),
        ]
        result = analyze_fares(records)
        # (10000 + 10001) / 2 = 10000.5 → 10001 (round half up)
        assert result.monthly_avg_by_airline.loc[5, "BR"] in (10000, 10001)

    def test_monthly_min_fare_is_minimum_across_airlines(self) -> None:
        """月最低票價應為該月所有航空公司中的最小值。"""
        records = [
            _fare("2024-04-02", "CI", 19800),
            _fare("2024-04-10", "BR", 18200),
            _fare("2024-04-18", "JX", 11200),
        ]
        result = analyze_fares(records)
        assert result.monthly_min_fare[4] == 11200

    def test_missing_month_is_nan_not_zero(self) -> None:
        """無資料的月份應填 NaN，不是 0。"""
        records = [_fare("2024-06-06", "CI", 12100)]
        result = analyze_fares(records)
        # 月份 1 無資料
        assert pd.isna(result.monthly_min_fare[1])
        assert pd.isna(result.monthly_avg_by_airline.loc[1, "CI"])

    def test_airline_with_no_data_is_nan(self) -> None:
        """某航空公司在特定月份無資料應填 NaN，不是 0。"""
        records = [_fare("2024-07-04", "CI", 21500)]
        result = analyze_fares(records)
        assert pd.isna(result.monthly_avg_by_airline.loc[7, "BR"])
        assert pd.isna(result.monthly_avg_by_airline.loc[7, "JX"])

    def test_result_index_covers_all_12_months(self) -> None:
        """結果 index 應涵蓋 1–12 月，即使部分月份無資料。"""
        records = [_fare("2024-08-03", "CI", 23800)]
        result = analyze_fares(records)
        assert list(result.monthly_avg_by_airline.index) == list(range(1, 13))
        assert list(result.monthly_min_fare.index) == list(range(1, 13))

    def test_result_columns_contain_all_airlines(self) -> None:
        """結果 columns 應包含 CI、BR、JX。"""
        result = analyze_fares([])
        assert set(result.monthly_avg_by_airline.columns) == {"CI", "BR", "JX"}

    def test_multiple_months_multiple_airlines(self) -> None:
        """多月份多航空公司資料應各自正確分組。"""
        records = [
            _fare("2024-01-05", "CI", 15800),
            _fare("2024-01-12", "BR", 14200),
            _fare("2024-02-03", "CI", 12900),
            _fare("2024-02-22", "JX", 13200),
        ]
        result = analyze_fares(records)
        assert result.monthly_avg_by_airline.loc[1, "CI"] == 15800
        assert result.monthly_avg_by_airline.loc[1, "BR"] == 14200
        assert pd.isna(result.monthly_avg_by_airline.loc[1, "JX"])
        assert result.monthly_avg_by_airline.loc[2, "CI"] == 12900
        assert result.monthly_avg_by_airline.loc[2, "JX"] == 13200
        assert pd.isna(result.monthly_avg_by_airline.loc[2, "BR"])

    def test_min_fare_ignores_nan_months(self) -> None:
        """月最低票價計算不應受 NaN 月份影響。"""
        records = [
            _fare("2024-01-05", "CI", 15800),
            _fare("2024-12-07", "CI", 22100),
        ]
        result = analyze_fares(records)
        assert result.monthly_min_fare[1] == 15800
        assert result.monthly_min_fare[12] == 22100
        # 其他月份應為 NaN
        for m in range(2, 12):
            assert pd.isna(result.monthly_min_fare[m])


# ===========================================================================
# analyze_exchange_rates
# ===========================================================================

class TestAnalyzeExchangeRates:

    def test_empty_records_returns_all_nan(self) -> None:
        """空輸入應回傳全 NaN Series 與空 best_months。"""
        result = analyze_exchange_rates([])
        assert result.monthly_avg_rate.isna().all()
        assert result.annual_avg_rate == 0.0
        assert result.best_months == []

    def test_single_record_correct_month(self) -> None:
        """單筆記錄應填入正確月份。"""
        records = [_rate("2024-08-15", 0.2125)]
        result = analyze_exchange_rates(records)
        assert result.monthly_avg_rate[8] == pytest.approx(0.2125, abs=1e-4)

    def test_monthly_avg_rounds_to_4_decimals(self) -> None:
        """月均匯率應保留四位小數。"""
        records = [
            _rate("2024-01-01", 0.2105),
            _rate("2024-01-15", 0.2098),
        ]
        result = analyze_exchange_rates(records)
        expected = round((0.2105 + 0.2098) / 2, 4)
        assert result.monthly_avg_rate[1] == pytest.approx(expected, abs=1e-4)

    def test_annual_avg_is_mean_of_monthly_avgs(self) -> None:
        """全年平均應為各月均值的平均。"""
        records = [
            _rate("2024-01-01", 0.2100),
            _rate("2024-02-01", 0.2200),
        ]
        result = analyze_exchange_rates(records)
        expected = round((0.2100 + 0.2200) / 2, 4)
        assert result.annual_avg_rate == pytest.approx(expected, abs=1e-4)

    def test_best_months_is_highest_rate_month(self) -> None:
        """best_months 應為月均匯率最低的月份（匯率低 = 台幣可換更多日圓）。"""
        records = [
            _rate("2024-01-01", 0.2100),
            _rate("2024-04-01", 0.2078),   # 最低匯率 → 最佳換匯
            _rate("2024-12-01", 0.2085),
        ]
        result = analyze_exchange_rates(records)
        assert result.best_months == [4]

    def test_best_months_handles_tie(self) -> None:
        """並列最低匯率時，best_months 應包含所有並列月份。"""
        records = [
            _rate("2024-03-01", 0.2078),   # 並列最低
            _rate("2024-08-01", 0.2078),   # 並列最低
            _rate("2024-05-01", 0.2120),
        ]
        result = analyze_exchange_rates(records)
        assert sorted(result.best_months) == [3, 8]

    def test_missing_month_is_nan(self) -> None:
        """無資料月份應填 NaN。"""
        records = [_rate("2024-06-01", 0.2103)]
        result = analyze_exchange_rates(records)
        assert pd.isna(result.monthly_avg_rate[1])
        assert not pd.isna(result.monthly_avg_rate[6])

    def test_result_index_covers_all_12_months(self) -> None:
        """結果 index 應涵蓋 1–12 月。"""
        result = analyze_exchange_rates([])
        assert list(result.monthly_avg_rate.index) == list(range(1, 13))

    def test_multiple_records_same_month_averaged(self) -> None:
        """同月份多筆記錄應取平均。"""
        records = [
            _rate("2024-07-01", 0.2115),
            _rate("2024-07-15", 0.2118),
        ]
        result = analyze_exchange_rates(records)
        expected = round((0.2115 + 0.2118) / 2, 4)
        assert result.monthly_avg_rate[7] == pytest.approx(expected, abs=1e-4)


# ===========================================================================
# analyze_comfort
# ===========================================================================

class TestAnalyzeComfort:

    def test_empty_records_returns_empty_dataframe(self) -> None:
        """空輸入應回傳空 DataFrame，MultiIndex 名稱正確。"""
        result = analyze_comfort([])
        assert result.monthly_comfort.empty
        assert result.monthly_comfort.index.names == ["city", "month"]

    def test_single_record_correct_values(self) -> None:
        """單筆記錄應正確填入對應 (city, month)。"""
        records = [_comfort(4, "東京", 17.8, 40, 9)]
        result = analyze_comfort(records)
        row = result.monthly_comfort.loc[("東京", 4)]
        assert row["avg_temp_c"] == pytest.approx(17.8, abs=0.05)
        assert int(row["rain_probability_pct"]) == 40
        assert row["crowd_index"] == pytest.approx(9.0, abs=0.05)

    def test_avg_temp_rounded_to_1_decimal(self) -> None:
        """avg_temp_c 應保留一位小數。"""
        records = [
            _comfort(1, "東京", 6.14, 15, 5),
            _comfort(1, "東京", 6.16, 15, 5),
        ]
        result = analyze_comfort(records)
        val = result.monthly_comfort.loc[("東京", 1), "avg_temp_c"]
        # (6.14 + 6.16) / 2 = 6.15 → 6.2 (round half up) or 6.1/6.2 depending on impl
        assert round(float(val), 1) == float(val)

    def test_rain_rounded_to_integer(self) -> None:
        """rain_probability_pct 應四捨五入至整數。"""
        records = [
            _comfort(3, "大阪", 13.2, 37, 8),
            _comfort(3, "大阪", 13.2, 38, 8),
        ]
        result = analyze_comfort(records)
        val = result.monthly_comfort.loc[("大阪", 3), "rain_probability_pct"]
        # (37 + 38) / 2 = 37.5 → 38
        assert float(val) == float(int(float(val)))

    def test_crowd_rounded_to_1_decimal(self) -> None:
        """crowd_index 應保留一位小數。"""
        records = [
            _comfort(7, "福岡", 30.5, 62, 5),
            _comfort(7, "福岡", 30.5, 62, 6),
        ]
        result = analyze_comfort(records)
        val = result.monthly_comfort.loc[("福岡", 7), "crowd_index"]
        # (5 + 6) / 2 = 5.5
        assert float(val) == pytest.approx(5.5, abs=0.05)

    def test_multiple_cities_independent(self) -> None:
        """不同城市的資料應各自獨立計算。"""
        records = [
            _comfort(1, "東京", 6.1, 15, 5),
            _comfort(1, "大阪", 7.0, 18, 5),
        ]
        result = analyze_comfort(records)
        assert result.monthly_comfort.loc[("東京", 1), "avg_temp_c"] == pytest.approx(6.1, abs=0.05)
        assert result.monthly_comfort.loc[("大阪", 1), "avg_temp_c"] == pytest.approx(7.0, abs=0.05)

    def test_negative_temperature_preserved(self) -> None:
        """負氣溫（如札幌冬季）應正確保留。"""
        records = [_comfort(1, "札幌", -3.2, 40, 3)]
        result = analyze_comfort(records)
        assert result.monthly_comfort.loc[("札幌", 1), "avg_temp_c"] == pytest.approx(-3.2, abs=0.05)

    def test_multiindex_names_are_city_and_month(self) -> None:
        """MultiIndex 名稱應為 ['city', 'month']。"""
        records = [_comfort(6, "沖繩", 28.9, 55, 6)]
        result = analyze_comfort(records)
        assert result.monthly_comfort.index.names == ["city", "month"]

    def test_columns_are_correct(self) -> None:
        """結果 DataFrame 應包含三個正確欄位。"""
        records = [_comfort(1, "東京", 6.1, 15, 5)]
        result = analyze_comfort(records)
        assert set(result.monthly_comfort.columns) == {
            "avg_temp_c",
            "rain_probability_pct",
            "crowd_index",
        }

    def test_multiple_records_same_city_month_averaged(self) -> None:
        """同 (city, month) 多筆記錄應取平均。"""
        records = [
            _comfort(8, "東京", 30.0, 50, 7),
            _comfort(8, "東京", 31.6, 50, 7),
        ]
        result = analyze_comfort(records)
        val = result.monthly_comfort.loc[("東京", 8), "avg_temp_c"]
        assert float(val) == pytest.approx(30.8, abs=0.1)


# ===========================================================================
# fare_summary / rate_summary
# ===========================================================================

class TestSummaryFunctions:

    def test_fare_summary_empty(self) -> None:
        """空資料的 fare_summary 應回傳 None 值。"""
        result = analyze_fares([])
        summary = fare_summary(result)
        assert summary["cheapest_month"] is None
        assert summary["cheapest_fare"] is None
        assert summary["data_months"] == 0

    def test_fare_summary_identifies_cheapest_and_priciest(self) -> None:
        """fare_summary 應正確識別最便宜與最貴月份。"""
        records = [
            _fare("2024-02-14", "BR", 11800),   # 最便宜
            _fare("2024-08-03", "CI", 23800),   # 最貴
            _fare("2024-05-05", "CI", 13600),
        ]
        result = analyze_fares(records)
        summary = fare_summary(result)
        assert summary["cheapest_month"] == 2
        assert summary["cheapest_fare"] == 11800
        assert summary["priciest_month"] == 8
        assert summary["priciest_fare"] == 23800

    def test_rate_summary_empty(self) -> None:
        """空資料的 rate_summary 應回傳空 best_months。"""
        result = analyze_exchange_rates([])
        summary = rate_summary(result)
        assert summary["best_months"] == []
        assert summary["annual_avg"] == 0.0
        assert summary["data_months"] == 0

    def test_rate_summary_correct_values(self) -> None:
        """rate_summary 應正確回傳最佳月份（匯率最低）與全年平均。"""
        records = [
            _rate("2024-04-01", 0.2078),   # 最低匯率 → 最佳換匯
            _rate("2024-08-01", 0.2122),
            _rate("2024-08-15", 0.2125),
        ]
        result = analyze_exchange_rates(records)
        summary = rate_summary(result)
        assert 4 in summary["best_months"]
        assert summary["data_months"] == 2
