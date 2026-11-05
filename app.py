import streamlit as st
import cv2
import numpy as np
import time
import os
import glob
import re
from datetime import datetime

# ==============================================================================
# 1. 頁面佈局與樣式設定
# ==============================================================================
st.set_page_config(
    page_title="無人機地盤進度監控與完成度 (%) 分析系統 PoC",
    layout="wide",
    page_icon="🏗️"
)

st.title("🏗️ 無人機地盤進度與動態完成度 (%) 分析系統")
st.markdown("---")

# ==============================================================================
# 2. 施工階段與 ABCD 四區域座標定義
# ==============================================================================
STAGE_MAP = {
    "黃色": {"stage": "State 1: 立金屬架 (Metal Framing)", "id": 1, "duration": 1, "color": "#FFD700"},
    "橙色": {"stage": "State 2: 釘板 (Formwork)", "id": 2, "duration": 2, "color": "#FF8C00"},
    "紅色": {"stage": "State 3: 紮鐵 (Rebar Binding)", "id": 3, "duration": 3, "color": "#FF4500"},
    "白色": {"stage": "State 4: 落水泥 (Concrete Pouring)", "id": 4, "duration": 1, "color": "#FFFFFF"},
    "藍色": {"stage": "State 5: 水泥養護 (Concrete Curing)", "id": 5, "duration": 8, "color": "#1E90FF"},
    "未開工": {"stage": "尚未開工 (Not Started)", "id": 0, "duration": 1, "color": "#808080"},
    "未知": {"stage": "未知 / 異常狀態", "id": -1, "duration": 1, "color": "#808080"}
}

COLOR_RANGES = {
    "黃色": [(np.array([20, 100, 100]), np.array([35, 255, 255]))],
    "橙色": [(np.array([10, 120, 120]), np.array([19, 255, 255]))],
    "紅色": [(np.array([0, 100, 100]), np.array([9, 255, 255])),
             (np.array([170, 100, 100]), np.array([180, 255, 255]))],
    "白色": [(np.array([0, 0, 180]), np.array([180, 45, 255]))],
    "藍色": [(np.array([95, 100, 100]), np.array([135, 255, 255]))]
}

# 2x2 四格區域的 (ymin, ymax, xmin, xmax) 座標比率劃分
BLOCK_CONFIGS = [
    {"name": "地塊 A (左上)", "code": "A", "start_day": 1, "offset": 0, "bbox_ratio": (0.0, 0.5, 0.0, 0.5)},
    {"name": "地塊 B (右上)", "code": "B", "start_day": 2, "offset": 1, "bbox_ratio": (0.0, 0.5, 0.5, 1.0)},
    {"name": "地塊 C (左下)", "code": "C", "start_day": 3, "offset": 2, "bbox_ratio": (0.5, 1.0, 0.0, 0.5)},
    {"name": "地塊 D (右下)", "code": "D", "start_day": 4, "offset": 3, "bbox_ratio": (0.5, 1.0, 0.5, 1.0)}
]

# ==============================================================================
# 3. Session State 初始化
# ==============================================================================
if "is_playing" not in st.session_state:
    st.session_state.is_playing = False
if "photo_idx" not in st.session_state:
    st.session_state.photo_idx = 0

# ==============================================================================
# 4. 後台解析與工序名稱精簡邏輯
# ==============================================================================
def get_short_stage_name(stage_str):
    """將長工序名稱簡化為固定短標籤，保持介面排列整齊"""
    if "立金屬架" in stage_str:
        return "立金屬架"
    elif "釘板" in stage_str:
        return "釘板"
    elif "紮鐵" in stage_str:
        return "紮鐵"
    elif "落水泥" in stage_str:
        return "落水泥"
    elif "水泥養護" in stage_str:
        return "水泥養護"
    elif "尚未開工" in stage_str or "未開工" in stage_str:
        return "未開工"
    return "未知"

def parse_info_from_filename(filename):
    day_match = re.search(r"[Dd]ay(\d+)", filename)
    day_num = int(day_match.group(1)) if day_match else 1

    fn_upper = filename.upper()
    if "AM" in fn_upper:
        slot_name = "AM (早上)"
        slot_weight = 0.0
    elif "NOON" in fn_upper:
        slot_name = "Noon (中午)"
        slot_weight = 0.5
    elif "NIGHT" in fn_upper or "PM" in fn_upper:
        slot_name = "Night (晚上)"
        slot_weight = 1.0
    else:
        slot_name = "AM (早上)"
        slot_weight = 0.0

    return day_num, slot_name, slot_weight

def calc_block_expected_status(block_offset, current_day, slot_weight):
    active_day = current_day - block_offset

    if active_day < 1:
        return {
            "stage_name": "尚未開工 (Not Started)",
            "stage_id": 0,
            "color": "未開工",
            "prev_color": "未開工",
            "planned_pct": 0.0,
            "duration": 1,
            "active_day": 0
        }

    day_in_cycle = (active_day - 1) % 15 + 1

    if day_in_cycle == 1:
        color, prev_color, stage_id, duration, day_in_stage = "黃色", "未開工", 1, 1, 1
    elif day_in_cycle in [2, 3]:
        color, prev_color, stage_id, duration, day_in_stage = "橙色", "黃色", 2, 2, day_in_cycle - 1
    elif day_in_cycle in [4, 5, 6]:
        color, prev_color, stage_id, duration, day_in_stage = "紅色", "橙色", 3, 3, day_in_cycle - 3
    elif day_in_cycle == 7:
        color, prev_color, stage_id, duration, day_in_stage = "白色", "紅色", 4, 1, 1
    else:
        color, prev_color, stage_id, duration, day_in_stage = "藍色", "白色", 5, 8, day_in_cycle - 7

    daily_increment = 100.0 / duration
    planned_pct = (day_in_stage - 1) * daily_increment + (slot_weight * daily_increment)
    planned_pct = min(100.0, round(planned_pct, 1))

    return {
        "stage_name": STAGE_MAP[color]["stage"],
        "stage_id": stage_id,
        "color": color,
        "prev_color": prev_color,
        "planned_pct": planned_pct,
        "duration": duration,
        "active_day": active_day
    }

def analyze_block_coverage_by_bbox(roi, exp_info):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    roi_h, roi_w, _ = roi.shape
    total_roi_pixels = roi_h * roi_w

    color_counts = {}
    for c_name, ranges in COLOR_RANGES.items():
        cnt = 0
        for l, u in ranges:
            cnt += cv2.countNonZero(cv2.inRange(hsv, l, u))
        color_counts[c_name] = cnt

    exp_color = exp_info["color"]
    prev_color = exp_info["prev_color"]
    exp_stage_id = exp_info["stage_id"]
    planned_pct = exp_info["planned_pct"]

    if exp_stage_id == 0:
        act_color = "未開工"
        act_pct = 0.0
    else:
        exp_cnt = color_counts.get(exp_color, 0)
        act_pct = min(100.0, round((exp_cnt / total_roi_pixels) * 100.0, 1))

        if act_pct > 0:
            act_color = exp_color
        else:
            prev_cnt = color_counts.get(prev_color, 0)
            prev_pct = min(100.0, round((prev_cnt / total_roi_pixels) * 100.0, 1))

            if planned_pct == 0.0 and prev_pct >= 95.0:
                act_color = exp_color
                act_pct = 0.0
            else:
                best_present = max(color_counts, key=color_counts.get)
                if color_counts[best_present] > total_roi_pixels * 0.05:
                    act_color = best_present
                else:
                    act_color = "未開工"

    act_info = STAGE_MAP.get(act_color, STAGE_MAP["未開工"])
    return act_color, act_info, act_pct

# ==============================================================================
# 5. 側邊欄：控制面板
# ==============================================================================
st.sidebar.header("⚙️ 模擬控制面板")

input_mode = st.sidebar.radio(
    "選擇影像輸入源：",
    [
        "自動監控資料夾 (Auto Watch Folder)",
        "手動上傳照片 (Upload Photo)",
        "網路攝影機 (Webcam)"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 判定標準設置")
tolerance_threshold = st.sidebar.slider("容許進度偏差閾值 (%)", min_value=1.0, max_value=20.0, value=5.0)

frame = None
current_day = 1
slot_name = "AM (早上)"
slot_weight = 0.0

# ------------------------------------------------------------------------------
# 模式 1：自動監控資料夾 (Auto Watch Folder)
# ------------------------------------------------------------------------------
if input_mode == "自動監控資料夾 (Auto Watch Folder)":
    st.sidebar.subheader("🎮 演播控制面板")
    col_p1, col_p2, col_p3 = st.sidebar.columns(3)

    if col_p1.button("▶️ 開始", use_container_width=True):
        st.session_state.is_playing = True

    if col_p2.button("⏸️ 暫停", use_container_width=True):
        st.session_state.is_playing = False

    if col_p3.button("🔄 重置", use_container_width=True):
        st.session_state.is_playing = False
        st.session_state.photo_idx = 0
        st.rerun()

    play_speed = st.sidebar.slider("⏱️ 自動播放速度 (秒/張)", min_value=0.5, max_value=5.0, value=1.5, step=0.5)
    watch_folder = st.sidebar.text_input("📁 監控資料夾名稱", value="./JPG_99")

    image_files = []
    if os.path.exists(watch_folder):
        image_files = sorted(glob.glob(os.path.join(watch_folder, "*.jpg")) + glob.glob(os.path.join(watch_folder, "*.JPG")))

    if image_files:
        st.session_state.photo_idx = st.sidebar.slider(
            "📸 照片進度拉桿 (共 99 張)",
            min_value=0,
            max_value=len(image_files) - 1,
            value=min(st.session_state.photo_idx, len(image_files) - 1)
        )

        current_photo_path = image_files[st.session_state.photo_idx]
        file_name = os.path.basename(current_photo_path)
        current_day, slot_name, slot_weight = parse_info_from_filename(file_name)
        frame = cv2.imread(current_photo_path)

        st.sidebar.success(f"📂 照片 [{st.session_state.photo_idx + 1}/{len(image_files)}]：\n`{file_name}`")
        st.sidebar.write(f"🔍 解析狀態：`Day {current_day} - {slot_name}`")
    else:
        st.warning(f"⚠️ 資料夾 `{watch_folder}` 目前無圖片檔案。")

# ------------------------------------------------------------------------------
# 模式 2：手動上傳照片 (Upload Photo)
# ------------------------------------------------------------------------------
elif input_mode == "手動上傳照片 (Upload Photo)":
    st.sidebar.subheader("📤 上傳照片對照")
    uploaded_file = st.sidebar.file_uploader("選擇 2x2 地盤俯拍照片", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        current_day, slot_name, slot_weight = parse_info_from_filename(uploaded_file.name)

        st.sidebar.success(f"📂 已載入檔案：`{uploaded_file.name}`")
        st.sidebar.write(f"🔍 檔名解析：`Day {current_day} - {slot_name}`")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ 手動校正天數與時段")
    current_day = st.sidebar.number_input("手動指定天數 (Day)", min_value=1, max_value=33, value=current_day)
    slot_choice = st.sidebar.selectbox("手動指定時段", ["AM (早上 - 0%)", "Noon (中午 - 50%)", "Night (晚上 - 100%)"])

    if "AM" in slot_choice or "早上" in slot_choice:
        slot_weight = 0.0
    elif "Noon" in slot_choice or "中午" in slot_choice:
        slot_weight = 0.5
    else:
        slot_weight = 1.0

# ------------------------------------------------------------------------------
# 模式 3：網路攝影機 (Webcam)
# ------------------------------------------------------------------------------
elif input_mode == "網路攝影機 (Webcam)":
    st.sidebar.subheader("📹 Webcam 即時擷取")
    if st.sidebar.button("📷 拍照並分析"):
        cap = cv2.VideoCapture(0)
        ret, captured_frame = cap.read()
        cap.release()
        if ret:
            frame = captured_frame
        else:
            st.sidebar.error("⚠️ 無法取得攝影機訊號。")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ 選擇比對目標天數與時段")
    current_day = st.sidebar.number_input("當前拍攝對應天數 (Day)", min_value=1, max_value=33, value=1)
    slot_choice = st.sidebar.selectbox("當前拍攝時段", ["AM (早上 - 0%)", "Noon (中午 - 50%)", "Night (晚上 - 100%)"])

    if "AM" in slot_choice or "早上" in slot_choice:
        slot_weight = 0.0
    elif "Noon" in slot_choice or "中午" in slot_choice:
        slot_weight = 0.5
    else:
        slot_weight = 1.0

# ==============================================================================
# 6. 主畫面：座標切割與影像分析
# ==============================================================================
col_img, col_info = st.columns([1.2, 1])

annotated_frame = None
block_analysis_results = []

if frame is not None:
    annotated_frame = frame.copy()
    img_h, img_w, _ = frame.shape

    mid_x, mid_y = int(img_w * 0.5), int(img_h * 0.5)
    cv2.line(annotated_frame, (mid_x, 0), (mid_x, img_h), (0, 255, 255), 2)
    cv2.line(annotated_frame, (0, mid_y), (img_w, mid_y), (0, 255, 255), 2)

    for idx, cfg in enumerate(BLOCK_CONFIGS):
        b_name = cfg["name"]
        b_code = cfg["code"]
        b_offset = cfg["offset"]

        r_ymin, r_ymax, r_xmin, r_xmax = cfg["bbox_ratio"]
        ymin, ymax = int(img_h * r_ymin), int(img_h * r_ymax)
        xmin, xmax = int(img_w * r_xmin), int(img_w * r_xmax)

        roi = frame[ymin:ymax, xmin:xmax]

        exp_info = calc_block_expected_status(b_offset, current_day, slot_weight)
        act_color, act_info, act_pct = analyze_block_coverage_by_bbox(roi, exp_info)

        text = f"{b_code}: {act_color} ({act_pct}%)"
        cv2.putText(annotated_frame, text, (xmin + 15, ymin + 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        planned_pct = exp_info["planned_pct"]
        delta_pct = round(act_pct - planned_pct, 1)
        is_delayed = False

        if exp_info["stage_id"] > 0:
            if act_info["id"] < exp_info["stage_id"]:
                if planned_pct > 0.0:
                    is_delayed = True
            elif act_info["id"] == exp_info["stage_id"] and delta_pct < -tolerance_threshold:
                is_delayed = True

        block_analysis_results.append({
            "name": b_name,
            "code": b_code,
            "start_day": cfg["start_day"],
            "exp_info": exp_info,
            "act_info": act_info,
            "act_pct": act_pct,
            "planned_pct": planned_pct,
            "delta_pct": delta_pct,
            "is_delayed": is_delayed
        })

with col_img:
    st.subheader("📷 無人機俯拍畫面 (2x2 座標精確劃分)")
    if annotated_frame is not None:
        st.image(cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB), use_container_width=True)
    else:
        st.info("💡 請在側邊欄上傳圖片或啟動自動監控。")

with col_info:
    st.subheader("⏱️ 施工監控指標 (ABCD 獨立時序)")
    m1, m2 = st.columns(2)
    m1.metric("當前計畫天數", f"Day {current_day}", delta=slot_name)
    m2.metric("播放模式", "▶️ 播放中" if st.session_state.is_playing else "⏸️ 已暫停")

    # 動態簡短顯示四區當前正在做的工作
    status_summary = []
    for res in block_analysis_results:
        act_short = get_short_stage_name(res["act_info"]["stage"])
        status_summary.append(f"**{res['code']}**: {act_short}")
    
    st.markdown("##### 📍 各區當前工序：")
    st.markdown(" | ".join(status_summary))

    st.markdown("##### 📍 15 天工序週期：")
    st.markdown("立架(1天) $\\rightarrow$ 釘板(2天) $\\rightarrow$ 紮鐵(3天) $\\rightarrow$ 落水泥(1天) $\\rightarrow$ 養護(8天)")

st.markdown("---")

# ==============================================================================
# 7. 2x2 區域獨立進度比對 (固定統一卡片格式)
# ==============================================================================
st.subheader("📊 2x2 區域獨立進度比對 (Planned % vs Actual %)")

cols = st.columns(4)
delayed_list = []

for idx, res in enumerate(block_analysis_results):
    exp_info = res["exp_info"]
    act_info = res["act_info"]
    planned_pct = res["planned_pct"]
    act_pct = res["act_pct"]
    delta_pct = res["delta_pct"]
    is_delayed = res["is_delayed"]

    # 提取簡短名稱以固定格式
    exp_short = get_short_stage_name(exp_info["stage_name"])
    act_short = get_short_stage_name(act_info["stage"])

    with cols[idx]:
        st.markdown(f"### 地塊 {res['code']}")
        st.caption(f"📅 施工第 {exp_info['active_day']} 天")
        st.markdown(f"**預期工序**：`{exp_short}`")
        st.markdown(f"**目標進度**：`{planned_pct}%` ({exp_info['color']})")
        st.markdown(f"📷 **實際進度**：`{act_pct}%` ({act_short})")

        st.progress(min(1.0, max(0.0, act_pct / 100.0)))

        # 狀態標籤框 (固定高度與文案)
        if is_delayed:
            st.error(f"⚠️ 落後 (Δ: {delta_pct:.1f}%)")
            delayed_list.append((res['name'], exp_short, delta_pct))
        elif exp_info["stage_id"] == 0:
            st.info("⚪ 尚未開工")
        else:
            st.success(f"✅ 正常 (Δ: {delta_pct:+.1f}%)")

st.markdown("---")

# ==============================================================================
# 8. 延誤警報與狀態摘要 (播放至 33 天自動停止)
# ==============================================================================
st.subheader("🚨 地盤進度延誤警報總覽")

if delayed_list:
    for del_b, stage_name, delta_pct in delayed_list:
        st.error(f"🚨 **進度延誤警報**：【{del_b}】現場覆蓋率未達標（進度偏差 Δ: `{delta_pct:.1f}%`），目前滯後於 **{stage_name}**！")
else:
    st.success("🎉 目前所有區域之影像進度均符合預期 Planned % 目標，施工狀態正常。")

# 自動播放控制：播完 99 張圖片 (Day 33) 自動停止並等待重置
if input_mode == "自動監控資料夾 (Auto Watch Folder)" and st.session_state.is_playing and 'image_files' in locals() and image_files:
    if st.session_state.photo_idx < len(image_files) - 1:
        time.sleep(play_speed)
        st.session_state.photo_idx += 1
        st.rerun()
    else:
        st.session_state.is_playing = False
        st.rerun()