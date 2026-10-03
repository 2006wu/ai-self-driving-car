# ai-self-driving-car

macOS Apple Silicon 上的 openpilot v0.9.1 Docker 編譯與顯示環境。兩個服務均為 linux/amd64 Ubuntu 20.04，由 Docker Desktop 模擬執行。

- compute：Python 3.8、Poetry 1.3.2、SCons 4.4.0、原始碼編譯與 replay。
- display：Xvfb 1920×1080、Openbox、啟動器、VNC/noVNC。
- [完整實作紀錄](docs/IMPLEMENTATION.md)
- [原始 JLL 安裝筆記](codex_command/README_OpenPilot_v0.9.1_Install_Replay.md)

## 目前完成範圍

官方 v0.9.1 完整 SCons 編譯已出現 `scons: done building targets.`。
官方 UI 與 `tools/replay/replay` 已產生；UI 關閉返回啟動器已實測兩輪成功。
官方 demo 的 qcamera 回放也已實測成功：compute 解碼，display 顯示道路、車速與車道標記。
這是片段回放驗證，未逐一播放完 route 的全部 11 個 segments。

**JLL 流程尚未全部完成**：目前沒有原筆記指定的 tools092.zip、JLL 設定檔、
replayJLL source、dataC/dataB6/aJLL。官方編譯產物叫 replay，不是 replayJLL。
健康 socket 成功不等於錄製資料回放成功；最後驗證結果見實作紀錄。

## 日常使用

建議使用快捷工具，不必每次輸入完整的 Docker Compose 指令：

```bash
./scripts/openpilot.sh up
./scripts/openpilot.sh display
./scripts/openpilot.sh status
```

之後新增功能也會集中在 `scripts/openpilot.sh`，先查看所有可用命令：

```bash
./scripts/openpilot.sh help
```

以下指令都在專案根目錄執行。先開啟 Docker Desktop：

```bash
docker compose -f docker/docker-compose.yaml up -d
```

連線方式：

- macOS 螢幕共享：`vnc://127.0.0.1:5910`
- 瀏覽器：[noVNC](http://localhost:6080/vnc.html)
- 密碼：`0000`（兩種方式相同，本機 loopback 限定）

noVNC 開啟後直接按 Connect，使用同一個網站的 WebSocket 連線，不需輸入容器內部的 5900。

點「開啟 OpenPilot」啟動官方 UI。拖曳標題列移動、拖曳邊框縮放；
按 UI 的 × 關閉後，會自動回到啟動器。沒有額外浮動退出按鈕。
啟動器自身的 × 會最小化，使用 Alt+Tab 或桌面中鍵視窗清單找回。

官方 UI 有固定大小元件，小視窗可能裁切；要完整閱讀，請最大化 UI，
再使用 VNC 的「縮放至視窗」。可拖曳大小不代表官方版面會等比例縮放。

## 第一次建立或搬到另一台機器

```bash
docker compose -f docker/docker-compose.yaml config --quiet
docker compose -f docker/docker-compose.yaml build
docker compose -f docker/docker-compose.yaml up -d
docker compose -f docker/docker-compose.yaml exec compute scons -u -j2
bash scripts/validate-docker.sh
```

第一次 clone、LFS、套件下載及 amd64 編譯可能較久。
image build 成功和 openpilot SCons 編譯成功是兩件事。
編譯應以結束碼 0 與 `scons: done building targets.` 判斷。

版本與 submodule 檢查：

```bash
docker compose -f docker/docker-compose.yaml exec compute git describe --tags --always
docker compose -f docker/docker-compose.yaml exec compute git submodule status
docker compose -f docker/docker-compose.yaml exec compute poetry --version
docker compose -f docker/docker-compose.yaml exec compute scons --version
```

固定官方 tag v0.9.1，commit 為 `d891d3df476cdaca52dc350bcfdaaa137bbc3840`；
detached HEAD 正常。相容性修正可能讓工作目錄顯示 dirty。

## 什麼時候需要 build？

| 修改 | 指令 |
| --- | --- |
| 只是關機後再次使用 | `up -d` |
| 只修改 Compose 環境變數、port、volume | `up -d` |
| 修改 Dockerfile、entrypoint、launcher.py 或 COPY 的 Python 檔 | `build` 後 `up -d` |
| 修改 openpilot C++ source | 在 compute 執行 SCons |

只更新 display：

```bash
docker compose -f docker/docker-compose.yaml build display
docker compose -f docker/docker-compose.yaml up -d --no-deps display
```

更新 compute 時，共享 IPC 的 display 也需重建：

```bash
docker compose -f docker/docker-compose.yaml build compute
docker compose -f docker/docker-compose.yaml up -d --force-recreate compute display
```

## 官方 replay

先在 VNC 開啟 UI，再在終端機執行：

```bash
./scripts/openpilot.sh replay-demo
```

這個快捷命令會自動啟動需要的 services，然後執行官方 demo。

Ctrl+C 停止。`--qcam` 使用較小的影片，`-c 1` 限制快取 segment 數量。
demo 需要舊版程式指定的遠端 route 可取得。
若出現 `Error opening terminal: unknown`，在 `exec` 後加上 `-e TERM=xterm`。
這是官方 replay 的操作方式，不代表指定的 JLL demo 已驗證完成。

本機資料可複製到持久化 /data（先把範例路徑換成實際資料位置）：

```bash
docker compose -f docker/docker-compose.yaml cp /absolute/path/to/dataC compute:/data/dataC
docker compose -f docker/docker-compose.yaml exec compute \
  tools/replay/replay --no-hw-decoder --data_dir /data/dataC \
  "8bfda98c9c9e4291|2020-05-11--03-00-57--61"
```

也可以使用快捷命令：

```bash
./scripts/openpilot.sh replay-route /data/dataC \
  "8bfda98c9c9e4291|2020-05-11--03-00-57--61"
```

必須先取得並驗證 route 資料的實際目錄結構；上述指令不會自動下載 dataC。
要完成原筆記的 replayJLL，需提供 tools092.zip/replayJLL source 及指定設定檔，
比較修改後再整合；不要將官方 binary 改名來取代。

## 檢查與停止

```bash
bash scripts/validate-docker.sh
docker compose -f docker/docker-compose.yaml ps -a
docker compose -f docker/docker-compose.yaml logs --tail=80 compute display
docker compose -f docker/docker-compose.yaml exec display tail -80 /tmp/launcher.log
docker compose -f docker/docker-compose.yaml exec display tail -80 /tmp/openpilot-ui.log
```

對應的快捷命令：

```bash
./scripts/openpilot.sh validate
./scripts/openpilot.sh logs
./scripts/openpilot.sh down
```

驗證腳本只檢查現有服務，不會自行 build 或關閉服務，也不認證 replay 資料完整性。

正常停止並保留資料：

```bash
docker compose -f docker/docker-compose.yaml down
```

不要加入 `-v`，除非確定要刪除原始碼、編譯產物與錄製資料 volumes。

## 目錄與持久化

```text
README.md                  使用說明
docs/IMPLEMENTATION.md     實作、修正與驗證紀錄
codex_command/             使用者提供的原始指示
docker/                    Compose、Dockerfiles、entrypoints、啟動器、健康 socket
scripts/validate-docker.sh 非破壞性的執行環境檢查
```

| Volume / namespace | 用途 |
| --- | --- |
| openpilot-repo → /opt/openpilot | 原始碼與編譯結果；display 唯讀 |
| replay-data → compute:/data | 本機 replay 資料 |
| op-socket → /run/openpilot | 自訂健康檢查 socket |
| op-runtime → /tmp | 官方 VisionIPC socket 與 runtime/cache |
| compute 的 IPC/PID namespace | display 共用 msgq shared memory 與程序通知 |

重建 image 不會覆蓋既有 openpilot-repo volume。需要更新 source 時，
先檢查 volume 裡的 Git 狀態；不要刪 volume 當作更新方法。
Git remote 已設定，專案目前已推送到 `origin/main`；後續修改需重新 commit/push。

## 原始 README 對照結果

原始 JLL 筆記的 Docker 對照如下：

| 原始步驟 | 目前結果 |
| --- | --- |
| Python 3.8 | 已完成，container 內為 3.8.10 |
| Poetry 1.3.2 | 已完成 |
| openpilot v0.9.1 | 已完成，固定 tag checkout |
| submodules | 已初始化並驗證 |
| Linux / Qt dependencies | 已寫入 Dockerfile 並驗證 |
| SCons build | 已完成，輸出 `done building targets` |
| UI | 已完成，VNC/noVNC 可顯示 |
| 官方 replay | 已完成，demo qcamera 跨容器顯示成功 |
| tools092 / replayJLL | 缺少原始外部檔案 |
| dataC / dataB6 / aJLL | 缺少資料與來源 |

因此目前環境已可用；JLL 專屬部分要取得原始檔案後才能繼續，不應用官方 `replay` 假裝替代。
