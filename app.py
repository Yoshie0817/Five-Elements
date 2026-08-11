import streamlit as st
from datetime import datetime, time
from lunar_python import Lunar, Solar

# ==========================================
# 1. 基礎資料庫 (五行對應與生剋規則)
# ==========================================
ELEMENT_MAPPING = {
    "木": {
        "color": "綠色、青色",
        "direction": "東方",
        "crystals": ["綠幽靈", "捷克隕石", "綠草莓晶", "孔雀石"]
    },
    "火": {
        "color": "紅色、粉色、紫色",
        "direction": "南方",
        "crystals": ["紫水晶", "粉晶", "紅碧璽", "石榴石"]
    },
    "土": {
        "color": "黃色、棕色、咖啡色",
        "direction": "中央、西南、東北",
        "crystals": ["黃水晶", "橙黃方解石", "黃虎眼石"]
    },
    "金": {
        "color": "白色、金色、銀色",
        "direction": "西方、西北",
        "crystals": ["白水晶", "鈦晶", "金髮晶"]
    },
    "水": {
        "color": "黑色、藍色、灰黑色",
        "direction": "北方",
        "crystals": ["黑曜石", "黑針水晶", "藍虎眼石", "拉長石"]
    }
}

GAN_ELEMENT = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"
}

# 地支藏幹細化表 (本氣, 中氣, 餘氣及權重比例)
ZHI_HIDDEN_GAN = {
    "子": [("癸", 1.0)],
    "丑": [("己", 0.6), ("癸", 0.25), ("辛", 0.15)],
    "寅": [("甲", 0.6), ("丙", 0.25), ("戊", 0.15)],
    "卯": [("乙", 1.0)],
    "辰": [("戊", 0.6), ("乙", 0.25), ("癸", 0.15)],
    "巳": [("丙", 0.6), ("戊", 0.25), ("庚", 0.15)],
    "午": [("丁", 0.7), ("己", 0.3)],
    "未": [("己", 0.6), ("丁", 0.25), ("乙", 0.15)],
    "申": [("庚", 0.6), ("壬", 0.25), ("戊", 0.15)],
    "酉": [("辛", 1.0)],
    "戌": [("戊", 0.6), ("辛", 0.25), ("丁", 0.15)],
    "亥": [("壬", 0.7), ("甲", 0.3)]
}

# 地支三合局與六合局對應表
SAN_HE = {
    frozenset(["申", "子", "辰"]): ("水", 45),
    frozenset(["亥", "卯", "未"]): ("木", 45),
    frozenset(["寅", "午", "戌"]): ("火", 45),
    frozenset(["巳", "酉", "丑"]): ("金", 45)
}

LIU_HE = {
    frozenset(["子", "丑"]): ("土", 20),
    frozenset(["寅", "亥"]): ("木", 20),
    frozenset(["卯", "戌"]): ("火", 20),
    frozenset(["辰", "酉"]): ("金", 20),
    frozenset(["巳", "申"]): ("水", 20),
    frozenset(["午", "未"]): ("土", 20)
}

# 五行生剋關係
ELEMENT_GENERATE = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # 生
ELEMENT_CONTROL = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}   # 剋
ELEMENT_RESTORE = {v: k for k, v in ELEMENT_GENERATE.items()}                  # 生我的五行 (印)

# ==========================================
# 2. 精準版八字排盤、合化與旺衰喜用神演算法
# ==========================================
def calculate_bazi_and_favorable(birth_datetime):
    solar = Solar.fromYmdHms(
        birth_datetime.year, birth_datetime.month, birth_datetime.day,
        birth_datetime.hour, birth_datetime.minute, birth_datetime.second
    )
    lunar = solar.getLunar()
    bazi = lunar.getEightChar()
    
    year_gz, month_gz = bazi.getYear(), bazi.getMonth()
    day_gz, time_gz = bazi.getDay(), bazi.getTime()
    
    day_master = bazi.getDayGan()
    dm_element = GAN_ELEMENT[day_master]
    
    gans = [bazi.getYearGan(), bazi.getMonthGan(), bazi.getDayGan(), bazi.getTimeGan()]
    zhis = [bazi.getYearZhi(), bazi.getMonthZhi(), bazi.getDayZhi(), bazi.getTimeZhi()]
    
    element_scores = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    combo_notes = []
    
    # --- Step 1: 地支合化局掃描 ---
    zhis_set = set(zhis)
    for combo, (target_elem, bonus) in SAN_HE.items():
        if combo.issubset(zhis_set):
            element_scores[target_elem] += bonus
            combo_notes.append(f"地支成【{''.join(combo)}】三合{target_elem}局 (+{bonus}分)")
            
    for combo, (target_elem, bonus) in LIU_HE.items():
        if combo.issubset(zhis_set):
            element_scores[target_elem] += bonus
            combo_notes.append(f"地支見【{''.join(combo)}】六合化{target_elem} (+{bonus}分)")

    # --- Step 2: 天干賦分 ---
    for gan in gans:
        element_scores[GAN_ELEMENT[gan]] += 10.0

    # --- Step 3: 地支藏幹細化賦分 (月令提綱給予雙倍權重) ---
    for idx, zhi in enumerate(zhis):
        base_weight = 30.0 if idx == 1 else 15.0
        for h_gan, ratio in ZHI_HIDDEN_GAN[zhi]:
            element_scores[GAN_ELEMENT[h_gan]] += base_weight * ratio

    for k in element_scores:
        element_scores[k] = round(element_scores[k], 1)

    # --- Step 4: 日主旺衰判定與專屬喜用神動態優化 ---
    same_group_score = element_scores[dm_element] + element_scores[ELEMENT_RESTORE[dm_element]]
    total_score = sum(element_scores.values())
    power_ratio = round((same_group_score / total_score) * 100, 1) if total_score > 0 else 0
    
    is_strong = power_ratio >= 48.0
    
    # 🌟 特殊格局動態觸發：乙木/甲木身旺且全局火氣弱 (火<=10分)
    if dm_element == "木" and is_strong and element_scores["火"] <= 10.0:
        status_desc = f"日主極旺木格（木氣占 {power_ratio}%，全局缺火調候）"
        favorable_element = "火"  # 強制鎖定「火」為第一核心用神 (通關、洩秀、生土)
        combo_notes.append("💡 觸發專屬調候：採『藉火洩木、以火生土、融會金氣』最佳平衡策略")
    else:
        # 常規喜用神邏輯
        if is_strong:
            status_desc = f"日主偏強（同類能量佔 {power_ratio}%）"
            favorable_element = ELEMENT_CONTROL[dm_element]
        else:
            status_desc = f"日主偏弱（同類能量佔 {power_ratio}%）"
            favorable_element = ELEMENT_RESTORE[dm_element]

    return {
        "bazi_str": f"{year_gz}年  {month_gz}月  {day_gz}日  {time_gz}時",
        "day_master": f"{day_master}（{dm_element}）",
        "dm_element": dm_element,
        "status_desc": status_desc,
        "favorable_element": favorable_element,
        "scores": element_scores,
        "combo_notes": combo_notes if combo_notes else ["無明顯地支合化局"]
    }

# ==========================================
# 優化版：干支綜合流日能量分析函數
# ==========================================
def analyze_daily_advice_advanced(favorable_element, target_date):
    """
    綜合計算流日天干 (40%) 與地支藏幹 (60%) 的能量分佈，
    並精準比對個人喜用神。
    """
    target_solar = Solar.fromYmd(target_date.year, target_date.month, target_date.day)
    target_lunar = target_solar.getLunar()
    
    day_gan = target_lunar.getDayGan()
    day_zhi = target_lunar.getDayZhi()
    
    # 1. 計算流日自身的五行力量分佈
    daily_element_scores = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    
    # 天干貢獻 40 分
    gan_elem = GAN_ELEMENT.get(day_gan, "木")
    daily_element_scores[gan_elem] += 40.0
    
    # 地支藏幹貢獻 60 分 (按本氣/中氣/餘氣比例分配)
    hidden_list = ZHI_HIDDEN_GAN.get(day_zhi, [("癸", 1.0)])
    for h_gan, ratio in hidden_list:
        h_elem = GAN_ELEMENT[h_gan]
        daily_element_scores[h_elem] += 60.0 * ratio
        
    # 取當日最強的主導五行 (Dominant Element)
    dominant_element = max(daily_element_scores, key=daily_element_scores.get)
    dominant_score = round(daily_element_scores[dominant_element], 1)
    
    # 2. 分析流日主導氣場對個人喜用神 (favorable_element) 的生剋影響
    if dominant_element == favorable_element:
        status_text = (
            f"今日干支【{day_gan}{day_zhi}】主導能量為【{dominant_element}】（佔 {dominant_score}%），"
            f"正是您的本命喜用五行，整體氣場共振極佳！"
        )
    elif ELEMENT_GENERATE[dominant_element] == favorable_element:
        status_text = (
            f"今日干支【{day_gan}{day_zhi}】主導能量為【{dominant_element}】（天干{gan_elem}/地支藏幹氣盛），"
            f"能順勢生扶您的喜用【{favorable_element}】，能量順暢有助益。"
        )
    elif ELEMENT_RESTORE[dominant_element] == favorable_element:
        status_text = (
            f"今日干支【{day_gan}{day_zhi}】主導能量為【{dominant_element}】，"
            f"會洩耗您的喜用【{favorable_element}】氣場，建議加強對應配件以穩定能量。"
        )
    elif ELEMENT_CONTROL[dominant_element] == favorable_element:
        status_text = (
            f"今日干支【{day_gan}{day_zhi}】主導能量為【{dominant_element}】，"
            f"對您的喜用【{favorable_element}】有強烈克制之象，需配戴專屬水晶進行通關與防護。"
        )
    else:
        status_text = (
            f"今日干支【{day_gan}{day_zhi}】氣場以【{dominant_element}】為主，"
            f"與喜用神關係平穩，維持日常能量補充即可。"
        )

    info = ELEMENT_MAPPING[favorable_element]
    
    # 生成地支藏幹文字說明 (例：午藏丁火、己土)
    hidden_str = "、".join([f"{g}{GAN_ELEMENT[g]}" for g, _ in hidden_list])

    return {
        "day_gz": f"{day_gan}{day_zhi}",
        "day_gan_elem": gan_elem,
        "day_zhi_info": hidden_str,
        "dominant_element": dominant_element,
        "status_text": status_text,
        "suggest_color": info["color"],
        "suggest_direction": info["direction"],
        "suggest_crystals": info["crystals"]
    }

# ==========================================
# 4. Streamlit UI 介面
# ==========================================
st.set_page_config(page_title="個人專屬八字喜用與每日水晶指南", layout="wide")
# ==========================================
# 自訂 UI 樣式 (調整字型、縮小手機端標題大小)
# ==========================================
st.markdown("""
    <style>
    /* 引入微軟正黑體或圓潤的繁體中文標準字型 */
    html, body, [class*="css"] {
        font-family: "PingFang TC", "Microsoft JhengHei", "Noto Sans TC", sans-serif;
    }
    
    /* 主標題 (st.title) 樣式微調：縮小字級、調小行高，適合手機螢幕 */
    h1 {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        line-height: 1.3 !important;
        color: #2C3E50 !important;
    }
    
    /* 副標題 (st.header) 樣式 */
    h2 {
        font-size: 1.4rem !important;
        color: #34495E !important;
    }
    
    /* 小標題 (st.subheader) 樣式 */
    h3 {
        font-size: 1.15rem !important;
    }
    
    /* 說明文字字級 */
    .stCaption {
        font-size: 0.85rem !important;
        color: #7F8C8D !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🔮 個人專屬八字喜用神與每日水晶穿搭系統")
st.caption("自動排盤八字四柱、判定日主旺衰與地支合化，並即時結合每日流日干支算出調和色彩與水晶建議")

# ==========================================
# 側邊欄：個人八字輸入區 (含 5 組常用書籤)
# ==========================================
st.sidebar.header("1. 個人出生時間設定")

# 定義 5 組常用生日書籤資料 (可自行修改名稱與預設年月日時)
BOOKMARKS = {
    "自訂輸入": {"date": datetime(1975, 1, 1), "time": time(12, 0)},
    "Yoshie (1975 乙卯)": {"date": datetime(1975, 8, 17), "time": time(8, 30)},
    "Irene (1977 丁巳)": {"date": datetime(1977, 1, 26), "time": time(10, 0)}, # 示例西曆
    "Papa (1942 壬午)": {"date": datetime(1942, 11, 27), "time": time(12, 0)},
    "Mama (1947 丁亥)": {"date": datetime(1947, 3, 28), "time": time(0, 0)},
    "Simon (1978 戊午)": {"date": datetime(1978, 10, 25), "time": time(9, 30)}
}

# 書籤下拉選單
selected_bookmark = st.sidebar.selectbox("📌 快速選擇預設書籤", list(BOOKMARKS.keys()))

# 根據選擇的書籤自動帶入日期與時間
default_date = BOOKMARKS[selected_bookmark]["date"]
default_time = BOOKMARKS[selected_bookmark]["time"]

min_birth_date = datetime(1940, 1, 1)
max_birth_date = datetime.now()

# 日期與時間選擇器 (可隨時手動微調)
birth_date = st.sidebar.date_input(
    "出生日期（公曆）",
    value=default_date,
    min_value=min_birth_date,
    max_value=max_birth_date,
    key=f"birth_date_{selected_bookmark}"  # 加上 key 確保切換書籤時自動更新畫面
)

birth_time = st.sidebar.time_input(
    "出生時辰", 
    value=default_time,
    key=f"birth_time_{selected_bookmark}"
)

birth_dt = datetime.combine(birth_date, birth_time)

# 進行精準八字計算
bazi_result = calculate_bazi_and_favorable(birth_dt)

st.sidebar.divider()
st.sidebar.subheader("📌 命格排盤結果")
st.sidebar.write(f"**八字四柱**：{bazi_result['bazi_str']}")
st.sidebar.write(f"**日主五行**：{bazi_result['day_master']}")
st.sidebar.write(f"**旺衰狀態**：{bazi_result['status_desc']}")

st.sidebar.markdown("**地支合化與格局調候**：")
for note in bazi_result['combo_notes']:
    st.sidebar.caption(f"• {note}")

st.sidebar.success(f"**建議核心喜用神**：【{bazi_result['favorable_element']}】")

# 主要區域：每日查詢
st.header("2. 每日能量運勢與調和指南")
query_date = st.date_input("選擇查詢日期", datetime.now())

# ----------------------------------------------------
# 新版的程式碼（展示完整的干支與藏幹資訊）：
# ----------------------------------------------------
if st.button("計算本日能量建議", type="primary"):
    # 1. 取得自動算出的喜用神
    favorable = bazi_result['favorable_element']
    
    # 2. 呼叫幹支綜合演算法
    daily_res = analyze_daily_advice_advanced(favorable, query_date)
    
    st.subheader(f"📅 {query_date.strftime('%Y-%m-%d')} 能量解析")
    
    # 3. 顯示包含天干與地支藏幹的完整卡片
    st.info(
        f"今日流日干支：**{daily_res['day_gz']}** "
        f"（天干屬 **{daily_res['day_gan_elem']}**，地支藏幹：**{daily_res['day_zhi_info']}**）\n\n"
        f"{daily_res['status_text']}"
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🎨 建議穿搭/配件顏色", value=daily_res["suggest_color"])
    with col2:
        st.metric(label="🧭 每日吉利方位", value=daily_res["suggest_direction"])
    with col3:
        st.metric(label="🌟 本命喜用補益", value=f"補充【{favorable}】能量")
        
    st.markdown("---")
    st.markdown("### 💎 推薦佩戴水晶種類")
    
    # 將陣列轉為字串呈現
    crystals_text = "、".join(daily_res["suggest_crystals"])
    st.success(crystals_text)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🎨 建議穿搭/配件顏色", value=daily_res["suggest_color"])
    with col2:
        st.metric(label="🧭 每日吉利方位", value=daily_res["suggest_direction"])
    with col3:
        st.metric(label="🌟 本命喜用補益", value=f"補充【{favorable}】能量")
        
    st.markdown("---")
    st.markdown("### 💎 推薦佩戴水晶種類")
    st.success(daily_res["suggest_crystals"])

    st.markdown("---")

with st.expander("📊 查看個人八字五行能量分佈權重"):
    scores = bazi_result["scores"]
    total_val = sum(scores.values()) if sum(scores.values()) > 0 else 1
    colors = {"木": "🟢", "火": "🔴", "土": "🟡", "金": "⚪", "水": "🔵"}
    
    for elem, score in scores.items():
        ratio = round((score / total_val) * 100, 1)
        col_name, col_prog = st.columns([1, 4])
        with col_name:
            st.write(f"{colors.get(elem, '⚪')} **{elem}** ({score}分)")
        with col_prog:
            st.progress(min(score / 100.0, 1.0), text=f"占比 {ratio}%")
