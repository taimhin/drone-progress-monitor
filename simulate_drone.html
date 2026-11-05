import time
import shutil
import glob
import os

def start_simulation():
    # 路徑定義
    source_dir = "./JPG_99"         # 請確保此資料夾放有 99 張 PoC 照片
    watch_folder = "./watch_folder"  # 系統監控資料夾

    os.makedirs(watch_folder, exist_ok=True)

    # 抓取並排序 99 張照片
    photos = sorted(glob.glob(os.path.join(source_dir, "*.jpg")))

    if not photos:
        print(f"❌ 錯誤：在 [{source_dir}] 資料夾內找不到 JPG 照片！")
        return

    print("==================================================")
    print("  🚀 開始模擬無人機巡檢傳送 99 張 PoC 照片")
    print(f"  來源目錄: {source_dir}")
    print(f"  目標目錄: {watch_folder}")
    print("==================================================\n")

    for photo_path in photos:
        filename = os.path.basename(photo_path)
        dest_path = os.path.join(watch_folder, filename)

        # 清空監控資料夾舊圖片，確保每次只有最新一張照片
        for old_file in glob.glob(os.path.join(watch_folder, "*")):
            try:
                os.remove(old_file)
            except Exception:
                pass

        # 複製最新照片
        shutil.copy(photo_path, dest_path)
        print(f"📸 傳送照片: {filename}")
        
        # 自由調整每張照片播放間隔 (秒)
        time.sleep(2)

if __name__ == "__main__":
    start_simulation()