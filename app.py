import base64
from datetime import datetime
import io
import os
import time
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

# 保存用CSVファイル名
STATS_FILE = "user_stats.csv"


# データ保存用関数
def save_user_stat(user_name, char_count, typing_speed, unique_words, text):
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  new_data = pd.DataFrame([{
      "timestamp": now,
      "user_name": user_name,
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


# データ読み込み用関数
def load_user_data(user_name):
  if not os.path.exists(STATS_FILE):
    return pd.DataFrame()
  df = pd.read_csv(STATS_FILE)
  return df[df["user_name"] == user_name]


# 画像をクリアに保持してbase64変換する関数
def encode_image(image_bytes):
  img = Image.open(io.BytesIO(image_bytes))
  if img.mode in ("RGBA", "P"):
    img = img.convert("RGB")
  img.thumbnail((1200, 1200))
  buffered = io.BytesIO()
  img.save(buffered, format="JPEG", quality=90)
  return base64.b64encode(buffered.getvalue()).decode("utf-8")


# 2. サイドバーでのページ切替 ＆ ユーザー設定
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

  st.divider()
  st.header("⚙️ せってい")
  api_key = st.secrets.get("OPENAI_API_KEY", "")
  if not api_key:
    api_key = st.text_input("OpenAI APIキーを入力", type="password")

  selected_model = st.selectbox(
      "🧠 AIのモデル",
      ["gpt-4o", "gpt-4o-mini"],
      index=0,
      help="gpt-4oを選ぶと生き物や写真の特定精度が高くなります！",
  )

# セッション状態の初期化
if "last_send_time" not in st.session_state:
  st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0

# ==========================================
# 📄 ページ1: チャット画面
# ==========================================
if page == "💬 チャット":
  st.markdown(
      f"""
      <div style="background: linear-gradient(135deg, #FFB74D, #FFD54F); padding: 15px; border-radius: 20px; text-align: center; margin-bottom: 15px;">
          <h1 style="color: #5D4037; margin:0; font-size: 22px;">🔍 わくわく理科探検チャット 🎓</h1>
          <p style="color: #795548; margin: 5px 0 0 0; font-weight: bold;">ようこそ、{user_name} さん！</p>
      </div>
  """,
      unsafe_allow_html=True,
  )

  # システムプロンプト
  SYSTEM_PROMPT = """
    あなたは小学3年生の理科の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
    身近な自然や生き物、理科の不思議に興味を持てるよう優しく対話します。
    写真が送られてきた時は、特徴をよく観察してから生物の種類や名前を分かりやすく解説してください。
    小学1〜3年生で習う漢字を中心に使い、難しい漢字にはルビ（<ruby>漢字<rt>かんじ</rt></ruby>）を振ってください。
    回答は100〜150文字程度で、最後は答えやすい質問で締めくくってください。
    """

  if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "assistant",
            "content": (
                f"こんにちは！{user_name}さん🎓\nきょうは"
                " どんな「ふしぎ」を"
                " はっけんしたかな？写真や文章で教えてね！"
            ),
        },
    ]

  # 履歴表示
  for msg in st.session_state.messages:
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
    st.info(
        "📸"
        " 写真が準備できました！下の入力欄に文章を書くか、たすけぶねボタンを押してね。"
    )

  # 💬 お助けボタン（たすけぶね）
  st.caption("💬 たすけぶねボタン（文字を打つのに困った時は押してね！）:")
  col1, col2, col3 = st.columns(3)
  preset_input = None
  if col1.button("💡 ヒントちょうだい！"):
    preset_input = "ヒントをちょうだい！"
  if col2.button("❓ つぎのミッション！"):
    preset_input = "つぎのミッションをだして！"
  if col3.button("🔍 これ なにか教えて！"):
    preset_input = "これ（写真や疑問）について詳しく教えて！"

  # ✏️ ユーザーの文字入力欄
  user_input = st.chat_input("ここに メッセージや しつもんを かこう！")

  # たすけぶねボタンが押された場合はそれを送信テキストにする
  if preset_input:
    user_input = preset_input

  # 送信処理
  if user_input:
    if not api_key:
      st.error("👈 ひだりの「せってい」に APIキーを入力してね！")
    else:
      # タイピング速度 & 語彙力の計算
      now_time = time.time()
      elapsed_time = max(now_time - st.session_state.last_send_time, 1.0)
      st.session_state.last_send_time = now_time

      char_cnt = len(user_input)
      typing_speed = (char_cnt / elapsed_time) * 60  # 文字/分
      unique_chars = len(set(user_input))

      # データの保存（CSVへ記録）
      save_user_stat(
          user_name, char_cnt, typing_speed, unique_chars, user_input
      )

      # API送信用のコンテンツ構成
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

      st.session_state.messages.append({
          "role": "user",
          "content": user_input,
          "image": image_data,
          "api_content": api_content,
      })

      # API通信
      try:
        client = openai.OpenAI(api_key=api_key)
        with st.chat_message("assistant", avatar="🎓"):
          with st.spinner("ハカセが かんがえ中..."):
            system_msg = [
                m for m in st.session_state.messages if m["role"] == "system"
            ]
            recent_msgs = [
                m for m in st.session_state.messages if m["role"] != "system"
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

        st.session_state.messages.append(
            {"role": "assistant", "content": reply}
        )
        st.session_state.uploader_key += 1
        st.rerun()

      except Exception as e:
        st.error(f"エラーが発生しました: {e}")

# ==========================================
# 📊 ページ2: 成長グラフ画面（ダッシュボード）
# ==========================================
elif page == "📊 成長グラフ":
  st.title(f"📈 {user_name} さんの せいちょう レポート")

  df_user = load_user_data(user_name)

  if df_user.empty:
    st.info(
        "まだ データがありません！チャットで ハカセと"
        " お話ししてみてね！"
    )
  else:
    total_chars = df_user["char_count"].sum()
    avg_speed = df_user["typing_speed"].mean()

    all_text = "".join(df_user["text"].tolist())
    vocab_size = len(set(all_text))

    # 指標カードの表示
    col1, col2, col3 = st.columns(3)
    col1.metric("⭐ ぜんぶで うった もじ", f"{total_chars} もじ")
    col2.metric("⚡ へいきん タイピング速度", f"{int(avg_speed)} もじ/分")
    col3.metric("📚 つかった もじの 種類（語彙）", f"{vocab_size} 種類")

    st.divider()

    # 1. タイピング速度の推移グラフ
    st.subheader("⚡ タイピングスピードの へんか（文字/分）")
    st.line_chart(df_user.set_index("timestamp")["typing_speed"])

    # 2. 語彙の広がり（累積文字種類の増加）
    st.subheader("📚 つかえる もじの 広がり（累計）")
    vocab_growth = []
    current_vocab = set()
    for text in df_user["text"]:
      current_vocab.update(set(text))
      vocab_growth.append(len(current_vocab))
    df_user["vocab_growth"] = vocab_growth

    st.line_chart(df_user.set_index("timestamp")["vocab_growth"])

    # 3. 過去の送信履歴リスト
    with st.expander("📝 これまでの 入力きろくを 見る"):
      st.dataframe(
          df_user[
              ["timestamp", "char_count", "typing_speed", "text"]
          ].reverse()
      )