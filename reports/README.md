# 最終報告

本目錄保存最新學生報告交付檔。PDF 適合直接閱讀／繳交，PPTX 保留可編輯內容。
這些檔案從本機已完成的交付版本原樣複製，未因 Git 整理修改簡報日期或內容。

| 專案 | PDF | 可編輯 PPTX | 頁數 |
| --- | --- | --- | --- |
| Project 1 BUILD | [最終 PDF](project1/Project1-Final-Report.pdf) | [最終 PPTX](project1/Project1-Final-Report.pptx) | 26 |
| Project 2 THINK | [v5 PDF](project2/Project2-Final-Report-v5.pdf) | [v5 PPTX](project2/Project2-Final-Report-v5.pptx) | 38 |

## 版本範圍

- Project 1：只修訂第 12、18、22 頁，加入實際 launcher／USA／Taiwan replay 圖片。
- Project 2 v4：改善調查主線、原始曲線讀圖、指標、修復門檻、Agent 成果與驗證狀態。
- Project 2 v5：進一步釐清第 10／11／32 頁三種 loss 評估；補上第 26 頁零基準
  限制；第 38 頁呈現 checkpoint、image/state、修復決策三項具體發現。
- 歷史交付版本與暫存 build 仍留在本機；本目錄只提供最新版本。

## 驗證與使用限制

Project 1 修訂頁曾在 PowerPoint 開啟／匯出後檢查；Project 2 修訂頁已完成
內部 render、結構檢查與最終 PDF 視覺檢查。Project 2 最新 PPTX 的 PowerPoint
實測未完成，Canva 未測試；跨應用程式風險為 MEDIUM。閱讀／繳交建議使用 PDF。
這些版面檢查不構成模型駕駛品質或 Diagnosis／Unified live 驗收。

[manifest.json](manifest.json) 保存四個檔案的 bytes、頁數與 SHA-256；
可在專案根目錄執行 `shasum -a 256 reports/project1/* reports/project2/*` 核對。
原始教材、資料集、模型 checkpoints、API key 與私有 build 未收錄。
