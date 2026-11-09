import base64
from datetime import datetime, date
import io
import os
import time
import uuid
import json

import openai
import pandas as pd
from PIL import Image
import streamlit as st

# ==========================================
# 1. 初期設定と定数
# ==========================================
st.set_page_config(
    page_title="わくわく理科探検チャット",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="expanded",
)

STATS_FILE = "user_stats.csv"
STREAK_FILE = "user_streaks.json"
QUIZ_STATS_FILE = "quiz_stats.json"

GRADE_OPTIONS = [
    "👦 小学1年生", "👦 小学2年生", "👦 小学3年生",
    "👦 小学4年生", "👦 小学5年生", "👦 小学6年生",
    "🧑 中学1年生", "🧑 中学2年生", "🧑 中学3年生",
    "🏫 高校1年生", "🏫 高校2年生", "🏫 高校3年生",
    "🎓 大人・一般",
]

PERSONA_OPTIONS = [
    "👨‍🏫 普通のハカセ (知的で穏やか)",
    "🥰 優しいハカセ (とにかく褒める・包容力)",
    "🤪 癖ありハカセ (マッドサイエンティスト風)",
    "🔥 熱血ハカセ (ハイテンションで熱い)"
]

DEFAULT_CONTENT = {
    "experiment": {"title": "🔑 APIキーをいれてね", "desc": "左のメニューからAPIキーを設定すると、ハカセが今日の実験を考えてくれるよ！"},
    "problem": {"title": "🧪 今日の挑戦問題", "question": "APIキーを設定すると、ここに計算問題やクイズが出るよ！", "hint": "ヒントもここに出るよ。"},
    "trivia": {"物理": "APIキーを入れると豆知識が見られるよ！", "化学": "APIキーを入れると豆知識が見られるよ！", "生物": "APIキーを入れると豆知識が見られるよ！", "地学・宇宙": "APIキーを入れると豆知識が見られるよ！"}
}

# ==========================================
# 2. 関数定義
# ==========================================

def get_grade_category(grade_name):
    if "小学" in grade_name:
        if any(g in grade_name for g in ["1年生", "2年生", "3年生"]): return "小学低学年"
        else: return "小学高学年"
    elif "中学" in grade_name:
        return "中学生"
    elif "高校" in grade_name:
        return "高校生"
    else:
        return "一般大人"

def generate_daily_content(api_key, grade_name, model_name, seed_date):
    grade_cat = get_grade_category(grade_name)
    system_prompt = f"""あなたは理科の専門家です。対象読者（{grade_cat}）に合わせて、以下の3つのコンテンツをJSON形式で生成してください。（今日の日付: {seed_date}）
以下のJSONフォーマットで出力してください。
{{
  "experiment": {{
    "title": "実験のタイトル（絵文字を含む）",
    "desc": "実験の簡単な手順（50文字程度）。※結果はどうなるか絶対に書かないこと！"
  }},
  "problem": {{
    "title": "🧪 今日の挑戦問題",
    "question": "問題文（計算問題など）",
    "hint": "解くためのヒントや公式（答えは書かない！）"
  }},
  "trivia": {{
    "物理": "物理の豆知識（50文字程度）", "化学": "化学の豆知識", "生物": "生物の豆知識", "地学・宇宙": "地学・宇宙の豆知識"
  }}
}}"""
    try:
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(model=model_name, messages=[{"role": "system", "content": system_prompt}], response_format={"type": "json_object"}, temperature=0.7)
        return json.loads(res.choices[0].message.content)
    except Exception:
        return None

def generate_quiz(api_key, grade_name, model_name):
    grade_cat = get_grade_category(grade_name)
    system_prompt = f"""あなたは理科の専門家です。{grade_cat}向けの理科の4択クイズを1問作成し、以下のJSON形式で出力してください。

【厳守するルール】
- 問題は学年に適した内容であり、学術的に正確であること。
- 選択肢の中に正解は必ず1つだけ存在し、他の3つは明確に誤りであること。
- 引っ掛け問題や言葉遊びなど、曖昧な表現は避けること。

{{
  "question": "問題文",
  "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
  "correct_index": 正解の選択肢のインデックス（0〜3の整数）,
  "explanation": "なぜそれが正解なのかの論理的な解説（対象読者に合わせた口調で分かりやすく）"
}}"""
    try:
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(model=model_name, messages=[{"role": "system", "content": system_prompt}], response_format={"type": "json_object"}, temperature=0.7)
        return json.loads(res.choices[0].message.content)
    except Exception:
        return None

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def update_streak(user_name):
    data = load_json(STREAK_FILE)
    today_str = date.today().isoformat()
    if user_name not in data: data[user_name] = {"streak": 1, "last_date": today_str}
    else:
        last_date_str = data[user_name]["last_date"]
        if last_date_str != today_str:
            last_date = date.fromisoformat(last_date_str)
            if (date.today() - last_date).days == 1: data[user_name]["streak"] += 1
            else: data[user_name]["streak"] = 1
            data[user_name]["last_date"] = today_str
    save_json(STREAK_FILE, data)
    return data[user_name]["streak"]

def get_streak(user_name):
    data = load_json(STREAK_FILE)
    if user_name in data:
        last_date = date.fromisoformat(data[user_name]["last_date"])
        if (date.today() - last_date).days <= 1: return data[user_name]["streak"]
    return 0

def update_quiz_stats(user_name, is_correct):
    data = load_json(QUIZ_STATS_FILE)
    if user_name not in data: data[user_name] = {"total": 0, "correct": 0, "streak": 0}
    
    data[user_name]["total"] += 1
    if is_correct:
        data[user_name]["correct"] += 1
        data[user_name]["streak"] += 1
    else:
        data[user_name]["streak"] = 0
    save_json(QUIZ_STATS_FILE, data)

def get_quiz_stats(user_name):
    data = load_json(QUIZ_STATS_FILE)
    return data.get(user_name, {"total": 0, "correct": 0, "streak": 0})

def save_user_stat(user_name, thread_id, thread_title, char_count, typing_speed, unique_words, text, role="user"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved_name = user_name.strip() if user_name.strip() else "探検者"
    new_data = pd.DataFrame([{"timestamp": now, "user_name": saved_name, "thread_id": thread_id, "thread_title": thread_title, "role": role, "char_count": char_count, "typing_speed": round(typing_speed, 1), "unique_words": unique_words, "text": text}])
    if os.path.exists(STATS_FILE): new_data.to_csv(STATS_FILE, mode="a", index=False, header=False, encoding="utf-8-sig")
    else: new_data.to_csv(STATS_FILE, mode="w", index=False, header=True, encoding="utf-8-sig")

def load_user_data(user_name):
    if not os.path.exists(STATS_FILE): return pd.DataFrame()
    try:
        df = pd.read_csv(STATS_FILE)
        return df[df["user_name"] == (user_name.strip() if user_name.strip() else "探検者")]
    except Exception: return pd.DataFrame()

def get_system_prompt(grade_name, persona_name):
    persona_instruction = ""
    if "優しい" in persona_name:
        persona_instruction = "【キャラクター】あなたは優しくて包容力のある探検ハカセです。「〜だね」「〜だよ」と温かく語りかけ、ユーザーをたくさん褒めて自己肯定感を高めてください。"
    elif "癖あり" in persona_name:
        persona_instruction = "【キャラクター】あなたは少し変わったマッドサイエンティスト風の探検ハカセです。「フハハ！」「〜なのだ！」「〜であるぞ！」と少しオーバーで芝居がかった口調で話してください。"
    elif "熱血" in persona_name:
        persona_instruction = "【キャラクター】あなたは熱血漢の探検ハカセです。「〜だぜ！」「燃えてきたー！」など、体育会系でハイテンションに励ましてください。"
    else:
        persona_instruction = "【キャラクター】あなたは知的で穏やかな探検ハカセです。親しみやすく丁寧な口調で話してください。"

    base_role = f"あなたは自然科学の学習を支援するパートナー「探検ハカセ」です。\n{persona_instruction}\n【重要】ユーザーが「今日の実験」の結果や問題の答えを送ってきたら、大げさに褒めてから正解と理由を解説してください。"
    qa_instruction = "\n【重要】回答の最後には必ず『---』で区切り、ユーザーが次に興味を持ちそうな「深掘り質問の候補」を3つ、箇条書きで提示してください。"

    if "小学" in grade_name: return f"{base_role}\n【対象】: {grade_name}\n・習っていない漢字はひらがなにするかルビを使用\n・返信は100〜150文字程度\n{qa_instruction}"
    elif "中学" in grade_name: return f"{base_role}\n【対象】: {grade_name}\n・化学式や物理公式を活用して理論的に解説\n{qa_instruction}"
    else: return f"{base_role}\n【対象】: {grade_name}\n・専門用語を用いた深掘り解説\n{qa_instruction}"

def encode_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    img.thumbnail((1200, 1200))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# ==========================================
# 3. セッション管理
# ==========================================
if "user_name" not in st.session_state: st.session_state.user_name = ""
if "selected_grade" not in st.session_state: st.session_state.selected_grade = GRADE_OPTIONS[2]
if "selected_persona" not in st.session_state: st.session_state.selected_persona = PERSONA_OPTIONS[0]
if "last_send_time" not in st.session_state: st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "suggested_questions" not in st.session_state: st.session_state.suggested_questions = []
if "auto_send_msg" not in st.session_state: st.session_state.auto_send_msg = None
if "daily_content" not in st.session_state: st.session_state.daily_content = None
if "content_date_grade" not in st.session_state: st.session_state.content_date_grade = ""
if "quiz_data" not in st.session_state: st.session_state.quiz_data = None
if "quiz_answered" not in st.session_state: st.session_state.quiz_answered = False
if "quiz_selected" not in st.session_state: st.session_state.quiz_selected = None
if "show_tutorial" not in st.session_state: st.session_state.show_tutorial = False

def create_new_thread(system_prompt, grade_name):
    new_id = str(uuid.uuid4())
    thread_count = len(st.session_state.get("threads", {})) + 1
    is_child = "小学" in grade_name
    default_title = f"あたらしい おはなし {thread_count}" if is_child else f"新しいテーマ {thread_count}"
    greeting = f"こんにちは！【{grade_name}】向けの 探検スタートだよ！\n今日の実験の結果や、問題の答えもここで教えてね！" if is_child else f"こんにちは！【{grade_name}】モードで解説します。\n今日の実験結果や計算問題の答えも、ここで教えてくださいね！"
    return new_id, {"title": default_title, "messages": [{"role": "system", "content": system_prompt}, {"role": "assistant", "content": greeting}]}

st.markdown("""
    <style>
    .stApp { background-color: #FFFDE7 !important; color: #212121 !important; }
    .user-card, .exp-card, .prob-card, .quiz-card { background-color: #FFFFFF; border: 2px solid #FFB74D; border-radius: 15px; padding: 12px 18px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    .exp-card { border-color: #4CAF50; background-color: #F1F8E9; }
    .prob-card { border-color: #AB47BC; background-color: #F3E5F5; }
    .quiz-card { border-color: #f44336; background-color: #ffebee; }
    .stChatMessage { border-radius: 16px !important; padding: 10px 14px !important; margin-bottom: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. サイドバー
# ==========================================
with st.sidebar:
    st.title("🧭 メニュー")
    selected_grade = st.selectbox("学年を選んでね", GRADE_OPTIONS, index=GRADE_OPTIONS.index(st.session_state.selected_grade))
    selected_persona = st.selectbox("ハカセの性格", PERSONA_OPTIONS, index=PERSONA_OPTIONS.index(st.session_state.selected_persona))
    
    if selected_grade != st.session_state.selected_grade or selected_persona != st.session_state.selected_persona:
        st.session_state.selected_grade = selected_grade
        st.session_state.selected_persona = selected_persona
        new_id, new_thread = create_new_thread(get_system_prompt(selected_grade, selected_persona), selected_grade)
        if "threads" not in st.session_state: st.session_state.threads = {}
        st.session_state.threads[new_id] = new_thread
        st.session_state.current_thread_id = new_id
        st.session_state.suggested_questions = []
        st.rerun()

    active_prompt = get_system_prompt(selected_grade, selected_persona)
    st.divider()
    page = st.radio("ページ選択", ["💬 チャット", "🎯 クイズ道場", "📊 学習記録レポート"])

    if "threads" not in st.session_state:
        init_id, init_thread = create_new_thread(active_prompt, selected_grade)
        st.session_state.threads = {init_id: init_thread}
        st.session_state.current_thread_id = init_id

    if "チャット" in page:
        st.divider()
        if st.button("➕ あたらしい おはなし", use_container_width=True):
            new_id, new_thread = create_new_thread(active_prompt, selected_grade)
            st.session_state.threads[new_id] = new_thread
            st.session_state.current_thread_id = new_id
            st.session_state.suggested_questions = []
            st.rerun()
        
        thread_options = {tid: data["title"] for tid, data in st.session_state.threads.items()}
        selected_thread_id = st.radio("これまでの会話:", options=list(thread_options.keys()), format_func=lambda x: thread_options[x], index=list(thread_options.keys()).index(st.session_state.current_thread_id))
        st.session_state.current_thread_id = selected_thread_id

    st.divider()
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key: api_key = st.text_input("OpenAI APIキーを入力", type="password")
    selected_model = st.selectbox("🧠 AIのモデル", ["gpt-4o", "gpt-4o-mini"], index=0)

# ==========================================
# 5. ヘッダー共通 (名前入力と新規ユーザー判定)
# ==========================================
st.markdown('<div class="user-card">', unsafe_allow_html=True)
u_col1, u_col2 = st.columns([2, 1])
with u_col1:
    input_name = st.text_input("👤 あなたの おなまえ", value=st.session_state.user_name, key="global_user_name_input")
    if input_name != st.session_state.user_name:
        # 新しい名前が入力された場合、過去の記録があるかチェック
        if input_name.strip():
            streaks = load_json(STREAK_FILE)
            if input_name not in streaks:
                st.session_state.show_tutorial = True
        st.session_state.user_name = input_name
        st.rerun()
with u_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.user_name.strip():
        st.success(f"🔥 チャット連続記録: {get_streak(st.session_state.user_name)} 日目！")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------
# ⚠️ 名前の入力がない場合は、ここでウェルカム画面を出してストップ
# ----------------------------------------------------
if not st.session_state.user_name.strip():
    st.title("🌟 わくわく理科探検チャットへようこそ！")
    st.markdown("""
    ここでは、AIの「探検ハカセ」と一緒に理科を楽しく学べるよ！
    
    ### 🛠️ できること
    - **💬 チャット**: 日替わりの実験や問題に挑戦！ハカセになんでも質問しよう。
    - **🎯 クイズ道場**: 4択クイズで知識を試そう。連続正解を目指してね！
    - **📊 学習記録レポート**: がんばった記録がグラフや数字で見られるよ。
    
    **👆 まずは、上の入力欄にあなたの名前（ニックネーム）を入れてね！**
    """)
    st.stop() # 名前がないとこれより下（チャットやクイズ）は実行されない

# ----------------------------------------------------
# ⚠️ 新規ユーザーの場合は、チュートリアルを出してストップ
# ----------------------------------------------------
if st.session_state.show_tutorial:
    st.info(f"🎉 初めまして、{st.session_state.user_name}さん！探検ハカセの研究所へようこそ！")
    st.markdown("""
    ### 🎓 アプリの使い方
    1. **サイドバーの設定**: 左のメニューから「学年」と「ハカセの性格」を選んでね。
    2. **APIキー**: 左下の設定からAPIキーを入れると、ハカセが動き出すよ！
    3. **チャットで話す**: 毎日の実験やクイズの答えをチャットで教えたり、わからないことを聞いてみよう。
    4. **クイズ道場**: メニューから「クイズ道場」に切り替えて、問題にチャレンジ！
    """)
    if st.button("👍 わかった！はじめる！", use_container_width=True):
        st.session_state.show_tutorial = False
        st.rerun()
    st.stop() # わかったボタンを押すまでメイン画面を出さない

# ==========================================
# 6. メイン画面の切り替え
# ==========================================
if "チャット" in page:
    current_thread = st.session_state.threads[st.session_state.current_thread_id]
    if current_thread["messages"][0]["role"] == "system":
        current_thread["messages"][0]["content"] = active_prompt

    # --- 日替わりコンテンツ ---
    today_str = date.today().isoformat()
    current_state_key = f"{today_str}_{st.session_state.selected_grade}_{selected_model}"
    is_child = "小学" in st.session_state.selected_grade

    if not api_key: daily_data = DEFAULT_CONTENT
    else:
        if st.session_state.content_date_grade != current_state_key or st.session_state.daily_content is None:
            with st.spinner("🧠 ハカセが今日の問題と豆知識を考え中..."):
                new_data = generate_daily_content(api_key, st.session_state.selected_grade, selected_model, today_str)
                if new_data:
                    st.session_state.daily_content = new_data
                    st.session_state.content_date_grade = current_state_key
                    daily_data = new_data
                else: daily_data = DEFAULT_CONTENT
        else: daily_data = st.session_state.daily_content

    todays_exp = daily_data.get("experiment", {})
    todays_prob = daily_data.get("problem", {})
    todays_trivias = daily_data.get("trivia", {})

    col_daily1, col_daily2 = st.columns(2)
    with col_daily1:
        st.markdown(f'<div class="exp-card"><h5 style="margin-top:0;">⏱️ 本日の実験</h5><b>{todays_exp.get("title", "")}</b><br><span style="font-size: 14px;">{todays_exp.get("desc", "")}</span><div style="margin-top: 5px; font-size: 12px; color: #d32f2f;">※結果がどうなったかハカセに教えてね！</div></div>', unsafe_allow_html=True)
    with col_daily2:
        st.markdown(f'<div class="prob-card"><h5 style="margin-top:0;">{todays_prob.get("title", "")}</h5><b style="font-size: 14px;">Q: {todays_prob.get("question", "")}</b><br><span style="font-size: 13px; color: #6a1b9a;">💡 ヒント: {todays_prob.get("hint", "")}</span></div>', unsafe_allow_html=True)

    st.markdown('<h5 style="margin-top:10px;">💡 今日の豆知識</h5>', unsafe_allow_html=True)
    t_cols = st.columns(2)
    for idx, (cat, trivia_text) in enumerate(todays_trivias.items()):
        with t_cols[idx % 2]:
            expander_title = f"📚 豆知識 {idx+1}" if is_child else f"📚 【{cat}】の豆知識"
            with st.expander(expander_title, expanded=True):
                st.markdown(f"> {trivia_text}")
                if st.button("🗣️ 詳しく聞く", key=f"trivia_btn_{cat}"):
                    st.session_state.auto_send_msg = f"「{trivia_text}」についてもっと教えて！"
                    st.rerun()

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)

    # --- チャット履歴表示 ---
    non_system_msgs = [m for m in current_thread["messages"] if m["role"] != "system"]
    for msg in non_system_msgs:
        with st.chat_message(msg["role"], avatar="🎓" if msg["role"] == "assistant" else "👦"):
            if "image" in msg and msg["image"]: st.image(msg["image"], use_container_width=True)
            content = msg["content"]
            if msg["role"] == "assistant" and "---" in content: content = content.split("---")[0].strip()
            st.markdown(content, unsafe_allow_html=True)

    if st.session_state.suggested_questions:
        st.caption("💡 おすすめの質問（タップで聞けるよ！）")
        q_cols = st.columns(min(len(st.session_state.suggested_questions), 3))
        for i, q in enumerate(st.session_state.suggested_questions[:3]):
            if q_cols[i].button(q, key=f"sug_q_{i}"):
                st.session_state.auto_send_msg = q
                st.rerun()

    # --- チャット入力 ---
    uploaded_file = st.file_uploader("📷 しゃしんを えらぶ", type=["jpg", "jpeg", "png"], key=f"uploader_{st.session_state.uploader_key}")
    user_input = st.chat_input("ここに メッセージを かこう！")
    
    if st.session_state.auto_send_msg:
        user_input = st.session_state.auto_send_msg
        st.session_state.auto_send_msg = None

    if user_input:
        if not api_key: st.error("👈 APIキーを入力してね！")
        else:
            current_time = time.time()
            elapsed_time = current_time - st.session_state.last_send_time
            st.session_state.last_send_time = current_time
            
            save_user_stat(st.session_state.user_name, st.session_state.current_thread_id, current_thread["title"], len(user_input), len(user_input) / (elapsed_time / 60) if elapsed_time > 0 else 0, len(set(user_input)), user_input)

            if any(word in user_input for word in ["実験", "できた", "結果", "やった", "答え", "わかった"]):
                update_streak(st.session_state.user_name)
                st.toast("🔥 れんぞく記録がのびたよ！", icon="🎉")

            if current_thread["title"].startswith("あたらしい") and len(current_thread["messages"]) <= 2: current_thread["title"] = f"💬 {user_input[:12]}..."
            
            api_content = [{"type": "text", "text": user_input}]
            image_data = None
            if uploaded_file:
                image_data = uploaded_file.getvalue()
                api_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(image_data)}", "detail": "low"}})

            current_thread["messages"].append({"role": "user", "content": user_input, "image": image_data, "api_content": api_content})
            st.session_state.suggested_questions = []

            with st.chat_message("user", avatar="👦"):
                if image_data: st.image(image_data)
                st.markdown(user_input)

            with st.chat_message("assistant", avatar="🎓"):
                with st.spinner("ハカセが かんがえ中..."):
                    api_msgs = [{"role": m["role"], "content": m.get("api_content", m["content"])} for m in current_thread["messages"][-6:]]
                    api_msgs.insert(0, {"role": "system", "content": current_thread["messages"][0]["content"]})

                    res = openai.OpenAI(api_key=api_key).chat.completions.create(model=selected_model, messages=api_msgs)
                    reply = res.choices[0].message.content
                    
                    display_reply = reply
                    suggested_qs = []
                    if "---" in reply:
                        parts = reply.split("---")
                        display_reply = parts[0].strip()
                        qs_text = parts[1].strip()
                        for line in qs_text.split('\n'):
                            if line.strip() and (line.strip()[0].isdigit() or line.startswith('-') or line.startswith('*')):
                                clean_q = line.strip().lstrip('1234567890.-* []')
                                if clean_q: suggested_qs.append(clean_q)
                    
                    st.markdown(display_reply)
            
            current_thread["messages"].append({"role": "assistant", "content": reply})
            if suggested_qs: st.session_state.suggested_questions = suggested_qs
            st.session_state.uploader_key += 1
            st.rerun()

elif "🎯 クイズ道場" in page:
    st.title("🎯 クイズ道場")
    q_stats = get_quiz_stats(st.session_state.user_name)
    accuracy = (q_stats['correct'] / q_stats['total'] * 100) if q_stats['total'] > 0 else 0

    qc1, qc2, qc3 = st.columns(3)
    qc1.metric("挑戦回数", f"{q_stats['total']} 回")
    qc2.metric("正解数", f"{q_stats['correct']} 問")
    qc3.metric("正答率", f"{accuracy:.1f} %")
    st.caption(f"🔥 現在の連続正解: {q_stats['streak']} 問")

    st.markdown("<hr>", unsafe_allow_html=True)

    if not api_key:
        st.warning("👈 クイズを生成するにはAPIキーを入力してね！")
    else:
        if st.session_state.quiz_data is None:
            if st.button("✨ 新しいクイズを出題する！", use_container_width=True):
                with st.spinner("AIがクイズを作っています..."):
                    q_data = generate_quiz(api_key, st.session_state.selected_grade, selected_model)
                    if q_data:
                        st.session_state.quiz_data = q_data
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_selected = None
                        st.rerun()
                    else:
                        st.error("クイズの作成に失敗しました。もう一度試してね。")
        else:
            q_data = st.session_state.quiz_data
            st.markdown(f'<div class="quiz-card"><h4>Q. {q_data["question"]}</h4></div>', unsafe_allow_html=True)

            if not st.session_state.quiz_answered:
                for i, choice in enumerate(q_data["choices"]):
                    if st.button(f"{i+1}. {choice}", use_container_width=True):
                        st.session_state.quiz_answered = True
                        st.session_state.quiz_selected = i
                        is_correct = (i == q_data["correct_index"])
                        update_quiz_stats(st.session_state.user_name, is_correct)
                        st.rerun()
            else:
                is_correct = (st.session_state.quiz_selected == q_data["correct_index"])
                if is_correct: st.success(f"🎉 大正解！！ あなたの答え: {q_data['choices'][st.session_state.quiz_selected]}")
                else: st.error(f"❌ ざんねん！ 正解は: {q_data['choices'][q_data['correct_index']]}")
                
                st.info(f"💡 【解説】\n{q_data['explanation']}")

                if st.button("⏭️ 次の問題へ", use_container_width=True):
                    with st.spinner("AIが次の問題を作っています..."):
                        new_q_data = generate_quiz(api_key, st.session_state.selected_grade, selected_model)
                        if new_q_data:
                            st.session_state.quiz_data = new_q_data
                            st.session_state.quiz_answered = False
                            st.session_state.quiz_selected = None
                            st.rerun()
                        else:
                            st.error("クイズの作成に失敗しました。")
                            st.session_state.quiz_data = None
                            st.rerun()

else:
    st.title("📊 学習記録レポート")
    st.subheader("💬 チャットの記録")
    df = load_user_data(st.session_state.user_name)
    if df.empty:
        st.info("まだチャットデータがないみたい！お話ししてみてね。")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("総メッセージ数", f"{len(df)} 回")
        col2.metric("総入力文字数", f"{df['char_count'].sum()} 文字")
        col3.metric("平均タイピング速度", f"{round(df['typing_speed'].mean(), 1)} 文字/分")
        
        st.markdown("##### 📈 入力文字数の推移")
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
        chart_data = df.set_index('timestamp_dt')[['char_count']]
        st.line_chart(chart_data)

        st.markdown("##### 📝 最近のやりとり")
        display_df = df[['timestamp', 'thread_title', 'text', 'char_count']].tail(10).sort_values("timestamp", ascending=False)
        display_df.columns = ['日時', 'テーマ', '入力内容', '文字数']
        st.dataframe(display_df, hide_index=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("🎯 クイズ道場の記録")
    q_stats = get_quiz_stats(st.session_state.user_name)
    if q_stats['total'] == 0:
        st.info("まだクイズに挑戦していないみたい！「クイズ道場」で遊んでみてね。")
    else:
        accuracy = (q_stats['correct'] / q_stats['total'] * 100)
        qc1, qc2, qc3 = st.columns(3)
        qc1.metric("総挑戦回数", f"{q_stats['total']} 回")
        qc2.metric("総正解数", f"{q_stats['correct']} 問")
        qc3.metric("通算正答率", f"{accuracy:.1f} %")