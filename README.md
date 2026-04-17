# SC Mining Overlay

Star Citizen 採礦 / 製作查詢系統浮動視窗。  
此專案提供一個以 **Tkinter** 製作的桌面浮動視窗，用來快速查詢：

- 礦物與寶石對應的星系 / 行星 / 衛星 / 礦帶
- 各地點的採集方式、風險、熱門程度、建議路線
- 圖紙 / 材料 / 關聯地點
- 中英對照名稱與常見地點資訊

本系統以 **外部 JSON 資料檔** 為核心，不把資料硬編進程式，方便你後續持續更新資料集、補點位、修正翻譯與擴充功能。

---

## 1. 系統定位

這套系統的主體不是地圖，而是 **資料驅動的查詢浮動視窗**。

你可以把它理解成：

- 一個可拖曳、可收合、可置頂的查詢 HUD
- 一個以 JSON 為主資料源的採礦 / 製作知識庫前端
- 一個適合在遊戲旁邊開著查點位、查礦物、查圖紙的輔助工具

---

## 2. 目前功能

### 2.1 查詢與聯想
上方輸入框會根據關鍵字自動聯想：

- 最近查詢
- 礦物
- 圖紙
- 地點

輸入後，系統會優先引導你先選擇正確的目標，再顯示關聯資訊，避免同名或模糊查詢造成誤判。

### 2.2 左側關聯區域
選定礦物後，左側會列出：

- 關聯星體
- 關聯地點
- 關聯圖紙或材料結果

### 2.3 右側詳細資訊
右側會顯示目前選中目標的詳細內容，例如：

- 星系 / 母星 / 類型
- 高品質礦潛力
- 是否需要洞穴
- 採集方式
- 熱點程度
- 可達性
- 快速路線
- 建議出發站
- 常見點位
- 地表 / 洞穴 / 小行星資源概況
- 製作圖紙或材料摘要

### 2.4 風險條
右側上方有風險橫條，會綜合以下因素顯示：

- 時段（尖峰 / 離峰）
- 熱點程度
- 可達性

這不是 PvP 即時偵測，而是 **根據資料與時間邏輯的提示**。

### 2.5 浮動視窗控制
工具欄可快速調整：

- `縮`：收合 / 展開
- `置`：切換是否置頂
- `透- / 透+`：調整透明度
- `字- / 字+`：調整文字大小
- `窗- / 窗+`：調整整體視窗大小
- `關`：關閉程式

### 2.6 拖曳與記憶
系統會記住：

- 主視窗位置
- 視窗尺寸
- 透明度
- 字體縮放
- 是否置頂
- 是否收合
- 最近查詢

設定會寫入 `config/overlay_settings.json`。

---

## 3. 專案結構

目前專案結構如下：

```text
sc_mining_overlay_latest/
├─ app.py
├─ README.md
├─ README_PACKAGING.txt
├─ build_exe_hidden_ico.bat
├─ version_info.txt
├─ requirements_build.txt
├─ requirements_runtime.txt
├─ config/
│  └─ overlay_settings.json
├─ core/
│  ├─ data_store.py
│  └─ search.py
├─ data/
│  ├─ sc_mining_dataset_latest.json
│  ├─ sccrafter_index.json
│  ├─ coverage_report_v8.md
│  └─ progress_note_for_future_runs.md
├─ logs/
│  └─ overlay.log
└─ assets/
   ├─ sc_mining_overlay.ico
   └─ sc_mining_overlay_256.png
```

---

## 4. 核心模組說明

### 4.1 `app.py`
主程式入口，負責：

- 建立主視窗與工具欄視窗
- 查詢流程控制
- 左右面板顯示
- 使用者操作（拖曳、收合、縮放、透明度）
- 套用外部設定
- 顯示風險條與詳細內容

### 4.2 `core/data_store.py`
資料讀取與轉換層，負責：

- 讀取主資料 JSON
- 建立 body / resource / blueprint 索引
- 中英對照處理
- 已知文字的雙語化
- 礦物、圖紙、地點等資料的格式整理
- 提供詳細文字內容給 UI 顯示

### 4.3 `core/search.py`
搜尋與聯想層，負責：

- 建立搜尋索引
- 根據查詢輸出建議項目
- 模糊搜尋 body / resource
- 找出礦物關聯星體

---

## 5. 資料檔說明

### 5.1 `data/sc_mining_dataset_latest.json`
主資料檔。  
包含：

- 系統（Stanton / Pyro / Nyx）
- 星體
- 採礦資訊
- 地點
- 風險與熱點判定
- 資源主表
- 部分圖紙 / 製作相關資料

### 5.2 `data/sccrafter_index.json`
補充圖紙與材料資料索引，提供：

- item / blueprint
- materials
- mission translation
- 製作相關對照資料

### 5.3 `config/overlay_settings.json`
使用者設定檔，會記住：

- 視窗大小與位置
- 透明度
- 字體大小
- 是否置頂
- 是否收合
- 最近查詢

### 5.4 `logs/overlay.log`
執行記錄檔。  
當程式啟動失敗或 UI 例外時，會寫入這裡。

---

## 6. 啟動方式

### 6.1 原始碼執行
在專案根目錄執行：

```bash
python app.py
```

### 6.2 安全模式
如果你想暫時停用無框視窗，可用：

```bash
python app.py --safe
```

安全模式下會保留較正常的視窗行為，方便除錯。

---

## 7. 執行需求

### 7.1 Python
建議：

- Python 3.10 以上
- 你目前的打包流程已實測使用 Python 3.13

### 7.2 必要條件
本專案主要依賴 Python 內建模組：

- `tkinter`
- `json`
- `logging`
- `pathlib`
- `sys`

因此最重要的是：**你的 Python 必須有 tkinter**。

### 7.3 打包需求
打包 EXE 時會使用：

- `setuptools<82`
- `wheel`
- `pyinstaller>=6.12,<7`

---

## 8. EXE 打包

專案內已提供：

```text
build_exe_hidden_ico.bat
```

用途：

- 打包成 EXE
- 自動帶入 ICO
- 使用 `--windowed` 隱藏 DOS 視窗
- 保持 `data / config / logs / assets` 外部讀取

### 8.1 打包方式
直接在專案根目錄雙擊：

```text
build_exe_hidden_ico.bat
```

### 8.2 預設輸出位置
```text
dist/SC_Mining_Overlay/
```

### 8.3 打包後的外部資料
EXE 模式下，程式會從 **EXE 同層** 讀取：

- `data/`
- `config/`
- `logs/`
- `assets/`

這樣你之後只要替換外部 JSON，就能更新資料，不需要重新編譯 EXE。

---

## 9. 路徑設計原則

本專案已調整為：

- **原始碼模式**：從專案目錄讀取資料
- **EXE 模式**：從 EXE 所在目錄讀取資料

也就是說，無論你用原始碼還是打包後版本，都不需要把 JSON 打進程式內部。

這對你目前的工作流很重要，因為你目前重點是：

- 主程式已經可用
- 後續主要是持續補資料
- 因此資料檔必須外部化，方便持續更新

---

## 10. 使用流程建議

建議實際操作流程：

1. 啟動程式
2. 在上方輸入礦物、圖紙或地點
3. 從聯想列選擇正確項目
4. 左側看關聯區域
5. 右側看詳細資訊與路線建議
6. 若要縮小干擾，可用右側工具欄調整透明度 / 字體 / 視窗大小 / 收合

---

## 11. 已知限制

### 11.1 資料完整度取決於 JSON
目前 UI 主邏輯已可用，但查詢結果的完整度取決於：

- `sc_mining_dataset_latest.json`
- `sccrafter_index.json`

如果資料尚未補齊，UI 不會自動推測不存在的點位。

### 11.2 很多礦點仍需繼續補資料
尤其是：

- 基礎地表礦
- 部分 Pyro / Nyx 點位
- 更細的 outpost / cave / mining area 關聯
- 部分 ship mining 與 generic asteroid type 的對應位置細化

### 11.3 風險條不是即時 PvP 監控
目前風險條是根據：

- 時段
- 熱點程度
- 可達性

去做靜態 / 半動態判斷，不是連線到遊戲伺服器的即時資料。

---

## 12. 後續擴充方向

這套系統後面很適合繼續往下補：

- 更完整的地表採礦點位
- 前哨 / 處理站 / 洞穴索引
- 礦物與地點的更細雙向關聯
- 更完整的圖紙取得方式
- 多資料檔切換
- 匯入更新版 JSON 的管理功能
- 更進一步的 EXE 發佈版流程

---

## 13. 開源與維護原則

目前這套系統是以 **公開原始碼** 為前提設計的：

- 主程式可直接閱讀與修改
- JSON 外部放置
- 打包後仍保留外部資料可更新
- 不把資料硬塞進 EXE

這種做法很適合你現在的維護方式，因為你之後主要工作不是重寫主程式，而是持續補資料與修正內容。

---

## 14. 快速檢查清單

如果你要確認系統正常，先檢查以下幾項：

- `app.py` 是否存在
- `data/sc_mining_dataset_latest.json` 是否存在
- `data/sccrafter_index.json` 是否存在
- `config/overlay_settings.json` 是否存在
- `assets/sc_mining_overlay.ico` 是否存在
- Python 是否含有 `tkinter`
- 打包時是否使用 `build_exe_hidden_ico.bat`

---

## 15. 錯誤排查

### 啟動失敗
先看：

```text
logs/overlay.log
```

### 打包失敗：`pkg_resources` 找不到
請確認使用：

- `setuptools<82`

### 打包後 EXE 能開但讀不到資料
請確認 EXE 同層有：

- `data/`
- `config/`
- `logs/`
- `assets/`

### 視窗不正常 / 無框難操作
請用：

```bash
python app.py --safe
```

---

## 16. 版本說明

這份 README 對應的是目前整理後的專案版本，重點是：

- 主系統邏輯可用
- 外部資料讀取可用
- EXE 打包流程已補齊
- 後續重心放在資料補充，而不是重寫 UI 主體

---

## 17. 最後說明

這個專案目前最重要的狀態不是「功能還沒成形」，而是：

**主邏輯已經可用，後續主要是補資料。**

所以這份 README 的核心目標是讓你自己或之後接手的人，能快速理解：

- 這系統現在能做什麼
- 哪些檔案是核心
- JSON 怎麼讀
- EXE 怎麼打包
- 後續要往哪裡補

---
****
