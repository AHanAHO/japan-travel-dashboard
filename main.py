"""
日本旅遊最佳出發時機分析 Dashboard
====================================
Entry point.

Usage
-----
    python main.py
    python main.py --data-dir my_data --output my_output/report.html
    python main.py --help

Exit codes
----------
    0  全部階段成功完成
    1  任何錯誤（檔案不存在、欄位缺失、輸出失敗等）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI 參數解析
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="分析台灣飛日本的票價、匯率與旅遊舒適度，產生靜態 HTML Dashboard。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        metavar="DATA_DIR",
        help="CSV 資料目錄（fares.csv / exchange_rates.csv / comfort_scores.csv）",
    )
    parser.add_argument(
        "--output",
        default="output/index.html",
        metavar="OUTPUT",
        help="HTML Dashboard 輸出路徑",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 進度輸出輔助
# ---------------------------------------------------------------------------

def _done(stage: str) -> None:
    """輸出階段完成訊息至 stdout。"""
    print(f"[完成] {stage}")


def _error(reason: str) -> None:
    """輸出錯誤訊息至 stderr。"""
    print(f"[錯誤] {reason}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_path = Path(args.output)

    # ------------------------------------------------------------------
    # 0. 驗證 data 目錄存在
    # ------------------------------------------------------------------
    if not data_dir.exists():
        _error(f"資料目錄不存在：{data_dir.resolve()}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 延遲 import（避免在 --help 時載入 pandas/plotly）
    # ------------------------------------------------------------------
    try:
        from src.analyzer import (
            analyze_comfort,
            analyze_exchange_rates,
            analyze_fares,
            fare_summary,
            rate_summary,
        )
        from src.data_loader import (
            load_comfort_scores,
            load_exchange_rates,
            load_fares,
        )
        from src.scorer import calculate_tci_all_cities
    except ImportError as exc:
        _error(f"模組載入失敗，請確認已安裝依賴（pip install -r requirements.txt）：{exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 1. 載入資料
    # ------------------------------------------------------------------
    try:
        fare_records = load_fares(data_dir / "fares.csv")
        rate_records = load_exchange_rates(data_dir / "exchange_rates.csv")
        comfort_records = load_comfort_scores(data_dir / "comfort_scores.csv")
    except SystemExit:
        # data_loader 已輸出 [錯誤] 訊息，直接傳遞退出碼
        raise
    except Exception as exc:
        _error(f"資料載入失敗：{exc}")
        sys.exit(1)

    _done("資料載入")

    # ------------------------------------------------------------------
    # 2. 資料驗證摘要（警告已由 data_loader 輸出至 stderr）
    # ------------------------------------------------------------------
    _done("資料驗證")

    # ------------------------------------------------------------------
    # 3. 票價分析
    # ------------------------------------------------------------------
    try:
        fare_result = analyze_fares(fare_records)
    except Exception as exc:
        _error(f"票價分析失敗：{exc}")
        sys.exit(1)

    fs = fare_summary(fare_result)
    if fs["cheapest_month"]:
        print(
            f"  → 最便宜月份：{fs['cheapest_month']} 月"
            f"（TWD {fs['cheapest_fare']:,}）"
            f"  最貴月份：{fs['priciest_month']} 月"
            f"（TWD {fs['priciest_fare']:,}）"
        )
    _done("票價分析")

    # ------------------------------------------------------------------
    # 4. 匯率分析
    # ------------------------------------------------------------------
    try:
        rate_result = analyze_exchange_rates(rate_records)
    except Exception as exc:
        _error(f"匯率分析失敗：{exc}")
        sys.exit(1)

    rs = rate_summary(rate_result)
    if rs["best_months"]:
        months_str = "、".join(f"{m} 月" for m in rs["best_months"])
        print(f"  → 最佳換匯月份：{months_str}（全年均值 {rs['annual_avg']:.4f}）")
    _done("匯率分析")

    # ------------------------------------------------------------------
    # 5. 舒適度分析
    # ------------------------------------------------------------------
    try:
        comfort_result = analyze_comfort(comfort_records)
    except Exception as exc:
        _error(f"舒適度分析失敗：{exc}")
        sys.exit(1)

    _done("舒適度分析")

    # ------------------------------------------------------------------
    # 6. 綜合評分（TCI）— 依城市分別計算（各城市使用自己的票價與舒適度）
    # ------------------------------------------------------------------
    try:
        city_scores = calculate_tci_all_cities(fare_records, rate_result, comfort_result)
    except Exception as exc:
        _error(f"TCI 計算失敗：{exc}")
        sys.exit(1)

    for city, score_result in city_scores.items():
        valid_scores = score_result.total_score.dropna()
        if not valid_scores.empty:
            best_month = int(valid_scores.idxmax())
            best_score = float(valid_scores.max())
            print(f"  → {city} 最佳出發月份：{best_month} 月（TCI {best_score} 分）")
    _done("綜合評分")

    # ------------------------------------------------------------------
    # 7. Dashboard 輸出
    # ------------------------------------------------------------------
    try:
        from src.renderer import render_dashboard
        render_dashboard(
            fare_result=fare_result,
            rate_result=rate_result,
            comfort_result=comfort_result,
            city_scores=city_scores,
            output_path=output_path,
            fare_records=fare_records,
        )
    except ImportError:
        # renderer 尚未實作（Task 7），輸出佔位訊息
        _render_placeholder(output_path)
    except Exception as exc:
        _error(f"Dashboard 輸出失敗：{exc}")
        sys.exit(1)

    _done("Dashboard 輸出")


# ---------------------------------------------------------------------------
# Renderer 佔位函式（Task 7 完成後由 src/renderer.py 取代）
# ---------------------------------------------------------------------------

def _render_placeholder(output_path: Path) -> None:
    """
    在 src/renderer.py 實作完成前，輸出一個簡單的 HTML 佔位頁面。
    確保 main.py 可以端對端執行。
    """
    from datetime import date

    output_path.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>日本旅遊最佳出發時機分析</title>
  <style>
    body {{ font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }}
    h1 {{ color: #d62728; }}
    .notice {{ background: #fff3cd; border: 1px solid #ffc107; padding: 16px; border-radius: 6px; }}
  </style>
</head>
<body>
  <header>
    <h1>日本旅遊最佳出發時機分析</h1>
    <p>資料更新日期：{date.today().isoformat()}</p>
  </header>
  <main>
    <div class="notice">
      <strong>⚠️ Dashboard 圖表尚未產生</strong><br>
      src/renderer.py（Task 7）完成後，此頁面將顯示完整的互動式分析圖表。
    </div>
  </main>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(f"輸出路徑：{output_path.resolve()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
