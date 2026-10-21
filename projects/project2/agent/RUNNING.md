# Diagnosis／Unified 執行、輸出與驗收

統一在 Docker 的 Agent 容器內讀取已匯出的證據；macOS 不需要 Python 環境。
Live 執行需要終端機已設定 `GOOGLE_API_KEY`，由入口按名稱轉交容器。
以下指令從 Repository 根目錄執行，首次先跑 `./scripts/dev.sh build agent`。

## 日常執行

先執行一個，結束後再執行另一個：

```sh
./scripts/dev.sh agent diagnosis_agent.py --model gemini-3.5-flash-lite
./scripts/dev.sh agent vision_agent.py --image step6/taiwan/best/frame_00001.png --unified --model gemini-3.5-flash-lite
```

原本 `GEMINI_MODEL_ID=gemini-3.5-flash-lite ...` 的寫法也可繼續使用。
優先順序是 `--model` > `GEMINI_MODEL_ID` > 原有預設；沒有永久修改預設模型。

執行時 stderr 顯示模型、紀錄位置、階段與經過時間。等待模型期間每 10 秒
提供一次狀態；它表示程序仍在等待，不是假造百分比或保證模型正在產生文字。
stdout 預設顯示可讀 Markdown，分成已核對資料、模型解讀、尚未證實事項及
查證紀錄。原始精度、完整 context／SHA-256 保存在本機 JSON。

## 時間與重試上限

| 參數 | 預設 | 意義 |
|---|---:|---|
| `--timeout` | 300 秒 | 所有 worker 嘗試與退避等待的總時間預算 |
| `--attempt-timeout` | 120 秒 | 一個完整 Agent worker 的最大執行時間 |
| `--request-timeout` | 45 秒 | SDK 每次 HTTP 請求逾時 |
| `--retries` | 1 | 初次以外最多再試一次，可設 0–3 |
| `--progress-every` | 10 秒 | 等待狀態輸出間隔 |

SDK、Agno model 與 Agent 的隱藏重試已關閉，由外層統一管理。
只對可辨識的 408／429／500／502／503／504 或 worker 逾時作有限重試；
未知錯誤、輸入／checksum／內容驗證錯誤不重試。整個嘗試只讀證據，重試會
重新建立 Agent，可能增加供應商請求／額度消耗，全部都有紀錄。
429 也可能代表長期額度限制；有限重試不代表額度已恢復。

逾時會終止本機 worker 程序群組，先 SIGTERM、必要時 SIGKILL，清理最多
額外約 1 秒。下一次嘗試在前一次終止後才啟動。Ctrl+C 同樣終止 worker，
紀錄為 CANCELLED、exit 130。這是本機執行上限，不保證供應商端已取消計費／工作。
SDK HTTP timeout 只是其中一層，不能替代整體逾時。

想先不重試：

```sh
./scripts/dev.sh agent diagnosis_agent.py --model gemini-3.5-flash-lite --retries 0
```

查證模式需要較長時間時，可明確調整，例如
`--timeout 600 --attempt-timeout 240 --request-timeout 60`。

## 兩種證據／工具模式

預設 `--tool-mode preload`：程式先用 checksum 驗證本機資料，再將精簡參考
提供給模型。`tools: []` 代表沒有模型主動工具呼叫，不能當成自主查證證據。
輸出會明確說明預載讀取與模型呼叫的差別。

`--tool-mode verify`：用同一批唯讀工具，要求與任務相關的自主查證並檢查結果。

```sh
./scripts/dev.sh agent diagnosis_agent.py --model gemini-3.5-flash-lite --tool-mode verify
./scripts/dev.sh agent vision_agent.py --image step6/taiwan/best/frame_00001.png --unified --model gemini-3.5-flash-lite --tool-mode verify
```

Diagnosis 要求 training／gradient／encoder 工具及 overfitting claim 檢查；
Unified 要求 verification 與 domain comparison。必須有呼叫回傳結果且沒有錯誤，
僅有工具名稱、無回傳內容、錯誤或查詢無關 claim 都不能通過要求。
這可測試模型是否遵循查證任務；不保證模型一定選工具或所有解讀都正確。
Vision-only 沒有這組數值工具，因此不接受 verify 模式。

`tool_audit` 保存回傳內容 SHA-256／bytes，避免將工具參數直接印出或存入摘要。
完整工具數值與來源仍可對照本機 canonical exports。不會為增加呼叫數而虛構工具紀錄。
此模式目前只有離線流程與測試通過，尚無本次優化後的真實 API 驗收。

## 自動保存

每次 live CLI 執行建立新的唯一目錄：

```text
projects/project2/agent/artifacts/live-runs/YYYYMMDD-HHMMSS-MODE-ID/
  request.json       模型、問題、圖片路徑與執行設定；不保存金鑰
  run.json           狀態、嘗試、耗時、環境版本、Git HEAD、Python source hashes
  events.jsonl       外層進度、重試／逾時／取消紀錄
  result.json        成功回傳的完整結果（仍需內容審查）
  report.md          可讀報告
  manifest.json      紀錄檔案的 SHA-256
  attempt-N/
    context.json    通過本機驗證的 context／圖片來源（到達該階段時）
    draft.json      模型草稿與工具回傳摘要（到達該階段時，包含驗證失敗草稿）
    response.json   該次嘗試的結果或錯誤
    stages.jsonl    worker 階段與耗時
    worker.log      經金鑰遮蔽的 SDK／框架輸出（有輸出時）
```

失敗、逾時與取消保留已有紀錄，不產生假的成功 `result.json`。
所有資料留在 Git 忽略的 `artifacts/`，不會上傳、覆寫既有驗收、刪除舊檔或提交 Git。
目錄權限限本機使用者，JSON 為 600；環境金鑰與典型 Gemini key 字串會遮蔽。
可用 `--output-dir /absolute/path` 更改紀錄父目錄。

需要舊版的完整 JSON stdout，附加 `--json`；進度仍寫到 stderr，便於分流：

```sh
./scripts/dev.sh agent diagnosis_agent.py --model gemini-3.5-flash-lite --json > /tmp/diagnosis-result.json
```

沒有 API Key 時會在送出前停止；檔案解析／schema／來源驗證錯誤也不重試。

## 解讀與驗收限制

- 已驗證的是本機來源／數值、特定格式條件及實際執行狀態。
- 模型視覺觀察與因果解讀一律仍需人工覆核；COMPLETED 不等於內容 PASS。
- 近端座標樣點 `[:,4:40]` 的 clip 統計、單張完整曲線的空間鋸齒，以及
  連續影格的時間變化是不同量。不能說鋸齒被時間平均消除。
- 程式會攔住已觀察到的明確「averaged out／away」正向說法；否定說法允許。
  這是針對性檢查，不是所有英文／中文敘述的通用語意驗證。
- 前車存在不等於已驗證模型 lead；車道疊圖不等於準確對齊。
- 仍沒有 ground truth precision／駕駛品質／閉迴路安全驗收。

## 離線驗證

```sh
./scripts/dev.sh test-agent
./scripts/dev.sh agent diagnosis_agent.py --offline
./scripts/dev.sh agent vision_agent.py --image step6/taiwan/best/frame_00001.png --unified --offline
```

本次新增測試使用假的回覆或不連網子程序，沒有呼叫 Gemini。

Step6 聚合方式由 `numerical_reference.metric_reductions` 明確標示：計數、
算術平均、最大值與平均絕對跨幀變化不同；gradient audit 的 median 不適用於
Step6。程式會攔住已觀察到的正向 `aggregation=median` 錯誤標籤。

## 2026-10-14：verify 改為先查證、再寫報告

22:55 的實測沒有通過完整工具查證：Diagnosis 只呼叫 training 與
check_diagnostic_claim，缺 gradient／encoder；Unified tools=[]。這不是 503，
也不是成功的工具驗收。原始 FAILED 紀錄保留。

verify 現分兩階段：程式逐項指定必要工具，讓模型在只有一個工具可用的
查證請求中發出 function call（tool_choice=any、完成一次即停）；每次必須
有實際成功回傳，claim_id 必須是 overfitting。最後才把這些結果和影像
交給報告請求。Unified 最後的 structured-output 請求不再同時掛工具。
這證明的是「程式指定、模型呼叫」流程，不是自主工具選擇。

Diagnosis 有 4 次查證請求＋1 次報告；Unified 有 2 次查證＋1 次報告。
可能比 preload 多耗時間／token；原有 deadline、有限 retry 與取消仍生效。
離線測試通過；修正後真實 API 尚待驗收。重試時可用相同指令，或增加
`--timeout 600 --attempt-timeout 240`。不需 Docker。

## 23:06–23:07 使用者實測

上述分階段 verify 兩項皆已完成：Diagnosis4必要工具＋報告（29.301s），
Unified2必要工具＋圖文報告（6.857s），各1attempt。詳見 audit §44 與
LIVE_REVIEW_20261014.md。沒有必要為同一張圖重複測試成功路徑；內容仍
須覆核，本次審閱稿已修正fresh-gradient引用與單張影像motion措辭。
