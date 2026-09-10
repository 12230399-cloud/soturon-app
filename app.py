from datetime import datetime
import os
import openai
import pandas as pd
import streamlit as st

# 1. ページ基本設定
st.set_page_config(
    page_title="わくわく理科探検チャット",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 2. セッション状態（入力文字数）の初期化
if "total_chars" not in st.session_state:
  st.session_state.total_chars = 0

# 3. 画面サイズ最適化 & ポップデザインのカスタムCSS
st.markdown(
    """
    <style>
    /* 全体の背景色と基本文字色 */
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

    /* タイトルエリア */
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

    /* 探検レベルバー */
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

    /* メッセージ吹き出し */
    .stChatMessage {
        border-radius: 18px !important;
        padding: 10px 14px !important;
        margin-bottom: 8px !important;
        font-size: clamp(14px, 3vw, 16px) !important;
    }
    
    .stChatMessage, .stChatMessage p, .stChatMessage span, .stChatMessage div {
        color: #212121 !important;
    }

    /* ふりがな（ルビ）の装飾 */
    rt {
        font-size: 0.65em;
        color: #E65100;
        font-weight: bold;
    }

    /* ユーザーメッセージ */
    div[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #E1F5FE !important;
        border: 2px solid #81D4FA !important;
    }

    /* AIメッセージ */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #E8F5E9 !important;
        border: 2px solid #A5D6A7 !important;
    }

    /* 入力フォーム */
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

# タイトル表示（やさしい言葉遣い）
st.markdown(
    """
    <div class="title-box">
        <h1>🔍 わくわく<ruby>理科<rt>りか</rt></ruby><ruby>探検<rt>たんけん</rt></ruby>チャット 🎓</h1>
        <p>ハカセと いっしょに ふしぎを はっけんしよう！</p>
    </div>
""",
    unsafe_allow_html=True,
)

# 探検レベル・入力文字数表示
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

# 5. システムプロンプト（小3向けの表記ルールを強化）
SYSTEM_PROMPT = """
あなたは小学3年生の理科の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
相手は小学3年生の児童です。身近な自然や理科の不思議に興味を持てるよう優しく対話します。

【重要：言葉遣いと漢字の制限】
- 原則として「小学1年生〜3年生で習う漢字」のみを使用してください。
- 4年生以上で習う難しい漢字や難しい用語は使わず、できるだけ「ひらがな」にするか、必ずルビタグを使ってふりがなを振ってください。
- ルビの書き方例: <ruby>観察<rt>かんさつ</rt></ruby>、<ruby>実験<rt>じっけん</rt></ruby>、<ruby>太陽<rt>たいよう</rt></ruby>、<ruby>昆虫<rt>こんちゅう</rt></ruby>

【会話を長続きさせるためのルール】
1. 【親しみやすいリアクション】
   - 明るくやさしい言葉遣い（〜だよ！、〜かな？、すごいね！）。
   - 返信は100文字程度で短く読みやすくする。

2. 【会話の展開フロー】
   - ① 児童の返事（タイピング）を褒める。
   - ② 身近な疑問や体験（天気、虫、植物、光、影、水など）へ自然につなげる。
   - ③ 必ず『具体的に答えやすい質問』で終わる（例：「どっちだと思う？」「見たことあるかな？」など）。

3. 【会話を終わらせない工夫】
   - 児童が「わからない」「忘れた」と答えたら、優しくヒント（2〜3個の選択肢など）を出して助ける。
"""

# 6. 会話履歴の初期化
if "messages" not in st.session_state:
  st.session_state.messages = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {
          "role": "assistant",
          "content": (
              "こんにちは！<ruby>探検<rt>たんけん</rt></ruby>ハカセだよ🎓\nハカセと一緒に、身の回りの「ふしぎ」を見つける<ruby>探検<rt>たんけん</rt></ruby>に出かけよう！\n\n【きょうのミッション1】\n最近、家の近くや学校で見かけた「すきな生き物」や「気になるお天気」はあるかな？文字で打って教えてね！"
          ),
      },
  ]

# 7. 会話の表示
for msg in st.session_state.messages:
  if msg["role"] != "system":
    avatar = "🎓" if msg["role"] == "assistant" else "👦"
    with st.chat_message(msg["role"], avatar=avatar):
      st.markdown(msg["content"], unsafe_allow_html=True)

# 入力補助ボタン（たすけぶね）
st.caption("💬 たすけぶねボタン（おすと すぐに へんじが できるよ）:")
col1, col2, col3 = st.columns(3)
preset_input = None
if col1.button("💡 ヒントちょうだい！"):
  preset_input = "ヒントをちょうだい！"
if col2.button("❓ つぎのミッション！"):
  preset_input = "つぎのミッションをだして！"
if col3.button("😅 ちょっとわからない"):
  preset_input = "ちょっとわからないから教えて！"

# 8. 入力処理
user_input = st.chat_input("ここに へんじを かこう！")
if preset_input:
  user_input = preset_input

if user_input:
  if not api_key:
    st.error(
        "👈 ひだりの「せってい」に OpenAI APIキー を入れてからおくってね！"
    )
  else:
    # 文字数カウントを加算
    st.session_state.total_chars += len(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👦"):
      st.markdown(user_input, unsafe_allow_html=True)

    try:
      client = openai.OpenAI(api_key=api_key)
      with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("ハカセが考え中..."):
          response = client.chat.completions.create(
              model="gpt-4o-mini", messages=st.session_state.messages
          )
          bot_reply = response.choices[0].message.content
          st.markdown(bot_reply, unsafe_allow_html=True)

      st.session_state.messages.append(
          {"role": "assistant", "content": bot_reply}
      )

      # ログの自動保存
      log_df = pd.DataFrame([{
          "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "user_input": user_input,
          "bot_response": bot_reply,
          "input_length": len(user_input),
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

      st.rerun()

    except Exception as e:
      st.error(f"エラーが発生しました: {e}")