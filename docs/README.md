# 文件導覽

先查看根目錄 [README](../README.md) 的使用方式，以及
[最新簡報／PDF](../reports/README.md)。狀態以 audit 頂端及最後的更新為準；
較早的實驗紀錄保留當時結果，不代表目前工作目錄仍含所有歷史檔案。

| 主題 | 文件 | 用途 |
| --- | --- | --- |
| 統一 Docker 操作 | [DOCKER](DOCKER.md) | 三個 Project 的建立、測試、執行與資料掛載 |
| Project 1 BUILD | [IMPLEMENTATION](IMPLEMENTATION.md) | Docker、UI、replay 的實作與修正 |
| Project 1 驗證 | [INSTALLOP_AUDIT](INSTALLOP_AUDIT.md) | 實測、驗證範圍與清理分類 |
| 原始流程參考 | [JLL 安裝與 Replay 歷史流程](reference/JLL_INSTALL_REPLAY.md) | 原始 Ubuntu 安裝、舊版排錯與 2026-10-04 快照；非目前操作手冊 |
| 本機資產 | [INSTALLOP_ASSETS](INSTALLOP_ASSETS.md) | 原始下載來源、hash 與保存位置 |
| 課程範圍 | [COURSE_PLAN](COURSE_PLAN.md) | 教授要求的專案摘要 |
| Project 3 ACT | [PROJECT3](PROJECT3.md) | Run1–2 稽核、追蹤／控制離線工具與硬體驗收連結 |
| Project 2 THINK | [PROJECT2](PROJECT2.md) | 課程要求、架構、目前狀態與歷史規劃 |
| Project 2 驗證 | [PROJECT2_AUDIT](PROJECT2_AUDIT.md) | 依日期累積的調查與驗收證據 |
| 實驗日誌 | [EXPERIMENT_LOG](EXPERIMENT_LOG.md) | 實驗、決策與結果的歷史紀錄 |
| ModelB6 操作 | [ModelB6 README](../projects/project2/modelb6/README.md) | 隔離環境、Steps 5–10 命令 |
| Agent 操作 | [Agent README](../projects/project2/agent/README.md) | 目前 baseline／v2 檔案與離線命令 |
| Do New v2 | [DO_NEW_V2](../projects/project2/agent/DO_NEW_V2.md) | Diagnosis、Vision、Unified 與證據工具 |
| Framework review | [FRAMEWORK_REVIEW](../projects/project2/agent/FRAMEWORK_REVIEW.md) | 5-Level 架構分析與歷史 v1 定位 |

## 目前狀態

- Project 1：已有 USA／Taiwan replay 畫面與環境技術驗證；全新空 volume
  的端到端重建仍不是已完成成果。
- Project 2：原始課程範圍完成；模型調查及短訓練修復候選的結果已記錄。
  技術驗證不等於駕駛品質通過。
- Agent：baseline、Evidence v1 歷史 live、USA/final Vision 單張 live 已驗收。
  Diagnosis／Unified 的指定工具實測已完成；2026-10-16 已核對這兩次回答並另存來源／措辭修正，
  詳見 [內容核對](../reports/evidence/project2/Agent-Content-Review-20261016.md)。未驗證跨樣本可靠度。
- Evidence v1 source 可由 Git `e1a1bc5` 追溯；目前工作目錄保留 baseline／v2。
  清理時 44 個測試與歷史 55 個測試的差異來自移除 11 個 v1-only tests；
  新增 CLI、Unified trace／prompt 與 report context 測試後，目前為 96/96；推送前再次通過。見 Project 2 audit §34–48。
- Project 3 ACT：YOLO、kalman_iou／benchmark、MOT/CVAT 匯入與三追蹤器評估、
  latest-frame webcam/stream、PID 模擬、control dataset、ridge/MLP BC、1.0 m
  too-close stop、mock/dry-run body interface、Run2 匯出／量測 checklist 及 Report 3
  圖表工具已完成；目前 293 tests，OK (skipped=0)（Mac Docker `./scripts/dev.sh test-p3`，`develop` 31f5527）。Mac `develop` 131faef 全機健檢
  為 472 tests（當時 P3 283），stream SIGINT 後軟體 STOP 約 0.05 s。
  仍待 Run2 真車 session／驗收、真人 CVAT 標註評估、`--display` 的 q/c/n/r/s
  手動測試、需 API key 的 Gemini online call，以及 2026-12-25 Report 3 文字／投影片。
  Run2 identity continuity 需人工 `target_identity`；實體 C2C/comma body 控制未實作，
  須另做安全審查。所有控制為 simulation_only，real transport 拒絕執行。
  詳見 [Project 3](PROJECT3.md)。MR Projects 不計入 Project 2 成果。

## 版本控制與本機內容

Git 保存學生 source、文件與 `reports/` 的交付檔。教授教材、原始 reference、
資料集、checkpoints、venv、canonical exports 和暫存 build 留在本機／Docker
volume，依 `.gitignore` 排除。整理文件不會重新訓練、重試 API 或刪除 volumes。
