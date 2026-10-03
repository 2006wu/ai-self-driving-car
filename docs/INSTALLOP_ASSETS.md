# InstallOP.docx 資產紀錄

本文件記錄 `/Users/2006wu/Downloads/InstallOP.docx` 內解析出的來源，以及
2026-10-03 在 Docker compute volume 中的驗證結果。二進位檔與 replay 資料
不提交 Git；它們保存在 Docker volumes。

## 來源對照

| 資產 | DOCX 來源 | SHA256（下載檔） | 容器內結果 |
| --- | --- | --- | --- |
| `tools092.zip` | [Google Drive](https://drive.google.com/file/d/1Gd3kd7XP11nZhrnxWBaWcgmaD7Awm1C4/view?usp=drive_link) | `0c99c7bfa7b1b780565728ad90cb2ecc32f8b2d70414aa62826d4251d0a8a4f4` | 已解壓至 `/opt/openpilot/tools` |
| `pyproject.toml` | [Google Drive](https://drive.google.com/file/d/1T41BOQRpZyYgjxgqCSsvll59DnCBnnVd/view?usp=sharing) | `dd260f119f59c637437fb1989ee425ab287a61789dc2c3bfe17ca5d463e37428` | 已放入 `/opt/openpilot` |
| `poetry.lock` | [Google Drive](https://drive.google.com/file/d/1zRPrcaMd2Mqoo8ZQT8Ef7gLDs__hoJBh/view?usp=drive_link) | `9b7eea4d27b7d94d45d3255e2e175a768c1224ac7d3d27d1ac212da0c625793b` | 已放入 `/opt/openpilot` |
| `update_requirements.sh` | [Google Drive](https://drive.google.com/file/d/1G2j7X_7Ynaz0pQv404ARmNN_eLyX_SFe/view?usp=sharing) | `c5cecb98317b0be0405517f3616a5fef5d57f7816060c37c892f57a0e962194e` | 已放入 `/opt/openpilot` 並設為可執行 |
| `libvisionipc.a` | [Google Drive](https://drive.google.com/file/d/12zvkGjHCHo-MkbkTUFhuS7e9w2nElzbN/view?usp=drive_link) | `8b02d860205f82969dd8bca25b8447e0a34aeded7ef0290c934bdac969f9940b` | 另存為 `cereal/libvisionipc.a.jll-source-20261003` |
| `dataB6` | [Google Drive](https://drive.google.com/file/d/1qq9InMsFZ2C_V8SsJo9b-aerkas6kybT/view?usp=sharing) | `36e216588fdaa2605c3e5ca9c1e04450aae5d76c55deea6e600548de1be68870` | 已解壓至 `/data/dataB6` |
| `aJLL` | [Google Drive folder](https://drive.google.com/drive/folders/1mbReInJ_96rpToDLkC3xPOlqceFWxA9u) | 未取得可下載的直接檔案 | 待確認 |

## 驗證結果

- `tools092.zip` 可正常解壓，包含 `replayJLL`、`replayJLL230316` 與 `dataC`。
- JLL dataC route `8bfda98c9c9e4291|2020-05-11--03-00-57--61` 已載入 1 個有效
  segment 並進入 `playing`。
- `dataB6` 已通過 `unzip -t`，解壓後 129 個檔案、約 2.8 GB；其 route 目錄是
  `UHD--2018-08-02--08-34-47--32/33/37`，與 JLL 的 `route|segment` 結構不同。
- `libvisionipc.a` 的 DOCX 版本與現有編譯版本 hash 不同，所以保留兩者，避免
  未驗證的 library 破壞既有官方 UI/replay。
- `aJLL` 連結目前只能識別為 Google Drive folder，沒有將未知內容猜成 executable
  或 library。

