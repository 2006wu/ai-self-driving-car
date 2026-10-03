# ai-self-driving-car

macOS Apple Silicon 上的 openpilot v0.9.1 Docker 編譯與顯示環境。兩個服務均為 linux/amd64 Ubuntu 20.04，由 Docker Desktop 模擬執行。

- compute：Python 3.8、Poetry 1.3.2、SCons 4.4.0、原始碼編譯與 replay。
- display：Xvfb 1920×1080、Openbox、啟動器、VNC/noVNC。
- [完整實作紀錄](docs/IMPLEMENTATION.md)
- [InstallOP 最新需求、實測與清理稽核](docs/INSTALLOP_AUDIT.md)
- [原始 JLL 安裝筆記](codex_command/README_OpenPilot_v0.9.1_Install_Replay.md)

## 目前完成範圍

2026-10-03 依教授 `InstallOP.docx` 稽核並修復：官方備份版 Replay 已與 UI
實際顯示道路；Taiwan dataC 也已用獨立編譯的 `replayJLL.compat` 在 VNC
看到夜間道路與車速。USA demo 的相容版也已進入 `playing`，並在核對
hostname 的新 VNC 連線看到白天道路、車道疊圖與車速 52 mph。
兩個容器重新啟動後都通過 Docker healthcheck。

教授提供的原版 `tools/replay/replayJLL` 沒有被覆蓋；其 msgq header
為 456 bytes，現有 UI 為 312 bytes。`replayJLL.compat` 由 tools092 的
SCons source 在隔離 volume 編出，供目前 UI 使用。不要混用這兩個 binary。

目前 `tools/replay/replay` 已被 tools092 附带 binary 覆蓋；本次確認可顯示的
官方編譯版保存在 `tools-official-backup-20261003/replay/replay`，請保留備份。
官方完整 build 的成功紀錄早於 tools092 overlay；相容版 JLL 的目標編譯
已成功，但**沒有**把這等同於 overlay 後全量 SCons build 或全新空 volume 重建。

教授對 `dataB6` 只有下載解壓要求：**InstallOP.docx does not require dataB6 replay**。
目前 `/data/dataB6` 的 129 files、2,977,906,784 bytes 全部與原 ZIP 的大小／CRC 相符。
`external/aJLL` 有 181 files，分類為 REFERENCE / ARCHIVE；根目錄重複副本已移出專案，Docker/build/runtime
沒有引用它，教授也沒有給出執行命令。Google Drive 遠端完整 manifest 尚未核對。
本階段不增加 ModelB6 training、simulation 或 dataB6 轉換。

## 日常使用

建議使用快捷工具，不必每次輸入完整的 Docker Compose 指令：

```bash
./scripts/openpilot.sh up
./scripts/openpilot.sh display
./scripts/openpilot.sh status
./scripts/openpilot.sh validate
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
容器重建後，請關閉過期的 VNC 視窗並重新連線；舊視窗可能保留上一個容器的最後影像。

點「開啟 OpenPilot」啟動官方 UI。拖曳標題列移動、拖曳邊框縮放；
按 UI 的 × 關閉後，會自動回到啟動器。沒有額外浮動退出按鈕。
啟動器自身的 × 會最小化，使用 Alt+Tab 或桌面中鍵視窗清單找回。

官方 UI 有固定大小元件，小視窗可能裁切；要完整閱讀，請最大化 UI，
再使用 VNC 的「縮放至視窗」。可拖曳大小不代表官方版面會等比例縮放。

## 第一次建立或搬到另一台機器

以下只建立官方基底環境，不會自動還原教授 tools092/dataC/dataB6。
現有 named volumes 內含手動整合的資產；目前尚未完成全新空 volume 的
端到端重現。六份教授原始下載檔保存在被 Git 忽略的
`external/installop-assets/`；請連同教授資料與已工作的官方備份保留，
勿直接覆蓋，也不要執行 `docker compose down -v`。
既有 tools092 volume 上執行全量 SCons 可能覆寫教授的 replayJLL，請勿
直接執行 `build-op`；重建相容版請用隔離流程 `build-jll-compat`。

```bash
docker compose -f docker/docker-compose.yaml config --quiet
docker compose -f docker/docker-compose.yaml build
docker compose -f docker/docker-compose.yaml up -d
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
docker compose -f docker/docker-compose.yaml exec -e TERM=xterm compute \
  tools-official-backup-20261003/replay/replay \
  --demo --qcam --no-hw-decoder --no-loop -c 1
```

同一指令可用 `./scripts/openpilot.sh replay-demo` 執行。

JLL 相容版：先在 VNC 桌面啟動 UI，再選一條路線；不要同時執行兩個 Replay。

```bash
docker compose -f docker/docker-compose.yaml exec -e TERM=xterm \
  -w /opt/openpilot/tools/replay compute \
  ./replayJLL.compat --demo --qcam --no-hw-decoder --no-loop -c 1

docker compose -f docker/docker-compose.yaml exec -e TERM=xterm \
  -w /opt/openpilot/tools/replay compute \
  ./replayJLL.compat --no-hw-decoder --data_dir dataC '8bfda98c9c9e4291|2020-05-11--03-00-57--61'
```

對應快捷命令是 `./scripts/openpilot.sh replay-jll-demo` 和
`./scripts/openpilot.sh replay-jll-datac`。Taiwan 已實測 `playing` 和 VNC 道路；
USA 已實測 `playing`，並在目前容器 VNC 確認道路畫面。plain `--demo` 曾在 120 秒
仍下載較大的檔案，不應直接判定為解碼卡死。

Ctrl+C 停止。`--qcam` 使用較小的影片，`-c 1` 限制快取 segment 數量。
demo 需要舊版程式指定的遠端 route 可取得。
若出現 `Error opening terminal: unknown`，在 `exec` 後加上 `-e TERM=xterm`。
qcam 與軟體解碼是此平台的播放設定；ABI 不一致是透過獨立編譯的
`replayJLL.compat` 解決。不要對 JLL 命令加 `-b uiDebug`：它會使舊資料中的
`pandaStateDEPRECATED` 被過濾，UI 收不到點火狀態而停在離線首頁。

本機資料可複製到持久化 /data（先把範例路徑換成實際資料位置）：

```bash
docker compose -f docker/docker-compose.yaml cp /absolute/path/to/dataC compute:/data/dataC
docker compose -f docker/docker-compose.yaml exec compute \
  tools-official-backup-20261003/replay/replay --no-hw-decoder --data_dir /data/dataC \
  "8bfda98c9c9e4291|2020-05-11--03-00-57--61"
```

也可以使用快捷命令：

```bash
./scripts/openpilot.sh replay-route /data/dataC \
  "8bfda98c9c9e4291|2020-05-11--03-00-57--61"
```

必須先取得並驗證 route 資料的實際目錄結構；上述指令不會自動下載 dataC。
JLL 資產來源、SHA256 與容器內位置見 [DOCX 資產紀錄](docs/INSTALLOP_ASSETS.md)。
教授 dataC 已在 `/opt/openpilot/tools/replay/dataC`，不需要再複製一份到 `/data`。
`dataB6` 按文件只保存，不建立 Replay pipeline；也不要把官方 `replay` 改名取代 JLL binary。

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

驗證腳本只檢查現有服務，不會自行 build 或關閉服務。它確認兩容器
`healthy`、dataB6 檔案數、dataC 必要檔案、兩版 JLL 雜湊及 VNC/noVNC 端口；
不等於完整逐檔資料校驗或影片畫面驗收。

若目前 volume 的相容版 JLL 遺失，可執行 `./scripts/openpilot.sh build-jll-compat`。
這會複製工作 source 到暫時 Docker volume，在副本中編譯，再把新 binary
安裝為 `replayJLL.compat`；不覆蓋教授原版。成功後自動移除暫時副本。

正常停止並保留資料：

```bash
docker compose -f docker/docker-compose.yaml down
```

不要加入 `-v`，除非確定要刪除原始碼、編譯產物與錄製資料 volumes。

## 目錄與持久化

```text
README.md                  使用說明
docs/IMPLEMENTATION.md     實作、修正與驗證紀錄
docs/INSTALLOP_ASSETS.md   InstallOP.docx 資產來源、hash 與驗證紀錄
codex_command/             使用者提供的原始指示
docker/                    Compose、Dockerfiles、entrypoints、啟動器、健康 socket
scripts/validate-docker.sh 非破壞性的執行環境檢查
scripts/build-jll-compatible.sh 隔離編譯 JLL 相容版
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
| SCons build | 官方基底有歷史成功紀錄；目前 tools092 overlay 的乾淨實際重建尚未驗證 |
| UI | 已完成，VNC/noVNC 可顯示 |
| 官方 replay | 官方備份版 demo qcamera 跨容器顯示成功 |
| tools092 / replayJLL | 原版保存；相容版 JLL 目標編譯成功。Taiwan 與 USA demo 均已在 VNC 顯示道路 |
| dataB6 | ZIP 與解壓 129 files 已驗證；教授沒有 Replay 要求 |
| aJLL | host external/aJLL 已保存，REFERENCE / ARCHIVE，無目前 runtime 依賴 |

目前官方 Replay、Taiwan JLL 與 USA JLL demo 均已顯示道路畫面。
Python 實際是 3.8.10，文件示範是 3.8.20；目前以 Docker 隔離取代 sconsvenv。
兩容器已有 healthcheck，且本次反覆冷啟動後都達到 `healthy`。
display 對 Xvfb 啟動加入就緒檢查和重試；最初一次失敗的根因仍未完整確定，
因此只能說目前冷啟動驗證通過，不能保證未來永不重啟。
清理分類與候選大小見最新稽核；本次未刪教授資料、images、volumes 或 cache。
驗證時曾重新建立本專案容器與 network，持久化資料保留。
