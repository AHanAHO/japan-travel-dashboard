# 資料目錄

此目錄存放三個 CSV 資料檔案，欄位名稱與 DataLoader 直接對應，無需額外 mapping。

---

## fares.csv — 航班來回票價

| 欄位 | 型別 | 驗證規則 |
|------|------|----------|
| `date` | YYYY-MM-DD | 必填，格式須符合 |
| `airline` | 字串 | 必須為 CI、BR、JX 之一 |
| `origin` | IATA 代碼 | 必填（例：TPE） |
| `destination` | 城市名稱 | 必填（例：東京） |
| `roundtrip_fare_twd` | 正整數 | 必須 > 0 |

---

## exchange_rates.csv — JPY/TWD 匯率

| 欄位 | 型別 | 驗證規則 |
|------|------|----------|
| `date` | YYYY-MM-DD | 必填，格式須符合 |
| `jpy_twd_rate` | 正浮點數 | 必須 > 0 |

---

## comfort_scores.csv — 旅遊舒適度

| 欄位 | 型別 | 驗證規則 |
|------|------|----------|
| `month` | 整數 | 1–12 |
| `city` | 字串 | 必填（例：東京、大阪） |
| `avg_temp_c` | 浮點數 | 無範圍限制 |
| `rain_probability_pct` | 整數 | 0–100 |
| `crowd_index` | 整數 | 1–10 |
