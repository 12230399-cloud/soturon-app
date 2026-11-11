import base64
from datetime import datetime, date
import io
import os
import time
import uuid
import json
import random
import csv

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

# Secrets または環境変数からAPIキーを取得
API_KEY = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
ADMIN_PW = st.secrets.get("ADMIN_PASSWORD", "admin")

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
    "experiment": {"title": "🧪 今日の実験", "desc": "AIが今日の実験を準備できなかったみたい。ハカセに直接聞いてみてね！"},
    "problem": {"title": "🧪 今日の挑戦問題", "question": "問題の準備に失敗しちゃった。ハカセに「問題を出して」とお願いしてみてね！", "hint": "ー"},
    "trivia": {"物理": "準備中だよ！", "化学": "準備中だよ！", "生物": "準備中だよ！", "地学・宇宙": "準備中だよ！"}
}

# ==========================================
# 2. 関数定義
# ==========================================
def save_chat_log(user_name, thread_title, user_message, ai_response, char_count, typing_speed):
    file_exists = os.path.isfile(STATS_FILE)
    with open(STATS_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user_name", "thread_title", "user_message", "ai_response", "char_count", "typing_speed"])
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        saved_name = user_name.strip() if user_name.strip() else "ゲストユーザー"
        writer.writerow([timestamp, saved_name, thread_title, user_message, ai_response, char_count, round(typing_speed, 1)])

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def update_streak(user_name):
    data = load_json(STREAK_FILE)
    today_str = date.today().isoformat()
    saved_name = user_name.strip() if user_name.strip() else "ゲストユーザー"
    
    if saved_name not in data: data[saved_name] = {"streak": 1, "last_date": today_str}
    else:
        last_date_str = data[saved_name]["last_date"]
        if last_date_str != today_str:
            last_date = date.fromisoformat(last_date_str)
            if (date.today() - last_date).days == 1: data[saved_name]["streak"] += 1
            else: data[saved_name]["streak"] = 1
            data[saved_name]["last_date"] = today_str
    save_json(STREAK_FILE, data)
    return data[saved_name]["streak"]

def get_streak(user_name):
    data = load_json(STREAK_FILE)
    saved_name = user_name.strip() if user_name.strip() else "ゲストユーザー"
    if saved_name in data:
        last_date = date.fromisoformat(data[saved_name]["last_date"])
        if (date.today() - last_date).days <= 1: return data[saved_name]["streak"]
    return 0

def update_quiz_stats(user_name, is_correct):
    data = load_json(QUIZ_STATS_FILE)
    saved_name = user_name.strip() if user_name.strip() else "ゲストユーザー"
    
    if saved_name not in data: data[saved_name] = {"total": 0, "correct": 0, "streak": 0}
    
    data[saved_name]["total"] += 1
    if is_correct:
        data[saved_name]["correct"] += 1
        data[saved_name]["streak"] += 1
    else:
        data[saved_name]["streak"] = 0
    save_json(QUIZ_STATS_FILE, data)

def get_quiz_stats(user_name):
    data = load_json(QUIZ_STATS_FILE)
    saved_name = user_name.strip() if user_name.strip() else "ゲストユーザー"
    return data.get(saved_name, {"total": 0, "correct": 0, "streak": 0})

def clean_grade_name(grade_name):
    return grade_name.replace("👦", "").replace("🧑", "").replace("🏫", "").replace("🎓", "").strip()

def generate_daily_content(api_key, grade_name, model_name, seed_date):
    exact_grade = clean_grade_name(grade_name)
    random_seed = random.randint(1, 10000)
    system_prompt = f"""あなたは日本の学校教育に精通した専門教師です。対象読者（{exact_grade}）に合わせて以下の3つのコンテンツをJSON形式で生成してください。（今日の日付: {seed_date}、シード値: {random_seed}）
【厳守するルール】
1. {exact_grade}の学習指導要領の範囲に適した内容にすること。
2. 「学年別漢字配当表」に基づき、{exact_grade}までに習う漢字のみを使用すること。
{{
  "experiment": {{ "title": "実験タイトル", "desc": "簡単な手順（結果は書かない）" }},
  "problem": {{ "title": "今日の挑戦問題", "question": "問題文", "hint": "ヒント" }},
  "trivia": {{ "物理": "豆知識", "化学": "豆知識", "生物": "豆知識", "地学・宇宙": "豆知識" }}
}}"""
    try:
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(model=model_name, messages=[{"role": "system", "content": system_prompt}], response_format={"type": "json_object"}, temperature=0.8)
        return json.loads(res.choices[0].message.content)
    except Exception: return None

def generate_quiz(api_key, grade_name, model_name):
    exact_grade = clean_grade_name(grade_name)
    random_topic = random.choice(["動物のふしぎ", "植物のそだち", "宇宙と星", "天気と気象", "力と運動", "電気と磁気", "身近な化学", "地球の歴史", "人体と健康"])
    system_prompt = f"""あなたは専門教師です。{exact_grade}向けの理科4択クイズ（テーマ: {random_topic}）をJSONで出力してください。必ず以下の構成の「単一のJSONオブジェクト」にしてください（"quiz"などのキーで囲まないこと）。
{{ "question": "問題文", "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"], "correct_index": 0, "explanation": "解説" }}"""
    try:
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(model=model_name, messages=[{"role": "system", "content": system_prompt}], response_format={"type": "json_object"}, temperature=0.8)
        data = json.loads(res.choices[0].message.content)
        if "quiz" in data and isinstance(data["quiz"], dict): data = data["quiz"]
        if "question" not in data or "choices" not in data or "correct_index" not in data: return None 
        return data
    except Exception: return None

def get_system_prompt(grade_name, persona_name):
    exact_grade = clean_grade_name(grade_name)
    persona_instruction = "親しみやすく丁寧な口調で話してください。"
    if "優しい" in persona_name: persona_instruction = "「〜だね」「〜だよ」と温かく語りかけ、たくさん褒めてください。"
    elif "癖あり" in persona_name: persona_instruction = "「フハハ！」「〜なのだ！」とマッドサイエンティスト風に。"
    elif "熱血" in persona_name: persona_instruction = "「〜だぜ！」「燃えてきたー！」と体育会系で。"

    return f"""あなたは自然科学の学習を支援する「探検ハカセ」です。
【キャラクター】{persona_instruction}
【対象】{exact_grade}
【厳守ルール】
1. {exact_grade}の学習指導要領の範囲内で解説すること。未習漢字はひらがなかルビを使用。
2. 答えをすぐに教えず、自ら考えさせる問いかけを行うこと。
【重要】回答の最後には必ず『---』で区切り、ユーザーが次に興味を持ちそうな「深掘り質問の候補」を3つ、箇条書きで提示してください。"""

# ==========================================
# 3. セッション管理とスタイル
# ==========================================
if "user_name" not in st.session_state: st.session_state.user_name = ""
if "selected_grade" not in st.session_state: st.session_state.selected_grade = GRADE_OPTIONS[2]
if "selected_persona" not in st.session_state: st.session_state.selected_persona = PERSONA_OPTIONS[0]
if "last_send_time" not in st.session_state: st.session_state.last_send_time = time.time()
if "suggested_questions" not in st.session_state: st.session_state.suggested_questions = []
if "auto_send_msg" not in st.session_state: st.session_state.auto_send_msg = None
if "daily_content" not in st.session_state: st.session_state.daily_content = None
if "content_date_grade" not in st.session_state: st.session_state.content_date_grade = ""
if "quiz_data" not in st.session_state: st.session_state.quiz_data = None
if "quiz_answered" not in st.session_state: st.session_state.quiz_answered = False
if "quiz_selected" not in st.session_state: st.session_state.quiz_selected = None
if "admin_auth" not in st.session_state: st.session_state.admin_auth = False

def create_new_thread(system_prompt, grade_name):
    new_id = str(uuid.uuid4())
    thread_count = len(st.session_state.get("threads", {})) + 1
    default_title = f"テーマ {thread_count}"
    greeting = f"こんにちは！【{clean_grade_name(grade_name)}】向けの 探検スタートだよ！\n今日の実験の結果や、疑問を教えてね！"
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
# 4. 初回登録画面
# ==========================================
if not st.session_state.user_name.strip():
    st.title("🌟 わくわく理科探検チャット")
    
    st.info("""
    **🔰 はじめての方へ（使い方）**
    このアプリは、AIの「探検ハカセ」と一緒に理科のふしぎを学ぶアプリです。
    1. **おなまえと学年** を入れてスタート！
    2. **チャット** でハカセに質問してみよう。
    3. **クイズ道場** で自分の知識をためそう。
    """)

    st.markdown('<div class="user-card">', unsafe_allow_html=True)
    st.markdown("👋 **はじめまして！まずはあなたのことを教えてね！**")
    col1, col2 = st.columns(2)
    with col1: input_name = st.text_input("👤 あなたの おなまえ", key="first_name_input")
    with col2: input_grade = st.selectbox("🎓 学年を選んでね", GRADE_OPTIONS, index=2, key="first_grade_input")
        
    if st.button("🚀 探検をはじめる！", type="primary", use_container_width=True):
        if input_name.strip():
            st.session_state.user_name = input_name
            st.session_state.selected_grade = input_grade
            st.rerun() 
        else: st.error("👆 おなまえを入力してね！")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop() 

# ==========================================
# 5. サイドバー
# ==========================================
st.markdown('<div class="user-card">', unsafe_allow_html=True)
u_col1, u_col2 = st.columns([2, 1])
with u_col1:
    edit_name = st.text_input("👤 おなまえ", value=st.session_state.user_name, key="global_user_name_input")
    if edit_name != st.session_state.user_name and edit_name.strip():
        st.session_state.user_name = edit_name
        st.rerun()
with u_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.success(f"🔥 連続記録: {get_streak(st.session_state.user_name)} 日目！")
st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar:
    st.title("🧭 メニュー")
    selected_grade = st.selectbox("学年を変える", GRADE_OPTIONS, index=GRADE_OPTIONS.index(st.session_state.selected_grade))
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

    active_prompt = get_system_prompt(st.session_state.selected_grade, st.session_state.selected_persona)
    st.divider()
    page = st.radio("ページ選択", ["💬 チャット", "🎯 クイズ道場", "📊 学習きろく", "👑 管理者画面"])

    if "threads" not in st.session_state:
        init_id, init_thread = create_new_thread(active_prompt, st.session_state.selected_grade)
        st.session_state.threads = {init_id: init_thread}
        st.session_state.current_thread_id = init_id

    if "チャット" in page:
        st.divider()
        if st.button("➕ あたらしい おはなし", use_container_width=True):
            new_id, new_thread = create_new_thread(active_prompt, st.session_state.selected_grade)
            st.session_state.threads[new_id] = new_thread
            st.session_state.current_thread_id = new_id
            st.session_state.suggested_questions = []
            st.rerun()
        
        thread_options = {tid: data["title"] for tid, data in st.session_state.threads.items()}
        st.session_state.current_thread_id = st.radio("これまでの会話:", options=list(thread_options.keys()), format_func=lambda x: thread_options[x], index=list(thread_options.keys()).index(st.session_state.current_thread_id))

    st.divider()
    selected_model = st.selectbox("🧠 AIモデル", ["gpt-4o", "gpt-4o-mini"], index=1)

# ==========================================
# 6. メイン機能
# ==========================================
if "チャット" in page:
    current_thread = st.session_state.threads[st.session_state.current_thread_id]
    today_str = date.today().isoformat()
    current_state_key = f"{today_str}_{st.session_state.selected_grade}_{selected_model}"
    
    if not API_KEY: 
        daily_data = DEFAULT_CONTENT
    else:
        if st.session_state.content_date_grade != current_state_key or st.session_state.daily_content is None:
            with st.spinner("🧠 今日の探検を準備中..."):
                new_data = generate_daily_content(API_KEY, st.session_state.selected_grade, selected_model, today_str)
                if new_data:
                    st.session_state.daily_content = new_data
                    st.session_state.content_date_grade = current_state_key
                    daily_data = new_data
                else: daily_data = DEFAULT_CONTENT
        else: daily_data = st.session_state.daily_content

    with st.expander("🎁 今日の探検コンテンツ（タップで開閉）", expanded=True):
        tab1, tab2, tab3 = st.tabs(["🧪 実験", "✍️ 問題", "💡 豆知識"])
        with tab1: st.markdown(f'<div class="exp-card"><h5>{daily_data.get("experiment", {}).get("title", "")}</h5><span style="font-size:14px;">{daily_data.get("experiment", {}).get("desc", "")}</span></div>', unsafe_allow_html=True)
        with tab2: st.markdown(f'<div class="prob-card"><h5>{daily_data.get("problem", {}).get("title", "")}</h5><b style="font-size:14px;">Q: {daily_data.get("problem", {}).get("question", "")}</b><br><span style="font-size:13px; color:#6a1b9a;">💡 ヒント: {daily_data.get("problem", {}).get("hint", "")}</span></div>', unsafe_allow_html=True)
        with tab3:
            for cat, text in daily_data.get("trivia", {}).items():
                st.markdown(f"**📚 【{cat}】**<br>{text}", unsafe_allow_html=True)
                if st.button(f"もっと聞く", key=f"btn_{cat}"):
                    st.session_state.auto_send_msg = f"「{text}」について詳しく教えて！"
                    st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    for msg in [m for m in current_thread["messages"] if m["role"] != "system"]:
        with st.chat_message(msg["role"], avatar="🎓" if msg["role"] == "assistant" else "👦"):
            if "image" in msg and msg["image"]: st.image(msg["image"])
            content = msg["content"].split("---")[0].strip() if msg["role"] == "assistant" and "---" in msg["content"] else msg["content"]
            st.markdown(content)

    if st.session_state.suggested_questions:
        q_cols = st.columns(min(len(st.session_state.suggested_questions), 3))
        for i, q in enumerate(st.session_state.suggested_questions[:3]):
            if q_cols[i].button(q, key=f"sug_q_{i}"):
                st.session_state.auto_send_msg = q
                st.rerun()

    user_input = st.chat_input("ここに メッセージを かこう！")
    if st.session_state.auto_send_msg:
        user_input = st.session_state.auto_send_msg
        st.session_state.auto_send_msg = None

    if user_input:
        if not API_KEY: st.error("⚠️ システムエラー：APIキーが設定されていません。")
        else:
            current_time = time.time()
            elapsed = current_time - st.session_state.last_send_time
            st.session_state.last_send_time = current_time
            typing_speed = len(user_input) / (elapsed / 60) if elapsed > 0 else 0

            if any(w in user_input for w in ["実験", "できた", "結果", "やった", "答え"]):
                update_streak(st.session_state.user_name)
                st.toast("🔥 連続記録がのびたよ！", icon="🎉")

            if current_thread["title"].startswith("テーマ") and len(current_thread["messages"]) <= 2:
                current_thread["title"] = f"💬 {user_input[:10]}..."

            current_thread["messages"].append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="👦"): st.markdown(user_input)

            with st.chat_message("assistant", avatar="🎓"):
                with st.spinner("ハカセが かんがえ中..."):
                    api_msgs = [{"role": m["role"], "content": m["content"]} for m in current_thread["messages"][-5:]]
                    api_msgs.insert(0, {"role": "system", "content": current_thread["messages"][0]["content"]})

                    res = openai.OpenAI(api_key=API_KEY).chat.completions.create(model=selected_model, messages=api_msgs)
                    reply = res.choices[0].message.content
                    
                    save_chat_log(st.session_state.user_name, current_thread["title"], user_input, reply, len(user_input), typing_speed)

                    display_reply = reply.split("---")[0].strip() if "---" in reply else reply
                    st.markdown(display_reply)

            current_thread["messages"].append({"role": "assistant", "content": reply})
            if "---" in reply:
                qs_text = reply.split("---")[1].strip()
                st.session_state.suggested_questions = [line.strip().lstrip('1234567890.-* []') for line in qs_text.split('\n') if line.strip() and (line.strip()[0].isdigit() or line.startswith('-') or line.startswith('*'))]
            else: st.session_state.suggested_questions = []
            st.rerun()

elif "🎯 クイズ道場" in page:
    st.title("🎯 クイズ道場")
    st.markdown("<div class='quiz-card'>ここでは、キミの学年にぴったりの理科クイズに挑戦できるよ！全問正解めざしてがんばろう！</div>", unsafe_allow_html=True)
    
    import json
    
    # セッションステートの初期化
    if "ai_quiz_data" not in st.session_state:
        st.session_state.ai_quiz_data = None
    if "ai_quiz_answered" not in st.session_state:
        st.session_state.ai_quiz_answered = False

    if "grade" not in st.session_state:
        st.session_state.grade = "小学3年生"
        
    st.markdown("##### 🏫 挑戦するレベル")
    selected_grade = st.selectbox(
        "学年を選んでね：", 
        ["小学1年生", "小学2年生", "小学3年生", "小学4年生", "小学5年生", "小学6年生", "中学生"],
        index=["小学1年生", "小学2年生", "小学3年生", "小学4年生", "小学5年生", "小学6年生", "中学生"].index(st.session_state.grade)
    )
    st.session_state.grade = selected_grade

    # --- クイズを出題するボタン（裏側でAIが動く） ---
    if st.button("🗡️ 新しい問題に挑戦する！", use_container_width=True):
        # ユーザーには「問題を準備中」とだけ見せる
        with st.spinner("新しい問題を準備中... しばらく待ってね！ぐるぐる...🤔"):
            try:
                # 裏側でAIが問題を生成
                prompt = f"""
                {selected_grade}向けの理科の4択クイズを1問作成してください。
                必ず以下のJSON形式のみで出力してください。Markdownのコードブロック(```json 等)は付けないでください。
                {{
                    "question": "問題文",
                    "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
                    "answer": "正解の選択肢の文字列（choicesの中の1つと完全一致させること）",
                    "explanation": "{selected_grade}にわかりやすい言葉と漢字で書かれた解説"
                }}
                """
                
                # APIリクエスト
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo", # または gpt-4o-mini など
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7 
                )
                
                ai_text = response.choices[0].message.content.strip()
                
                if ai_text.startswith("```json"): ai_text = ai_text[7:-3].strip()
                elif ai_text.startswith("```"): ai_text = ai_text[3:-3].strip()
                
                st.session_state.ai_quiz_data = json.loads(ai_text)
                st.session_state.ai_quiz_answered = False
                
                st.rerun() 
                
            except Exception as e:
                st.error("問題の準備に失敗しちゃった。もう一度「挑戦する」を押してみてね！")

    # --- 作成されたクイズの表示と回答処理 ---
    if st.session_state.ai_quiz_data:
        st.markdown("---")
        q_data = st.session_state.ai_quiz_data
        
        st.caption(f"難易度: {selected_grade} レベル")
        st.markdown(f"### Q. {q_data.get('question', '')}")
        
        user_choice = st.radio(
            "答えを選んでね:", 
            q_data.get("choices", []), 
            disabled=st.session_state.ai_quiz_answered, 
            index=None
        )
        
        if not st.session_state.ai_quiz_answered:
            if st.button("🚀 答える！"):
                if user_choice:
                    st.session_state.ai_quiz_answered = True
                    st.rerun()
                else:
                    st.warning("選択肢を選んでから「答える！」を押してね。")
        
        if st.session_state.ai_quiz_answered:
            correct_answer = q_data.get("answer", "")
            
            if user_choice == correct_answer:
                st.success("🎉 大正解！！すごい！")
                # 例: update_quiz_stats(st.session_state.user_name, True)
            else:
                st.error(f"残念！正解は「{correct_answer}」でした。")
                # 例: update_quiz_stats(st.session_state.user_name, False)
            
            st.info("📝 **解説**\n\n" + q_data.get("explanation", ""))
            
elif "📊 学習きろく" in page:
    st.title("📊 学習きろく")
    q_stats = get_quiz_stats(st.session_state.user_name)
    accuracy = (q_stats['correct'] / q_stats['total'] * 100) if q_stats['total'] > 0 else 0
    qc1, qc2, qc3, qc4 = st.columns(4)
    qc1.metric("挑戦回数", f"{q_stats['total']} 回")
    qc2.metric("正解数", f"{q_stats['correct']} 問")
    qc3.metric("正答率", f"{accuracy:.1f} %")
    qc4.metric("連続正解", f"{q_stats['streak']} 問")

    if os.path.exists(STATS_FILE):
        df = pd.read_csv(STATS_FILE, encoding="utf-8-sig")
        user_df = df[df['user_name'] == st.session_state.user_name]
        if not user_df.empty:
            total_chars = user_df['char_count'].sum()
            avg_speed = user_df['typing_speed'].mean()
            sc1, sc2 = st.columns(2)
            sc1.metric("入力文字数（合計）", f"{total_chars} 文字")
            sc2.metric("タイピング速度（平均）", f"{avg_speed:.1f} 文字/分")
            st.dataframe(user_df[['timestamp', 'user_message']].tail(10), use_container_width=True, hide_index=True)
        else: st.info("チャットのきろくがないみたい。ハカセに質問してみよう！")
    else: st.info("きろくファイルがありません。チャットを始めると記録されます。")

elif "👑 管理者画面" in page:
    st.title("👑 管理者専用ダッシュボード")
    
    if not st.session_state.admin_auth:
        st.info("先生・研究者向けの管理画面です。パスワードを入力してください。")
        pw = st.text_input("パスワード", type="password")
        if st.button("ログイン"):
            if pw == ADMIN_PW:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
    else:
        if st.button("🚪 ログアウト", key="logout_btn"):
            st.session_state.admin_auth = False
            st.rerun()

        tab1, tab2, tab3 = st.tabs(["📝 チャットログ", "🎯 クイズ成績", "⚙️ データ管理"])

        with tab1:
            st.subheader("ユーザー別 チャット利用状況")
            if os.path.exists(STATS_FILE):
                df_chat = pd.read_csv(STATS_FILE, encoding="utf-8-sig")
                if not df_chat.empty:
                    # 全体のグラフ
                    char_counts = df_chat.groupby("user_name")["char_count"].sum()
                    st.markdown("##### 📊 合計入力文字数")
                    st.bar_chart(char_counts)
                    
                    st.markdown("---")
                    st.markdown("##### 🔍 履歴の絞り込み")
                    
                    # 記録されているユーザー名の一覧を作成（「すべて」を先頭に追加）
                    user_list = ["すべて"] + list(df_chat["user_name"].dropna().unique())
                    selected_user = st.selectbox("確認したいユーザーを選んでください", user_list)
                    
                    # 選択したユーザーに合わせてデータを絞り込む
                    if selected_user == "すべて":
                        filtered_df = df_chat
                    else:
                        filtered_df = df_chat[df_chat["user_name"] == selected_user]
                        
                    # 絞り込んだ結果を表示
                    st.dataframe(filtered_df, use_container_width=True)
                    
                with open(STATS_FILE, "rb") as f:
                    st.download_button("📥 チャットログ(CSV)をダウンロード", f, file_name="user_stats.csv", mime="text/csv")
            else: st.write("まだチャットの記録がありません。")

        with tab2:
            st.subheader("ユーザー別 クイズ成績")
            if os.path.exists(QUIZ_STATS_FILE):
                q_data = load_json(QUIZ_STATS_FILE)
                if q_data:
                    df_quiz = pd.DataFrame.from_dict(q_data, orient='index')
                    st.markdown("##### 📊 正解数 / 挑戦回数")
                    if 'correct' in df_quiz.columns and 'total' in df_quiz.columns:
                        st.bar_chart(df_quiz[['correct', 'total']])
                    st.dataframe(df_quiz, use_container_width=True)
                else: st.write("データが空です。")
            else: st.write("まだクイズの記録がありません。")

        with tab3:
            st.subheader("⚙️ データリセット操作")
            st.warning("⚠️ ボタンを押すと研究データが消去されます。")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🗑️ チャットログを全消去", use_container_width=True):
                    if os.path.exists(STATS_FILE):
                        os.remove(STATS_FILE)
                        st.success("チャットログを消去しました。")
                        time.sleep(1)
                        st.rerun()
            with col2:
                if st.button("🗑️ クイズ成績を全消去", use_container_width=True):
                    if os.path.exists(QUIZ_STATS_FILE):
                        os.remove(QUIZ_STATS_FILE)
                        st.success("クイズ成績を消去しました。")
                        time.sleep(1)
                        st.rerun()
            with col3:
                if st.button("🗑️ ログイン記録を全消去", use_container_width=True):
                    if os.path.exists(STREAK_FILE):
                        os.remove(STREAK_FILE)
                        st.success("連続ログイン記録を消去しました。")
                        time.sleep(1)
                        st.rerun()