# 日本旅遊最佳出發時機分析 Dashboard

分析台灣飛日本的來回票價（中華航空 CI、長榮航空 BR、星宇航空 JX）、JPY/TWD 匯率與旅遊舒適度，找出最划算且舒適的出國時機，並輸出單一可離線瀏覽的 HTML Dashboard。

## 安裝

```bash
pip install -r requirements.txt
```

## 使用方式

```bash
# 使用預設資料目錄（data/）與輸出路徑（output/dashboard.html）
python main.py

# 指定自訂資料目錄與輸出路徑
python main.py --data-dir my_data --output my_output/report.html

# 查看說明
python main.py --help
```

## 資料格式

將以下三個 CSV 檔案放入 `data/` 目錄：

### data/fares.csv

| 欄位 | 型別 | 說明 |
|------|------|------|
| `date` | YYYY-MM-DD | 票價查詢日期 |
| `airline` | CI / BR / JX | 航空公司代碼 |
| `origin` | IATA 代碼 | 出發機場（例：TPE） |
| `destination` | 目的地城市名稱 | 例：東京、大阪、福岡、札幌、沖繩 |
| `roundtrip_fare_twd` | 正整數 | 來回票價（新台幣） |

```csv
date,airline,origin,destination,roundtrip_fare_twd
2024-01-05,CI,TPE,東京,15800
2024-01-12,BR,TPE,大阪,14200
2024-01-20,JX,TPE,東京,13500
```

### data/exchange_rates.csv

| 欄位 | 型別 | 說明 |
|------|------|------|
| `date` | YYYY-MM-DD | 匯率日期 |
| `jpy_twd_rate` | 正浮點數 | JPY/TWD 匯率（1 日圓 = ? 台幣） |

```csv
date,jpy_twd_rate
2024-01-01,0.2105
2024-01-15,0.2098
2024-02-01,0.2112
```

### data/comfort_scores.csv

| 欄位 | 型別 | 說明 |
|------|------|------|
| `month` | 1–12 | 月份 |
| `city` | 字串 | 目的地城市（東京、大阪、福岡、札幌、沖繩） |
| `avg_temp_c` | 浮點數 | 平均氣溫（°C） |
| `rain_probability_pct` | 0–100 整數 | 降雨機率（%） |
| `crowd_index` | 1–10 整數 | 觀光人潮指數（1=人少，10=非常擁擠） |

```csv
month,city,avg_temp_c,rain_probability_pct,crowd_index
1,東京,6.1,15,5
2,東京,7.2,20,4
1,大阪,7.0,18,5
```

## 專案結構

```
japan-travel-dashboard/
├── main.py              # CLI 入口
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── models.py        # 資料模型（dataclass）
│   ├── data_loader.py   # CSV 讀取與驗證
│   ├── analyzer.py      # 票價、匯率、舒適度分析
│   ├── scorer.py        # 綜合評分計算
│   └── renderer.py      # plotly 圖表與 HTML 輸出
├── data/                # 放置 CSV 資料檔案
│   ├── fares.csv            # 航班來回票價（date, airline, origin, destination, roundtrip_fare_twd）
│   ├── exchange_rates.csv   # JPY/TWD 匯率（date, jpy_twd_rate）
│   └── comfort_scores.csv   # 旅遊舒適度（month, city, avg_temp_c, rain_probability_pct, crowd_index）
├── output/              # 產生的 HTML Dashboard
└── tests/               # pytest 單元測試
```

## 輸出

執行後會在 `output/dashboard.html` 產生互動式 Dashboard，包含：



HTML 檔案內嵌所有資源，可在無網路環境下開啟。
