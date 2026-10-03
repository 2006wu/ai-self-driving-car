# InstallOP 需求與現況稽核

日期：2026-10-03。主要需求依據為使用者提供的
`/Users/2006wu/Downloads/InstallOP.docx`，SHA256：
`126a4c685b8e6d8d9de5a10bb7b8bec83f77e0bfd010ce11d28c14e3e4e95613`。
本次重新讀取全部正文、附錄、超連結關係及兩張內嵌截圖；下文以章節與原文命令定位，沒有推測 Word 頁碼。

## 結論

教授要求安裝及 build openpilot v0.9.1、顯示 UI、使用 replayJLL 播放 USA demo 和 Taiwan dataC，以及下載保存 dataB6、aJLL。文件沒有要求 ModelB6 training、simulation 或 dataB6 replay。

**InstallOP.docx does not require dataB6 replay**。

首次稽核時，官方備份版 Replay 已在 UI 顯示道路，而教授原版 JLL 與 UI
的 msgq header 不相容。後續已隔離編譯相容版，Taiwan 畫面驗證通過；
USA 後續也已在新 VNC 視窗完成畫面驗收。最新狀態見第 11 節。

首次稽核沒有清理教授資料、重建 image、重裝 openpilot、改動 dataB6/dataC、修改教授原版 replayJLL binary 或執行 aJLL。只移除了根目錄的重複副本；原副本可從 `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003` 恢復。後續為驗證啟動與排查暫存 IPC，曾以 `compose down`（沒有 `-v`）及 `up -d --no-build` 重新建立本專案容器與 network，全部 named volumes 保留。

## 1. 依教授文件順序還原需求

| 順序／原文位置 | 對應文字或命令 | 需求與判定 |
| --- | --- | --- |
| 標題 | `(A) Install openpilot v0.9.1 (on Dual Boot with Copilot)`、`(B) Do Replay` | 安裝/build 與 Replay 是主流程。原教學為雙開機環境；macOS Docker 是本專案的移植方式。 |
| Notice | `Read Notes 1~3 in Q&A`、兩份 Report1、`VSCode Copilot chat_log` | 指定閱讀的安裝/debug 參考資料；不是需常駐執行的服務。本次只以 InstallOP 本文還原需求，未冒稱讀完外連資料。 |
| Notice | `replace “jinn” ... with your username` | `/home/jinn` 是教授範例路徑，可做明確 Docker 路徑映射。 |
| Notice／A | `Poetry (version 1.3.2)`、`Python 3.8.20` | 文件提醒檢查版本；不能把 3.8.10 說成精確符合 3.8.20。 |
| A install poetry | `sudo apt install python3.8`、`python3.8-venv`、`curl ... \| python3.8 - --version 1.3.2` | 安裝 Python 3.8 與 Poetry 1.3.2。`alias python=python3.8`、修改 PATH 是主機 shell 設定。 |
| A download OP091 | `git clone -b v0.9.1 https://github.com/commaai/openpilot`、`sudo git submodule update --init` | 固定 v0.9.1 並取得 submodules，要求下載完整。 |
| A replace tools | `download “tools” from tools092.zip (also get /tools/replay/dataC)` | 替換 tools，取得 JLL source/binaries 及 dataC。原文 `rm -rf tools` 是其安裝操作，不是本次清理授權。 |
| A environment | `python -m venv ~/sconsvenv`、`. ~/sconsvenv/bin/activate`、`poetry shell` | 原教學使用 venv。Docker 內目前直接安裝套件，是實作差異。 |
| A 3a–3c | `download pyproject.toml`、`replace yours with my ... poetry.lock`、`poetry lock`、`chmod +rwx update_requirements.sh` | 保存教授設定；找不到檔案時下載。文件要求設 executable，沒有直接要求執行 update_requirements.sh。 |
| A build OP | `pip install scons==4.4.0`、`scons -i`、`scons -u -j$(nproc)` | 使用 SCons build；`scons -i` 是前期排錯，不是最後成功證據。 |
| A packages | `pip3 install casadi` 等逐項命令 | Python build/runtime 套件：casadi、libusb1、cython、pycapnp < 1.1、numpy、pycryptodome、hatanaka、pycurl、atomicwrites、sympy、cffi、zmq。 |
| A conditional errors | `if Error` 後列 Qt、clang、zmq.h、capnp、Eigen、Python.h、OpenCL、FFmpeg、bz2、curl 等 | 解決實際缺失的 build dependencies；並非每台機器都需再執行所有 workaround。 |
| A source fixes | laika 路徑、`#include <cstdarg>`、`Download libvisionipc.a`、註解 cereal/proclogd SConscript | 都有錯誤條件。只在對應失敗發生時評估，不能無條件套到已工作的 source。 |
| A acceptance | `scons: done building targets.`、`Finally, you must see “done”` | 要求實際 build 成功；dry-run 出現同一句不等於真正編譯成功。 |
| A end | `export PYTHONPATH=/home/jinn/openpilot` | Python module 路徑設定；目前映射為 `/opt/openpilot`。`Go to Step (C)` 在所提供文件沒有對應 C 章，不自行補出新實驗。 |
| B Terminal 1 | `./selfdrive/ui/ui` | UI 必須可執行／顯示。 |
| B NG first try | libcapnp、libkj、libcrypto symlink；接著 `OPENSSL_1_1_0 not found` | 失敗的嘗試紀錄，尤其不能把不同 OpenSSL 主版本 symlink 視為必需配置。 |
| B OK second try | `sudo apt install libgles2-mesa-dev`，SCons 指定 `selfdrive/ui/_ui`，再 `./selfdrive/ui/ui` | 重新編譯 UI 的成功 workaround。需要的是能運行的 UI 與相符函式庫。 |
| B USA | `Terminal 2 (run USA data via WiFi)`、`./replayJLL --demo`、`--- OK` | 明確要求 JLL USA demo。內嵌 image2.png 顯示道路、56 mph、車道，以及 `STATUS: playing`。 |
| B Taiwan | `run Taiwan data in /replay/dataC`、`./replayJLL --data_dir dataC "8bfda98c9c9e4291\|2020-05-11--03-00-57--61"` | dataC 是明確指定的本機 Taiwan Replay 輸入。另一張圖 image1.png 顯示夜間道路及 18 mph。 |
| B end dataB6 | `Download and unzip dataB6 to /home/jinn/dataB6` | 下載並解壓保存；沒有 replay、轉格式、training 或顯示命令。 |
| B end aJLL | `Download aJLL to /home/jinn/openpilot` | 要求取得教授資料；沒有 aJLL 執行命令，也沒有說明 runtime 用途。REFERENCE / ARCHIVE 是本次依實作依賴查核得到的分類。 |
| Appendix | `tools/ubuntu_setup.sh`、Ubuntu 24.04 unsupported、`OPENPILOT SETUP DONE`、失敗時重做／chown | Ubuntu 20.04 setup 補充與故障排除，不是另一組 Replay 或 ModelB6 實驗要求。 |

Docker、display container、VNC/noVNC、桌面啟動器、official replay 對照測試是使用者先前要求或本專案的實作選擇，並非教授文件另行指定的軟體架構。

## 2. 首次稽核快照：Requirement 與實際 implementation

本表保留首次稽核當時的容器、檔案與程序輸出，供追溯當時的
msgq ABI 失敗；**不是修復後的最終狀態**。相容版及最新 USA/Taiwan 畫面
驗收結果見第 10、11 節。

| Requirement | Current implementation | Status | Evidence |
| --- | --- | --- | --- |
| openpilot v0.9.1 | `/opt/openpilot` 固定 tag commit | PASS 基底版本；tools 已客製 | `git rev-parse HEAD` = `d891d3df476cdaca52dc350bcfdaaa137bbc3840`；8 個 submodules 均無未初始化標記 |
| Python environment | Ubuntu Python 3.8.10、系統 site-packages，無教授 sconsvenv | 平台差異／非精確版本一致 | `python3.8 --version`；`pip check` = `No broken requirements found.`。不等於全部功能 import 測試 |
| Poetry | 1.3.2，教授 pyproject/lock 已存在 | 版本 PASS；未證實依 lock 完整安裝 | `poetry --version`；Dockerfile 用 pip 安裝套件，沒有完整 `poetry install` 流程 |
| SCons | 4.4.0 | PASS | `scons --version`、`pip show SCons` |
| tools092 | 解壓覆蓋 tools，原官方 tools 留備份 | 資產 PASS；引入 ABI 問題 | host ZIP `unzip -t` 通過；binary SHA256 與解壓原檔相同 |
| openpilot build | 有 UI、官方備份 Replay、libraries、object files | 歷史已 build；現況全量 rebuild 未驗證 | 本次 `scons -n -u -j2` exit 0，列出重編 JLL/UI 等命令；這是 dry-run，不可當 fresh build PASS |
| selfdrive UI | display 執行現有 `_ui` | 官方 Replay 顯示 PASS；JLL FAIL | VNC 觀察到道路、63 mph、車道；JLL 時 exit 134、msgq assertion |
| display container | Xvfb/Openbox/launcher/x11vnc/websockify | 基本功能 PASS | 程序存在、動態庫無 `not found`；啟動器中文字出現方框，字型是獨立的小型顯示缺口 |
| compute / display healthy | 容器 running；自訂健康 socket 回傳 ok | 功能探測 PASS；冷啟動穩定性有缺口 | inspect `Healthcheck=null`；最後 compute RestartCount=0、display=1，詳見驗證節 |
| VNC/noVNC | 5910→5900，6080；127.0.0.1 限定 | VNC 畫面 PASS；noVNC HTTP/WebSocket PASS | VNC `RFB 003.008`；HTTP 200；WebSocket 101，收到 RFB frame。未完成瀏覽器端登入畫面驗證 |
| official replay | 真正官方編譯版在 `tools-official-backup-20261003/replay/replay` | PASS 片段及畫面 | banner 0.9.1、USA route、實際 VNC 道路。當前 `tools/replay/replay` 是 tools092 附帶 binary，不能當同一個產物 |
| replayJLL | tools092 預編譯 x86_64 ELF | 可執行；UI ABI FAIL | 11,862,704 bytes；SConscript 的確有 `qt_env.Program("replayJLL", ["mainJLL.cc"], ...)`，但現用檔案 hash 與 archive 相同，不是此次 source build |
| replayJLL USA demo | qcam/no-hw-decoder/no-loop/cache1 | playing PASS；畫面 FAIL | 本次進入 playing，但 UI msgq assertion；plain demo 的結果見驗證節 |
| Taiwan dataC replay | 教授原命令、segment 61 | playing PASS；畫面 FAIL | `1 valid segments`、`TOYOTA PRIUS 2017`、速度約 11.56 m/s；UI 同樣 exit 134 |
| dataB6 | replay-data volume 的 `/data/dataB6` | 本地完整性 PASS | 129 files、2,977,906,784 bytes；逐檔 size/CRC 與原 ZIP 一致；ZIP CRC 全通過 |
| aJLL | host `external/aJLL`；原根目錄副本已移至暫存備份 | 本地保存 PASS；遠端完整性 UNKNOWN | 181 files，約 75 MiB；移除前 `diff -qr` 無差異；本次沒有 Google Drive 完整 manifest 可驗證遠端是否還有其他檔案 |

## 3. JLL 顯示失敗的直接證據

本次沒有把 `playing` 與「看見畫面」混為一談。

| 產物 | SHA256 | msgq header |
| --- | --- | --- |
| 現有 `selfdrive/ui/_ui` | `ced469c4b8c7724ddf966dd3f175fc6c29c1f6d3cb822d9471a001d4420806dc` | 312 bytes (`0x138`) |
| `tools/replay/replayJLL` | `a1ef5396de9817df8fc8a4deeb87cd384899009b9e2260fd8a36e46962cda5f1` | 456 bytes (`0x1c8`) |
| `tools/replay/replay`，tools092 附帶 | `4df868ad28e304b2bf4616438c460b83118c9d64d9b4dcdf723be4e5cd846fad` | 本次未反組譯此檔；不可假設與官方備份相同 |
| 官方備份 `tools-official-backup-20261003/replay/replay` | `ea342d6d6f37a6d1d1bd8b8b813733c8aa94d3e623aebf07599de1b5a9fe9afe` | 與目前 UI 實測可互通 |

`objdump -d --demangle --disassemble='msgq_new_queue(msgq_queue_t*, char const*, unsigned long)'`：

```text
replayJLL: 472b40 lea 0x1c8(%rax),%rbx  → ftruncate
           472dcb add $0x1c8,%r12       → data 起點
_ui:       4c7bb0 lea 0x138(%rax),%rbx  → ftruncate
           4c7d7e add $0x138,%r12       → data 起點
```

原 source `cereal/messaging/msgq.cc` 第 103/108/129 行用
`size + sizeof(msgq_header_t)` 配置檔案與 mmap，並以 header 大小設定 data 起點。
JLL 執行時 `/dev/shm/modelV2` 大小為 10,486,216；官方備份執行時為 10,486,072。
二者差 144 bytes，與 header 差相符。讀寫方因此對訊息資料起點有不同解讀。

本次首先遇到的實際 UI error：

```text
_ui: cereal/messaging/msgq.cc:386:
int msgq_msg_recv(msgq_msg_t *, msgq_queue_t *): Assertion `size > 0' failed.
```

也出現第 385 行 `Assertion '(uint64_t)size < q->size' failed`。UI exit 134。
重啟兩容器後仍可重現；官方備份播放時 UI 正常，換 Taiwan JLL 後 UI 立即 assertion。
這已足以確認這組 producer/consumer 的 msgq ABI 不一致，不能以網路下載或缺 aJLL 解釋 UI 崩潰。

建議後續在獨立 build 位置，用與現有 UI 相同的 cereal/msgq source 重建 JLL，保留教授原 binary 及 hash，先驗證兩個 route 再選擇切換。不要原地執行全量 SCons 覆蓋 working binary，也不要更改 dataB6。這是下一步建議，本次未實作。

## 4. aJLL 依賴查核

本地頂層內容：

```text
external/aJLL/
├── Agent/
├── Body/
├── Coding/
├── Control/
├── ModelB6/
├── UI/
├── bodyjim/
└── tools/
```

| 查核項目 | 實際證據 | 判定 |
| --- | --- | --- |
| Dockerfile | COPY 僅專案 docker entrypoint、launcher、socket helper；沒有 aJLL COPY/RUN | 無依賴 |
| Compose | inspect 與 YAML 只有 openpilot-repo、replay-data、op-socket、op-runtime | 未 mount aJLL |
| scripts | 搜尋 `external/aJLL`／`aJLL` 沒有命中執行引用 | 無依賴 |
| openpilot runtime | 容器未掛 host workspace，沒有 aJLL 資料目錄或指向它的 symlink；UI/官方 Replay 可運行 | 本次 runtime 不依賴本地 external/aJLL |
| replayJLL | ELF ldd 無遺失庫；RUNPATH 指向教授 `/home/jinn/openpilot/{third_party,cereal,common}`，沒有 aJLL；在 aJLL 不可見時仍 playing | 不依賴 external/aJLL；目前失敗是 msgq ABI |
| dataC | source/data 在 tools/replay；無 aJLL mount 仍載入 segment 61 並 playing | 無 aJLL 依賴 |
| official replay | 官方備份版在 aJLL 不可見時實際顯示畫面 | 無 aJLL 依賴 |
| build | 現有 SConstruct/site_scons/replay/UI 引用搜尋及 SCons dry-run 未見 aJLL | 現有 build graph 未引用 external/aJLL |

因此分類為 **REFERENCE / ARCHIVE**。這個結論限定目前 InstallOP 流程，不否定教授其他實驗可能使用其中內容；文件沒有要求在這階段執行它。host 暫存保存與教授 `/home/jinn/openpilot` 原字面位置不同，已明確記錄，不把位置差异隱藏成完全照做。

## 5. dataB6 與 dataC 保存狀態

dataB6 的 Docker 映射為 `/home/jinn/dataB6` → compute `/data/dataB6`，存放在
`ai-self-driving-car_replay-data` volume，非 host 專案資料夾。原 ZIP 仍在 compute `/tmp/dataB6.zip` 及 host `external/installop-assets/dataB6.download`，兩者 SHA256：
`36e216588fdaa2605c3e5ca9c1e04450aae5d76c55deea6e600548de1be68870`。

```text
/data/dataB6/
├── UHD--2018-08-02--08-34-47--32/
├── UHD--2018-08-02--08-34-47--33/
└── UHD--2018-08-02--08-34-47--37/
```

129 個原 ZIP 檔案均存在、size/CRC 一致，解壓檔案總數也為 129；ZIP `testzip()` 無錯。
這證明與目前保存的原 archive 一致，並非逐個 HDF5/影片內容語意驗證。沒有修改或轉換任何資料。

dataC 實際完整目錄：

```text
/opt/openpilot/tools/replay/dataC/
├── 8bfda98c9c9e4291|2020-05-11--03-00-57/
│   └── 61/
│       ├── rlog.bz2       6,178,480 bytes
│       └── fcamera.hevc  37,603,914 bytes
└── 62/
    ├── rlog.bz2           6,178,480 bytes
    └── fcamera.hevc      37,603,914 bytes
```

兩組檔案分別 hash 相同，但 `62/` 是教授 archive 內容，不能直接當垃圾刪除。
rlog SHA256 `f08f5fa0fa72b6259ad9c0b4e63d4e9603c121eb9d7abb3b9fa32c442dcdabf4`；
camera SHA256 `fc0315d752ed74f1318fd92a174953e687b746ebe3b8ee10a1ff5308e7008600`。
rlog 可完整解壓成 24,108,608 bytes；Replay 可解析且播放 segment 61。dataC 保存在 openpilot-repo volume。

## 6. 保留分類與清理候選

所有項目本次均未刪除。大小為本次快照，MiB/磁碟配置及 bytes 口徑可能不同，不將重疊項目相加。

| 分類 | 項目 | 理由 |
| --- | --- | --- |
| KEEP | 兩個現有 image/container、Compose、Dockerfiles、scripts、launcher、runtime libraries | 已有可工作官方 UI/Replay 基礎 |
| KEEP | openpilot-repo、replay-data、op-socket、op-runtime volumes；共享 IPC/PID | source、資料、socket、VisionIPC；不可整個清除 `/tmp` |
| KEEP | `_ui`、replayJLL、tools092 必要 source、cereal/libvisionipc.a、其他必要 libraries | 程式及 build 依賴；不要改名冒充另一 binary |
| KEEP | `/opt/openpilot/tools-official-backup-20261003`，225,730,844 bytes | 保存本次已實測可顯示的官方 Replay；目前不是多餘備份 |
| KEEP | 現有 build artifacts 與 `.sconsign.dblite` | 未完成乾淨重建驗證前保留；`.o` 259 個共 573,286,168 bytes，`.a` 共 202,370,780 bytes，含可能 runtime/build 必需物，不能一概刪除 |
| REFERENCE / ARCHIVE | external/aJLL，181 files，約 75 MiB | 教授要求保存，現有 runtime 不需使用；根目錄副本已移出專案 |
| REFERENCE / ARCHIVE | InstallOP.docx、原始指示與教授 pyproject/lock/update_requirements、另存 supplied libvisionipc | 需求及重現依據 |
| REFERENCE / ARCHIVE | host tools092.zip，158,460,737 bytes | ZIP CRC 與已記錄 SHA256 通過；保留原 source/binary/dataC 來源 |
| DATA | `/data/dataB6`，2,977,906,784 bytes | 已驗證；教授只要求下載解壓 |
| DATA | `/opt/openpilot/tools/replay/dataC`，约 84 MiB | 教授指定 Taiwan route；包括原始重複檔案 |
| KEEP（暫留） | demo download cache，145,994,572 bytes | 正在診斷且可避免重新下載；影響首次 Replay 等候时间 |
| UNKNOWN | 全新 empty-volume 重建結果、aJLL 遠端完整 manifest、舊版 replayJLL230316 的後續用途 | 證據不足；保留 |
| UNKNOWN／本專案範圍外 | navigation2、ros2-vnc 的停止容器／images、其他 Docker volumes | 是其他專案；本次不處理 |

下面只是 **REMOVE CANDIDATE**，須先確認精確範圍與備份，再執行清理。

| 候選 | size | 為什麼不需常駐／可否再生 | 對 build | 對 UI | 對 replayJLL | 對 dataC |
| --- | --- | --- | --- | --- | --- | --- |
| Docker build cache | Docker 回報 17.12 GB、162 entries | 可重新 build；是全機共用數值，需另篩本專案與 unused 範圍；不等於可回收實體磁碟精確值 | 冷 build 更慢／需網路 | 不影響已建 image | 不影響現存 binary | 不影響資料 |
| host 根 `aJLL/` 重複副本 | 約 75 MiB | 已確認與 external/aJLL `diff -qr` 相同，已移至 `/private/tmp/ai-self-driving-car-aJLL-duplicate-20261003`；可直接移回恢復 | 無影響 | 無影響 | 無影響 | 無影響 |
| host 暫存 `extracted/` | 約 379 MiB | tools092.zip 已保留且 CRC 通過；可重新解壓。未來可能需從此比對 source，先記錄 | 現有 build 不讀 host 暫存 | 無影響 | 現有檔在 volume | 原資料已在 ZIP/volume |
| compute `/tmp/dataB6.zip` 重複 archive | 356,218,452 bytes | host 原 archive 相同 SHA256；確認至少一份持久化封存後可去重。不能把整個 /tmp 刪掉 | 無影響 | 無影響 | 非 replay 輸入 | 無影響 |
| `/tmp/replayJLL-demo-observe/` | 10,610,138 bytes（含目錄） | 舊調查 cache；同名內容在正常 cache 也存在，可重下載 | 無影響 | 無影響 | 正常 cache 未清時無影響 | 無影響 |
| 舊調查 replay log、help、畫面 | log 快照 18 個合計 262,467 bytes；兩 PNG 488,471 bytes | 摘要／驗證證據保存後可去除舊調查檔；活躍 x11vnc/launcher log 不列批次刪除 | 無影響 | 不刪 socket/密碼/active log 即無影響 | 失去歷史排錯證據 | 不影響資料 |
| `/tmp/libvisionipc-supplied.a` | 1,006,620 bytes | 與 `cereal/libvisionipc.a.jll-source-20261003` SHA256 相同；可去除一份暫存。保留 source/archive | 不刪現用 library 即無影響 | 無影響 | 無影響 | 無影響 |
| host `aJLL-folder.html`、`aJLL.download` | 634,940 bytes、0 bytes | 舊下載頁與空失敗產物，非 aJLL 本體；頁面可重新取得 | 無影響 | 無影響 | 無影響 | 無影響 |
| host `docker/__pycache__/` | 8 KiB 磁碟配置 | Python 可再生，Dockerfile 未 COPY | 無影響 | 無影響 | 無影響 | 無影響 |
| 本次 `/tmp/installop-audit.T2Cedq/` | 約 3.5 MiB | DOCX 兩張附圖的解壓副本，原 DOCX 保留可再生 | 無影響 | 無影響 | 無影響 | 無影響 |

一般 demo cache 可在不用離線 demo、網路來源仍可用時清除，但目前列 KEEP 暫留。六份原始下載檔後續已移到 host `external/installop-assets/` 並通過 SHA256 核對；不能因 ZIP 另存就把工作中的 volumes 當作可隨意刪除。

## 7. 最終系統架構與重現缺口

```text
macOS ARM64 / Docker Desktop
  ├─ compute  (linux/amd64 Ubuntu 20.04)
  │    /opt/openpilot  ← openpilot-repo [rw]
  │    /data/dataB6    ← replay-data
  │    replay / replayJLL → msgq shared memory + VisionIPC
  └─ display  (linux/amd64 Ubuntu 20.04)
       /opt/openpilot ← 同一 volume [ro]
       共享 compute IPC/PID、/tmp sockets
       official UI → Xvfb :99 → x11vnc → localhost:5910
                                 └─ websockify/noVNC → localhost:6080

host external/aJLL → 參考封存，未 mount 至 runtime
自訂 /run/openpilot/replay.sock → 健康 JSON；不是影片資料流
```

可用現有 volumes 不等於從零可重現。Dockerfile 會 clone 官方 v0.9.1，但没有自動安裝 tools092/dataC/dataB6 或保留教授檔案的完整 bootstrap；部分 Python 套件未鎖定，Poetry lock 也未作為 image 安裝來源。既有 volume 會遮住新 image 的 source。

下一步應限於這些缺口：保留教授資產與 hashes 的持久化封存、可重現 bootstrap、隔離重建與驗證 JLL ABI、可觀測健康狀態。沒有 ModelB6 容器或 training 的需求。

## 8. 首次稽核時的驗證與驗收界線

| 驗證 | 結果 |
| --- | --- |
| Compose config 與 `up -d --no-build` | config PASS；最後冷啟動 display 曾失敗並自動重啟一次，之後兩服務正常 |
| compute 健康 socket | PASS `ok: true` |
| display 依賴／程序 | PASS Xvfb/Openbox/launcher 與 UI 動態庫解析 |
| Docker healthy | 未配置，不能宣稱 PASS healthy |
| VNC | PASS RFB 握手、桌面、官方道路畫面實際可見 |
| noVNC | PASS HTTP 200、WebSocket 101 與 RFB frame；瀏覽器端完整登入尚未完成 |
| UI＋官方備份 Replay | PASS 片段顯示；非整條 11 segments 全量驗收 |
| JLL demo workaround | playing PASS，UI FAIL msgq ABI |
| plain `./replayJLL --demo` | 120 秒 timeout exit 124，仍 loading；顯示下載 71.53 MB，進度持續至約 53%，沒有 playing |
| Taiwan 原命令 | 1 valid segment、playing PASS，UI FAIL msgq ABI |
| dataB6 | PASS archive CRC 與全部 129 files 比對 |
| tools092 archive | PASS unzip CRC；當前 replay/replayJLL hash 與原檔相同 |
| source build | dry-run PASS；未跑會覆寫 binary 的實際 rebuild |

最後冷啟動的 display 日誌先出現
`/usr/local/bin/display-entrypoint: line 27: kill: (20) - No such process`，
第 27 行檢查的是 Xvfb PID，表示該次 Xvfb 提前結束；再由 `restart: unless-stopped` 恢復。當前 RestartCount 為 compute 0、display 1。
這是額外的啟動穩定性缺口，不能宣稱完全無自動退出；日誌會在重啟時覆寫子程序 log，
故第一次子程序退出的完整 stderr 尚未保存，根因未確定。
最後 UI 在乾淨 IPC 中成功啟動，之後測試 session exit 0，另有 QPixmap null pixmap 警告；
結束時確認僅剩啟動器與兩服務，無背景 Replay，健康 JSON、HTTP 200 與 VNC RFB 握手再次通過。
教授 replayJLL 與 UI hash 均未變，dataB6 仍為 129 files。

保留以下 USA 平台參數。首次稽核時僅確認能進入 playing；後續隔離
編譯相容版後，已在目前容器的 VNC 視窗完成畫面驗收（第 11 節）：

```bash
./replayJLL --demo --qcam --no-hw-decoder --no-loop -c 1
```

qcam/軟體解碼/限制快取是 macOS ARM64 上執行 amd64 Linux 的實用播放設定，但不能修復上述 header ABI。本次 plain demo 顯示正在下載 71.53 MB 檔案，120 秒時進度約 53%，所以此次觀察窗口內未完成下載是直接證據；沒有證據可把它直接斷言為 full fcamera 解碼卡死。下載完成後 plain 模式是否有其他問題尚未驗證。

## 9. 最簡單的日常使用

在專案根目錄執行：

```bash
./scripts/openpilot.sh up
./scripts/openpilot.sh display
./scripts/openpilot.sh validate
```

VNC `vnc://127.0.0.1:5910`，或 `http://localhost:6080/vnc.html`，密碼 `0000`。
點啟動器的「開啟 OpenPilot」。一次只啟動一個 Replay，停止目前 Replay 後才換資料。

本次已確認可與現有 UI 顯示的官方版本：

```bash
docker compose -f docker/docker-compose.yaml exec -e TERM=xterm compute \
  tools-official-backup-20261003/replay/replay \
  --demo --qcam --no-hw-decoder --no-loop -c 1
```

JLL 相容版日常入口（教授原版 binary 保留不變）：

```bash
docker compose -f docker/docker-compose.yaml exec -e TERM=xterm \
  -w /opt/openpilot/tools/replay compute \
  ./replayJLL.compat --demo --qcam --no-hw-decoder --no-loop -c 1

docker compose -f docker/docker-compose.yaml exec -e TERM=xterm \
  -w /opt/openpilot/tools/replay compute \
  ./replayJLL.compat --no-hw-decoder --data_dir dataC '8bfda98c9c9e4291|2020-05-11--03-00-57--61'
```

`q` 或 Ctrl+C 停止 Replay，UI 的 × 關閉畫面。正常停機使用
`./scripts/openpilot.sh down`，保留 volumes，不加入 `-v`。
快捷命令 `replay-demo` 已指向官方備份，`replay-jll-demo` 已加入 qcam
workaround，`replay-jll-datac` 使用相容版。USA 新連線畫面後續已通過，見第 11 節。

## 10. 真正尚未完成的 checklist

- [x] v0.9.1 基底 source/submodules、Poetry 1.3.2、SCons 4.4.0 可用。
- [x] tools092/source/dataC、dataB6、aJLL 已有本地保存。
- [x] dataB6 完整性核對，沒有增加 replay 要求。
- [x] 兩容器目前運行，基本服務探測通過。
- [x] display 加入 Xvfb 就緒檢查與重試，數次冷啟動後均 healthy；最初失敗原因仍未完全確定。
- [x] 官方備份 Replay 與 UI 的道路畫面本次已看到。
- [x] JLL Taiwan `playing`＋VNC 道路畫面（相容版）；教授原版未覆蓋。
- [x] JLL USA 相容版 `playing`，新容器 VNC 道路畫面已目視驗收。
- [ ] 現有 tools092 overlay 的全量 clean build 與新 volume 重現。
- [ ] Python 3.8.10／3.8.20、Docker／sconsvenv 的差異需保留在驗收說明。
- [x] noVNC 瀏覽器以既有密碼登入曾成功，兩容器 Docker healthcheck 已配置；每次容器重建後應重新連線。
- [ ] aJLL 遠端完整 manifest 核對；六份原始下載檔已移到 host 專案的 `external/installop-assets/`。
- [x] 根目錄重複 aJLL 已移出專案；保留 external/aJLL，原副本仍可恢復。
- [ ] 其他清理候選得到使用者確認後，才做精確清理。

dataB6 replay、aJLL 執行、ModelB6 training/simulation 不在這份文件的未完成清單中。

## 11. 後續修復與階段驗證（更新於 2026-10-03）

上方第 1–8 節保留首次稽核當時的證據與限制；以下是之後的最新狀態。

1. display 的 Xvfb 改為等待 X11 socket 就緒，失敗時留下 log 並重試；
   compute/display 新增 Docker healthcheck，display 等 compute healthy 才啟動。
   本次反覆以 `compose down`（不加 `-v`）和 `up -d --no-build` 冷啟動，
   兩者均達 `healthy`。最初某次 Xvfb 提前退出的根因仍未完整確認。
2. 把工作中的 `/opt/openpilot` 唯讀複製至隔離 Docker volume，執行
   `scons -u -j2 tools/replay/replayJLL`，得到 exit 0 與
   `scons: done building targets.`。獨立安裝為 `tools/replay/replayJLL.compat`。
   後來 `scripts/build-jll-compatible.sh` 已實際重跑同樣流程並通過，
   成功後清除它自己建立的暫時 volume。
3. 教授原版 `replayJLL` SHA256 仍為
   `a1ef5396de9817df8fc8a4deeb87cd384899009b9e2260fd8a36e46962cda5f1`；
   相容版為
   `40fbd0add9ffdf12f77006744992bb90b83235359a43ac2254284732afd92b8a`。
   原版沒有被覆蓋，dataB6/dataC 沒有修改。
4. Taiwan dataC 用相容版執行後進入 `STATUS: playing`，並在當時連接的
   VNC 視窗目視確認夜間道路、機車、車速 26 mph。UI 沒有因 msgq assertion
   立即退出。這是 Taiwan 路線的端到端片段驗證。
5. 曾嘗試加入 `-b uiDebug` 降低 publisher 衝突，但它會觸發服務白名單
   載入，意外過濾舊 rlog 的 `pandaStateDEPRECATED`。證據是同一次播放中
   `deviceState.started=True`，但 `pandaStates` 訂閱 12 秒收不到訊息，UI
   停在 `NO PANDA` 離線頁。拿掉 `-b` 後，`pandaStates` 訂閱即收到
   `ignitionLine=True`，UI 切到道路畫面。日常命令不能加這個參數。
6. USA demo 的相容版加 `--qcam --no-hw-decoder --no-loop -c 1` 後，
   11 valid segments，終端進入 `playing`。由於 macOS 螢幕共享仍顯示前一個
   容器的過期 Taiwan 畫面，**尚無可採信的新 VNC 視窗 USA 畫面證據**；
   不能宣稱 USA 視覺驗收已通過。plain `--demo` 的下載／解碼行為也尚未
   再次完整驗收，保留已驗證能進入 playing 的 workaround。
7. `scripts/openpilot.sh` 的官方/JLL 快捷命令已分別指向官方備份及相容版，
   `scripts/validate-docker.sh` 已實際通過健康狀態、dataB6 129 files、
   dataC 必要檔、兩版雜湊、VNC/noVNC 端口檢查。這不是完整影片或資料
   CRC 驗收；早先完整 dataB6 ZIP CRC 核對證據仍見第 5 節。
8. 只清理了本次診斷建立、沒有容器掛載的
   `ai-self-driving-car-jll-build-20261003` 隔離編譯 volume（約 2.2 GB）；
   可用重建腳本重新產生。清理後 compute/display 仍 healthy，兩版 JLL
   hash 與 dataB6 129 files 不變。工作中的 source/data volumes 均未刪除。

仍未完成：全新空 volumes 從教授
archives 的自動還原、tools092 overlay 的全量 clean build、aJLL 遠端完整
manifest 核對與經使用者確認的精確清理。這些不影響目前 Taiwan 與官方
片段可用，但不能寫成全系統 100% 完成。

### 2026-10-03 後續啟動與原始檔保存核對

- 六份教授原始下載檔已保存於 host `external/installop-assets/`，搬移後
  SHA256 與 [資產紀錄](INSTALLOP_ASSETS.md) 一致；這不是新的 runtime mount。
- 後續檢查發現兩個容器曾退出：compute exit 137、display exit 143。
  Docker `OOMKilled=false`，停止前最後的 healthcheck 均為 exit 0；
  沒有足夠證據把退出歸因於記憶體不足或程式崩潰。
- 使用既有 images 執行 `docker compose up -d --no-build`，compute 與
  display 再次達 healthy；`scripts/validate-docker.sh` 通過資料、socket、
  5910 VNC 與 6080 noVNC 的檢查。
- 重新連線的 macOS 螢幕共享視窗標題為 `357c93456a28:99`，與當時
  `docker compose exec display hostname` 的 `357c93456a28` 完全一致。
  在此容器啟動官方 UI 後，`replayJLL.compat --demo --qcam
  --no-hw-decoder --no-loop -c 1` 載入 11 valid segments，進入
  `STATUS: playing`；同一 VNC 視窗實際看到白天道路、多輛車、車道疊圖
  與 52 mph。USA demo 的本平台 workaround 已完成畫面驗收。
  畫面提示 `Gear not D / openpilot Unavailable` 是資料中當下車況，
  不代表影像播放失敗；plain `--demo` 的完整下載／播放仍未驗證。
