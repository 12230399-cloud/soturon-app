import base64
from datetime import datetime
import io
import os
import time
import uuid
import openai
import pandas as pd
from PIL import Image
import streamlit as st

# 1. ページ基本設定
st.set_page_config(
    page_title="わくわく理科探検チャット",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="expanded",
)

STATS_FILE = "user_stats.csv"
SYSTEM_PROMPT = """
あなたは小学3年生の理科の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
身近な自然や生き物、理科の不思議に興味を持てるよう優しく対話します。
写真が送られてきた時は、特徴をよく観察してから生物の種類や名前を分かりやすく解説してください。
小学1〜3年生で習う漢字を中心に使い、難しい漢字にはルビ（<ruby>漢字<rt>かんじ</rt></ruby>）を振ってください。
回答は100〜150文字程度で、最後は答えやすい質問で締めくくってください。
"""


# --- データ保存・読み込み ---
def save_user_stat(
    user_name,
    thread_id,
    thread_title,
    char_count,
    typing_speed,
    unique_words,
    text,
    role="user",
):
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  new_data = pd.DataFrame([{
      "timestamp": now,
      "user_name": user_name,
      "thread_id": thread_id,
      "thread_title": thread_title,
      "role": role,
      "char_count": char_count,
      "typing_speed": round(typing_speed, 1),
      "unique_words": unique_words,
      "text": text,
  }])

  if os.path.exists(STATS_FILE):
    new_data.to_csv(
        STATS_FILE, mode="a", index=False, header=False, encoding="utf-8-sig"
    )
  else:
    new_data.to_csv(
        STATS_FILE, mode="w", index=False, header=True, encoding="utf-8-sig"
    )


def load_user_data(user_name):
  if not os.path.exists(STATS_FILE):
    return pd.DataFrame()
  try:
    df = pd.read_csv(STATS_FILE)
    return df[df["user_name"] == user_name]
  except Exception:
    return pd.DataFrame()


def encode_image(image_bytes):
  img = Image.open(io.BytesIO(image_bytes))
  if img.mode in ("RGBA", "P"):
    img = img.convert("RGB")
  img.thumbnail((1200, 1200))
  buffered = io.BytesIO()
  img.save(buffered, format="JPEG", quality=90)
  return base64.b64encode(buffered.getvalue()).decode("utf-8")


# --- セッション初期化 ---
if "threads" not in st.session_state:
  # {thread_id: {"title": "おはなし 1", "messages": [...]}}
  initial_id = str(uuid.uuid4())
  st.session_state.threads = {
      initial_id: {
          "title": "あたらしい おはなし 1",
          "messages": [
              {"role": "system", "content": SYSTEM_PROMPT},
              {
                  "role": "assistant",
                  "content": (
                      "こんにちは！探検ハカセだよ🎓\nきょうは"
                      " どんな「ふしぎ」を"
                      " はっけんしたかな？写真や文章で教えてね！"
                  ),
              },
          ],
      }
  }
  st.session_state.current_thread_id = initial_id

if "last_send_time" not in st.session_state:
  st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0


# 新規チャット作成関数
def create_new_thread():
  new_id = str(uuid.uuid4())
  thread_count = len(st.session_state.threads) + 1
  st.session_state.threads[new_id] = {
      "title": f"あたらしい おはなし {thread_count}",
      "messages": [
          {"role": "system", "content": SYSTEM_PROMPT},
          {
              "role": "assistant",
              "content": (
                  "新しい探検のスタートだね！🎓\nどんなことを"
                  " はかせに 聞いてみる？"
              ),
          },
      ],
  }
  st.session_state.current_thread_id = new_id


# --- CSSスタイル ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFFDE7 !important;
        color: #212121 !important;
    }
    .main .block-container {
        max-width: 800px;
        padding-top: 1rem;
    }
    .chat-header {
        background: linear-gradient(135deg, #FFB74D, #FFD54F);
        padding: 12px 20px;
        border-radius: 18px;
        text-align: center;
        margin-bottom: 15px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.08);
    }
    .chat-header h2 {
        color: #5D4037;
        margin: 0;
        font-size: 20px;
    }
    .chat-header p {
        color: #795548;
        margin: 4px 0 0 0;
        font-size: 13px;
        font-weight: bold;
    }
    .stChatMessage {
        border-radius: 16px !important;
        padding: 10px 14px !important;
        margin-bottom: 10px !important;
    }
    rt {
        font-size: 0.65em;
        color: #E65100;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- サイドバー (ナビゲーション＆スレッド切替) ---
with st.sidebar:
  st.title("🧭 メニュー")
  page = st.radio("ページを えらんでね", ["💬 チャット", "📊 成長グラフ"])

  st.divider()
  st.header("👤 ユーザー設定")
  user_name = st.text_input(
      "あなたの おなまえ",
      value="たろう",
      help="名前を変えると自分の記録が残るよ！",
  )

  # CSVから会話スレッドを復元（ユーザー名が変わった時など）
  if (
      "current_user" not in st.session_state
      or st.session_state.current_user != user_name
  ):
    st.session_state.current_user = user_name
    df_user_data = load_user_data(user_name)

    if not df_user_data.empty and "thread_id" in df_user_data.columns:
      restored_threads = {}
      grouped = df_user_data.groupby("thread_id")
      for tid, group in grouped:
        title = group["thread_title"].iloc[0] if "thread_title" in group.columns else "過去のおはなし"
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for _, row in group.iterrows():
          role = row.get("role", "user")
          if pd.isna(role):
            role = "user"
          msgs.append({"role": role, "content": str(row["text"])})
        restored_threads[tid] = {"title": title, "messages": msgs}

      if restored_threads:
        st.session_state.threads = restored_threads
        st.session_state.current_thread_id = list(restored_threads.keys())[-1]

  if page == "💬 チャット":
    st.divider()
    st.header("💬 話題（チャット一覧）")

    # 新しいチャットを作るボタン
    if st.button("➕ あたらしい おはなし", use_container_width=True):
      create_new_thread()
      st.rerun()

    # スレッド（話題）リストの選択
    thread_options = {
        tid: data["title"] for tid, data in st.session_state.threads.items()
    }
    selected_thread_id = st.radio(
        "これまでの おはなし:",
        options=list(thread_options.keys()),
        format_func=lambda x: thread_options[x],
        index=list(thread_options.keys()).index(
            st.session_state.current_thread_id
        ),
    )
    st.session_state.current_thread_id = selected_thread_id

  st.divider()
  st.header("💾 バックアップ")
  if os.path.exists(STATS_FILE):
    with open(STATS_FILE, "rb") as f:
      st.download_button(
          label="📥 記録（CSV）を保存する",
          data=f,
          file_name=f"理科探検きろく_{user_name}.csv",
          mime="text/csv",
      )

  uploaded_csv = st.file_uploader("📤 過去の記録（CSV）を読込", type=["csv"])
  if uploaded_csv is not None:
    try:
      df_uploaded = pd.read_csv(uploaded_csv)
      df_uploaded.to_csv(STATS_FILE, index=False, encoding="utf-8-sig")
      st.success("過去の記録を読み込みました！再読み込みしてね。")
    except Exception:
      st.error("ファイルの読み込みに失敗しました。")

  st.divider()
  st.header("⚙️ せってい")
  api_key = st.secrets.get("OPENAI_API_KEY", "")
  if not api_key:
    api_key = st.text_input("OpenAI APIキーを入力", type="password")

  selected_model = st.selectbox("🧠 AIのモデル", ["gpt-4o", "gpt-4o-mini"], index=0)


# ==========================================
# 📄 ページ1: チャット画面
# ==========================================
if page == "💬 チャット":
  current_thread = st.session_state.threads[st.session_state.current_thread_id]

  # 現在の話題ヘッダーを表示
  st.markdown(
      f"""
      <div class="chat-header">
          <h2>🔍 {current_thread['title']} 🎓</h2>
          <p>たんけんしゃ: {user_name} さん</p>
      </div>
  """,
      unsafe_allow_html=True,
  )

  # 会話履歴の描画
  for msg in current_thread["messages"]:
    if msg["role"] != "system":
      avatar = "🎓" if msg["role"] == "assistant" else "👦"
      with st.chat_message(msg["role"], avatar=avatar):
        if "image" in msg and msg["image"]:
          st.image(msg["image"], use_container_width=True)
        st.markdown(msg["content"], unsafe_allow_html=True)

  # 📷 写真選択エリア
  uploaded_file = st.file_uploader(
      "📷 しゃしんを えらぶ（選んだあと、下に文章を打ってね）",
      type=["jpg", "jpeg", "png"],
      key=f"uploader_{st.session_state.uploader_key}",
  )

  if uploaded_file:
    st.info("📸 写真が準備できました！下の入力欄に質問を書いて送信してね。")

  # 💬 たすけぶねボタン
  st.caption("💬 たすけぶねボタン（文字を打つのに困った時は押してね！）:")
  col1, col2, col3 = st.columns(3)
  preset_input = None
  if col1.button("💡 ヒントちょうだい！"):
    preset_input = "ヒントをちょうだい！"
  if col2.button("❓ つぎのミッション！"):
    preset_input = "つぎのミッションをだして！"
  if col3.button("🔍 これ なにか教えて！"):
    preset_input = "これ（写真や疑問）について詳しく教えて！"

  # ✏️ 入力エリア
  user_input = st.chat_input("ここに メッセージや しつもんを かこう！")
  if preset_input:
    user_input = preset_input

  # 送信処理
  if user_input:
    if not api_key:
      st.error("👈 ひだりの「せってい」に APIキーを入力してね！")
    else:
      # 初回発言時に自動で話題タイトルをつける（例: 先頭12文字）
      if (
          current_thread["title"].startswith("あたらしい おはなし")
          and len(current_thread["messages"]) <= 2
      ):
        short_title = user_input[:12] + ("..." if len(user_input) > 12 else "")
        current_thread["title"] = f"💬 {short_title}"

      now_time = time.time()
      elapsed_time = max(now_time - st.session_state.last_send_time, 1.0)
      st.session_state.last_send_time = now_time

      char_cnt = len(user_input)
      typing_speed = (char_cnt / elapsed_time) * 60
      unique_chars = len(set(user_input))

      # ログを保存（スレッドID・話題タイトル付き）
      save_user_stat(
          user_name,
          st.session_state.current_thread_id,
          current_thread["title"],
          char_cnt,
          typing_speed,
          unique_chars,
          user_input,
          role="user",
      )

      api_content = [{"type": "text", "text": user_input}]
      image_data = None
      if uploaded_file:
        image_data = uploaded_file.getvalue()
        base64_img = encode_image(image_data)
        api_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}",
                "detail": "high",
            },
        })

      current_thread["messages"].append({
          "role": "user",
          "content": user_input,
          "image": image_data,
          "api_content": api_content,
      })

      try:
        client = openai.OpenAI(api_key=api_key)
        with st.chat_message("assistant", avatar="🎓"):
          with st.spinner("ハカセが かんがえ中..."):
            system_msg = [
                m for m in current_thread["messages"] if m["role"] == "system"
            ]
            recent_msgs = [
                m for m in current_thread["messages"] if m["role"] != "system"
            ][-6:]
            api_msgs = [
                {"role": "system", "content": system_msg[0]["content"]}
            ] + [
                {
                    "role": m["role"],
                    "content": m.get("api_content", m["content"]),
                }
                for m in recent_msgs
            ]

            res = client.chat.completions.create(
                model=selected_model, messages=api_msgs
            )
            reply = res.choices[0].message.content
            st.markdown(reply, unsafe_allow_html=True)

        current_thread["messages"].append(
            {"role": "assistant", "content": reply}
        )

        save_user_stat(
            user_name,
            st.session_state.current_thread_id,
            current_thread["title"],
            len(reply),
            0,
            len(set(reply)),
            reply,
            role="assistant",
        )

        st.session_state.uploader_key += 1
        st.rerun()

      except Exception as e:
        st.error(f"エラーが発生しました: {e}")

# ==========================================
# 📊 ページ2: 成長グラフ画面
# ==========================================
elif page == "📊 成長グラフ":
  st.title(f"📈 {user_name} さんの せいちょう レポート")

  df_all = load_user_data(user_name)

  if df_all.empty:
    st.info(
        "まだ データがありません！チャットで ハカセと"
        " お話ししてみてね！"
    )
  else:
    df_user = (
        df_all[df_all["role"] == "user"]
        if "role" in df_all.columns
        else df_all
    )

    if df_user.empty:
      st.info("まだ チャットの送信データがありません！")
    else:
      total_chars = df_user["char_count"].sum()
      avg_speed = df_user["typing_speed"].mean()

      all_text = "".join(df_user["text"].dropna().tolist())
      vocab_size = len(set(all_text))

      col1, col2, col3 = st.columns(3)
      col1.metric("⭐ ぜんぶで うった もじ", f"{total_chars} もじ")
      col2.metric("⚡ へいきん タイピング速度", f"{int(avg_speed)} もじ/分")
      col3.metric("📚 つかった もじの 種類（語彙）", f"{vocab_size} 種類")

      st.divider()

      st.subheader("⚡ タイピングスピードの へんか（文字/分）")
      st.line_chart(df_user.set_index("timestamp")["typing_speed"])

      st.subheader("📚 つかえる もじの 広がり（累計）")
      vocab_growth = []
      current_vocab = set()
      for text in df_user["text"].dropna():
        current_vocab.update(set(str(text)))
        vocab_growth.append(len(current_vocab))
      df_user["vocab_growth"] = vocab_growth

      st.line_chart(df_user.set_index("timestamp")["vocab_growth"])

      with st.expander("📝 これまでの 入力きろくを 見る"):
        display_cols = ["timestamp", "thread_title", "char_count", "typing_speed", "text"]
        available_cols = [c for c in display_cols if c in df_user.columns]
        st.dataframe(df_user[available_cols].iloc[::-1])