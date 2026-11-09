import base64
from datetime import datetime
import io
import os
import random
import time
import uuid
import openai
import pandas as pd
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components

# 1. ページ基本設定
st.set_page_config(
    page_title="わくわく理科探検チャット",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="expanded",
)

STATS_FILE = "user_stats.csv"

# --- 学年リスト ---
GRADE_OPTIONS = [
    "👦 小学1年生",
    "👦 小学2年生",
    "👦 小学3年生",
    "👦 小学4年生",
    "👦 小学5年生",
    "👦 小学6年生",
    "🧑 中学1年生",
    "🧑 中学2年生",
    "🧑 中学3年生",
    "🏫 高校生",
    "🎓 大人・一般",
]

# --- 雑学（トリビア）データベース ---
TRIVIA_CHILD = [
    {
        "card": (
            "🌌 <b>宇宙（うちゅう）には 音（おと）が ない！</b><br>空気（くうき）がないから、どんなに大きな音も"
            " つたわらないんだよ。"
        ),
        "query": (
            "「宇宙には音が無い」ことについて、どうして音が伝わらないのか詳しく教えて！"
        ),
    },
    {
        "card": (
            "🐛 <b>あおむしの くさい ツノ！</b><br>アゲハチョウの"
            " 幼虫（ようちゅう）は、びっくりすると あたまから くさいツノを"
            " 出すよ！"
        ),
        "query": (
            "「アゲハチョウの幼虫のくさいツノ」について、どんなにおいなのか詳しく教えて！"
        ),
    },
    {
        "card": (
            "🍌 <b>バナナは「木（き）」じゃない！？</b><br>バナナの"
            " 木に 見える部分は、実は 大きな「くさ（草）」なんだよ！"
        ),
        "query": "「バナナは木じゃなくて草」ということについて、詳しく教えて！",
    },
    {
        "card": (
            "🦦 <b>ラッコは 手を つないで"
            " ねる！</b><br>海（うみ）で 流（なが）されないように、仲良（なかよ）しと"
            " 手を つないで ねるんだよ。"
        ),
        "query": (
            "「ラッコが手をつないで寝る」ことについて、どんな風に過ごしているのか詳しく教えて！"
        ),
    },
    {
        "card": (
            "🦴 <b>赤ちゃんは 大人（おとな）より"
            " ほねが多い！</b><br>赤ちゃんの ほねは 約300個（こ）あって、大きくなると"
            " くっついて 約206個になるよ！"
        ),
        "query": (
            "「赤ちゃんのほねは大人より多い」ことについて、どうしてくっつくのか詳しく教えて！"
        ),
    },
]

TRIVIA_ADVANCED = [
    {
        "card": (
            "⚛️ <b>水の電気分解と化学反応式</b><br>2H₂O → 2H₂ +"
            " O₂。陰極には水素、陽極には酸素が2:1の気体積比で発生します。"
        ),
        "query": (
            "「水の電気分解の化学反応式とイオンの動き」について詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🌌 <b>宇宙空間における音波と電波</b><br>音波は疎密波（密度の波）のため真空を伝播しませんが、電波（電磁波）は真空でも届きます。"
        ),
        "query": (
            "「音波と電磁波の物理的な違いと宇宙での伝播」について詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🌿 <b>光合成と呼吸の化学平衡</b><br>6CO₂ + 6H₂O → C₆H₁₂O₆ +"
            " 6O₂。植物も夜間は光合成を行わず呼吸のみを行います。"
        ),
        "query": (
            "「光合成の明反応・暗反応および補償点・光飽和点」について詳しく教えてください。"
        ),
    },
    {
        "card": (
            "🧪 <b>酸・塩基の中和熱とモル濃度</b><br>HCl + NaOH → NaCl +"
            " H₂O + 56.5kJ。強酸と強塩基の中和熱は常にほぼ一定です。"
        ),
        "query": (
            "「酸・塩基の中和反応と計算問題の解法ステップ」について例題付きで教えてください。"
        ),
    },
    {
        "card": (
            "⚡ <b>オームの法則と合成抵抗</b><br>V = RI。"
            " 直列回路では抵抗の和、並列回路では逆数の和の逆数となります。"
        ),
        "query": (
            "「並列回路の合成抵抗の計算問題」を1問出題して、解法を解説してください！"
        ),
    },
]


# --- 学年別プロンプト生成関数 ---
def get_system_prompt(grade_name):
  base_role = "あなたは自然科学の学習を支援する親しみやすいパートナー「探検ハカセ」です。"

  if "小学" in grade_name:
    return f"""
{base_role}
【対象ユーザー】: {grade_name}（小学生）

【言葉遣い・漢字制限】
1. 原則として「{grade_name}までに学校で習う漢字」のみを使用してください。
2. それ以上の学年で習う漢字や難しい専門用語はひらがなにするか、ルビタグ（例: <ruby>観察<rt>かんさつ</rt></ruby>）を使用してください。
3. 明るく優しい言葉遣い（〜だよ！、〜かな？）。
4. 返信は100〜150文字程度にし、最後に『答えやすい質問』を1つ添えて会話を続けてください。

【学習単元・写真アドバイス】
- {grade_name}の理科単元（植物、昆虫、天体、テコ、電気など）に即した身近な例えで解説してください。
- 写真が送られた場合は形や色の特徴をほめて観察の着眼点を教えてあげてください。
"""
  elif "中学" in grade_name:
    return f"""
{base_role}
【対象ユーザー】: {grade_name}（中学生向け）

【言葉遣い・表現ルール】
1. 丁寧な「です・ます調」で解説してください。過剰なルビは不要です。
2. 化学式（H₂O, CuO, NaCl, 2H₂ + O₂ → 2H₂O）や物理公式（オームの法則 V=RI, 圧力 P=F/S, 密度 d=m/V）を積極的に活用し、理論的に解説してください。

【機能・計算問題対応】
- ユーザーから「問題をだして」「計算問題をだして」と言われた場合、{grade_name}の理科（質量パーセント濃度、オームの法則、湿度、フックの法則など）の計算問題を1問出題し、ヒントやステップ解説を行ってください。
- 写真（実験器具、生物、天体等）が送られた場合は、理科の単元に関連する科学的原理を含めて解説してください。
"""
  else:
    return f"""
{base_role}
【対象ユーザー】: {grade_name}（高校生・大人・研究/分析）

【言葉遣い・表現ルール】
1. 知的で論理的な「です・ます調」で記述します。
2. 化学反応式、構造式、物理公式、SI単位系、国際命名法などを正確に用いて深掘り解説してください。

【機能・計算問題対応】
- 物理・化学（モル計算、反応熱、酸・塩基中和、力学、電磁気学等）の計算問題の解法解説や問題出題要請に柔軟に対応します。ステップバイステップで論理的に説明してください。
- 写真が送信された場合、分類学、解剖学、物理化学的メカニズムに基づく深い考察を提供してください。
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
  saved_name = user_name.strip() if user_name.strip() else "探検者"
  new_data = pd.DataFrame([{
      "timestamp": now,
      "user_name": saved_name,
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
    target_name = user_name.strip() if user_name.strip() else "探検者"
    return df[df["user_name"] == target_name]
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
if "user_name" not in st.session_state:
  st.session_state.user_name = ""
if "selected_grade" not in st.session_state:
  st.session_state.selected_grade = GRADE_OPTIONS[2]  # 初期値: 小学3年生
if "last_send_time" not in st.session_state:
  st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0
if "trivia_seed" not in st.session_state:
  st.session_state.trivia_seed = random.randint(0, 1000)


def create_new_thread(system_prompt, grade_name):
  new_id = str(uuid.uuid4())
  thread_count = len(st.session_state.get("threads", {})) + 1
  is_child = "小学" in grade_name
  default_title = (
      f"あたらしい おはなし {thread_count}"
      if is_child
      else f"新しいテーマ {thread_count}"
  )
  greeting = (
      f"こんにちは！【{grade_name}】向けの 探検スタートだよ！🎓\nどんなことを"
      " ハカセに 聞いてみる？"
      if is_child
      else (
          f"こんにちは！探検ハカセです🎓【{grade_name}】モードで解説します。\n質問や写真の解析、化学式・計算問題など何でも聞いてくださいね。"
      )
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
    .user-card {
        background-color: #FFFFFF;
        border: 2px solid #FFB74D;
        border-radius: 15px;
        padding: 12px 18px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
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
    .trivia-card {
        background-color: #FFFFFF;
        border: 2px solid #FFE082;
        border-radius: 12px;
        padding: 10px 12px;
        font-size: 13px;
        color: #424242;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        margin-bottom: 6px;
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

  st.header("🎓 学年・対象設定")
  selected_grade = st.selectbox(
      "学年を選んでね",
      GRADE_OPTIONS,
      index=GRADE_OPTIONS.index(st.session_state.selected_grade),
      help="学年に合わせて使う漢字・計算問題・専門用語の深さが変化します！",
  )
  
  # ★ここが修正ポイント！学年を変えたら自動で新しいおはなしを作る★
  if selected_grade != st.session_state.selected_grade:
    st.session_state.selected_grade = selected_grade
    # 自動的に新しい学年でスレッドを作成
    new_id, new_thread = create_new_thread(get_system_prompt(selected_grade), selected_grade)
    if "threads" not in st.session_state:
        st.session_state.threads = {}
    st.session_state.threads[new_id] = new_thread
    st.session_state.current_thread_id = new_id
    st.rerun()

  is_child = "小学" in selected_grade
  active_prompt = get_system_prompt(selected_grade)

  st.divider()

  labels = {
      "nav_page": (
          st.radio("ページ選択", ["💬 チャット", "📊 成長グラフ"])
          if is_child
          else st.radio("ページ選択", ["💬 チャット", "📊 記録レポート"])
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
      "chat_input_ph": (
          "ここに メッセージや しつもんを かこう！"
          if is_child
          else "質問やメッセージ、計算問題の依頼などを入力..."
      ),
      "dash_title": (
          f"📈 {st.session_state.user_name if st.session_state.user_name else '探検者'} さんの せいちょう レポート"
          if is_child
          else f"📈 {st.session_state.user_name if st.session_state.user_name else '探検者'} さんの 探検・タイピング記録"
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

  # スレッド初期化
  if "threads" not in st.session_state:
    init_id, init_thread = create_new_thread(active_prompt, selected_grade)
    st.session_state.threads = {init_id: init_thread}
    st.session_state.current_thread_id = init_id

  # ユーザー切り替え復元
  if (
      "current_user" not in st.session_state
      or st.session_state.current_user != st.session_state.user_name
  ):
    st.session_state.current_user = st.session_state.user_name
    df_user_data = load_user_data(st.session_state.user_name)

    if not df_user_data.empty and "thread_id" in df_user_data.columns:
      restored_threads = {}
      grouped = df_user_data.groupby("thread_id")
      for tid, group in grouped:
        title = (
            group["thread_title"].iloc[0]
            if "thread_title" in group.columns
            else ("過去の会話" if not is_child else "過去のおはなし")
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
      new_id, new_thread = create_new_thread(active_prompt, selected_grade)
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
    download_filename = (
        st.session_state.user_name if st.session_state.user_name else "探検者"
    )
    with open(STATS_FILE, "rb") as f:
      st.download_button(
          label="📥 記録（CSV）を保存する",
          data=f,
          file_name=f"理科探検きろく_{download_filename}.csv",
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
      help="gpt-4oを選ぶと画像識別や詳細な計算問題の精度が高くなります！",
  )


# ==========================================
# 📄 ページ1: チャット画面
# ==========================================
if "チャット" in page:
  current_thread = st.session_state.threads[st.session_state.current_thread_id]

  # システムプロンプトを現在の学年に同期
  if current_thread["messages"][0]["role"] == "system":
    current_thread["messages"][0]["content"] = active_prompt

  # お名前入力エリア
  with st.container():
    st.markdown('<div class="user-card">', unsafe_allow_html=True)
    u_col1, u_col2 = st.columns([3, 1])
    with u_col1:
      input_name = st.text_input(
          "👤 あなたの おなまえをおしえてね！"
          if is_child
          else "👤 ユーザー名を入力してください",
          value=st.session_state.user_name,
          placeholder="例: たろう" if is_child else "例: 山田太郎",
          key="global_user_name_input",
      )
      if input_name != st.session_state.user_name:
        st.session_state.user_name = input_name
        st.rerun()

    with u_col2:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.session_state.user_name.strip():
        st.caption(
            f"✨ **{st.session_state.user_name}** さんで準備完了！"
            if is_child
            else f"👤 設定中: **{st.session_state.user_name}**"
        )
      else:
        st.markdown(
            "<span style='color: #E65100; font-weight: bold; font-size: 12px;'>⚠️"
            " お名前を入力してね！</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

  # ヘッダー表示
  display_user_name = (
      st.session_state.user_name.strip()
      if st.session_state.user_name.strip()
      else "探検者"
  )
  header_title = (
      f"🔍 理科探検チャット （{selected_grade}）🎓"
      if not is_child
      else (
          f"🔍 わくわく<ruby>理科<rt>りか</rt></ruby><ruby>探検<rt>たんけん</rt></ruby>チャット"
          f"（{selected_grade}） 🎓"
      )
  )
  header_sub = f"たんけんしゃ: {display_user_name} さん"

  st.markdown(
      f"""
      <div class="chat-header">
          <h2>{header_title}</h2>
          <p>{header_sub}</p>
      </div>
  """,
      unsafe_allow_html=True,
  )

  # 💡 トリビアセクション（学年にあわせて変化）
  trivia_db = TRIVIA_CHILD if is_child else TRIVIA_ADVANCED
  random.seed(st.session_state.trivia_seed)
  selected_trivia = random.sample(trivia_db, min(3, len(trivia_db)))

  t_col1, t_col2 = st.columns([4, 1])
  with t_col1:
    st.markdown(
        "<b>💡 きょうの 理科トリビア（3選）:</b>"
        if is_child
        else "<b>💡 本日の科学・理科豆知識（3選）:</b>",
        unsafe_allow_html=True,
    )
  with t_col2:
    if st.button("🎲 シャッフル", help="別の雑学に入れ替えます"):
      st.session_state.trivia_seed = random.randint(0, 1000)
      st.rerun()

  preset_input = None
  c1, c2, c3 = st.columns(3)
  cols = [c1, c2, c3]

  for i, col in enumerate(cols):
    with col:
      st.markdown(
          f'<div class="trivia-card">{selected_trivia[i]["card"]}</div>',
          unsafe_allow_html=True,
      )
      btn_label = "🔍 詳しくきく" if is_child else "🔍 詳しく聞く"
      if st.button(
          btn_label, key=f"trivia_btn_{i}", use_container_width=True
      ):
        preset_input = selected_trivia[i]["query"]

  st.divider()

  # 履歴表示
  non_system_msgs = [
      m for m in current_thread["messages"] if m["role"] != "system"
  ]
  for idx, msg in enumerate(non_system_msgs):
    avatar = "🎓" if msg["role"] == "assistant" else "👦"

    if (
        msg["role"] == "assistant"
        and idx == len(non_system_msgs) - 1
        and len(non_system_msgs) > 1
    ):
      st.markdown(
          '<div id="latest-reply-start"></div>', unsafe_allow_html=True
      )

    with st.chat_message(msg["role"], avatar=avatar):
      if "image" in msg and msg["image"]:
        st.image(msg["image"], use_container_width=True)
      st.markdown(msg["content"], unsafe_allow_html=True)

  # 📷 写真選択
  uploaded_file = st.file_uploader(
      labels["uploader_label"],
      type=["jpg", "jpeg", "png"],
      key=f"uploader_{st.session_state.uploader_key}",
  )
  if uploaded_file:
    st.info(labels["uploader_info"])

  # 💬 学年別のクイック質問ボタン
  st.caption("💬 クイック質問ボタン:")
  col1, col2, col3 = st.columns(3)

  if is_child:
    btn1_txt, btn2_txt, btn3_txt = (
        "💡 ヒントちょうだい！",
        "❓ つぎのミッション！",
        "🔍 これ なにか教えて！",
    )
    req1, req2, req3 = (
        "ヒントをちょうだい！",
        "つぎの探検ミッションをだして！",
        "これ（写真や疑問）について詳しく教えて！",
    )
  elif "中学" in selected_grade:
    btn1_txt, btn2_txt, btn3_txt = (
        "🧪 計算問題をだして！",
        "⚛️ 化学式・理論の解説",
        "💡 実験・観察のポイント",
    )
    req1, req2, req3 = (
        f"{selected_grade}の理科の計算問題を1問出題して！",
        "中学理科で習う重要な化学反応式について分かりやすく解説して！",
        "理科の実験や観察で注意すべきポイントやコツを教えて！",
    )
  else:
    btn1_txt, btn2_txt, btn3_txt = (
        "📐 理論・計算問題を出題",
        "🔬 専門メカニズムの深掘り",
        "💡 実験・研究の着眼点",
    )
    req1, req2, req3 = (
        f"{selected_grade}レベルの物理または化学の計算問題を1問出題して！",
        "このテーマについて、化学反応式や物理法則を用いて深掘り解説して！",
        "この自然現象や実験における科学的な観察の着眼点を詳しく教えて！",
    )

  if col1.button(btn1_txt):
    preset_input = req1
  if col2.button(btn2_txt):
    preset_input = req2
  if col3.button(btn3_txt):
    preset_input = req3

  # 入力エリア
  user_input = st.chat_input(labels["chat_input_ph"])
  if preset_input:
    user_input = preset_input

  # 送信処理
  if user_input:
    if not api_key:
      st.error("👈 ひだりの「せってい」に APIキーを入力してね！")
    else:
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

      save_user_stat(
          st.session_state.user_name,
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
            st.session_state.user_name,
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

  # 最新回答冒頭へ自動ジャンプ
  components.html(
      """
      <script>
          function scrollToReplyStart() {
              var parentDoc = window.parent.document;
              var target = parentDoc.getElementById('latest-reply-start');
              if (target) {
                  target.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
          }
          setTimeout(scrollToReplyStart, 150);
          setTimeout(scrollToReplyStart, 400);
      </script>
      """,
      height=0,
  )

# ==========================================
# 📊 ページ2: 成長グラフ（記録レポート）画面
# ==========================================
else:
  st.title(labels["dash_title"])

  df_all = load_user_data(st.session_state.user_name)

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