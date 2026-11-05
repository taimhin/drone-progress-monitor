# 🏗️ 無人機地盤進度監控 PoC（HTML 版）

把原本的 Streamlit + OpenCV 示範（`app.py`）改寫成**純前端靜態網站**。不需要 Python 伺服器、不需要安裝套件，直接把資料夾放上 GitHub Pages 就能展示。

- 影像只在瀏覽器內用 Canvas 取樣分析，**不會上傳到任何伺服器**。
- 內建 99 張 `Day01–Day33 × AM / Noon / Night` 範例照片。
- 分析結果已與 Python 版逐張比對，Planned %、Actual %、顏色判定與延誤判定一致。

## ✨ 功能

| 功能 | 說明 |
| --- | --- |
| 📁 自動監控資料夾 | 播放 `JPG_99/` 內 99 張照片，可調速度、暫停、重置、拉桿跳轉 |
| 📤 手動上傳 | 上傳 JPG / PNG / WebP，自動從檔名解析 `Day` 與 `AM / Noon / Night`，也可手動校正 |
| 📹 網路攝影機 | 即時拍照分析（需 `https://` 或 `localhost`） |
| 🎯 容許偏差 | 1%–20% 可調，超過閾值即觸發延誤警報 |
| 🖼️ 2×2 區域分析 | A / B / C / D 四個地塊獨立計算 HSV 色彩覆蓋率 |
| 📊 進度卡片 | 預期工序、目標進度、實際進度、進度條與 Δ 值 |
| 🚨 延誤總覽 | 列出所有落後地塊與落後工序 |
| ⌨️ 快捷鍵 | `←` / `→` 切換照片、`Space` 播放 / 暫停 |

## 🚀 本機開啟

> ⚠️ 不要直接雙擊 `index.html`。`file://` 會讓瀏覽器禁止 Canvas 讀取圖片像素，分析會失敗。

在專案資料夾執行：

```bash
cd Drone_Demo
python -m http.server 8000
```

再開啟 <http://localhost:8000/>。也可以用 `?photo=99` 直接跳到指定的第 99 張照片。

## 🧠 分析邏輯

1. 影像依畫面中心切成 2×2 四個地塊：A 左上、B 右上、C 左下、D 右下。
2. 每個地塊換算 HSV，統計以下顏色覆蓋率：

   | 顏色 | 工序 | OpenCV HSV 範圍 |
   | --- | --- | --- |
   | 黃色 | 立金屬架 | H 20–35, S ≥ 100, V ≥ 100 |
   | 橙色 | 釘板 | H 10–19, S ≥ 120, V ≥ 120 |
   | 紅色 | 紮鐵 | H 0–9 或 170–180, S ≥ 100, V ≥ 100 |
   | 白色 | 落水泥 | S 0–45, V ≥ 180 |
   | 藍色 | 水泥養護 | H 95–135, S ≥ 100, V ≥ 100 |

3. 依 15 天工序週期（立架 1 天 → 釘板 2 天 → 紮鐵 3 天 → 落水泥 1 天 → 養護 8 天）與 AM / Noon / Night 時段，計算每個地塊的 Planned %。
4. Actual % 為該地塊預期顏色的像素覆蓋率；若完全沒有預期顏色，會依原 `app.py` 的邏輯回退到上一工序或佔比最高的顏色。
5. 實際進度落後目標超過容許閾值時，顯示延誤警報。

瀏覽器會把 HSV 量化成與 OpenCV 相同的 8-bit 整數域（H 0–180、S/V 0–255），因此數值能與 Python 版對齊。

## 📁 專案結構

```text
Drone_Demo/
├── index.html            # 純前端主程式（部署時的首頁）
├── JPG_99/               # 99 張範例照片 Day01–Day33
├── app.py                # 原始 Streamlit + OpenCV 版本
├── simulate_drone.py     # 原始照片搬移模擬腳本
├── requirements.txt      # Python 版本依賴
└── simulate_drone.html   # 舊的 .py 改名檔案（未使用，可忽略）
```

## 🌐 部署到 GitHub Pages

### 方法 A：GitHub 網頁介面

1. 在 GitHub 建立新的 repository（公開最簡單）。
2. 將這個資料夾推上去：

   ```bash
   git init
   git add .
   git commit -m "Add drone progress monitor HTML demo"
   git branch -M main
   git remote add origin https://github.com/<你的帳號>/<repo>.git
   git push -u origin main
   ```

3. 到 repo 的 **Settings → Pages**。
4. **Build and deployment → Source** 選 `Deploy from a branch`。
5. Branch 選 `main`、資料夾選 `/ (root)`，按 **Save**。
6. 幾分鐘後開啟：

   ```text
   https://<你的帳號>.github.io/<repo>/
   ```

### 方法 B：GitHub CLI

```bash
gh repo create drone-progress-monitor --public --source=. --remote=origin --push
```

建立後再到 **Settings → Pages** 啟用即可（CLI 也能用 `gh api` 啟用 Pages，但用網頁介面最快）。

> 私有 repo 能否使用 GitHub Pages 取決於帳號方案；免費帳號請使用公開 repo。

## 🐍 執行原始 Python 版本

```bash
pip install -r requirements.txt

# Streamlit 版
streamlit run app.py

# 照片搬移模擬（會把 JPG_99 的照片逐張複製到 watch_folder）
python simulate_drone.py
```

## 📝 備註

- `simulate_drone.html` 是原本把 Python 檔直接改名成 `.html` 的檔案，內容不是可執行的網頁；實際 HTML 版本是 `index.html`。
- 若要換成自己的照片，保留 `DayXX_YY_AM|Noon|Night.jpg` 命名並放入 `JPG_99/`，或使用「手動上傳照片」模式。
