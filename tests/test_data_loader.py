"""
tests/test_data_loader.py
=========================
DataLoader 單元測試。

涵蓋：
  - 正常資料載入
  - 檔案不存在 → sys.exit(1)
  - 必要欄位缺失 → sys.exit(1)
  - 無效資料列 → 略過並輸出警告
  - 空值列 → 略過並輸出警告
  - 回傳型別正確
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.data_loader import load_comfort_scores, load_exchange_rates, load_fares
from src.models import ComfortScoreRecord, ExchangeRateRecord, FareRecord


# ---------------------------------------------------------------------------
# 輔助函式：在 tmp_path 建立測試 CSV
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, filename: str, content: str) -> Path:
    """去除縮排後寫入 CSV，回傳路徑。"""
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


# ===========================================================================
# load_fares
# ===========================================================================

class TestLoadFares:

    def test_valid_data_returns_records(self, tmp_path: Path) -> None:
        """正常資料應回傳對應數量的 FareRecord。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-01-05,CI,TPE,東京,15800
            2024-02-10,BR,TPE,大阪,14200
            2024-03-15,JX,TPE,福岡,12400
        """)
        records = load_fares(p)
        assert len(records) == 3
        assert all(isinstance(r, FareRecord) for r in records)

    def test_correct_field_values(self, tmp_path: Path) -> None:
        """欄位值應正確對應。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-07-04,CI,TPE,東京,21500
        """)
        records = load_fares(p)
        r = records[0]
        assert r.date == "2024-07-04"
        assert r.airline == "CI"
        assert r.origin == "TPE"
        assert r.destination == "東京"
        assert r.roundtrip_fare_twd == 21500

    def test_file_not_found_exits(self, tmp_path: Path) -> None:
        """檔案不存在應 sys.exit(1)。"""
        with pytest.raises(SystemExit) as exc_info:
            load_fares(tmp_path / "nonexistent.csv")
        assert exc_info.value.code == 1

    def test_missing_required_column_exits(self, tmp_path: Path) -> None:
        """缺少必要欄位應 sys.exit(1)。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination
            2024-01-05,CI,TPE,東京
        """)
        with pytest.raises(SystemExit) as exc_info:
            load_fares(p)
        assert exc_info.value.code == 1

    def test_invalid_airline_skipped_with_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """非法 airline 代碼應略過並輸出警告。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-01-05,CI,TPE,東京,15800
            2024-02-10,ANA,TPE,大阪,14200
        """)
        records = load_fares(p)
        assert len(records) == 1
        assert records[0].airline == "CI"
        captured = capsys.readouterr()
        assert "[警告]" in captured.err
        assert "ANA" in captured.err

    def test_negative_fare_skipped_with_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """負票價應略過並輸出警告。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-01-05,CI,TPE,東京,15800
            2024-02-10,BR,TPE,大阪,-500
        """)
        records = load_fares(p)
        assert len(records) == 1
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_zero_fare_skipped(self, tmp_path: Path) -> None:
        """票價為 0 應略過。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-01-05,CI,TPE,東京,0
        """)
        records = load_fares(p)
        assert len(records) == 0

    def test_invalid_date_format_skipped_with_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """日期格式不符應略過並輸出警告。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024/01/05,CI,TPE,東京,15800
        """)
        records = load_fares(p)
        assert len(records) == 0
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_empty_value_skipped_with_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """空值欄位應略過並輸出警告。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-01-05,,TPE,東京,15800
        """)
        records = load_fares(p)
        assert len(records) == 0
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_warning_contains_row_number(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """警告訊息應包含 CSV 列號。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
            2024-01-05,CI,TPE,東京,15800
            2024-02-10,INVALID,TPE,大阪,14200
        """)
        load_fares(p)
        captured = capsys.readouterr()
        # 第 2 列為有效資料，第 3 列為無效 → 列號應為 3
        assert "3" in captured.err

    def test_multiple_missing_columns_exits(self, tmp_path: Path) -> None:
        """缺少多個必要欄位時，錯誤訊息應列出所有缺少欄位。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline
            2024-01-05,CI
        """)
        with pytest.raises(SystemExit):
            load_fares(p)

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """只有標頭列（無資料）應回傳空清單。"""
        p = _write(tmp_path, "fares.csv", """
            date,airline,origin,destination,roundtrip_fare_twd
        """)
        records = load_fares(p)
        assert records == []


# ===========================================================================
# load_exchange_rates
# ===========================================================================

class TestLoadExchangeRates:

    def test_valid_data_returns_records(self, tmp_path: Path) -> None:
        """正常資料應回傳對應數量的 ExchangeRateRecord。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date,jpy_twd_rate
            2024-01-01,0.2105
            2024-02-01,0.2112
            2024-03-01,0.2095
        """)
        records = load_exchange_rates(p)
        assert len(records) == 3
        assert all(isinstance(r, ExchangeRateRecord) for r in records)

    def test_correct_field_values(self, tmp_path: Path) -> None:
        """欄位值應正確對應。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date,jpy_twd_rate
            2024-08-15,0.2125
        """)
        records = load_exchange_rates(p)
        assert records[0].date == "2024-08-15"
        assert records[0].jpy_twd_rate == pytest.approx(0.2125)

    def test_file_not_found_exits(self, tmp_path: Path) -> None:
        """檔案不存在應 sys.exit(1)。"""
        with pytest.raises(SystemExit) as exc_info:
            load_exchange_rates(tmp_path / "no_file.csv")
        assert exc_info.value.code == 1

    def test_missing_column_exits(self, tmp_path: Path) -> None:
        """缺少 jpy_twd_rate 欄位應 sys.exit(1)。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date
            2024-01-01
        """)
        with pytest.raises(SystemExit) as exc_info:
            load_exchange_rates(p)
        assert exc_info.value.code == 1

    def test_negative_rate_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """負匯率應略過並輸出警告。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date,jpy_twd_rate
            2024-01-01,0.2105
            2024-02-01,-0.01
        """)
        records = load_exchange_rates(p)
        assert len(records) == 1
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_zero_rate_skipped(self, tmp_path: Path) -> None:
        """匯率為 0 應略過。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date,jpy_twd_rate
            2024-01-01,0
        """)
        records = load_exchange_rates(p)
        assert len(records) == 0

    def test_invalid_date_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """日期格式不符應略過並輸出警告。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date,jpy_twd_rate
            20240101,0.2105
        """)
        records = load_exchange_rates(p)
        assert len(records) == 0
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """只有標頭列應回傳空清單。"""
        p = _write(tmp_path, "exchange_rates.csv", """
            date,jpy_twd_rate
        """)
        records = load_exchange_rates(p)
        assert records == []


# ===========================================================================
# load_comfort_scores
# ===========================================================================

class TestLoadComfortScores:

    def test_valid_data_returns_records(self, tmp_path: Path) -> None:
        """正常資料應回傳對應數量的 ComfortScoreRecord。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,東京,6.1,15,5
            7,大阪,31.2,58,6
            12,札幌,-1.5,48,3
        """)
        records = load_comfort_scores(p)
        assert len(records) == 3
        assert all(isinstance(r, ComfortScoreRecord) for r in records)

    def test_correct_field_values(self, tmp_path: Path) -> None:
        """欄位值應正確對應。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            4,東京,17.8,40,9
        """)
        records = load_comfort_scores(p)
        r = records[0]
        assert r.month == 4
        assert r.city == "東京"
        assert r.avg_temp_c == pytest.approx(17.8)
        assert r.rain_probability_pct == 40
        assert r.crowd_index == 9

    def test_file_not_found_exits(self, tmp_path: Path) -> None:
        """檔案不存在應 sys.exit(1)。"""
        with pytest.raises(SystemExit) as exc_info:
            load_comfort_scores(tmp_path / "missing.csv")
        assert exc_info.value.code == 1

    def test_missing_column_exits(self, tmp_path: Path) -> None:
        """缺少必要欄位應 sys.exit(1)。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c
            1,東京,6.1
        """)
        with pytest.raises(SystemExit) as exc_info:
            load_comfort_scores(p)
        assert exc_info.value.code == 1

    def test_month_out_of_range_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """month 超出 1–12 應略過並輸出警告。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,東京,6.1,15,5
            13,大阪,7.0,18,5
        """)
        records = load_comfort_scores(p)
        assert len(records) == 1
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_rain_out_of_range_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """rain_probability_pct 超出 0–100 應略過並輸出警告。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,東京,6.1,110,5
        """)
        records = load_comfort_scores(p)
        assert len(records) == 0
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_crowd_out_of_range_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """crowd_index 超出 1–10 應略過並輸出警告。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,東京,6.1,15,15
        """)
        records = load_comfort_scores(p)
        assert len(records) == 0
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_negative_temperature_accepted(self, tmp_path: Path) -> None:
        """負氣溫（如札幌冬季）應被接受。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,札幌,-3.2,40,3
        """)
        records = load_comfort_scores(p)
        assert len(records) == 1
        assert records[0].avg_temp_c == pytest.approx(-3.2)

    def test_empty_city_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """city 為空值應略過並輸出警告。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,,6.1,15,5
        """)
        records = load_comfort_scores(p)
        assert len(records) == 0
        captured = capsys.readouterr()
        assert "[警告]" in captured.err

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """只有標頭列應回傳空清單。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
        """)
        records = load_comfort_scores(p)
        assert records == []

    def test_warning_contains_row_number(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """警告訊息應包含 CSV 列號。"""
        p = _write(tmp_path, "comfort_scores.csv", """
            month,city,avg_temp_c,rain_probability_pct,crowd_index
            1,東京,6.1,15,5
            2,大阪,8.1,22,4
            13,福岡,14.6,45,5
        """)
        load_comfort_scores(p)
        captured = capsys.readouterr()
        # 第 4 列（row_num=4）為無效資料
        assert "4" in captured.err
