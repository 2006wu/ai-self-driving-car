# Project 2 — Diagnosis／Unified 內容核對（2026-10-16）

使用者要求重新核對並修正簡報第二頁。本次由助理逐項對照原始實驗資料、兩次既有成功執行及指定圖片；不是使用者已簽核，也不是重新呼叫 Gemini。

**結論：這兩次實測的數值與工具證據核對通過；原始回答的來源引用、解讀依據及影像措辭已另存修正稿。簡報可寫「本次已核對並修正」，不再寫「還要核對內容」。**

核對範圍是下面兩次既有 run，不代表其他樣本、其他模型或未來每次回答皆正確。原始逐字回答保留，有錯誤的原文不升級為完全正確。

## 執行紀錄與資料來源

| 模式 | Run ID | 必要工具 | 時間 |
|---|---|---:|---:|
| Diagnosis | 20261014-230632-diagnosis-5ae5d652 | 4 | 29.301 秒 |
| Unified | 20261014-230705-unified-598a0b14 | 2 | 6.857 秒 |

- 兩次 run 都是 COMPLETED，各 12 個 manifest 檔案 SHA-256 重新驗證吻合，共 24 個。
- 6 個記錄中的實際工具回傳逐一核對原始 payload 指紋，再解析並與目前 canonical readers 的回傳完整比對，均吻合。
- 兩份報告的 reference context 與本機讀取器完整吻合；保存的 Python source hashes 與目前程式吻合。
- canonical exports 自身的 export_manifest、來源路徑、檔案 SHA 與 schema 亦驗證通過。
- 這是程式指定查證項目、模型發出 function calls，不代表模型自主選工具。
- 沒有新增 API 請求、訓練或測試實驗；不修改原始 run／模型／實驗資料。

## Diagnosis：核對結果

| 原回答項目 | 原始資料與本次判斷 |
|---|---|
| 訓練紀錄 | 60 epochs；final train loss 3.204094648361206；final validation loss 71.71458435058594；best validation loss 0.5254096388816833，epoch 25。吻合 Step 5 run.json。 |
| 原始條件梯度 | final／overall／original 的 image_rms 9.774764271218935e-15、state_rms 0.1906711417505237、state_parameter_rms 0.013210675543571816，均為 median。吻合 P29。 |
| mismatched_state 梯度 | image_rms 1.3956618905256544e-14、state_rms 0.23725305578133277、state_parameter_rms 0.020467443504596387。條件與數值吻合。 |
| Encoder magnitude | final stem baseline RMS 73.52477114182263、flatten 5.003806555615661；best 分別 73.51303073396723、4.6388366191403545。吻合 P28；不能稱為影像差異或飽和證明。 |
| Fresh-gradient 9.30–9.40 orders | 數字吻合，但原文誤引 P28 reference_controls.json。**改引 /output/p210-gradient-controls/summary.json**，是 backward gradient 衰減，非 forward activation RMS。 |
| 影像不敏感 | **主要依據改為 P27 的受控影像替換實驗**。極小 loss gradients 只能當補充，不能單獨證明輸出對影像不敏感。 |
| Step 6 四組結果 | USA／Taiwan Final 非正近端車道寬度幀數 1006／941，Best 皆 0；近端路徑最大座標幅值 Final 20.46601676940918／21.714637756347656 m，Best 1.5551618337631226／1.4551631212234497 m。 |
| 機制與因果 | 過度擬合僅部分支持，訓練不穩定也是可能解釋；無法確認 initializer 是唯一原因、訓練才造成衰減或存在普遍 shortcut。原回答的主要限制保留。 |

`path_near_abs_max_m` 是模型預測座標的最大幅值，不是相對真實路線的誤差。`lane_width_near_nonpositive_frames` 是寬度 ≤ 0 的幀數，不是負路徑幀數。以上不證明駕駛準確度、部署適用性或修復成功。

## Unified：核對結果

圖片 `step6/taiwan/best/frame_00001.png` 的 SHA-256 為 `2a46e36a96b78ed0ff6edd9e9f256240cca06fd1f0b405ecc95d4122bf849a5d`；1200×900，domain=taiwan、checkpoint=best，均吻合。

| 原回答項目 | 本次判斷與修正 |
|---|---|
| 夜間道路、車輛、路旁招牌及高架結構 | 圖片可支持這些可見內容。**moving vehicles 改為 visible vehicles**；單張圖無法確認車輛移動。 |
| 綠色路徑、紅／藍車道線有不規則與鋸齒 | 可由原始四格圖直接觀察，限空間上的形狀。不能延伸為跨幀震盪、駕駛失穩或時間平均消除了鋸齒。 |
| 前方同車道／model lead 對應 | 圖片有可見車輛，但無明確 model lead 對應標記。**改為「可見前方車輛；是否同車道與是否對應 model lead 無法由此圖確認」**。 |
| 車道線對齊與跨越標線 | 只描述紅／藍疊圖線的可見形狀，不把「正確對齊」或「跨越標線」當作已驗證結論；缺少 ground truth 與投影誤差對照。 |
| 數值對照 | Taiwan Best：1201 frames、path_near_abs_max_m=1.4551631212234497 m、path_near_mean_m=0.02472166662830858 m、非正近端車道寬度幀數=0，吻合 comparison.json。 |
| 統計範圍 | 數字屬整段 clip，不能確認或否定此幀局部鋸齒，也不是該幀誤差。count、mean 與 max 分開；不是全部 median。 |
| 模型信心 | Medium 是模型自述，非經校準或獨立量測的機率；不作為內容正確率證據。 |

## 簡報調整

更新第 2、33、36、37、38 頁，其他頁序與實驗數字不變。第二頁改為「本次已核對並修正」，第 36–37 頁說明原始回答與修正稿分開保存，核對範圍限上述實測。四段原始英文節錄保持逐字不變。未把修正稿冒充模型原始輸出。

原始 run 在 `projects/project2/agent/artifacts/live-runs/`。完整 checksum 與 source 比對、修正稿、建置與 QA 在私人歸檔 `Documents/Project2-Archive/01-Reports/Project2-Final/content-review-20261016/build/`。

本次狀態取代先前精修 v7 中「等待最終內容驗收」的保留用語；較早的審閱紀錄仍作為歷史保留。未驗證範圍仍包含跨樣本可靠度、駕駛品質、閉迴路安全、單一原因、有效修復與自主工具選擇。

## 交付與版面檢查

- INTERNAL RENDER QA：PASS: all five changed slides inspected in Artifact Tool and independent final-PDF Poppler render; 33 unchanged slide/PDF content streams checked
- PPTX STRUCTURAL QA：PASS: official package/layout finalizer zero findings; first-party reimport;38 slides,11 native tables,5 native charts
- CROSS-APPLICATION SAFETY QA：reference PingFang TC, original geometry/media/chart/workbook retained; PowerPoint and Canva NOT TESTED
- CROSS-APPLICATION RISK：MEDIUM: actual target application import not tested

新版 v8 共38頁，修改第2／33／36／37／38頁；其餘33頁的原生slide XML與PDF內容stream不變。所有charts／workbooks／media／theme／masters／layouts及relationships維持原bytes；四段原始英文節錄的shape XML不變。

正式PPTX／PDF放在reports/project2，桌面Project2-Latest同步；v7保留，未覆蓋目前開啟的原檔。未commit／push。

PPTX SHA-256：`ca4c461acd6369a5538ae8b7e689583b4932971872a075d43c492eaee73d05f4`。

PDF SHA-256：`a80b48898ba85039a929033b32debef6888c8a91d8c5fe5f6af0a6a1e16e5c19`。
