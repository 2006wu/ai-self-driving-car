# Project 2 全份口語化修訂

日期：2026-10-16（Asia/Taipei）。沿用最新 v7，38頁、原頁序、版型與可編輯結構保留。
交付模式：SELF-CONTAINED REPORT DECK MODE。口語化是讓教授閱讀時更容易理解，不刪除影響結論的條件或限制。

本輪重新讀過全部38頁，修改284處原生文字與70個表格儲存格。英文原始回答逐字保留，只改旁邊的中文摘要。

## 主要寫法調整

| 原來的用語 | 改寫方向 |
| --- | --- |
| 產物／artifact | 結果檔案、模型結果 |
| 控制介入／intervention | 固定其他條件，只換一項輸入比較 |
| 執行 gate／升級門檻 | 執行前檢查、是否繼續長訓練的條件 |
| 幾何異常早於視覺化投影 | 曲線在投影到畫面前，就已經不正常 |
| State policy | state 的輸入方式、用誰的 state |
| Frozen-Best state | 固定 Best 模型、先存好的 state |
| 循環軌跡／temporal behavior | 連續預測、相鄰兩幀的變化 |
| canonical readers／有界 claim catalogue | 讀取實驗資料、依已整理的證據檢查說法 |
| finite／train-seen | 沒有 NaN／Inf、曾用於訓練的片段 |
| hash | 檔案指紋（SHA-256） |
| live execution／content correctness | API 有跑完、回答還要核對 |

Loss、state、Teacher forcing、Encoder、MAE／MSE／RMS等必要技術名稱保留，搭配中文說明。
原程式參數與8個工具的精確函式名稱保留，五層架構改用中文描述能力，但不改分級判斷。
特別避免把「平均誤差較低」改寫成「每一筆預測都較好」，或把「實測完成」改成「內容全部正確」。

## 逐頁檢查與修改

| 頁 | 原標題／用途 | 本輪主標題或說明 |
| --- | --- | --- |
| 1 | Model B6 Investigation／& Evidence-Grounded Agents | Model B6 Investigation／& Evidence-Grounded Agents |
| 2 | 課程要求已完成；額外擴充分開驗收 | 課程要求已完成，新增功能另外驗收 |
| 3 | 學生貢獻與模型調查主線 | 我完成的工作，以及怎麼追查模型問題 |
| 4 | 兩條工作流共享同一份實驗證據 | 模型訓練與 Agent 分開跑，共用實驗資料 |
| 5 | Model B6 的四輸入與分支 | Model B6 讀入哪些資料，怎麼產生輸出 |
| 6 | 訓練資料與 teacher forcing | 訓練資料與 Teacher forcing（教師引導） |
| 7 | 修正資料錯配與跨序列 state 延續風險 | 把資料配對好，換影片時重設 state |
| 8 | 正式訓練前的執行 gate | 開始正式訓練前，先通過五個檢查 |
| 9 | 60 epochs 的正式 baseline 訓練 | 完成 60 epochs 的基準訓練 |
| 10 | Validation loss 的波動與 final / best 差距 | 驗證 loss 起伏很大，最後的模型不是最佳模型 |
| 11 | 固定 120 筆評估：Final loss 約為 Best 的 6.48 倍 | 用同樣 120 筆資料，Final loss 是 Best 的 6.48 倍 |
| 12 | Step 6 的可檢查推論管線 | Step 6：把影片送進模型，再檢查結果 |
| 13 | 四組完整影片技術驗證 | 四組影片都跑完，再看輸出是否合理 |
| 14 | 同幀對照：Student 原始曲線已出現鋸齒 | 同一張影像，Student 的原始輸出已有鋸齒 |
| 15 | 幾何異常早於視覺化投影 | 曲線在投影到畫面前，就已經不正常 |
| 16 | 已測輸入確實不同，配對與 scale 一致 | 影像真的不同，資料配對與數值範圍也查過了 |
| 17 | 換影像後輸出幾乎不變，換 state 的影響較大 | 只換影像，輸出幾乎不變；換 state，差異就很大 |
| 18 | 影像差異沿 Encoder 深度整體衰減 | 不同影像經過 Encoder 後，反應差異整體縮小 |
| 19 | 局部 loss gradient：影像方向極弱，state 較大 | 微調影像與 state 時，loss 的反應差很多 |
| 20 | Fresh controls：訓練前就有嚴重梯度衰減 | 還沒開始訓練，梯度往前傳就已大幅變小 |
| 21 | State 來源差異：一項待檢驗的 mismatch 假設 | 訓練讀 Teacher state，推論卻回饋自己的 state |
| 22 | State policy 明顯改變整段幾何行為 | 換成 Teacher 的 state，整段曲線就明顯不同 |
| 23 | 單次 teacher-state 注入取決於時機 | 只換一次 Teacher state，效果取決於時機 |
| 24 | Depthwise：2／5 門檻通過，未升級長訓練 | 改 Depthwise 起始權重，5 項檢查只通過 2 項 |
| 25 | 混入 Frozen-Best state 能改善 free-run 嗎？ | 混入 Best 模型的 state，能讓連續預測更穩嗎？ |
| 26 | Mixed-state：失敗計數增加，DO NOT PROMOTE | 混合 state 後異常更多，因此不繼續長訓練 |
| 27 | 單點誤差改善，不代表循環軌跡更穩定 | 平均誤差變小，不代表連續預測更穩 |
| 28 | Model B6 調查：已知、已測與待解問題 | Model B6：查到了什麼，還有哪些問題沒解 |
| 29 | Agent 基線在獨立 Python 環境執行 | 在獨立 Python 環境中跑完教授的 Agent 範例 |
| 30 | 以 adapter 處理 Agno API 相容性 | 加一層相容處理，讓舊範例能用新版 Agno |
| 31 | 5-Level review：目前主要符合 Level 1 | 依五層架構來看，目前主要做到 Level 1 |
| 32 | 原始 Do New：真實工具數值與已驗收回答 | 第一版 Do New：Agent 讀資料，數值逐項核對 |
| 33 | 教授 baseline 與我的 Do New 新增能力 | 教授範例與我新增的 Do New 功能 |
| 34 | 八個工具＋可重現的證據驗證工具鏈 | 八個工具讀取實驗資料，也檢查資料來源 |
| 35 | Vision live：真實 PNG 輸入與回答節錄 | Vision 實測：給真實圖片，看 Agent 怎麼描述 |
| 36 | Diagnosis／Unified：真實輸入、工具與回答 | Diagnosis／Unified：給什麼資料，得到什麼回答 |
| 37 | Agent 驗證：執行成功與內容正確分開看 | Agent 有跑完，不代表回答都正確 |
| 38 | Project 2：從實作走到可追溯的研究判斷 | Project 2：完成實作，也用實驗追查問題 |

## 原始內容與數據保留

- 所有5個原生圖表的XML、cache、嵌入workbook，以及圖片、theme、master、layout與relationships均byte-identical。
- 35個純數值表格欄位逐格核對不變；原始實驗、模型檔與live run未更動。
- Vision／Diagnosis／Unified的4段原文節錄所屬shape XML逐位元相同，沒有改譯後冒充原文。
- 三種loss評估分開：每epoch平均、固定120筆平均、18筆中位數；6.48倍的對照條件保留。
- MAE／MSE與state RMS不混用；局部梯度與全域因果分開，未把小梯度寫成0。
- teacher state非部署條件、E0零基準問題、修復未達續訓條件、未找到唯一原因等限制保留。
- Diagnosis4工具29.301秒、Unified2工具6.857秒，各一次執行、12項hashes吻合；執行完成但內容待審的狀態不變。
- 96／96是先前離線紀錄，本輪沒有重跑Agent、API或訓練。

## 版面與結構檢查

完整38頁以Artifact Tool及最終PDF的獨立Poppler渲染檢查，修正8／12頁詞彙被拆開的換行，以及中文標籤的長度。
原始頁數、圖表、表格、照片、身份資料、封面日期及頁序保留；本輪改文字，不新增實驗或美化研究數據。

INTERNAL RENDER QA：PASS（38頁檢視及修改頁重檢）。
PPTX STRUCTURAL QA：PASS（38頁、11原生表格、5原生chart；官方package／layout零finding，第一方reimport通過）。
CROSS-APPLICATION SAFETY QA：字型與靜態幾何檢查完成，沿用PingFangTC，PDF使用既有Regular／Semibold實際字檔。
PowerPoint：NOT TESTED；Canva：NOT TESTED。CROSS-APPLICATION RISK：MEDIUM。

## 來源、備份與交付

修改前PPTX／PDF／上一輪報告備份：`/Users/2006wu/Documents/Project2-Archive/01-Reports/Project2-Final/plain-language-refinement-20261016/backup/`。
正式交付：`/Users/2006wu/Desktop/ai-self-drive-car-ws/reports/project2/Project2-Final-Report-v7.pptx`及同名PDF。
桌面同步：`/Users/2006wu/Desktop/Project2-Latest/`，沿用v7，未新增v8或桌面build資料夾。
建置、最終規格、完整逐項變更、QA與備份SHA：`/Users/2006wu/Documents/Project2-Archive/01-Reports/Project2-Final/plain-language-refinement-20261016/build/`。

先前來源、實驗數字核對及所有逐頁審查歷史，保存在本輪backup中的原Professor-Review-Refinement.md；本輪僅改寫表達方式。
Git HEAD 0098f886e078cacbe08eb2d1282922cd78b5b1dc，develop。保留既有未提交工作，未commit／push。

Final PPTX SHA-256：`c99b873401f77d39260fbe3960bf652a9a247bb624281a26f6fe81b95095f089`。

Final PDF SHA-256：`df1be06dde55b5dda428035b071f6366f87a9eaa7882bb449ec4e0aefe6b5569`。
