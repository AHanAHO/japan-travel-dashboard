
"""
src/renderer.py — 目的地分頁模式 Dashboard
"""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .models import ComfortAnalysisResult, FareAnalysisResult, RateAnalysisResult, ScoreResult

_MONTH_LABELS = [f"{m}月" for m in range(1, 13)]
_MONTHS = list(range(1, 13))
_AIRLINE_COLORS = {"CI": "#4C9BE8", "BR": "#2ECC71", "JX": "#E67E22"}
_DARK_BG = "#1a1a2e"
_CARD_BG = "#16213e"
_ACCENT = "#e94560"
_TEXT = "#eaeaea"
_SUBTEXT = "#a0a0b0"
_CITY_EMOJI = {"東京": "🗼", "大阪": "🏯", "福岡": "🌸", "札幌": "❄️", "沖繩": "🌺"}

def _tci_color(score: float) -> str:
    if score >= 70: return "#2ecc71"
    elif score >= 40: return "#f39c12"
    else: return "#e74c3c"

def _base_layout(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=16, color=_TEXT), x=0.02),
        template="plotly_dark",
        paper_bgcolor=_CARD_BG,
        plot_bgcolor=_CARD_BG,
        font=dict(family="'Noto Sans TC','Microsoft JhengHei',sans-serif", color=_TEXT, size=11),
        margin=dict(l=55, r=25, t=55, b=45),
        height=400,
        autosize=True,
    )

def _fig_to_html(fig: go.Figure, div_id: str) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config={"responsive": True, "displayModeBar": False},
    )

def _build_tci_chart(score_result: ScoreResult, city: str) -> go.Figure:
    tci = score_result.total_score.reindex(_MONTHS)
    fare = score_result.fare_score.reindex(_MONTHS)
    estimated = score_result.fare_estimated.reindex(_MONTHS).fillna(False)
    colors, texts = [], []
    for m in _MONTHS:
        val = tci.get(m)
        fare_val = fare.get(m)
        is_est = bool(estimated.get(m, False))
        if pd.isna(val):
            colors.append("#555566"); texts.append("無資料")
        elif is_est:
            colors.append(_tci_color(float(val))); texts.append(f"{val:.1f}~")
        elif pd.isna(fare_val):
            colors.append(_tci_color(float(val))); texts.append(f"{val:.1f}*")
        else:
            colors.append(_tci_color(float(val))); texts.append(f"{val:.1f}")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=_MONTH_LABELS,
        y=[float(v) if not pd.isna(v) else 0 for v in tci],
        marker_color=colors, text=texts, textposition="outside",
        textfont=dict(size=11, color=_TEXT),
        hovertemplate="<b>%{x}</b><br>TCI：%{text}<extra></extra>", name="TCI",
    ))
    valid = tci.dropna()
    if not valid.empty:
        best_m = int(valid.idxmax()); best_v = float(valid.max())
        fig.add_annotation(x=_MONTH_LABELS[best_m-1], y=best_v+6,
            text=f"🏆 最佳：{best_m}月", showarrow=False,
            font=dict(size=12, color="#f1c40f"))
    fig.update_layout(**_base_layout(f"{city} 綜合旅遊指數（TCI）各月排名"),
        yaxis=dict(range=[0, 115], title="TCI 分數", gridcolor="#2a2a4a"),
        xaxis=dict(title="月份"))
    return fig

def _build_fare_chart(fare_result: FareAnalysisResult, city: str, fare_estimated: "pd.Series | None" = None) -> go.Figure:
    """
    票價圖表。使用 fare_result.monthly_avg_by_airline（已含估算補值）。
    fare_result.estimated_by_airline 標記哪些格是估算值（淡色 + tooltip 標示）。
    """
    # 確保 index 對齊：用 1–12 整數 list reindex，不依賴 index name
    raw_df = fare_result.monthly_avg_by_airline
    df = raw_df.reindex(list(range(1, 13)))

    est_raw = fare_result.estimated_by_airline
    est_df = est_raw.reindex(list(range(1, 13))) if est_raw is not None else None

    fig = go.Figure()
    for airline in ["CI", "BR", "JX"]:
        if airline not in df.columns:
            continue
        vals = df[airline]

        # 補值後應全部有值；若仍全 NaN 才跳過
        if not vals.notna().any():
            continue

        y_vals = [float(v) if not pd.isna(v) else None for v in vals]

        # 判斷每個月份是否為估算值
        if est_df is not None and airline in est_df.columns:
            est_flags = [
                bool(est_df.loc[m, airline])
                if (not pd.isna(vals.get(m, float("nan"))))
                else False
                for m in range(1, 13)
            ]
        else:
            est_flags = [False] * 12

        # 顏色：估算值用半透明（opacity 0.35），實際值用正常顏色
        actual_color = _AIRLINE_COLORS.get(airline, "#aaa")
        hex_c = actual_color.lstrip("#")
        r_c, g_c, b_c = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)

        marker_colors = []
        for v, is_est in zip(y_vals, est_flags):
            if v is None:
                marker_colors.append("rgba(0,0,0,0)")
            elif is_est:
                marker_colors.append(f"rgba({r_c},{g_c},{b_c},0.25)")
            else:
                marker_colors.append(actual_color)

        hover = []
        for i, (v, is_est) in enumerate(zip(y_vals, est_flags)):
            if v is None:
                hover.append(f"<b>{_MONTH_LABELS[i]}</b><br>{airline}：無資料")
            elif is_est:
                hover.append(
                    f"<b>{_MONTH_LABELS[i]}</b><br>{airline}：NT$ {int(v):,}"
                    f"<br><span style='color:#f39c12'>⚠ 估算票價</span>"
                )
            else:
                hover.append(f"<b>{_MONTH_LABELS[i]}</b><br>{airline}：NT$ {int(v):,}")

        fig.add_trace(go.Bar(
            name=airline,
            x=_MONTH_LABELS,
            y=y_vals,
            marker_color=marker_colors,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover,
        ))

    # 最低票價標注
    min_fare = fare_result.monthly_min_fare.reindex(list(range(1, 13)))
    for idx, m in enumerate(range(1, 13)):
        v = min_fare.get(m)
        if v is not None and not pd.isna(v):
            # 判斷該月最低票價是否來自估算格
            is_est_min = False
            if est_df is not None:
                for airline in ["CI", "BR", "JX"]:
                    if airline in est_df.columns and airline in df.columns:
                        av = df.loc[m, airline]
                        if not pd.isna(av) and abs(float(av) - float(v)) < 1:
                            if bool(est_df.loc[m, airline]):
                                is_est_min = True
                                break
            label = f"NT${int(v):,}{'*' if is_est_min else ''}"
            fig.add_annotation(
                x=_MONTH_LABELS[idx], y=float(v),
                text=label, showarrow=False, yshift=13,
                font=dict(size=8, color="#f39c12" if is_est_min else _SUBTEXT),
            )

    fig.update_layout(
        **_base_layout(f"各航空公司月均來回票價（飛往{city}）"),
        barmode="group",
        yaxis=dict(title="票價（NT$）", gridcolor="#2a2a4a", tickformat=",.0f", tickprefix="NT$"),
        xaxis=dict(title="月份"),
        legend=dict(title="航空公司", bgcolor="rgba(0,0,0,0)"),
    )
    return fig

def _build_rate_chart(rate_result: RateAnalysisResult) -> go.Figure:
    rates = rate_result.monthly_avg_rate.reindex(_MONTHS)
    annual_avg = rate_result.annual_avg_rate
    best_months = rate_result.best_months
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=_MONTH_LABELS, y=[float(v) if not pd.isna(v) else None for v in rates],
        mode="lines+markers", line=dict(color="#4C9BE8", width=2.5),
        marker=dict(size=7, color="#4C9BE8"), connectgaps=False, name="月均匯率",
        hovertemplate="<b>%{x}</b><br>匯率：%{y:.4f}<extra></extra>"))
    if annual_avg > 0:
        fig.add_hline(y=annual_avg, line_dash="dash", line_color="#f39c12",
            annotation_text=f"全年均值 {annual_avg:.4f}", annotation_position="top right",
            annotation_font=dict(color="#f39c12", size=10))
    for m in best_months:
        v = rates.get(m)
        if not pd.isna(v):
            fig.add_trace(go.Scatter(
                x=[_MONTH_LABELS[m-1]], y=[float(v)], mode="markers",
                marker=dict(symbol="star", size=16, color="#f1c40f",
                            line=dict(color="#fff", width=1)),
                name=f"最佳換匯（{m}月）",
                hovertemplate=f"<b>{m}月</b><br>最佳換匯（匯率最低）：{float(v):.4f}<extra></extra>",
                showlegend=True))
    valid = rates.dropna()
    y_min = float(valid.min()) * 0.997 if not valid.empty else 0
    y_max = float(valid.max()) * 1.003 if not valid.empty else 1
    fig.update_layout(**_base_layout("JPY/TWD 月均匯率走勢（各城市共用）"),
        yaxis=dict(title="匯率（1 JPY = ? TWD）", range=[y_min, y_max],
                   gridcolor="#2a2a4a", tickformat=".4f"),
        xaxis=dict(title="月份"), legend=dict(bgcolor="rgba(0,0,0,0)"))
    return fig

def _build_comfort_chart(comfort_result: ComfortAnalysisResult, city: str) -> go.Figure:
    if comfort_result.monthly_comfort.empty:
        fig = go.Figure()
        fig.add_annotation(text="無舒適度資料", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=_SUBTEXT))
        fig.update_layout(**_base_layout(f"{city} 旅遊舒適度分析"))
        return fig
    df = comfort_result.monthly_comfort.reset_index()
    city_df = df[df["city"] == city]
    if city_df.empty:
        fig = go.Figure()
        fig.add_annotation(text=f"無 {city} 舒適度資料", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=_SUBTEXT))
        fig.update_layout(**_base_layout(f"{city} 旅遊舒適度分析"))
        return fig
    monthly = city_df.groupby("month").agg(
        avg_rain=("rain_probability_pct", "mean"),
        avg_crowd=("crowd_index", "mean"),
        avg_temp=("avg_temp_c", "mean"),
    ).reindex(_MONTHS)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=_MONTH_LABELS, y=[float(v) if not pd.isna(v) else None for v in monthly["avg_rain"]],
        name="降雨機率（%）", marker_color="rgba(76,155,232,0.6)",
        hovertemplate="<b>%{x}</b><br>降雨機率：%{y:.0f}%<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=_MONTH_LABELS, y=[float(v) if not pd.isna(v) else None for v in monthly["avg_crowd"]],
        name="人潮指數（1–10）", mode="lines+markers",
        line=dict(color=_ACCENT, width=2.5), marker=dict(size=8, color=_ACCENT),
        connectgaps=False,
        hovertemplate="<b>%{x}</b><br>人潮指數：%{y:.1f}<extra></extra>"), secondary_y=True)
    fig.add_trace(go.Scatter(
        x=_MONTH_LABELS, y=[float(v) if not pd.isna(v) else None for v in monthly["avg_temp"]],
        name="平均氣溫（°C）", mode="lines+markers",
        line=dict(color="#f39c12", width=2, dash="dot"), marker=dict(size=6, color="#f39c12"),
        connectgaps=False,
        hovertemplate="<b>%{x}</b><br>平均氣溫：%{y:.1f}°C<extra></extra>"), secondary_y=True)
    fig.update_layout(**_base_layout(f"{city} 旅遊舒適度（降雨 / 人潮 / 氣溫）"),
        legend=dict(bgcolor="rgba(0,0,0,0)"), barmode="overlay")
    fig.update_yaxes(title_text="降雨機率（%）", range=[0, 110],
                     gridcolor="#2a2a4a", secondary_y=False)
    fig.update_yaxes(title_text="人潮指數 / 氣溫", secondary_y=True,
                     gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(title_text="月份")
    return fig

def _build_tci_table(score_result: ScoreResult) -> str:
    tci = score_result.total_score.reindex(_MONTHS)
    fare = score_result.fare_score.reindex(_MONTHS)
    rate = score_result.rate_score.reindex(_MONTHS)
    comfort = score_result.comfort_score.reindex(_MONTHS)
    estimated = score_result.fare_estimated.reindex(_MONTHS).fillna(False)

    rows_data = sorted(
        [(m, tci.get(m)) for m in _MONTHS],
        key=lambda x: (pd.isna(x[1]), -(x[1] if not pd.isna(x[1]) else 0))
    )
    rows_html = ""
    for rank, (m, t) in enumerate(rows_data, 1):
        f_val, r_val, c_val = fare.get(m), rate.get(m), comfort.get(m)
        is_est = bool(estimated.get(m, False))

        if pd.isna(t):
            tci_cell = '<span style="color:#666">無資料</span>'; row_class = "row-na"
        else:
            color = _tci_color(float(t))
            tci_cell = f'<span style="color:{color};font-weight:bold">{t:.1f}</span>'
            row_class = "row-data"

        def _fmt(v, mark_est: bool = False) -> str:
            if pd.isna(v):
                return "—"
            s = f"{float(v):.1f}"
            if mark_est:
                s += ' <span style="color:#f39c12;font-size:0.72em" title="估算票價（跨城市平均）">估算</span>'
            return s

        medal = " 🥇" if rank == 1 and not pd.isna(t) else \
                " 🥈" if rank == 2 and not pd.isna(t) else \
                " 🥉" if rank == 3 and not pd.isna(t) else ""

        rows_html += f"""
        <tr class="{row_class}">
          <td>{rank}</td><td><strong>{m}月</strong>{medal}</td>
          <td>{tci_cell}</td>
          <td>{_fmt(c_val)}</td>
          <td>{_fmt(f_val, mark_est=is_est)}</td>
          <td>{_fmt(r_val)}</td>
        </tr>"""

    return f"""
    <table class="tci-table">
      <thead><tr>
        <th>排名</th><th>月份</th><th>TCI 總分</th>
        <th>舒適分 (50%)</th><th>票價分 (40%)</th><th>匯率分 (10%)</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>"""


def _build_city_tab_content(
    city: str,
    score_result: ScoreResult,
    fare_result: FareAnalysisResult,
    rate_result: RateAnalysisResult,
    comfort_result: ComfortAnalysisResult,
    tab_idx: int,
    fare_records: "list | None" = None,
) -> str:
    """產生單一城市分頁的完整 HTML 內容。"""
    emoji = _CITY_EMOJI.get(city, "📍")

    tci_fig = _build_tci_chart(score_result, city)

    # 票價圖表：使用補值後的完整資料（每月每航空公司都有值）
    if fare_records is not None:
        from .analyzer import build_fare_chart_data_for_city
        chart_fare_result = build_fare_chart_data_for_city(fare_records, city)
    else:
        chart_fare_result = fare_result
    fare_fig = _build_fare_chart(chart_fare_result, city)

    rate_fig = _build_rate_chart(rate_result)
    comfort_fig = _build_comfort_chart(comfort_result, city)

    tci_div = _fig_to_html(tci_fig, f"chart-tci-{tab_idx}")
    fare_div = _fig_to_html(fare_fig, f"chart-fare-{tab_idx}")
    rate_div = _fig_to_html(rate_fig, f"chart-rate-{tab_idx}")
    comfort_div = _fig_to_html(comfort_fig, f"chart-comfort-{tab_idx}")
    tci_table = _build_tci_table(score_result)

    valid_tci = score_result.total_score.dropna()
    if not valid_tci.empty:
        best_m = int(valid_tci.idxmax()); best_v = float(valid_tci.max())
        hero = f"最佳出發月份：<span class='hero-month'>{best_m} 月</span>（TCI {best_v:.1f} 分）"
    else:
        hero = "資料不足，無法計算最佳月份"

    return f"""
<div class="tab-panel" id="panel-{tab_idx}">
  <div class="city-hero">{emoji} {city}｜{hero}</div>

  <section>
    <h2>📊 {city} 綜合旅遊指數（TCI）排名</h2>
    <p class="desc">TCI = 舒適度分數（50%）＋ 票價分數（40%）＋ 匯率分數（10%）。
      舒適度依 {city} 自身氣候計算，不與其他城市平均。<br>
      標示 <strong>~</strong> 的月份票價為<span style="color:#f39c12">估算票價</span>（以同月份其他目的地平均補值）；
      標示 <strong>*</strong> 的月份無票價資料，TCI 由舒適度、機票票價與匯率加權計算。
      <span style="color:#2ecc71">■</span> ≥70 優秀 &nbsp;
      <span style="color:#f39c12">■</span> 40–69 普通 &nbsp;
      <span style="color:#e74c3c">■</span> &lt;40 較差</p>
    <div class="chart-wrap">{tci_div}</div>
    {tci_table}
  </section>

  <section>
    <h2>🌤️ {city} 旅遊舒適度分析</h2>
    <p class="desc">
      藍色長條為降雨機率（%），紅色折線為人潮指數（1–10），橙色虛線為平均氣溫（°C）。<br>
      舒適度分數 = 氣溫 40% + 降雨 30% + 人潮 30%。<br>
      氣溫：10–25°C 滿分；低於 10°C 每度扣 2 分，0°C 以下每度扣 3 分；高於 25°C 每度扣 3 分，30°C 以上每度扣 5 分。<br>
      降雨：降雨機率越高，舒適度越低。<br>
      <strong>人潮：</strong>指數 1–5 輕微扣分，6–7 中度扣分，8–10 重度扣分（二次曲線）。
    </p>
    <div class="chart-wrap">{comfort_div}</div>
  </section>

  <section>
    <h2>✈️ 飛往{city}的月均來回票價</h2>
    <p class="desc">依各航空公司分組計算月均來回票價（NT$）。長條頂端標示為該月最低票價。<br>
      <span style="color:{_SUBTEXT}">亮色柱狀為實際票價；<span style="color:#f39c12">深色柱狀</span>為估算票價（以同月份同航空公司其他目的地平均補值）。
      估算票價 tooltip 顯示「<span style="color:#f39c12">⚠ 估算票價</span>」，最低票價標示 <strong>*</strong>。</span></p>
    <div class="chart-wrap">{fare_div}</div>
    <div class="legend-row">
      <span><span class="legend-dot" style="background:#4C9BE8"></span>CI 中華航空</span>
      <span><span class="legend-dot" style="background:#2ECC71"></span>BR 長榮航空</span>
      <span><span class="legend-dot" style="background:#E67E22"></span>JX 星宇航空</span>
      <span>（亮色=實際，深色=估算）<span>
    </div>
  </section>

  <section>
    <h2>💱 JPY/TWD 月均匯率走勢</h2>
    <p class="desc">匯率不分城市，各分頁共用相同資料。
      ⭐ 星形標記為最佳換匯月份（匯率最低點）。</p>
    <div class="chart-wrap">{rate_div}</div>
  </section>
</div>"""


def render_dashboard(
    fare_result: FareAnalysisResult,
    rate_result: RateAnalysisResult,
    comfort_result: ComfortAnalysisResult,
    city_scores: dict[str, ScoreResult],
    output_path: str | Path = "output/index.html",
    fare_records: "list | None" = None,
) -> None:
    """
    產生目的地分頁模式的靜態 HTML Dashboard 並寫入檔案。

    Parameters
    ----------
    fare_result : FareAnalysisResult
        全域票價分析結果（備用，當 fare_records 未提供時使用）。
    rate_result : RateAnalysisResult
    comfort_result : ComfortAnalysisResult
    city_scores : dict[str, ScoreResult]
        {城市名稱: ScoreResult}，由 calculate_tci_all_cities() 產生。
    output_path : str | Path
    fare_records : list[FareRecord] | None
        原始票價記錄，用於依城市過濾票價圖表。若提供，每個城市顯示自己的票價。
    """
    output_path = Path(output_path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[錯誤] 無法建立輸出目錄 {output_path.parent}：{exc}", file=sys.stderr)
        raise

    cities = list(city_scores.keys())
    if not cities:
        cities = ["東京", "大阪", "福岡", "札幌", "沖繩"]

    # 強制 TAB 順序：東京、大阪、札幌、福岡、沖繩
    _PREFERRED_ORDER = ["東京", "大阪", "札幌", "福岡", "沖繩"]
    ordered = [c for c in _PREFERRED_ORDER if c in cities]
    remaining = [c for c in cities if c not in _PREFERRED_ORDER]
    cities = ordered + remaining

    tab_buttons = ""
    tab_panels = ""
    for i, city in enumerate(cities):
        emoji = _CITY_EMOJI.get(city, "📍")
        active_btn = " active" if i == 0 else ""
        tab_buttons += f'<button class="tab-btn{active_btn}" onclick="switchTab({i})" id="btn-{i}">{emoji} {city}</button>\n'
        score_result = city_scores.get(city)
        if score_result is None:
            tab_panels += f'<div class="tab-panel" id="panel-{i}"><p style="color:{_SUBTEXT};padding:40px">無 {city} 資料</p></div>\n'
        else:
            tab_panels += _build_city_tab_content(
                city, score_result, fare_result, rate_result, comfort_result, i,
                fare_records=fare_records,
            )

    from plotly.offline import get_plotlyjs
    plotly_js_inline = f"<script>{get_plotlyjs()}</script>"
    today = date.today().isoformat()

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>日本旅遊最佳出發時機分析 Dashboard</title>
  {plotly_js_inline}
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: {_DARK_BG};
      color: {_TEXT};
      font-family: 'Noto Sans TC','Microsoft JhengHei','PingFang TC',sans-serif;
      min-height: 100vh;
    }}
    header {{
      background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
      padding: 24px 40px 18px;
      border-bottom: 2px solid {_ACCENT};
    }}
    header h1 {{ font-size: 1.7rem; color: #fff; letter-spacing: 0.04em; }}
    header .meta {{ margin-top: 5px; font-size: 0.82rem; color: {_SUBTEXT}; }}

    /* Tab 切換列 */
    .tab-bar {{
      display: flex;
      gap: 4px;
      padding: 16px 40px 0;
      background: {_DARK_BG};
      border-bottom: 2px solid #2a2a4a;
      flex-wrap: wrap;
    }}
    .tab-btn {{
      background: #16213e;
      color: {_SUBTEXT};
      border: 1px solid #2a2a4a;
      border-bottom: none;
      padding: 10px 22px;
      font-size: 0.95rem;
      font-family: inherit;
      cursor: pointer;
      border-radius: 6px 6px 0 0;
      transition: background 0.15s, color 0.15s;
    }}
    .tab-btn:hover {{ background: #1e2d50; color: {_TEXT}; }}
    .tab-btn.active {{
      background: {_CARD_BG};
      color: #fff;
      border-color: #3a3a6a;
      border-bottom: 2px solid {_CARD_BG};
      margin-bottom: -2px;
    }}

    /* 分頁內容 */
    .tab-panel {{ display: none; padding: 24px 40px 48px; }}
    .tab-panel.visible {{ display: block; }}

    .city-hero {{
      background: {_CARD_BG};
      border-left: 4px solid #f1c40f;
      margin-bottom: 24px;
      padding: 14px 22px;
      border-radius: 6px;
      font-size: 1.05rem;
    }}
    .hero-month {{ color: #f1c40f; font-size: 1.3rem; font-weight: bold; }}

    section {{
      background: {_CARD_BG};
      border-radius: 10px;
      padding: 18px 22px 14px;
      box-shadow: 0 4px 18px rgba(0,0,0,0.4);
      margin-bottom: 28px;
    }}
    section h2 {{
      font-size: 1.05rem; color: {_TEXT};
      padding-bottom: 9px; border-bottom: 1px solid #2a2a4a; margin-bottom: 4px;
    }}
    section p.desc {{
      font-size: 0.8rem; color: {_SUBTEXT};
      margin-bottom: 12px; line-height: 1.6;
    }}
    .chart-wrap {{
      width: 100%;
      overflow: visible;
      display: block;
    }}
    .chart-wrap > div {{
      width: 100% !important;
      min-width: 0 !important;
    }}
    /* Force plotly SVG to fill container */
    .chart-wrap .plotly-graph-div {{
      width: 100% !important;
    }}

    .tci-table {{
      width: 100%; border-collapse: collapse;
      font-size: 0.88rem; margin-top: 14px;
    }}
    .tci-table th {{
      background: #0f3460; color: {_TEXT};
      padding: 9px 12px; text-align: center; font-weight: 600;
    }}
    .tci-table td {{
      padding: 8px 12px; text-align: center;
      border-bottom: 1px solid #2a2a4a;
    }}
    .tci-table tr.row-data:hover td {{ background: rgba(255,255,255,0.04); }}
    .tci-table tr.row-na td {{ color: #666; }}

    .legend-row {{
      display: flex; gap: 18px; flex-wrap: wrap;
      margin-top: 9px; font-size: 0.78rem; color: {_SUBTEXT};
    }}
    .legend-dot {{
      display: inline-block; width: 9px; height: 9px;
      border-radius: 50%; margin-right: 4px; vertical-align: middle;
    }}

    @media (max-width: 768px) {{
      header, .tab-bar, .tab-panel {{ padding-left: 14px; padding-right: 14px; }}
      header h1 {{ font-size: 1.2rem; }}
      .tab-btn {{ padding: 8px 14px; font-size: 0.85rem; }}
    }}
  </style>
</head>
<body>

<header>
  <h1>🗾 日本旅遊最佳出發時機分析 Dashboard</h1>
  <p class="meta">資料更新日期：{today} ｜ 分析航空：中華航空（CI）、長榮航空（BR）、星宇航空（JX）｜ 目的地分頁模式</p>
</header>

<div class="tab-bar">
{tab_buttons}
</div>

{tab_panels}

<script>
function switchTab(idx) {{
  document.querySelectorAll('.tab-panel').forEach(function(p, i) {{
    p.classList.toggle('visible', i === idx);
  }});
  document.querySelectorAll('.tab-btn').forEach(function(b, i) {{
    b.classList.toggle('active', i === idx);
  }});
  // 切換分頁後觸發 plotly 重新計算寬度
  setTimeout(function() {{
    var panel = document.getElementById('panel-' + idx);
    if (panel) {{
      var divs = panel.querySelectorAll('.plotly-graph-div');
      divs.forEach(function(d) {{
        if (window.Plotly) {{ Plotly.relayout(d, {{autosize: true}}); }}
      }});
    }}
  }}, 50);
}}
// 預設顯示第一個分頁
switchTab(0);
</script>

<footer style="
    text-align:center;
    color:#8a93a8;
    font-size:0.85rem;
    margin:48px 0 24px 0;
    letter-spacing:0.03em;
">
    Japan Travel Dashboard Project ｜ LI ZONG HAN<br>
</footer>
</body>
</html>"""

    try:
        output_path.write_text(html, encoding="utf-8")
    except OSError as exc:
        print(f"[錯誤] 無法寫入 {output_path}：{exc}", file=sys.stderr)
        raise

    print(f"輸出路徑：{output_path.resolve()}")
