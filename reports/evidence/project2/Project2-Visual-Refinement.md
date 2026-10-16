# Project 2 背景配色修訂（2026-10-16）

以使用者最後儲存的桌面 v8（2026-10-16 13:13）為來源；不採用專案目錄內較早的 v8，也不沿用過期的 PDF。
交付模式：SELF-CONTAINED REPORT DECK MODE，38頁，保留使用者的所有文字、數字、換行、備註、原圖、字型及物件位置。

## 配色與參考

參考 Project 1 的深底封面、第15頁發現及第26頁總結，用背景換色標示重點與章節，不逐頁交替。
Project 2 保留 THINK 的紫色主題，深底 #1C1930，白色主標、淡紫 #C4B5FD 重點及灰紫 #D4CFE2 內文；淡紫背景 #F1EDFA。

| 頁碼 | 用途 | 調整 |
|---|---|---|
| 1 | 封面 | 原深底調成一致的深紫 |
| 15 | 投影前即出現異常的發現 | 深紫底；原始證據圖片保持原色 |
| 20 | 尚未訓練就有梯度衰減 | 淡紫底；圖表保持淺底 |
| 28 | Model B6 調查小結 | 淡紫底，銜接章節 |
| 29 | Agent 章節入口 | 深紫底與高對比文字 |
| 38 | 最後總結 | 深紫底，呼應封面 |

其他32頁保持來源樣式；內部PNG逐像素比對一致。沒有新增頁面或修改任何文字內容、圖片、實驗資料或研究結論。

## 原生圖表的儲存精度處理

來源經PowerPoint儲存後，123個圖表快取數字字串與其內嵌工作表僅有浮點數序列化末位差異，最大絕對差1e-14。
官方chart/workbook一致性檢查要求精確相等，因此只將chart cache對齊其原本內嵌worksheet值。內嵌xlsx bytes、公式、資料範圍、曲線、座標軸與格式不變；並未替換成新的資料表或修改實驗數值。
詳細記錄在私人build/cache-refresh.json。不能宣稱chart XML逐位元相同，但沒有可見數值或圖形變動；32個未改背景頁的render逐像素一致。

## QA

- INTERNAL RENDER QA：PASS。38頁完整render／contact scan，六個修改頁前後及最終PDF獨立Poppler render檢視，文字對比及圖表可讀。
- PPTX STRUCTURAL QA：PASS。官方package／layout零finding，first-party reimport通過；38slides／11native tables／5native charts。
- CROSS-APPLICATION SAFETY QA：沿用來源PingFang TC與實際Regular／Semibold字檔；原生圖表、工作表、媒體、notes、theme、masters、layouts與relationships保留。除顏色外slide XML內容相同。
- PowerPoint最新v9：NOT TESTED；Canva：NOT TESTED。CROSS-APPLICATION RISK：MEDIUM，目標應用程式匯入仍未實測。

私人備份與建置：Documents/Project2-Archive/01-Reports/Project2-Final/background-rhythm-20261016。
桌面最新與repo均另存v9；使用者v8原檔不變。未變更Project1、專案程式、模型、原始實驗或live run；未commit／push。

Source v8 SHA-256：`ca3c53b025d439b290b50e12c867d9d3cb7715c2f3dc3f8259c9d7775f43e2ea`。

Final PPTX SHA-256：`80a69d2148a523a23dd3ad0a01cca1bffb27530925f08bf0643afac6cea26e2c`。

Final PDF SHA-256：`411ce121a85b0aae2a27df0c71bbd60a4159f634908846be8a67d2a7687fc9f9`。
