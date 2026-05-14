# 需求文件

## Introduction

「日本旅遊最佳出發時機分析 Dashboard」是一個以 Python 為核心、輸出靜態 HTML 的分析工具。  
系統從 CSV 檔案讀取台灣飛日本的來回票價（中華航空 CI、長榮航空 BR、星宇航空 JX）、JPY/TWD 匯率，以及旅遊舒適度指標（天氣、人潮），透過 pandas 進行資料處理，並以 plotly 產生互動式圖表，最終輸出單一 HTML 檔案，協助使用者找出最划算且舒適的出國時機。

資料更新方式為手動執行，不包含背景常駐程式、資料庫、容器化或機器學習功能。

---

## 詞彙表

- **Dashboard**：本系統產生的靜態 HTML 分析報告頁面
- **Analyzer**：負責讀取 CSV、執行資料分析與計算的 Python 模組
- **Renderer**：負責將分析結果轉換為 plotly 圖表並輸出 HTML 的 Python 模組
- **Scorer**：負責計算綜合評分的 Python 模組
- **CSV_Store**：存放所有輸入資料的 CSV 檔案集合
- **Fare_Record**：單筆航班票價資料，包含日期、航空公司、出發地、目的地、來回票價（TWD）
- **Rate_Record**：單筆匯率資料，包含日期、JPY/TWD 匯率
- **Comfort_Record**：單筆旅遊舒適度資料，包含月份、目的地城市、平均氣溫（°C）、降雨機率（%）、觀光人潮指數（1–10）
- **綜合評分**：由票價分數、匯率分數、舒適度分數依權重加總所得的 0–100 分數值
- **出發時機**：以月份為單位的出行建議區間

---

## Requirements

### Requirement 1：資料輸入與驗證

**User Story:** 身為資料分析師，我希望系統能讀取並驗證 CSV 資料，以確保後續分析基於正確且完整的資料。

#### Acceptance Criteria

1. THE Analyzer SHALL 從 `data/fares.csv` 讀取 Fare_Record，欄位包含 `date`（YYYY-MM-DD）、`airline`（CI／BR／JX）、`origin`（IATA 機場代碼）、`destination`（IATA 機場代碼）、`roundtrip_fare_twd`（正整數）。
2. THE Analyzer SHALL 從 `data/rates.csv` 讀取 Rate_Record，欄位包含 `date`（YYYY-MM-DD）、`jpy_twd_rate`（正浮點數）。
3. THE Analyzer SHALL 從 `data/comfort.csv` 讀取 Comfort_Record，欄位包含 `month`（1–12）、`city`（城市名稱）、`avg_temp_c`（浮點數）、`rain_probability_pct`（0–100 整數）、`crowd_index`（1–10 整數）。
4. WHEN 任一 CSV 檔案不存在，THE Analyzer SHALL 將錯誤訊息輸出至 stderr，說明缺少的檔案完整路徑，並以退出碼 1 終止執行。
5. WHEN CSV 欄位缺少必要欄位，THE Analyzer SHALL 將列出所有缺少欄位名稱的錯誤訊息輸出至 stderr，並以退出碼 1 終止執行。
6. WHEN Fare_Record 的 `roundtrip_fare_twd` 為非正整數或空值，THE Analyzer SHALL 略過該筆資料並將警告訊息輸出至 stderr，訊息包含該筆資料的 CSV 列號（從 2 開始計，含標頭列）。
7. WHEN Rate_Record 的 `jpy_twd_rate` 為非正浮點數或空值，THE Analyzer SHALL 略過該筆資料並將警告訊息輸出至 stderr，訊息包含該筆資料的 CSV 列號。
8. WHEN Comfort_Record 的 `crowd_index` 超出 1–10 範圍、`rain_probability_pct` 超出 0–100 範圍，或 `month` 超出 1–12 範圍，THE Analyzer SHALL 略過該筆資料並將警告訊息輸出至 stderr，訊息包含該筆資料的 CSV 列號及超出範圍的欄位名稱。
9. WHEN Fare_Record 的 `airline` 欄位值不屬於 CI、BR、JX 之一，THE Analyzer SHALL 略過該筆資料並將警告訊息輸出至 stderr，訊息包含該筆資料的 CSV 列號及實際讀取到的值。
10. WHEN 任一 CSV 的 `date` 欄位值不符合 YYYY-MM-DD 格式，THE Analyzer SHALL 略過該筆資料並將警告訊息輸出至 stderr，訊息包含該筆資料的 CSV 列號及實際讀取到的值。

---

### Requirement 2：票價分析

**User Story:** 身為旅遊規劃者，我希望能看到各航空公司按月份的票價趨勢，以便比較不同時期的機票費用。

#### Acceptance Criteria

1. THE Analyzer SHALL 依 `airline` 與 `date` 所屬月份分組，計算每組的平均來回票價（TWD），平均值四捨五入至整數。
2. THE Analyzer SHALL 計算所有航空公司合併後，每個月份的最低來回票價（TWD）（即該月份所有有效 Fare_Record 中 `roundtrip_fare_twd` 的最小值）。
3. WHEN 某航空公司在特定月份無有效 Fare_Record，THE Analyzer SHALL 在該月份的該航空公司欄位填入空值（NaN），而非以 0 代替，且該空值不參與任何平均或最低票價計算。
4. THE Renderer SHALL 產生折線圖，X 軸為月份（整數 1–12，標籤顯示為「1月」至「12月」），Y 軸為平均來回票價（TWD），每條折線代表一家航空公司（CI、BR、JX），並以不同顏色區分；圖例須標示航空公司代碼。
5. THE Renderer SHALL 在折線圖上以標記點（marker）標示每條折線中票價最低的資料點，並在該點旁顯示標籤，格式為「TWD {金額}」（金額為整數，無千分位符號）。
6. WHEN 某航空公司所有月份均無資料，THE Renderer SHALL 不為該航空公司繪製折線，但須在圖例中以灰色標示並附註「無資料」。

---

### Requirement 3：JPY/TWD 匯率分析

**User Story:** 身為旅遊規劃者，我希望能看到 JPY/TWD 匯率的歷史走勢，以便判斷換匯的最佳時機。

#### Acceptance Criteria

1. THE Analyzer SHALL 依 `date` 所屬月份分組，計算每個月份的平均 JPY/TWD 匯率，平均值保留小數點後四位。
2. THE Analyzer SHALL 識別平均匯率最高的月份；WHEN 多個月份並列最高，THE Analyzer SHALL 將所有並列月份均標記為最佳換匯月份。
3. THE Renderer SHALL 產生折線圖，X 軸為月份（整數 1–12，標籤顯示為「1月」至「12月」），Y 軸為平均 JPY/TWD 匯率，Y 軸起始值為資料集中的最小月均匯率（非零），並以水平虛線標示全年（所有月份）平均匯率，虛線旁標示數值。
4. THE Renderer SHALL 在匯率折線圖上以可辨識的視覺標記（如星形符號）標示所有最佳換匯月份，該標記須與折線圖其他資料點在視覺上可明確區分（例如使用不同形狀或顏色）。
5. WHEN 某月份無 Rate_Record，THE Analyzer SHALL 在該月份填入空值（NaN），且 THE Renderer SHALL 在折線圖中以斷線（gap）呈現該月份，不以插值填補。

---

### Requirement 4：旅遊舒適度分析

**User Story:** 身為旅遊規劃者，我希望能看到各目的地城市按月份的天氣與人潮資訊，以便選擇舒適的旅遊時機。

#### Acceptance Criteria

1. THE Analyzer SHALL 依 `city` 與 `month` 分組，分別計算 `avg_temp_c`、`rain_probability_pct`、`crowd_index` 三項指標的平均值；`avg_temp_c` 保留小數點後一位，`rain_probability_pct` 四捨五入至整數，`crowd_index` 四捨五入至小數點後一位。
2. THE Renderer SHALL 產生熱力圖（heatmap），X 軸為月份（1–12），Y 軸為目的地城市，色彩深淺代表 `crowd_index` 數值，色彩映射範圍使用資料集中 `crowd_index` 的實際最小值至最大值，數值越低（人潮越少）色彩越淺。
3. THE Renderer SHALL 產生長條圖，X 軸為月份（1–12），Y 軸為 `rain_probability_pct`（%，範圍 0–100），每個目的地城市以不同顏色的長條呈現，並在圖例中標示城市名稱。
4. THE Renderer SHALL 在熱力圖的每個格子內顯示 `avg_temp_c` 的平均值，格式為「{數值}°C」（數值保留小數點後一位，例如「18.5°C」）。
5. WHEN 某城市在特定月份無 Comfort_Record，THE Renderer SHALL 在熱力圖對應格子顯示「N/A」，並以中性色（灰色）填充該格子。

---

### Requirement 5：綜合評分計算

**User Story:** 身為旅遊規劃者，我希望系統能整合票價、匯率與舒適度，給出每個月份的綜合評分，以便快速找出最佳出發時機。

#### Acceptance Criteria

1. THE Scorer SHALL 依下列公式計算每個月份的票價分數：`票價分數 = 100 × (最高月均最低票價 − 當月月均最低票價) ÷ (最高月均最低票價 − 最低月均最低票價)`，分數越高代表票價越低；WHEN 所有月份票價相同（分母為零），THE Scorer SHALL 將所有月份票價分數設為 50.0。
2. THE Scorer SHALL 依下列公式計算每個月份的匯率分數：`匯率分數 = 100 × (當月平均匯率 − 最低月均匯率) ÷ (最高月均匯率 − 最低月均匯率)`，分數越高代表換匯越划算；WHEN 所有月份匯率相同（分母為零），THE Scorer SHALL 將所有月份匯率分數設為 50.0。
3. THE Scorer SHALL 依下列公式計算每個月份的舒適度分數（使用該月份所有城市的平均值）：`舒適度分數 = 100 × (1 − (avg_rain_probability_pct ÷ 100) × 0.5 − (avg_crowd_index ÷ 10) × 0.5)`，結果限制在 0–100 範圍內，分數越高代表越舒適。
4. THE Scorer SHALL 依下列權重計算綜合評分：`綜合評分 = 票價分數 × 0.4 + 匯率分數 × 0.3 + 舒適度分數 × 0.3`，結果四捨五入至小數點後一位。
5. WHEN 某月份缺少票價資料（票價分數為 NaN），THE Scorer SHALL 以該月份的綜合評分填入空值（NaN），且 THE Renderer SHALL 在綜合評分圖中以灰色長條並標示「資料不足」呈現該月份。
6. THE Renderer SHALL 產生長條圖，X 軸為月份（1–12），Y 軸為綜合評分（0–100），長條顏色依評分高低連續漸變：評分 ≥ 70 為綠色系，評分 40–69 為黃色系，評分 < 40 為紅色系。
7. THE Renderer SHALL 在綜合評分圖上標示評分最高的月份（排除 NaN），標示格式為「最佳月份：{月份}月（{評分}分）」，標示位置為該長條頂端正上方。

---

### Requirement 6：靜態 HTML Dashboard 輸出

**User Story:** 身為使用者，我希望系統能輸出單一 HTML 檔案，讓我無需安裝任何軟體即可在瀏覽器中瀏覽所有分析結果。

#### Acceptance Criteria

1. THE Renderer SHALL 將所有圖表整合至單一 HTML 檔案，預設輸出路徑為 `output/dashboard.html`（可透過 `--output` 參數覆寫）。
2. THE Renderer SHALL 使用 plotly 的 `include_plotlyjs='cdn'` 以外的方式（即 `include_plotlyjs=True` 或 `include_plotlyjs='inline'`）在 HTML 檔案中嵌入 plotly JavaScript 資源，使 HTML 檔案可在無網路環境下獨立開啟。
3. THE Dashboard SHALL 包含頁首 `<header>` 元素，顯示標題「日本旅遊最佳出發時機分析」及資料更新日期，日期取自執行當下的系統日期，格式為 YYYY-MM-DD。
4. THE Dashboard SHALL 依序呈現以下四個區塊，每個區塊以 `<section>` 元素包裹並附有對應標題：（1）綜合評分總覽、（2）票價分析、（3）匯率分析、（4）旅遊舒適度分析。
5. THE Dashboard SHALL 在每個圖表區塊下方以 `<p>` 元素顯示說明文字，說明文字須包含該圖表的判讀方式（例如：如何識別最佳月份、數值的意義）。
6. WHEN `output/` 目錄（或 `--output` 指定路徑的父目錄）不存在，THE Renderer SHALL 嘗試以 `os.makedirs(..., exist_ok=True)` 自動建立；IF 目錄建立失敗，THEN THE Renderer SHALL 將包含 Python 例外訊息的錯誤訊息輸出至 stderr，並以退出碼 1 終止執行。
7. THE Renderer SHALL 在 HTML 寫入嘗試完成後（無論成功或失敗），於 stdout 顯示一行訊息，格式為「輸出路徑：{絕對路徑}」。

---

### Requirement 7：命令列執行介面

**User Story:** 身為使用者，我希望能透過單一命令執行完整分析流程，以便快速產生最新的 Dashboard。

#### Acceptance Criteria

1. THE Analyzer SHALL 支援以 `python main.py` 指令執行完整分析流程，依序包含：資料讀取、欄位驗證、資料列驗證、票價分析、匯率分析、舒適度分析、綜合評分計算、HTML 輸出。
2. WHEN 使用者執行 `python main.py --help`，THE Analyzer SHALL 於 stdout 顯示所有可用參數的名稱、預設值及一行說明文字，並以退出碼 0 結束。
3. WHERE 使用者指定 `--data-dir {路徑}` 參數，THE Analyzer SHALL 從指定路徑讀取 `fares.csv`、`rates.csv`、`comfort.csv`，而非預設的 `data/` 目錄；WHEN 指定路徑不存在，THE Analyzer SHALL 輸出錯誤訊息至 stderr 並以退出碼 1 終止。
4. WHERE 使用者指定 `--output {路徑}` 參數，THE Renderer SHALL 將 HTML 輸出至指定路徑，而非預設的 `output/dashboard.html`；指定路徑的副檔名不限，但建議為 `.html`。
5. WHEN 分析流程每個階段執行成功，THE Analyzer SHALL 於 stdout 顯示該階段完成訊息，格式為「[完成] {階段名稱}」，階段名稱包含：資料載入、資料驗證、票價分析、匯率分析、舒適度分析、綜合評分、Dashboard 輸出。
6. WHEN 分析流程因任何錯誤終止，THE Analyzer SHALL 於 stderr 顯示一行錯誤摘要（格式：「[錯誤] {錯誤原因}」），並以退出碼 1 結束程序；退出碼 0 僅在所有階段均成功完成時使用。
