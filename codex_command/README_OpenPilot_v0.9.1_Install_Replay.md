# openpilot v0.9.1 Installation & Replay Guide

> 整理自 JLL 筆記（2020-08-11 ~ 2026-09-29）
>
> **用途**：這份 README 的目標不是把原始操作紀錄逐字保存，而是整理成之後可以快速閱讀、重現、除錯的流程。  
> 目標環境是 **openpilot v0.9.1 + Python 3.8 + Poetry 1.3.2 + SCons 4.4.0**，並執行 `replayJLL` / openpilot UI Replay。
>
> **重要**：原筆記包含不少針對舊版 openpilot 與較新 Ubuntu/系統函式庫的 workaround。它們不是標準 openpilot 安裝方式，不應一開始全部套用；應在遇到對應錯誤時才使用。

---

## 0. 最終要完成什麼？

整個工作可以拆成兩個主要階段：

```text
Ubuntu / Dual Boot
       │
       ▼
準備 Python 3.8 + Poetry 1.3.2
       │
       ▼
取得 openpilot v0.9.1
       │
       ▼
補入指定 tools / pyproject.toml / poetry.lock
       │
       ▼
建立 Python venv
       │
       ▼
安裝 Python / Ubuntu dependencies
       │
       ▼
用 SCons Build openpilot
       │
       ▼
Build 成功：scons: done building targets.
       │
       ├───────────────┐
       ▼               ▼
啟動 openpilot UI     執行 replayJLL
       │               │
       └───────┬───────┘
               ▼
         Replay 錄製資料
```

### 階段 A：Install OP

目的：

1. 固定舊版 openpilot 所需的 Python/Poetry/SCons 環境。
2. 下載 `openpilot v0.9.1`。
3. 補入 JLL 筆記所依賴的 `tools`、設定檔及其他檔案。
4. 解決編譯 dependency。
5. 成功 Build openpilot。

### 階段 B：Replay

目的：

1. 啟動 openpilot UI。
2. 使用 `replayJLL` 播放 demo 或錄製資料。
3. 確認 UI 可以正常顯示 replay 結果。

---

# 1. 開始前先確認

## 1.1 平台

原筆記特別要求使用 **Windows 電腦上的 Dual Boot Ubuntu**。

筆記也記錄：

```text
ubuntu 24.04 is unsupported.
This setup script is written for Ubuntu 20.04.
```

因此這份流程本質上是：

- 舊版 openpilot v0.9.1
- 舊版 Python 3.8
- 原本偏向 Ubuntu 20.04 的 dependency
- 在較新的 Ubuntu 上可能需要大量相容性修正

---

## 1.2 不要照抄 `jinn`

原筆記中的：

```bash
jinn@Liu:~$
```

只是作者的 terminal prompt。

你的 username 不一定是 `jinn`。

查看自己的 username：

```bash
whoami
```

查看 HOME：

```bash
echo $HOME
```

因此原本：

```text
/home/jinn/openpilot
```

應理解成：

```text
$HOME/openpilot
```

例如 username 是 `abc`：

```text
/home/abc/openpilot
```

本 README 優先使用 `$HOME`，避免之後換電腦或帳號時出錯。

---

# 2. 版本需求

開始前最重要的是確認版本。

## Poetry

```bash
poetry --version
```

預期：

```text
Poetry (version 1.3.2)
```

## Python

進入 `sconsvenv` 後：

```bash
python --version
```

預期：

```text
Python 3.8.x
```

原筆記成功環境為：

```text
Python 3.8.20
```

## SCons

```bash
scons --version
```

預期：

```text
SCons: v4.4.0
```

---

# 3. 安裝流程總覽

建議照以下順序處理：

```text
Step 1  安裝 Python 3.8
Step 2  安裝 Poetry 1.3.2
Step 3  Clone openpilot v0.9.1
Step 4  初始化 submodules
Step 5  放入指定 tools / 設定檔
Step 6  建立 sconsvenv
Step 7  安裝 Python dependencies
Step 8  第一次 SCons build
Step 9  依錯誤補 Linux dependencies
Step 10 修正少數 source / SConstruct 相容性問題
Step 11 Build 到 done
Step 12 設定 PYTHONPATH
Step 13 啟動 UI
Step 14 執行 replayJLL
```

---

# 4. Step 1 — 準備 Python 3.8

先確認：

```bash
python --version
```

如果不是 Python 3.8，原筆記使用：

```bash
sudo apt install python3.8
sudo apt install python3.8-venv
```

編輯：

```bash
gedit ~/.bashrc
```

加入：

```bash
alias python=python3.8
```

關閉 terminal，再重新開啟。

再次確認：

```bash
python --version
```

> 注意：全域 alias `python=python3.8` 可能影響其他專案。較乾淨的方式通常是只在 virtual environment 中固定 Python 版本，但本 README 保留原流程的行為。

---

# 5. Step 2 — 安裝 Poetry 1.3.2

先裝 curl：

```bash
sudo apt install curl -y
```

使用 Python 3.8 安裝指定 Poetry：

```bash
curl -sSL https://install.python-poetry.org | python3.8 - --version 1.3.2
```

編輯：

```bash
gedit ~/.bashrc
```

加入：

```bash
export PATH=$PATH:$HOME/.local/bin
```

重開 terminal。

確認：

```bash
poetry --version
```

應看到：

```text
Poetry (version 1.3.2)
```

---

# 6. Step 3 — 下載 openpilot v0.9.1

安裝 Git：

```bash
sudo apt install git
```

Clone 指定版本：

```bash
cd ~
git clone -b v0.9.1 https://github.com/commaai/openpilot
```

原筆記特別提醒 clone 應完整結束，例如：

```text
Resolving deltas: 100% (...), done.
```

進入 repo：

```bash
cd ~/openpilot
```

初始化 submodules：

```bash
git submodule update --init
```

---

# 7. Step 4 — 替換 / 補入 JLL 使用的 tools

這一步不是單純官方 openpilot v0.9.1 clone。

原流程會刪掉 repo 內的 `tools`：

```bash
cd ~/openpilot
rm -rf tools
```

接著將：

```text
tools092.zip
```

解壓到：

```text
$HOME/openpilot
```

完成後應存在類似：

```text
openpilot/
└── tools/
    ├── cabana
    ├── replay
    ├── ubuntu_setup.sh
    └── ...
```

而 Replay 所需的 Taiwan data 原筆記放在：

```text
openpilot/tools/replay/dataC
```

> **關鍵點**：這表示目前環境其實是「openpilot v0.9.1 + 指定 tools 版本/修改」，並非完全原生 v0.9.1。之後若發生 API、SCons 或 binary mismatch，要優先檢查這個版本混用問題。

---

# 8. Step 5 — 建立 Python virtual environment

建立：

```bash
python -m venv ~/sconsvenv
```

啟用：

```bash
source ~/sconsvenv/bin/activate
```

或原筆記寫法：

```bash
. ~/sconsvenv/bin/activate
```

成功後 terminal 前方會出現：

```text
(sconsvenv)
```

確認 Python：

```bash
python --version
```

應為：

```text
Python 3.8.x
```

---

# 9. Step 6 — Poetry / project 設定

進入：

```bash
cd ~/openpilot
```

執行：

```bash
poetry shell
```

## 如果出現

```text
Poetry could not find a pyproject.toml file
```

表示 repo 目前缺少：

```text
pyproject.toml
```

原流程要求把指定的 `pyproject.toml` 放入：

```text
$HOME/openpilot/pyproject.toml
```

另外使用 JLL 提供的：

```text
poetry.lock
```

取代目前版本。

再執行：

```bash
poetry shell
```

如果仍有 lock 問題：

```bash
poetry lock
```

接著：

```bash
pip install --upgrade pip
```

如果有 `update_requirements.sh`：

```bash
chmod +rwx update_requirements.sh
```

若不存在，原筆記要求另外取得並放到：

```text
$HOME/openpilot/update_requirements.sh
```

---

# 10. Step 7 — 安裝 SCons

每次新的 terminal 先啟用環境：

```bash
source ~/sconsvenv/bin/activate
```

安裝：

```bash
pip install scons==4.4.0
```

確認：

```bash
scons --version
```

應為：

```text
SCons: v4.4.0
```

---

# 11. Step 8 — 第一次 Build

進入 repo：

```bash
cd ~/openpilot
```

先執行：

```bash
scons -i
```

原筆記的策略是：

> 第一次 build 的 errors 先用來找缺少哪些 dependencies，再逐步補齊。

接著安裝 Python packages：

```bash
pip3 install casadi
pip3 install libusb1
pip3 install cython
pip3 install "pycapnp < 1.1"
pip3 install numpy
pip3 install pycryptodome
pip3 install hatanaka
pip3 install pycurl
pip3 install atomicwrites
pip3 install sympy
pip3 install cffi
pip3 install zmq
```

正式重新 build：

```bash
scons -u -j$(nproc)
```

其中：

```bash
-j$(nproc)
```

代表依 CPU core 數量平行編譯。

---

# 12. Step 9 — Build Error 對照表

原筆記的主要方法是：

```text
執行 scons
    ↓
看第一個真正的 compiler / linker error
    ↓
補 package 或修 source
    ↓
重新執行 scons -u -j$(nproc)
    ↓
重複直到 done
```

## 12.1 laika path error

錯誤：

```text
TypeError: File .../openpilot/laika found where directory expected.
```

`SConstruct` Line 67 原本：

```python
default=os.path.islink(Dir('#laika/').abspath),
```

改成：

```python
default=os.path.islink(Dir('#laika_repo/laika').abspath),
```

再 build：

```bash
scons -u -j$(nproc)
```

---

## 12.2 qmake 不存在

錯誤：

```text
FileNotFoundError: No such file or directory: 'qmake'
```

安裝：

```bash
sudo apt install qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools
```

---

## 12.3 clang++ 不存在

錯誤：

```text
sh: 1: clang++: not found
```

安裝：

```bash
sudo apt install clang
```

---

## 12.4 zmq.h 不存在

錯誤：

```text
fatal error: 'zmq.h' file not found
```

安裝：

```bash
sudo apt-get install libzmq3-dev
```

---

## 12.5 Cap'n Proto headers 不存在

錯誤：

```text
fatal error: 'capnp/serialize.h' file not found
```

安裝：

```bash
sudo apt-get install libcapnp-dev capnproto
```

---

## 12.6 Eigen 不存在

錯誤：

```text
fatal error: 'eigen3/Eigen/Dense' file not found
```

安裝：

```bash
sudo apt install libeigen3-dev
```

---

## 12.7 Cap'n Proto generated code / library version mismatch

錯誤：

```text
Version mismatch between generated code and library headers.
You must use the same version of the Cap'n Proto compiler and library.
```

原筆記先 clean cereal：

```bash
cd ~/openpilot/cereal
scons -c
```

再回 repo：

```bash
cd ~/openpilot
scons -u -j$(nproc)
```

> 如果仍然 mismatch，不應直接假設 clean 一定能解決；需要確認 `capnp --version`、系統 library 與 generated files 的版本是否一致。

---

## 12.8 Python.h 不存在

```text
fatal error: 'Python.h' file not found
```

安裝：

```bash
sudo apt install python3.8-dev
```

---

## 12.9 OpenCL header 不存在

```text
fatal error: 'CL/cl.h' file not found
```

安裝：

```bash
sudo apt-get install opencl-headers
```

---

## 12.10 FFmpeg headers 不存在

```text
fatal error: 'libavcodec/avcodec.h' file not found
```

安裝：

```bash
sudo apt-get install libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
```

---

## 12.11 bzlib.h 不存在

```text
fatal error: 'bzlib.h' file not found
```

安裝：

```bash
sudo apt-get install libbz2-dev
```

---

## 12.12 replay util.cc 的 va_start error

錯誤：

```text
tools/replay/util.cc:30:3: error: use of undeclared identifier 'va_start'
```

編輯：

```bash
gedit ~/openpilot/tools/replay/util.cc
```

加入：

```cpp
#include <cstdarg>
```

再 build。

---

## 12.13 libvisionipc.a 不存在

錯誤：

```text
Implicit dependency `cereal/libvisionipc.a' not found
```

原筆記處理方式：

```text
Download libvisionipc.a to /openpilot/cereal
```

> **注意**：直接下載預編譯 `.a` library 可能產生 ABI / compiler / dependency mismatch。最好記錄這個 `libvisionipc.a` 的來源、編譯環境及對應 commit。若之後出現奇怪 linker/runtime 問題，這是重要檢查點。

---

## 12.14 curl linker error

```text
cannot find -lcurl
```

安裝：

```bash
sudo apt install libcurl4-openssl-dev
```

---

## 12.15 Qt Multimedia

```text
cannot find -lQt5Multimedia
```

安裝：

```bash
sudo apt install qtmultimedia5-dev
```

---

## 12.16 Qt Quick

```text
cannot find -lQt5Quick
```

安裝：

```bash
sudo apt install qtdeclarative5-dev
```

---

## 12.17 Qt Location

```text
cannot find -lQt5Location
```

安裝：

```bash
sudo apt install qtlocation5-dev
```

---

## 12.18 Qt Positioning

```text
cannot find -lQt5Positioning
```

安裝：

```bash
sudo apt install qtpositioning5-dev
```

---

## 12.19 OpenCL linker error

```text
cannot find -lOpenCL
```

安裝：

```bash
sudo apt install ocl-icd-opencl-dev
```

---

# 13. 特殊 workaround：停用部分 SCons targets

這些修改的目的不是「修好」對應模組，而是 **略過它們，讓目前 Replay 需要的部分可以先 build 完成**。

因此之後若需要完整 openpilot 功能，必須重新檢查。

## visionipc tests error

如果：

```text
scons: *** [cereal/visionipc/visionipc_tests.o] Error 1
```

原筆記將 `SConstruct` Line 357：

```python
SConscript(['cereal/SConscript'])
```

改為註解：

```python
#SConscript(['cereal/SConscript'])
```

---

## proclogd tests error

如果：

```text
scons: *** [system/proclogd/tests/test_proclog.o] Error 1
```

原筆記將 `SConstruct` Line 400：

```python
'system/proclogd/SConscript'
```

改成：

```python
#'system/proclogd/SConscript'
```

---

# 14. Build 成功判斷

每次修改後：

```bash
cd ~/openpilot
scons -u -j$(nproc)
```

最後必須看到：

```text
scons: done building targets.
```

這才算原筆記定義的 Build 完成。

---

# 15. Step 10 — 設定 PYTHONPATH

編輯：

```bash
gedit ~/.bashrc
```

加入：

```bash
export PYTHONPATH=$HOME/openpilot
```

重新開 terminal，或：

```bash
source ~/.bashrc
```

到這裡原筆記視為：

```text
OP Done
```

---

# 16. Ubuntu setup script：什麼時候用？

原筆記 Appendix 還有：

```bash
cd ~/openpilot
tools/ubuntu_setup.sh
```

但在 Ubuntu 24.04 會提示：

```text
ubuntu 24.04 is unsupported.
This setup script is written for Ubuntu 20.04.
Would you like to attempt installation anyway?
```

原紀錄選：

```text
n
```

Ubuntu 20.04 的情況下，如果最後看到：

```text
---- OPENPILOT SETUP DONE ----
```

代表 script 完成。

可能還會看到：

```text
cat: .python-version: No such file or directory
```

原筆記認為此訊息可接受。

如果權限有問題：

```bash
sudo chown -R $USER:$USER ~/openpilot/
```

---

# 17. 階段 B — Replay

Replay 需要兩個 terminal。

每個 terminal 開始前都建議：

```bash
source ~/sconsvenv/bin/activate
```

---

# 18. Terminal 1 — 啟動 openpilot UI

```bash
cd ~/openpilot
./selfdrive/ui/ui
```

正常情況下 UI 應啟動。

---

# 19. UI 舊 binary 的 shared-library 問題

原本第一次執行曾出現：

```text
./_ui: error while loading shared libraries: libcapnp-0.7.0.so
```

系統實際只有：

```text
libcapnp-1.0.1.so
```

原紀錄曾嘗試用 symlink：

```bash
sudo ln -s /usr/lib/x86_64-linux-gnu/libcapnp-1.0.1.so \
  /usr/lib/x86_64-linux-gnu/libcapnp-0.7.0.so
```

也對 `libkj` 做類似操作。

之後甚至嘗試：

```bash
sudo ln -s /usr/lib/x86_64-linux-gnu/libcrypto.so.3 \
  /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1
```

結果：

```text
version `OPENSSL_1_1_0' not found
```

## 不建議把這當正式解法

不同 major/minor ABI 的 library **不能因檔名相似就視為相容**。

例如：

```text
libcrypto.so.3
```

不能靠改名/symlink 就真正變成：

```text
libcrypto.so.1.1
```

這也是為什麼會出現 symbol/version error。

### 原筆記最後成功的方法

安裝 GLES dependency：

```bash
sudo apt install libgles2-mesa-dev
```

然後重新 build UI：

```bash
cd ~/openpilot

sed "s@#SConscript(\['selfdrive/ui/SConscript'\])@SConscript(['selfdrive/ui/SConscript'])@" \
SConstruct | /home/$USER/sconsvenv/bin/scons --site-dir=site_scons -f - selfdrive/ui/_ui
```

再執行：

```bash
./selfdrive/ui/ui
```

核心概念是：

> **不要硬跑舊 binary；改成用目前系統 library 重新 build UI。**

這比假裝舊 library 名稱存在可靠。

---

# 20. Terminal 2 — Replay demo

另開 terminal：

```bash
source ~/sconsvenv/bin/activate
cd ~/openpilot/tools/replay
```

執行：

```bash
./replayJLL --demo
```

這是原筆記的 USA demo / Wi-Fi replay。

---

# 21. Replay Taiwan dataC

Terminal 1：

```bash
source ~/sconsvenv/bin/activate
cd ~/openpilot
./selfdrive/ui/ui
```

Terminal 2：

```bash
source ~/sconsvenv/bin/activate
cd ~/openpilot/tools/replay
```

執行：

```bash
./replayJLL --data_dir dataC "8bfda98c9c9e4291|2020-05-11--03-00-57--61"
```

其中：

```text
dataC
```

是 local replay data directory。

而：

```text
8bfda98c9c9e4291|2020-05-11--03-00-57--61
```

是這次 Replay 使用的 route / segment identifier。

---

# 22. 其他資料

原筆記另外要求：

```text
dataB6
```

下載並解壓至：

```text
$HOME/dataB6
```

以及：

```text
aJLL
```

放到：

```text
$HOME/openpilot
```

目前原始筆記沒有完整說明兩者在後續哪個 command 被使用。

因此未來若要繼續整理，應補充：

- `dataB6` 是什麼資料？
- `aJLL` 是 executable、script、library 還是其他檔案？
- 來源 URL / 版本？
- 對應哪個 replay command？

---

# 23. 每次重新開機後最常用的指令

不需要重新安裝。

## Terminal 1：UI

```bash
source ~/sconsvenv/bin/activate
cd ~/openpilot
./selfdrive/ui/ui
```

## Terminal 2：Replay demo

```bash
source ~/sconsvenv/bin/activate
cd ~/openpilot/tools/replay
./replayJLL --demo
```

## Terminal 2：Replay dataC

```bash
source ~/sconsvenv/bin/activate
cd ~/openpilot/tools/replay
./replayJLL --data_dir dataC "8bfda98c9c9e4291|2020-05-11--03-00-57--61"
```

---

# 24. 如果之後壞掉，先檢查這些

不要一開始就重新安裝全部。

依序執行：

```bash
whoami
python --version
poetry --version

source ~/sconsvenv/bin/activate

python --version
pip --version
scons --version

cd ~/openpilot
git status
git branch --show-current
git submodule status
```

另外建議：

```bash
capnp --version
qmake -v
clang++ --version
```

如果是 runtime library error：

```bash
ldd ~/openpilot/selfdrive/ui/_ui | grep "not found"
```

這可以直接找出 UI 缺少哪些 `.so`。

---

# 25. Debugging 原則

之後把錯誤交給 ChatGPT / Copilot 時，最好提供：

```text
1. Ubuntu version
2. openpilot commit / tag
3. Python version
4. Poetry version
5. SCons version
6. 執行的完整 command
7. 第一個真正的 error
8. error 前後約 30~50 行
9. 最近改過哪些 SConstruct / source files
10. 是否使用 JLL 提供的 tools / poetry.lock / binary files
```

Ubuntu version：

```bash
lsb_release -a
```

openpilot commit：

```bash
cd ~/openpilot
git rev-parse HEAD
git describe --tags --always
```

---

# 26. 目前這套環境最重要的特殊點

這不是單純：

```text
git clone openpilot v0.9.1 → build
```

而比較接近：

```text
openpilot v0.9.1
+ 指定 tools092
+ dataC
+ 指定 pyproject.toml
+ 指定 poetry.lock
+ update_requirements.sh
+ Python 3.8
+ Poetry 1.3.2
+ SCons 4.4.0
+ 多個 Ubuntu development packages
+ SConstruct modifications
+ replay util.cc modification
+ 可能的預編譯 libvisionipc.a
+ replayJLL
```

因此之後 Debug 時，**版本混用與自訂修改**應列為第一級檢查項目。

---

# 27. 建議保存的外部檔案清單

為了未來能真正重建環境，最好把以下檔案和 README 放在同一個備份資料夾：

```text
OP091_backup/
├── README_OpenPilot_v0.9.1_Replay.md
├── tools092.zip
├── pyproject.toml
├── poetry.lock
├── update_requirements.sh
├── libvisionipc.a              # 若真的需要
├── replayJLL                   # 或其 source
├── aJLL
├── dataC/
└── source_info.txt
```

`source_info.txt` 建議記：

```text
Ubuntu version:
openpilot tag:
openpilot commit:
tools092 source:
pyproject.toml source:
poetry.lock source:
replayJLL source/version:
libvisionipc.a source:
dataC source:
dataB6 source:
aJLL source:
last known working date:
```

---

# 28. 一頁版 Checklist

## Install

- [ ] 使用適合的 Ubuntu 環境
- [ ] Python 3.8.x
- [ ] Poetry 1.3.2
- [ ] Clone openpilot v0.9.1
- [ ] `git submodule update --init`
- [ ] 放入指定 `tools`
- [ ] 建立 `~/sconsvenv`
- [ ] SCons 4.4.0
- [ ] 放入指定 `pyproject.toml`
- [ ] 放入指定 `poetry.lock`
- [ ] 安裝 Python dependencies
- [ ] 安裝缺少的 Ubuntu development packages
- [ ] 必要時套用 source / SConstruct workaround
- [ ] `scons -u -j$(nproc)`
- [ ] 看到 `scons: done building targets.`
- [ ] 設定 `PYTHONPATH=$HOME/openpilot`

## Replay

- [ ] Terminal 1 啟用 `sconsvenv`
- [ ] `./selfdrive/ui/ui`
- [ ] Terminal 2 啟用 `sconsvenv`
- [ ] `cd ~/openpilot/tools/replay`
- [ ] `./replayJLL --demo`
- [ ] 或執行 `dataC` replay
- [ ] UI 正常顯示 replay

---

# 29. 給未來 ChatGPT / Copilot 的上下文

如果未來要繼續處理這個專案，可以直接提供這份 README，並說：

> 我正在重建一個舊版 openpilot v0.9.1 Replay 環境。這不是完全官方原版，而是依 JLL 筆記混合了 tools092、replayJLL、自訂 poetry 設定與數個 SConstruct workaround。請先閱讀 README，確認我目前進行到哪一步，再針對我貼出的「第一個真正 error」除錯。不要直接叫我重裝全部，也不要假設新版 openpilot 的安裝方式適用於 v0.9.1。

這樣後續除錯時，比直接重新貼整份原始筆記容易判斷問題。
