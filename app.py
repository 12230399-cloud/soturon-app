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


# 画像をクリアに保持してbase64変換する関数
def encode_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail((1200, 1200))  # 識別精度を高めるため大きめのサイズを保持
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=90)
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

    # 精度の切り替えオプション（gpt-4o: 高精度, gpt-4o-mini: 高速・軽量）
    selected_model = st.selectbox(
        "🧠 AIのモデル（精度設定）",
        ["gpt-4o", "gpt-4o-mini"],
        index=0,
        help="gpt-4oは写真の生き物や魚の識別精度がとても高くなります！",
    )

    st.divider()
    st.info("💡 対話ログは `chat_log.csv` に自動保存されます。")

# 5. システムプロンプト（高精度な観察ステップを導入）
SYSTEM_PROMPT = """
あなたは小学3年生の理科の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
相手は小学3年生の児童です。身近な自然や生き物、理科の不思議に興味を持てるよう優しく対話します。

【写真（画像）が送られてきた場合ルール】
1. 写真を観察する時は、いきなり結論を出さず、まず「色、形、模様、ヒレや足、特徴的な部分」を慎重に観察してください。
2. 観察した特徴をもとに、生き物・魚・昆虫・植物などの「名前や種類」を特定・推測して教えてあげてください。
3. もし写真がぼやけていたり、角度的に判別が難しい場合は、可能性が高い候補をいくつか挙げた上で「もっと横から撮るとはっきり分かるよ！」などアドバイスをしてください。

【重要：言葉遣いと漢字の制限】
- 原則として「小学1年生〜3年生で習う漢字」のみを使用してください。
- 4年生以上で習う難しい漢字や専門用語は使わず、ひらがなにするかルビタグを使ってふりがなを振ってください。
- ルビの書き方例: <ruby>観察<rt>かんさつ</rt></ruby>、<ruby>特徴<rt>とくちょう</rt></ruby>、<ruby>種類<rt>しゅるい</rt></ruby>

【会話を長続きさせるためのルール】
1. 明るくやさしい言葉遣い（〜だよ！、〜かな？、すごいね！）。
2. 返信は100〜150文字程度でコンパクトにする。
3. 必ず『具体的に答えやすい質問』で終わる（例：「どこで見つけたのかな？」「触るとどんな感じだった？」など）。
"""

# 6. 会話履歴の初期化
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "assistant",
            "content": (
                "こんにちは！<ruby>探検<rt>たんけん</rt></ruby>ハカセだよ🎓\nハカセと一緒に、身の回りの「ふしぎ」を見つける<ruby>探検<rt>たんけん</rt></ruby>に出かけよう！\n\n【きょうのミッション】\n気になる写真があったら選んで、下に知りたいことを文章で打って送ってみてね！"
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

# 8. 写真の選択エリア（選ぶだけでは送信されません）
uploaded_file = st.file_uploader(
    "📷 しゃしんを えらぶ（選んだあと、一番下の入力欄に文章を書いて送ってね）",
    type=["jpg", "jpeg", "png"],
    key=f"uploader_{st.session_state.uploader_key}",
)

if uploaded_file:
    st.info("📸 写真が準備できました！一番下の欄に文章（「この名前は？」など）を入力して送信してね。")

# 入力補助ボタン（たすけぶね）
st.caption("💬 たすけぶねボタン（押すと文字が入るよ）:")
col1, col2, col3 = st.columns(3)
preset_input = None
if col1.button("💡 ヒントちょうだい！"):
    preset_input = "ヒントをちょうだい！"
if col2.button("❓ つぎのミッション！"):
    preset_input = "つぎのミッションをだして！"
if col3.button("🔍 これ なにか教えて！"):
    preset_input = "これについて詳しく教えて！"

# 9. 入力処理（ユーザーが文字を入力して「送信」を押した時だけAPIを動かす）
user_input = st.chat_input("ここに へんじや しつもんを かこう！")
if preset_input:
    user_input = preset_input

# ★重要★ uploaded_file だけでは送信せず、user_input（送信操作）があった時のみ実行！
if user_input:
    if not api_key:
        st.error("👈 ひだりの「せってい」に OpenAI APIキー を入れてからおくってね！")
    else:
        text_content = user_input
        st.session_state.total_chars += len(text_content)

        api_content = [{"type": "text", "text": text_content}]

        image_data = None
        if uploaded_file:
            image_data = uploaded_file.getvalue()
            base64_img = encode_image(image_data)
            api_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_img}",
                    "detail": "high",  # 観察精度を高める最高画質モード
                },
            })

        user_msg = {
            "role": "user",
            "content": text_content,
            "image": image_data,
            "api_content": api_content,
        }
        st.session_state.messages.append(user_msg)

        # API送信用のメッセージ組み立て（直近6件）
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
                with st.spinner("ハカセが じっくり かんさつ中..."):
                    response = client.chat.completions.create(
                        model=selected_model,  # サイドバーで選択したモデル（高精度のgpt-4o）を使用
                        messages=api_messages,
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

            # 送信成功後、写真選択枠をクリア
            st.session_state.uploader_key += 1
            st.rerun()

        except openai.RateLimitError:
            st.warning("⌛ ハカセが考えすぎて少し疲れちゃったみたい！5秒くらい待ってから、もう一度送ってみてね！")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")