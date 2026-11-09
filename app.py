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

GRADE_OPTIONS = [
    "👦 小学1年生", "👦 小学2年生", "👦 小学3年生",
    "👦 小学4年生", "👦 小学5年生", "👦 小学6年生",
    "🧑 中学1年生", "🧑 中学2年生", "🧑 中学3年生",
    "🏫 高校生", "🎓 大人・一般",
]

# APIキー未入力時のダミーデータ
DEFAULT_CONTENT = {
    "experiment": {
        "title": "🔑 APIキーをいれてね",
        "desc": "左のメニューからAPIキーを設定すると、ハカセが今日の実験を考えてくれるよ！"
    },
    "problem": {
        "title": "🧪 今日の挑戦問題",
        "question": "APIキーを設定すると、ここに計算問題やクイズが出るよ！",
        "hint": "ヒントもここに出るよ。"
    },
    "trivia": {
        "物理": "APIキーを入れると豆知識が見られるよ！",
        "化学": "APIキーを入れると豆知識が見られるよ！",
        "生物": "APIキーを入れると豆知識が見られるよ！",
        "地学・宇宙": "APIキーを入れると豆知識が見られるよ！"
    }
}

# ==========================================
# 2. 関数定義
# ==========================================

def get_grade_category(grade_name):
    if any(g in grade_name for g in ["1年生", "2年生", "3年生"]) and "小学" in grade_name:
        return "小学低学年"
    elif any(g in grade_name for g in ["4年生", "5年生", "6年生"]) and "小学" in grade_name:
        return "小学高学年"
    else:
        return "中学生以上"

# --- 毎日のコンテンツをAIに生成させる関数 ---
def generate_daily_content(api_key, grade_name, model_name, seed_date):
    grade_cat = get_grade_category(grade_name)
    system_prompt = f"""あなたは理科の専門家です。対象読者（{grade_cat}）に合わせて、以下の3つのコンテンツをJSON形式で生成してください。（今日の日付: {seed_date}）

1. 家庭で安全にできる1日5分の簡単な理科実験
2. {grade_cat}向けの「物理」または「化学」の計算問題（※小学生の場合は算数を使った簡単な理科クイズ）
3. 4分野の豆知識

以下のJSONフォーマットで出力してください。
{{
  "experiment": {{
    "title": "実験のタイトル（絵文字を含む）",
    "desc": "実験の簡単な手順や解説（50〜80文字程度）"
  }},
  "problem": {{
    "title": "🧪 今日の挑戦問題（物理・化学など）",
    "question": "問題文（計算問題など）",
    "hint": "解くためのヒントや公式（答えは書かないこと！）"
  }},
  "trivia": {{
    "物理": "物理に関する驚きの豆知識（50文字程度）",
    "化学": "化学に関する驚きの豆知識（50文字程度）",
    "生物": "生物に関する驚きの豆知識（50文字程度）",
    "地学・宇宙": "地学・宇宙に関する驚きの豆知識（50文字程度）"
  }}
}}"""
    try:
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system_prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        return None

# --- 連続記録（ストリーク）管理 ---
def load_streaks():
    if os.path.exists(STREAK_FILE):
        with open(STREAK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_streaks(data):
    with open(STREAK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_streak(user_name):
    data = load_streaks()
    today_str = date.today().isoformat()
    if user_name not in data:
        data[user_name] = {"streak": 1, "last_date": today_str}
    else:
        last_date_str = data[user_name]["last_date"]
        if last_date_str != today_str:
            last_date = date.fromisoformat(last_date_str)
            if (date.today() - last_date).days == 1:
                data[user_name]["streak"] += 1
            else:
                data[user_name]["streak"] = 1
            data[user_name]["last_date"] = today_str
    save_streaks(data)
    return data[user_name]["streak"]

def get_streak(user_name):
    data = load_streaks()
    if user_name in data:
        last_date_str = data[user_name]["last_date"]
        last_date = date.fromisoformat(last_date_str)
        if (date.today() - last_date).days <= 1:
            return data[user_name]["streak"]
    return 0

# --- 学習記録（CSV）管理 ---
def save_user_stat(user_name, thread_id, thread_title, char_count, typing_speed, unique_words, text, role="user"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved_name = user_name.strip() if user_name.strip() else "探検者"
    new_data = pd.DataFrame([{
        "timestamp": now, "user_name": saved_name, "thread_id": thread_id,
        "thread_title": thread_title, "role": role, "char_count": char_count,
        "typing_speed": round(typing_speed, 1), "unique_words": unique_words, "text": text,
    }])
    if os.path.exists(STATS_FILE):
        new_data.to_csv(STATS_FILE, mode="a", index=False, header=False, encoding="utf-8-sig")
    else:
        new_data.to_csv(STATS_FILE, mode="w", index=False, header=True, encoding="utf-8-sig")

def load_user_data(user_name):
    if not os.path.exists(STATS_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(STATS_FILE)
        target_name = user_name.strip() if user_name.strip() else "探検者"
        return df[df["user_name"] == target_name]
    except Exception:
        return pd.DataFrame()

# --- プロンプト・画像処理 ---
def get_system_prompt(grade_name):
    base_role = "あなたは自然科学の学習を支援する親しみやすいパートナー「探検ハカセ」です。"
    qa_instruction = "\n【重要】回答の最後には必ず『---』で区切り、ユーザーが次に興味を持ちそうな「深掘り質問の候補」を3つ、箇条書きで提示してください。\n例:\n---\n1. なぜ〇〇は△△になるの？\n2. 〇〇以外の条件だとどうなる？\n3. 〇〇の仕組みを詳しく教えて！"

    if "小学" in grade_name:
        return f"{base_role}\n【対象】: {grade_name}\n・習っていない漢字はひらがなにするかルビを使用\n・明るく優しい言葉遣い\n・返信は100〜150文字程度\n{qa_instruction}"
    elif "中学" in grade_name:
        return f"{base_role}\n【対象】: {grade_name}\n・丁寧な「です・ます調」\n・化学式や物理公式を活用して理論的に解説\n{qa_instruction}"
    else:
        return f"{base_role}\n【対象】: {grade_name}\n・知的で論理的な「です・ます調」\n・専門用語を用いた深掘り解説\n{qa_instruction}"

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
if "last_send_time" not in st.session_state: st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "suggested_questions" not in st.session_state: st.session_state.suggested_questions = []
if "auto_send_msg" not in st.session_state: st.session_state.auto_send_msg = None

if "daily_content" not in st.session_state: st.session_state.daily_content = None
if "content_date_grade" not in st.session_state: st.session_state.content_date_grade = ""

def create_new_thread(system_prompt, grade_name):
    new_id = str(uuid.uuid4())
    thread_count = len(st.session_state.get("threads", {})) + 1
    is_child = "小学" in grade_name
    default_title = f"あたらしい おはなし {thread_count}" if is_child else f"新しいテーマ {thread_count}"
    greeting = f"こんにちは！【{grade_name}】向けの 探検スタートだよ！🎓\nどんなことを ハカセに 聞いてみる？" if is_child else f"こんにちは！探検ハカセです🎓【{grade_name}】モードで解説します。計算問題の答えもここで教えてね！"
    return new_id, {"title": default_title, "messages": [{"role": "system", "content": system_prompt}, {"role": "assistant", "content": greeting}]}

# CSSスタイル
st.markdown("""
    <style>
    .stApp { background-color: #FFFDE7 !important; color: #212121 !important; }
    .user-card, .exp-card, .prob-card { background-color: #FFFFFF; border: 2px solid #FFB74D; border-radius: 15px; padding: 12px 18px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    .exp-card { border-color: #4CAF50; background-color: #F1F8E9; }
    .prob-card { border-color: #AB47BC; background-color: #F3E5F5; }
    .stChatMessage { border-radius: 16px !important; padding: 10px 14px !important; margin-bottom: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. サイドバー
# ==========================================
with st.sidebar:
    st.title("🧭 メニュー")
    selected_grade = st.selectbox("学年を選んでね", GRADE_OPTIONS, index=GRADE_OPTIONS.index(st.session_state.selected_grade))
    if selected_grade != st.session_state.selected_grade:
        st.session_state.selected_grade = selected_grade
        new_id, new_thread = create_new_thread(get_system_prompt(selected_grade), selected_grade)
        if "threads" not in st.session_state: st.session_state.threads = {}
        st.session_state.threads[new_id] = new_thread
        st.session_state.current_thread_id = new_id
        st.session_state.suggested_questions = []
        st.rerun()

    active_prompt = get_system_prompt(selected_grade)
    st.divider()
    page = st.radio("ページ選択", ["💬 チャット", "📊 学習記録レポート"])

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
# 5. メイン画面（チャット or レポート）
# ==========================================
if "チャット" in page:
    current_thread = st.session_state.threads[st.session_state.current_thread_id]
    if current_thread["messages"][0]["role"] == "system":
        current_thread["messages"][0]["content"] = active_prompt

    # お名前＆ストリーク表示
    st.markdown('<div class="user-card">', unsafe_allow_html=True)
    u_col1, u_col2 = st.columns([2, 1])
    with u_col1:
        input_name = st.text_input("👤 あなたの おなまえ", value=st.session_state.user_name, key="global_user_name_input")
        if input_name != st.session_state.user_name:
            st.session_state.user_name = input_name
            st.rerun()
    with u_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.user_name.strip():
            st.success(f"🔥 実験・問題れんぞく: {get_streak(st.session_state.user_name)} 日目！")
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 日替わり要素の自動生成 (API経由)
    # ---------------------------------------------------------
    today_str = date.today().isoformat()
    current_state_key = f"{today_str}_{st.session_state.selected_grade}_{selected_model}"

    if not api_key:
        daily_data = DEFAULT_CONTENT
    else:
        if st.session_state.content_date_grade != current_state_key or st.session_state.daily_content is None:
            with st.spinner("🧠 ハカセが今日の問題と豆知識を考え中... (数秒かかります)"):
                new_data = generate_daily_content(api_key, st.session_state.selected_grade, selected_model, today_str)
                if new_data:
                    st.session_state.daily_content = new_data
                    st.session_state.content_date_grade = current_state_key
                    daily_data = new_data
                else:
                    st.error("コンテンツの生成に失敗しちゃった！もう一度画面を読み込むか、APIキーを確認してね。")
                    daily_data = DEFAULT_CONTENT
        else:
            daily_data = st.session_state.daily_content

    todays_exp = daily_data.get("experiment", {})
    todays_prob = daily_data.get("problem", {})
    todays_trivias = daily_data.get("trivia", {})
    exp_cat = get_grade_category(st.session_state.selected_grade)

    col_daily1, col_daily2 = st.columns(2)
    
    with col_daily1:
        # 実験カード表示
        st.markdown(f"""
            <div class="exp-card">
                <h5 style="margin-top:0;">⏱️ 本日の実験（{exp_cat}向け）</h5>
                <b>{todays_exp.get("title", "実験タイトル")}</b><br>
                <span style="font-size: 14px;">{todays_exp.get("desc", "説明")}</span>
            </div>
        """, unsafe_allow_html=True)
    
    with col_daily2:
        # 計算問題カード表示（追加した機能！）
        st.markdown(f"""
            <div class="prob-card">
                <h5 style="margin-top:0;">{todays_prob.get("title", "🧪 今日の挑戦問題")}</h5>
                <b style="font-size: 14px;">Q: {todays_prob.get("question", "問題文")}</b><br>
                <span style="font-size: 13px; color: #6a1b9a;">💡 ヒント: {todays_prob.get("hint", "ヒント")}</span>
            </div>
        """, unsafe_allow_html=True)

    # 豆知識カード表示（折りたたみ式できれいに！）
    st.markdown('<h5 style="margin-top:10px;">💡 今日の豆知識（タップで開く）</h5>', unsafe_allow_html=True)
    
    # 4つの豆知識を2列に分けて配置する
    t_cols = st.columns(2)
    for idx, (cat, trivia_text) in enumerate(todays_trivias.items()):
        with t_cols[idx % 2]:
            with st.expander(f"📚 【{cat}】の豆知識"):
                st.markdown(f"> {trivia_text}")
                if st.button("🗣️ ハカセに詳しく聞く", key=f"trivia_btn_{cat}"):
                    st.session_state.auto_send_msg = f"「{trivia_text}」という豆知識について、もっと詳しく教えて！"
                    st.rerun()

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # チャット履歴とUI
    # ---------------------------------------------------------
    non_system_msgs = [m for m in current_thread["messages"] if m["role"] != "system"]
    for msg in non_system_msgs:
        with st.chat_message(msg["role"], avatar="🎓" if msg["role"] == "assistant" else "👦"):
            if "image" in msg and msg["image"]: st.image(msg["image"], use_container_width=True)
            content = msg["content"]
            if msg["role"] == "assistant" and "---" in content:
                content = content.split("---")[0].strip()
            st.markdown(content, unsafe_allow_html=True)

    if st.session_state.suggested_questions:
        st.caption("💡 ハカセからの おすすめの質問（タップで聞けるよ！）")
        q_cols = st.columns(min(len(st.session_state.suggested_questions), 3))
        for i, q in enumerate(st.session_state.suggested_questions[:3]):
            if q_cols[i].button(q, key=f"sug_q_{i}"):
                st.session_state.auto_send_msg = q
                st.rerun()

    uploaded_file = st.file_uploader("📷 しゃしんを えらぶ", type=["jpg", "jpeg", "png"], key=f"uploader_{st.session_state.uploader_key}")
    user_input = st.chat_input("ここに メッセージや 答えを かこう！")
    
    if st.session_state.auto_send_msg:
        user_input = st.session_state.auto_send_msg
        st.session_state.auto_send_msg = None

    if user_input:
        if not api_key: st.error("👈 APIキーを入力してね！")
        else:
            current_time = time.time()
            elapsed_time = current_time - st.session_state.last_send_time
            st.session_state.last_send_time = current_time
            
            char_count = len(user_input)
            typing_speed = char_count / (elapsed_time / 60) if elapsed_time > 0 else 0
            unique_words = len(set(user_input))

            save_user_stat(
                user_name=st.session_state.user_name,
                thread_id=st.session_state.current_thread_id,
                thread_title=current_thread["title"],
                char_count=char_count,
                typing_speed=typing_speed,
                unique_words=unique_words,
                text=user_input
            )

            # 実験報告か、問題の答えらしき文字があったらストリーク追加
            if any(word in user_input for word in ["実験", "できた", "結果", "やった", "答え", "わかった"]):
                if st.session_state.user_name.strip():
                    update_streak(st.session_state.user_name)
                    st.toast("🔥 実験・問題クリア！れんぞく記録がのびたよ！", icon="🎉")

            if current_thread["title"].startswith("あたらしい") and len(current_thread["messages"]) <= 2:
                current_thread["title"] = f"💬 {user_input[:12]}..."
            
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

else:
    st.title("📊 学習記録レポート")
    df = load_user_data(st.session_state.user_name)
    if df.empty:
        st.info("まだデータがないみたい！チャットでお話ししてみてね。")
    else:
        st.success(f"🔥 現在の実験・問題 連続記録: {get_streak(st.session_state.user_name)} 日目！")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("総メッセージ数", f"{len(df)} 回")
        col2.metric("総入力文字数", f"{df['char_count'].sum()} 文字")
        col3.metric("平均タイピング速度", f"{round(df['typing_speed'].mean(), 1)} 文字/分")
        
        st.subheader("📝 これまでの会話データ")
        st.dataframe(df.tail(20).sort_values("timestamp", ascending=False))