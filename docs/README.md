# 文件導覽

先查看根目錄 [README](../README.md) 的使用方式，以及
[最新簡報／PDF](../reports/README.md)。狀態以 audit 頂端及最後的更新為準；
較早的實驗紀錄保留當時結果，不代表目前工作目錄仍含所有歷史檔案。

| 主題 | 文件 | 用途 |
| --- | --- | --- |
| Project 1 BUILD | [IMPLEMENTATION](IMPLEMENTATION.md) | Docker、UI、replay 的實作與修正 |
| Project 1 驗證 | [INSTALLOP_AUDIT](INSTALLOP_AUDIT.md) | 實測、驗證範圍與清理分類 |
| 本機資產 | [INSTALLOP_ASSETS](INSTALLOP_ASSETS.md) | 原始下載來源、hash 與保存位置 |
| 課程範圍 | [COURSE_PLAN](COURSE_PLAN.md) | 教授要求的專案摘要 |
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
  Diagnosis／Unified 已實作並離線驗證，完整 live 驗收仍擱置。
- Evidence v1 source 可由 Git `e1a1bc5` 追溯；目前工作目錄保留 baseline／v2。
  44 個目前測試與 55 個歷史測試的差異來自移除 11 個 v1-only tests。
- Project 3 ACT：後續規劃，MR Projects 不計入 Project 2 成果。

## 版本控制與本機內容

Git 保存學生 source、文件與 `reports/` 的交付檔。教授教材、原始 reference、
資料集、checkpoints、venv、canonical exports 和暫存 build 留在本機／Docker
volume，依 `.gitignore` 排除。整理文件不會重新訓練、重試 API 或刪除 volumes。
