import base64
from datetime import datetime
import io
import os
import openai
import pandas as pd
from PIL import Image
import streamlit as st

# 1. ページ基本設定
st.set_page_config(
    page_title="わくわく理科探検チャット",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 2. セッション状態の初期化
if "total_chars" not in st.session_state:
  st.session_state.total_chars = 0

if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0


# 魚などの識別精度を高めるため、画質・解像度を確保してbase64変換する関数
def encode_image(image_bytes):
  img = Image.open(io.BytesIO(image_bytes))
  if img.mode in ("RGBA", "P"):
    img = img.convert("RGB")
  img.thumbnail((1024, 1024))  # 魚の特徴が読める解像度を保持
  buffered = io.BytesIO()
  img.save(buffered, format="JPEG", quality=85)
  return base64.b64encode(buffered.getvalue()).decode("utf-8")


# 3. カスタムCSS
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFFDE7 !important;
        color: #212121 !important;
    }
    .main .block-container {
        max-width: 800px;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1rem;
    }
    .title-box {
        background: linear-gradient(135deg, #FFB74D, #FFD54F);
        padding: 15px 20px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .title-box h1 {
        color: #5D4037 !important;
        font-size: clamp(18px, 4vw, 26px);
        margin: 0;
    }
    .title-box p {
        color: #795548 !important;
        font-size: clamp(12px, 2.5vw, 15px);
        margin-top: 5px;
        font-weight: bold;
    }
    .status-bar {
        background-color: #FFFFFF;
        border: 2px solid #FFCA28;
        border-radius: 15px;
        padding: 8px 15px;
        text-align: center;
        font-weight: bold;
        color: #5D4037;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        font-size: clamp(13px, 3vw, 16px);
    }
    .stChatMessage {
        border-radius: 18px !important;
        padding: 10px 14px !important;
        margin-bottom: 8px !important;
        font-size: clamp(14px, 3vw, 16px) !important;
    }
    .stChatMessage, .stChatMessage p, .stChatMessage span, .stChatMessage div {
        color: #212121 !important;
    }
    rt {
        font-size: 0.65em;
        color: #E65100;
        font-weight: bold;
    }
    div[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #E1F5FE !important;
        border: 2px solid #81D4FA !important;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #E8F5E9 !important;
        border: 2px solid #A5D6A7 !important;
    }
    .stChatInputContainer {
        border-radius: 25px !important;
        border: 3px solid #FFB74D !important;
    }
    .stChatInputContainer textarea {
        color: #212121 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# タイトル表示
st.markdown(
    """
    <div class="title-box">
        <h1>🔍 わくわく<ruby>理科<rt>りか</rt></ruby><ruby>探検<rt>たんけん</rt></ruby>チャット 🎓</h1>
        <p>ハカセと いっしょに ふしぎを はっけんしよう！</p>
    </div>
""",
    unsafe_allow_html=True,
)

# 探検レベル表示
level = (st.session_state.total_chars // 30) + 1
st.markdown(
    f"""
    <div class="status-bar">
        ⭐ うった もじの かず: <b>{st.session_state.total_chars}</b> もじ ｜ 🏆 たんけんレベル: <b>Lv.{level}</b>
    </div>
""",
    unsafe_allow_html=True,
)

# 4. APIキーの自動取得
api_key = st.secrets.get("OPENAI_API_KEY", "")

with st.sidebar:
  st.header("⚙️ せってい")
  if not api_key:
    api_key = st.text_input(
        "OpenAI APIキーを入力", type="password", help="sk-...を入力"
    )
  else:
    st.success("🗝️ APIキーは自動で読み込まれています！")
  st.divider()
  st.info("💡 対話ログは `chat_log.csv` に自動保存されます。")

# 5. システムプロンプト（魚や生き物の特定ルールを追加）
SYSTEM_PROMPT = """
あなたは小学3年生の理科の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
相手は小学3年生の児童です。身近な自然や理科の不思議に興味を持てるよう優しく対話します。

【写真（画像）が送られてきた場合ルール】
1. 写真に写っているもの（魚、生き物、昆虫、植物、空など）の形・色・模様などの特徴をよく観察し、名前や種類（例：「〇〇という魚だね！」「〇〇の葉っぱかな？」）を特定・推測して教えてあげてください。
2. 魚や生き物の場合は、ヒレや体模様の特徴を教えてあげながら、どんな場所で暮らしているかなどの面白ポイントを説明してください。
3. もし元気がない状態なら、理由とお世話のしかたを優しく教えてあげてください。

【重要：言葉遣いと漢字の制限】
- 原則として「小学1年生〜3年生で習う漢字」のみを使用してください。
- 4年生以上で習う難しい漢字や専門用語は使わず、ひらがなにするかルビタグを使ってふりがなを振ってください。
- ルビの書き方例: <ruby>観察<rt>かんさつ</rt></ruby>、<ruby>魚<rt>さかな</rt></ruby>、<ruby>特徴<rt>とくちょう</rt></ruby>

【会話を長続きさせるためのルール】
1. 明るくやさしい言葉遣い（〜だよ！、〜かな？、すごいね！）。
2. 返信は100〜150文字程度でコンパクトにする。
3. 必ず『具体的に答えやすい質問』で終わる（例：「どこで見つけた魚かな？」「泳ぐのははやかったかな？」など）。
"""

# 6. 会話履歴の初期化
if "messages" not in st.session_state:
  st.session_state.messages = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {
          "role": "assistant",
          "content": (
              "こんにちは！<ruby>探検<rt>たんけん</rt></ruby>ハカセだよ🎓\nハカセと一緒に、身の回りの「ふしぎ」を見つける<ruby>探検<rt>たんけん</rt></ruby>に出かけよう！\n\n【きょうのミッション】\nつかまえた魚や生き物、気になった植物の「写真」があったら送ってみてね！質問もいっしょに書けるよ！"
          ),
      },
  ]

# 7. 会話の表示
for msg in st.session_state.messages:
  if msg["role"] != "system":
    avatar = "🎓" if msg["role"] == "assistant" else "👦"
    with st.chat_message(msg["role"], avatar=avatar):
      if "image" in msg and msg["image"]:
        st.image(msg["image"], use_container_width=True)
      st.markdown(msg["content"], unsafe_allow_html=True)

# 写真アップロードエリア
uploaded_file = st.file_uploader(
    "📷 しゃしんを えらぶ（クリックして えらぶ / パシャリと とる）",
    type=["jpg", "jpeg", "png"],
    key=f"uploader_{st.session_state.uploader_key}",
)

# 写真が選択されている場合の案内表示
if uploaded_file:
  st.info(
      "📌 写真がセットされました！下の入力欄に「この魚の名前は？」などメッセージを入れて送信してね！"
  )

# 入力補助ボタン（たすけぶね）
st.caption("💬 たすけぶねボタン（おすと すぐに へんじが できるよ）:")
col1, col2, col3 = st.columns(3)
preset_input = None
if col1.button("💡 ヒントちょうだい！"):
  preset_input = "ヒントをちょうだい！"
if col2.button("❓ つぎのミッション！"):
  preset_input = "つぎのミッションをだして！"
if col3.button("🐟 このお魚なにかな？"):
  preset_input = "写真のお魚（さかな）の名前や特徴（とくちょう）を教えて！"

# 8. 入力処理
user_input = st.chat_input("ここに へんじを かこう！")
if preset_input:
  user_input = preset_input

if user_input or uploaded_file:
  if not api_key:
    st.error(
        "👈 ひだりの「せってい」に OpenAI APIキー を入れてからおくってね！"
    )
  else:
    text_content = (
        user_input if user_input else "しゃしんを おくったよ！なにか教えて！"
    )
    st.session_state.total_chars += len(text_content)

    api_content = []
    api_content.append({"type": "text", "text": text_content})

    image_data = None
    if uploaded_file:
      image_data = uploaded_file.getvalue()
      base64_img = encode_image(image_data)
      api_content.append({
          "type": "image_url",
          "image_url": {
              "url": f"data:image/jpeg;base64,{base64_img}",
              "detail": "high",  # 魚のヒレや模様の特定精度を高める高解像度モード
          },
      })

    user_msg = {
        "role": "user",
        "content": text_content,
        "image": image_data,
        "api_content": api_content,
    }
    st.session_state.messages.append(user_msg)

    # API送信用のメッセージ組み立て（直近6件に絞ってトークン節約）
    system_msg = [m for m in st.session_state.messages if m["role"] == "system"]
    other_msgs = [m for m in st.session_state.messages if m["role"] != "system"]
    recent_msgs = other_msgs[-6:]

    api_messages = []
    for m in system_msg:
      api_messages.append({"role": "system", "content": m["content"]})
    for m in recent_msgs:
      if m["role"] == "user":
        content_to_send = m.get("api_content", m["content"])
        api_messages.append({"role": "user", "content": content_to_send})
      elif m["role"] == "assistant":
        api_messages.append({"role": "assistant", "content": m["content"]})

    try:
      client = openai.OpenAI(api_key=api_key)
      with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("ハカセが しゃしんを かんさつ中..."):
          response = client.chat.completions.create(
              model="gpt-4o-mini", messages=api_messages
          )
          bot_reply = response.choices[0].message.content
          st.markdown(bot_reply, unsafe_allow_html=True)

      st.session_state.messages.append(
          {"role": "assistant", "content": bot_reply}
      )

      # ログの自動保存
      log_df = pd.DataFrame([{
          "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "user_input": text_content,
          "has_image": True if uploaded_file else False,
          "bot_response": bot_reply,
          "total_chars": st.session_state.total_chars,
      }])
      log_file = "chat_log.csv"
      file_exists = os.path.exists(log_file)
      log_df.to_csv(
          log_file,
          mode="a",
          index=False,
          header=not file_exists,
          encoding="utf-8-sig",
      )

      # 送信成功後、写真欄をクリア（キー切り替え）
      st.session_state.uploader_key += 1
      st.rerun()

    except openai.RateLimitError:
      st.warning(
          "⌛ ハカセが考えすぎて少し疲れちゃったみたい！5秒くらい待ってから、もう一度送ってみてね！"
      )
    except Exception as e:
      st.error(f"エラーが発生しました: {e}")