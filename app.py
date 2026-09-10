from datetime import datetime
import os
import openai
import pandas as pd
import streamlit as st

# 1. ページ基本設定
st.set_page_config(
    page_title="社会×理科 わくわく探検チャット",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="collapsed",  # 自動調整のためサイドバーはデフォルトで閉じる
)

# 2. 画面サイズ最適化（レスポンシブ）＆ ポップデザインのカスタムCSS
st.markdown(
    """
    <style>
    /* 全体の背景色 */
    .stApp {
        background-color: #FFFDE7;
    }
    
    /* コンテナの幅を画面サイズに合わせて自動調整 */
    .main .block-container {
        max-width: 800px;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1.5rem;
    }

    /* タイトルエリア（レスポンシブ対応） */
    .title-box {
        background: linear-gradient(135deg, #FFB74D, #FFD54F);
        padding: 15px 20px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .title-box h1 {
        color: #5D4037;
        font-size: clamp(18px, 4vw, 26px); /* 画面サイズで文字サイズが自動変化 */
        margin: 0;
    }
    .title-box p {
        color: #795548;
        font-size: clamp(12px, 2.5vw, 15px);
        margin-top: 5px;
        font-weight: bold;
    }

    /* メッセージ吹き出し（スマホ・タブレット最適化） */
    .stChatMessage {
        border-radius: 18px !important;
        padding: 10px 14px !important;
        margin-bottom: 8px !important;
        font-size: clamp(14px, 3vw, 16px) !important;
    }
    
    div[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #E1F5FE !important;
        border: 2px solid #81D4FA !important;
    }

    div[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #E8F5E9 !important;
        border: 2px solid #A5D6A7 !important;
    }

    /* 入力フォームの画面最適化 */
    .stChatInputContainer {
        border-radius: 25px !important;
        border: 3px solid #FFB74D !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# タイトル表示
st.markdown(
    """
    <div class="title-box">
        <h1>🔍 社会×理科 わくわく探検チャット 🎓</h1>
        <p>タイピングで ハカセと 楽しく おしゃべりしよう！</p>
    </div>
""",
    unsafe_allow_html=True,
)

# 3. APIキーの自動取得（secrets.toml または 手入力）
api_key = st.secrets.get("OPENAI_API_KEY", "")

with st.sidebar:
  st.header("⚙️ せってい")
  if not api_key:
    api_key = st.text_input(
        "OpenAI APIキーを入力", type="password", help="sk-...を入力"
    )
  else:
    st.success("鍵 APIキーは自動で読み込まれています！")
  st.divider()
  st.info("💡 対話ログは `chat_log.csv` に自動保存されます。")

# 4. システムプロンプト
SYSTEM_PROMPT = """
あなたは小学3年生の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
相手はタイピングが得意で、社会科が好きですが、理科に苦手意識がある小学3年生です。

【重要：会話を長続きさせるためのルール】
1. 【表記・言葉遣い】
   - 小学3年生が読める漢字中心、難しい言葉には「（ルビ）」を付ける。
   - 明るくやさしい言葉遣い（〜だよ！、〜かな？、すごいね！）。
   - 1回の返信は100〜150文字程度でコンパクトにする。

2. 【会話の展開フロー（社会から理科へ）】
   - ① 児童の入力をしっかり褒める（タイピングの頑張りを評価）。
   - ② 「社会（地域、食べ物、都道府県、昔のくらしなど）」から「理科（天気、季節、生き物、水、太陽など）」へ自然に繋げる。
   - ③ 必ず『具体的に答えやすい質問』で終わる（例：「どっちが好きかな？」「〜見たことある？」など）。

3. 【会話を終わらせない工夫】
   - 児童が「わからない」「忘れた」と答えたら、優しくヒント（選択肢など）を出して助ける。
"""

# 5. 会話履歴の初期化
if "messages" not in st.session_state:
  st.session_state.messages = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {
          "role": "assistant",
          "content": (
              "こんにちは！探検ハカセだよ🎓\nきみの得意なタイピングで、一緒に探検に出かけよう！\n\n【きょうのミッション1】\n最近、学校の社会や本で知った「すきな場所」や「行ってみたい都道府県」はあるかな？キーボードで打って教えてね！"
          ),
      },
  ]

# 6. 会話の表示
for msg in st.session_state.messages:
  if msg["role"] != "system":
    avatar = "🎓" if msg["role"] == "assistant" else "👦"
    with st.chat_message(msg["role"], avatar=avatar):
      st.write(msg["content"])

# 7. タイピング入力処理
if user_input := st.chat_input("ここにタイピングして返事をかこう！"):
  if not api_key:
    st.error(
        "👈 ひだりの「せってい」に OpenAI APIキー を入れてからおくってね！"
    )
  else:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👦"):
      st.write(user_input)

    try:
      client = openai.OpenAI(api_key=api_key)
      with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("ハカセが考え中..."):
          response = client.chat.completions.create(
              model="gpt-4o-mini", messages=st.session_state.messages
          )
          bot_reply = response.choices[0].message.content
          st.write(bot_reply)

      st.session_state.messages.append(
          {"role": "assistant", "content": bot_reply}
      )

      # ログの自動保存
      log_df = pd.DataFrame([{
          "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "user_input": user_input,
          "bot_response": bot_reply,
          "input_length": len(user_input),
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

    except Exception as e:
      st.error(f"エラーが発生しました: {e}")