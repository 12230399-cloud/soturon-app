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

# --- プロンプト定義 ---
CHILD_SYSTEM_PROMPT = """
あなたは小学3年生の理科の学習をサポートする親しみやすいパートナー「探検ハカセ」です。
身近な自然や生き物、理科の不思議に興味を持てるよう優しく対話します。

【写真（画像）が送られてきた場合ルール】
1. 写真に写っているもの（生き物、虫、魚、植物、空など）の形・色・特徴をよく観察し、名前や種類を特定・推測して分かりやすく教えてあげてください。
2. 植物の病気や不調の場合は、怖がらせないように理由とお世話のアドバイスを優しく教えてあげてください。

【重要：言葉遣いと漢字の制限】
- 原則として「小学1年生〜3年生で習う漢字」のみを使用してください。
- 4年生以上で習う難しい漢字や専門用語は使わず、ひらがなにするかルビタグを使ってふりがなを振ってください。
- ルビの書き方例: <ruby>観察<rt>かんさつ</rt></ruby>、<ruby>病気<rt>びょうき</rt></ruby>、<ruby>特徴<rt>とくちょう</rt></ruby>

【会話を長続きさせるためのルール】
1. 明るくやさしい言葉遣い（〜だよ！、〜かな？、すごいね！）。
2. 返信は100〜150文字程度でコンパクトにする。
3. 必ず『具体的に答えやすい質問』で終わる（例：「どこで見つけたのかな？」「お水は毎日あげてるかな？」など）。
"""

ADULT_SYSTEM_PROMPT = """
あなたは自然科学の知識が豊富な親しみやすいパートナー「探検ハカセ（大人モード）」です。
保護者や先生、大人の探検者に向けて、自然や生き物の魅力を少し深掘りした知識とともに、分かりやすく解説します。

【写真（画像）の分析ルール】
1. 生物・昆虫・植物・自然現象などの名前や特徴を特定・推測して解説してください。
2. 植物の不調や病気などの場合は、考えられる原因と具体策（水やり、日照、お手入れなど）を丁寧にアドバイスしてください。

【文体・表現ルール】
1. ルビタグは使わず、通常の漢字混じりの丁寧で親しみやすい日本語（です・ます調）で記述してください。
2. 単なる名前の特定だけでなく、大人も「なるほど！」と思える豆知識や生態の面白さ、科学的な理由を添えて解説してください。
3. 返信の長さは200〜300文字程度で、読んで知的好奇心が刺激されるようなトーンを心がけてください。
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
if "last_send_time" not in st.session_state:
  st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0


# 新規スレッド作成用関数
def create_new_thread(system_prompt, is_child):
  new_id = str(uuid.uuid4())
  thread_count = len(st.session_state.get("threads", {})) + 1
  default_title = (
      f"あたらしい おはなし {thread_count}"
      if is_child
      else f"新しいおはなし {thread_count}"
  )
  greeting = (
      "新しい探検のスタートだね！🎓\nどんなことを ハカセに 聞いてみる？"
      if is_child
      else "こんにちは！探検ハカセです🎓\n気になる写真や、自然の「なぜ？」について気軽に質問してくださいね。"
  )
  return new_id, {
      "title": default_title,
      "messages": [
          {"role": "system", "content": system_prompt},
          {"role": "assistant", "content": greeting},
      ],
  }


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


# --- サイドバーナビゲーション ---
with st.sidebar:
  st.title("🧭 メニュー")

  st.header("🎭 モード設定")
  mode = st.radio(
      "表示・対話モード",
      ["👦 こどもモード", "🧑 オトナモード"],
      index=0,
      help="オトナモードではルビがなくなり、大人も楽しめる少し詳しい解説になります。",
  )
  is_child = "こども" in mode

  st.divider()

  # 画面用ラベルの定義（自然で親しみやすい言葉にマイルド化）
  labels = {
      "nav_page": (
          st.radio("ページ選択", ["💬 チャット", "📊 成長グラフ"])
          if is_child
          else st.radio("ページ選択", ["💬 チャット", "📊 記録レポート"])
      ),
      "user_name_label": (
          "あなたの おなまえ" if is_child else "お名前（ユーザー名）"
      ),
      "btn_new_chat": (
          "➕ あたらしい おはなし" if is_child else "➕ 新しいおはなし"
      ),
      "thread_list_title": (
          "これまでの おはなし:" if is_child else "これまでの会話:"
      ),
      "uploader_label": (
          "📷 しゃしんを えらぶ（選んだあと、下に文章を打ってね）"
          if is_child
          else "📷 写真を選ぶ（選んだあと、下にメッセージを入力してね）"
      ),
      "uploader_info": (
          "📸"
          " 写真が準備できました！下の入力欄に質問を書くか、たすけぶねボタンを押してね。"
          if is_child
          else (
              "📸"
              " 写真がセットされました！下の入力欄に聞きたいことを書いて送信してください。"
          )
      ),
      "helper_caption": (
          "💬 たすけぶねボタン（文字を打つのに困った時は押してね！）:"
          if is_child
          else "💬 クイック質問ボタン:"
      ),
      "btn1": "💡 ヒントちょうだい！" if is_child else "💡 詳しい観察のコツ",
      "btn2": "❓ つぎのミッション！" if is_child else "❓ 深掘りミッション",
      "btn3": (
          "🔍 これ なにか教えて！" if is_child else "🔍 これについて詳しく！"
      ),
      "chat_input_ph": (
          "ここに メッセージや しつもんを かこう！"
          if is_child
          else "質問やメッセージを入力してください..."
      ),
      "dash_title": (
          f"📈 {st.session_state.get('current_user', '')} さんの せいちょう"
          " レポート"
          if is_child
          else f"📈 {st.session_state.get('current_user', '')} さんの"
          " 探検・タイピング記録"
      ),
      "metric_chars": (
          "⭐ ぜんぶで うった もじ" if is_child else "⭐ トータル入力文字数"
      ),
      "metric_speed": (
          "⚡ へいきん タイピング速度" if is_child else "⚡ 平均タイピング速度"
      ),
      "metric_vocab": (
          "📚 つかった もじの 種類（語彙）"
          if is_child
          else "📚 使った文字・語彙数"
      ),
      "chart_speed": (
          "⚡ タイピングスピードの へんか（文字/分）"
          if is_child
          else "⚡ タイピング速度の変化（文字/分）"
      ),
      "chart_vocab": (
          "📚 つかえる もじの 広がり（累計）"
          if is_child
          else "📚 使える文字・語彙の広がり（累計）"
      ),
      "expander_history": (
          "📝 これまでの 入力きろくを 見る" if is_child else "📝 これまでの入力履歴を見る"
      ),
  }

  page = labels["nav_page"]

  active_prompt = (
      CHILD_SYSTEM_PROMPT if is_child else ADULT_SYSTEM_PROMPT
  )

  st.divider()
  st.header("👤 ユーザー設定")
  user_name = st.text_input(
      labels["user_name_label"],
      value="たろう",
      help="名前を変えると自分の記録が残るよ！",
  )

  # スレッド管理の初期化
  if "threads" not in st.session_state:
    init_id, init_thread = create_new_thread(active_prompt, is_child)
    st.session_state.threads = {init_id: init_thread}
    st.session_state.current_thread_id = init_id

  # ユーザー切り替え時の過去データ復元
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
        title = (
            group["thread_title"].iloc[0]
            if "thread_title" in group.columns
            else ("過去のおはなし" if is_child else "過去の会話")
        )
        msgs = [{"role": "system", "content": active_prompt}]
        for _, row in group.iterrows():
          role = row.get("role", "user")
          if pd.isna(role):
            role = "user"
          msgs.append({"role": role, "content": str(row["text"])})
        restored_threads[tid] = {"title": title, "messages": msgs}

      if restored_threads:
        st.session_state.threads = restored_threads
        st.session_state.current_thread_id = list(restored_threads.keys())[-1]

  if "チャット" in page:
    st.divider()
    st.header("💬 会話履歴")

    if st.button(labels["btn_new_chat"], use_container_width=True):
      new_id, new_thread = create_new_thread(active_prompt, is_child)
      st.session_state.threads[new_id] = new_thread
      st.session_state.current_thread_id = new_id
      st.rerun()

    thread_options = {
        tid: data["title"] for tid, data in st.session_state.threads.items()
    }
    selected_thread_id = st.radio(
        labels["thread_list_title"],
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
      st.success("過去の記録を読み込みました！")
    except Exception:
      st.error("ファイルの読み込みに失敗しました。")

  st.divider()
  st.header("⚙️ せってい")
  api_key = st.secrets.get("OPENAI_API_KEY", "")
  if not api_key:
    api_key = st.text_input("OpenAI APIキーを入力", type="password")

  selected_model = st.selectbox(
      "🧠 AIのモデル",
      ["gpt-4o", "gpt-4o-mini"],
      index=0,
      help="gpt-4oを選ぶと画像識別や詳細解説の精度が高くなります！",
  )


# ==========================================
# 📄 ページ1: チャット画面
# ==========================================
if "チャット" in page:
  current_thread = st.session_state.threads[st.session_state.current_thread_id]

  # システムプロンプトを現在のモードに同期
  if current_thread["messages"][0]["role"] == "system":
    current_thread["messages"][0]["content"] = active_prompt

  # ヘッダー表示
  header_title = (
      "🔍 わくわく<ruby>理科<rt>りか</rt></ruby><ruby>探検<rt>たんけん</rt></ruby>チャット"
      " 🎓"
      if is_child
      else "🔍 大人も楽しむ理科探検チャット 🎓"
  )
  header_sub = (
      f"たんけんしゃ: {user_name} さん"
      if is_child
      else f"探検者: {user_name} さん（オトナモード）"
  )

  st.markdown(
      f"""
      <div class="chat-header">
          <h2>{header_title}</h2>
          <p>{header_sub}</p>
      </div>
  """,
      unsafe_allow_html=True,
  )

  # 履歴表示
  for msg in current_thread["messages"]:
    if msg["role"] != "system":
      avatar = "🎓" if msg["role"] == "assistant" else "👦"
      with st.chat_message(msg["role"], avatar=avatar):
        if "image" in msg and msg["image"]:
          st.image(msg["image"], use_container_width=True)
        st.markdown(msg["content"], unsafe_allow_html=True)

  # 📷 写真選択エリア
  uploaded_file = st.file_uploader(
      labels["uploader_label"],
      type=["jpg", "jpeg", "png"],
      key=f"uploader_{st.session_state.uploader_key}",
  )

  if uploaded_file:
    st.info(labels["uploader_info"])

  # 💬 補助ボタン
  st.caption(labels["helper_caption"])
  col1, col2, col3 = st.columns(3)
  preset_input = None
  if col1.button(labels["btn1"]):
    preset_input = "ヒントをちょうだい！" if is_child else "観察のコツやポイントを教えて！"
  if col2.button(labels["btn2"]):
    preset_input = (
        "つぎのミッションをだして！"
        if is_child
        else "次に探検・観察してみるのにおすすめのテーマを教えて！"
    )
  if col3.button(labels["btn3"]):
    preset_input = (
        "これ（写真や疑問）について詳しく教えて！"
        if is_child
        else "これ（写真や疑問）について、大人向けに少し詳しく教えて！"
    )

  # ✏️ 入力エリア
  user_input = st.chat_input(labels["chat_input_ph"])
  if preset_input:
    user_input = preset_input

  # 送信処理
  if user_input:
    if not api_key:
      st.error("👈 ひだりの「せってい」に APIキーを入力してね！")
    else:
      # 初回発言時に自動で話題タイトルを設定
      if (
          current_thread["title"].startswith("あたらしい")
          or current_thread["title"].startswith("新しい")
      ) and len(current_thread["messages"]) <= 2:
        short_title = user_input[:12] + ("..." if len(user_input) > 12 else "")
        current_thread["title"] = f"💬 {short_title}"

      now_time = time.time()
      elapsed_time = max(now_time - st.session_state.last_send_time, 1.0)
      st.session_state.last_send_time = now_time

      char_cnt = len(user_input)
      typing_speed = (char_cnt / elapsed_time) * 60
      unique_chars = len(set(user_input))

      # データ保存
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
          with st.spinner(
              "ハカセが かんがえ中..." if is_child else "ハカセが調べ中..."
          ):
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
# 📊 ページ2: 成長グラフ（記録レポート）画面
# ==========================================
else:
  st.title(labels["dash_title"])

  df_all = load_user_data(user_name)

  if df_all.empty:
    st.info("まだ データがありません！チャットで ハカセと お話ししてみてね！")
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
      col1.metric(labels["metric_chars"], f"{total_chars} 文字")
      col2.metric(labels["metric_speed"], f"{int(avg_speed)} 文字/分")
      col3.metric(labels["metric_vocab"], f"{vocab_size} 種類")

      st.divider()

      st.subheader(labels["chart_speed"])
      st.line_chart(df_user.set_index("timestamp")["typing_speed"])

      st.subheader(labels["chart_vocab"])
      vocab_growth = []
      current_vocab = set()
      for text in df_user["text"].dropna():
        current_vocab.update(set(str(text)))
        vocab_growth.append(len(current_vocab))
      df_user["vocab_growth"] = vocab_growth

      st.line_chart(df_user.set_index("timestamp")["vocab_growth"])

      with st.expander(labels["expander_history"]):
        display_cols = [
            "timestamp",
            "thread_title",
            "char_count",
            "typing_speed",
            "text",
        ]
        available_cols = [c for c in display_cols if c in df_user.columns]
        st.dataframe(df_user[available_cols].iloc[::-1])