# Docker 執行與開發

2026-10-21：三個 Project 合共 352 個容器內測試通過，圖片／影片及 VNC 顯示
流程已執行，詳見 [測試紀錄](../projects/project3/evidence/docker-20261021/RESULTS.md)。

所有 Python、套件安裝、測試、推論及訓練都在容器內執行。macOS 只需
Docker Desktop 和專案原始碼。舊 `.venv` 不再被目前入口使用，保留原檔。

| 範圍 | Compose service | 環境 |
| --- | --- | --- |
| Project 1 OpenPilot / replay | compute | Ubuntu 20.04、Python 3.8、linux/amd64 |
| Project 1 桌面 | display | Xvfb / VNC / noVNC、linux/amd64 |
| Project 2 ModelB6 | modelb6 | TensorFlow CPU、Python 3.8、linux/amd64 |
| Project 2 Agent | agent | Python 3.11、原 requirements、原生 Linux 架構 |
| Project 3 | project3 | Python 3.11、ONNX Runtime CPU、原生 Linux 架構 |

## 建立與測試

在專案根目錄執行：

```bash
./scripts/dev.sh build
./scripts/dev.sh up
./scripts/dev.sh test
```

第一次建立會下載映像與套件；既有映像使用 build cache。ModelB6 延用
已驗證的 compute 基底；統一 build 入口在容器內下載／驗證 TensorFlow wheel，
存放於忽略追蹤的 wheelhouse。單獨準備可用 `./scripts/dev.sh prepare-modelb6`。
換電腦仍需
攜帶教授提供的模型、原始檔與既有資料 volumes，詳見根 README 的還原限制。
這些私有資產不會自動下載。不要用 `docker compose down -v` 清理資料。

日常只重建有變更的依賴環境：

```bash
./scripts/dev.sh build agent project3
./scripts/dev.sh test-modelb6
./scripts/dev.sh test-agent
./scripts/dev.sh test-p3
```

Agent / Project 3 / ModelB6 使用按需容器；測試或工作完成即退出。
原始碼掛載為唯讀，修改程式後下一次執行直接使用新檔。

## Project 3

原 `projects/project3/setup.sh`、`run.sh`、`verify.sh` 現在也一律走 Docker。
相對輸入與輸出路徑以容器 `/workspace/projects/project3` 為準。

```bash
./scripts/dev.sh p3 check
./scripts/dev.sh p3 run artifacts/bus.jpg --track --output artifacts/docker-image
./scripts/dev.sh p3 run artifacts/inputs/usa.hevc --track --simulate-follow --max-frames 300 --output artifacts/docker-video
./scripts/dev.sh p3-python -m p3.research.tracker_benchmark --output artifacts/docker-synthetic.json
./scripts/dev.sh p3-python validate_vision.py --output artifacts/docker-validation
```

每次選新的輸出路徑。結果保存在主機 `projects/project3/artifacts/`；模型
`external/aJLL/bodyjim/yolov5n_flat.onnx` 及 replay-data volume 均為唯讀。
影片也能直接讀 `/data/dataB6/.../video.hevc`，不必在主機解碼或安裝工具。

Linux 容器使用 CPUExecutionProvider，macOS CoreML 不適用；原生 macOS 的
歷史 FPS 不代表 Docker FPS。預設 headless，輸出 PNG / AVI 與 JSON。
要在既有 VNC/noVNC 桌面顯示 Project 3，可透過共用的 X11 socket：

```bash
./scripts/dev.sh p3-display run artifacts/inputs/usa.hevc --track --display --max-frames 300 --output artifacts/docker-display
```

桌面連線為 [noVNC](http://localhost:6080/vnc.html)，密碼與 Project 1 相同。
`p3-display` 使用專案固定的 `ai-self-driving-car_op-runtime` volume。

macOS AVFoundation 相機無法直接映射為 Linux 裝置，現有相機入口未在 Docker
驗證；請先使用影像／影片。Run2 實體裝置與 C2C 驗收仍需硬體流程。

## Project 2 Agent

```bash
./scripts/dev.sh agent baseline_check.py
./scripts/dev.sh agent prepare_v2.py --verify
./scripts/dev.sh agent diagnosis_agent.py --offline
./scripts/dev.sh agent vision_agent.py --list-images
```

Agent 直接唯讀掛載 ModelB6 的 `/output`，匯出程序在容器內驗證來源 SHA256；
不需要 Docker socket 或在容器內再啟動 Docker。匯出與執行紀錄保存在主機
`projects/project2/agent/artifacts/`。無金鑰的測試使用離線路徑。

需要 live API 時，由已設定的 shell 環境傳入 `GOOGLE_API_KEY` 和
`GEMINI_MODEL_ID`（按變數名稱轉交，不寫入 image 或 Compose）：

```bash
./scripts/dev.sh agent diagnosis_agent.py
```

此命令會呼叫外部模型並可能計費；全套離線測試不會執行它。

## ModelB6 與 OpenPilot

原有 Docker 指令持續適用。ModelB6 可用統一入口：

```bash
./scripts/dev.sh modelb6 /workspace/student/compatibility_check.py
./scripts/dev.sh modelb6 /workspace/student/step5.py preflight
./scripts/openpilot.sh display
./scripts/openpilot.sh replay-jll-demo
```

訓練不是環境驗證的必要步驟；不會為遷移環境重跑長時間訓練或覆寫既有成果。
Project 1 的 `validate` 檢查容器、資產、連接與桌面服務，不等同重新目視驗收 replay。
