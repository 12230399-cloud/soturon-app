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
    {
        "card": (
            "🐟 <b>トビウオは 空（そら）を 400mも"
            " とぶ！</b><br>敵（てき）から にげるために、海（うみ）の上を"
            " パトカーより はやく とべるんだよ。"
        ),
        "query": (
            "「トビウオが空をとぶ」ことについて、どうやって飛んでいるのか詳しく教えて！"
        ),
    },
    {
        "card": (
            "🍉 <b>スイカは「やさい」の"
            " なかま！</b><br>甘（あま）くて フルーツみたいだけど、畑（はたけ）で"
            " できるから「野菜（やさい）」なんだよ！"
        ),
        "query": (
            "「スイカは野菜のなかま」ということについて、果物との違いを詳しく教えて！"
        ),
    },
    {
        "card": (
            "🐙 <b>タコには 心臓（しんぞう）が"
            " 3つある！</b><br>からだ全体に 血液（けつえき）を おくるために、3つの"
            " 心臓が はたらいているんだよ。"
        ),
        "query": (
            "「タコには心臓が3つある」ことについて、どうして3つもあるのか詳しく教えて！"
        ),
    },
]

TRIVIA_ADULT = [
    {
        "card": (
            "🌌 <b>宇宙空間には「音」が存在しない</b><br>音波を伝える媒体（空気）が存在しないため完全な静寂ですが、電波を音に変換すると惑星特有の音が聴こえます。"
        ),
        "query": (
            "「宇宙空間には音が描かれない理由と電波変換の音」について、大人向けに詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🐛 <b>アゲハチョウの幼虫の臭い角の秘密</b><br>威嚇時に出す橙色の角（臭角）の匂いは、食べた柑橘類の葉の脂肪酸を体内で濃縮・合成したものです。"
        ),
        "query": (
            "「アゲハチョウの幼虫がもつ臭角の化学的メカニズム」について、もう少し詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🍌 <b>バナナは樹木ではなく「巨大な草」</b><br>木に見える幹のような部分は、葉の柄が重なり合った「偽茎（ぎけい）」と呼ばれる草本構造です。"
        ),
        "query": (
            "「バナナの偽茎構造と草本植物としての分類」について、詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🦦 <b>ラッコが手をつないで眠る理由</b><br>海流で沖に流されるのを防ぐため、仲間と手をつないだり、海藻（ジャイアントケルプ）を体に巻き付けて眠ります。"
        ),
        "query": (
            "「ラッコの睡眠生態と海藻利用の習性」について、詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🦴 <b>赤ちゃんの骨の数は大人より約100個多い</b><br>誕生時は約300個の軟骨中心ですが、成長に伴って骨同士が結合し、大人になると約206個になります。"
        ),
        "query": (
            "「乳幼児の骨の結合プロセス（骨化）と理由」について、詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🐟 <b>トビウオの滑空能力は時速70km</b><br>大型魚から逃れるため発達した胸ビレを広げ、水面を切って最大400m以上も空中を滑空できます。"
        ),
        "query": (
            "「トビウオの滑空に必要な解剖学的特徴と流体力学」について、詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🍉 <b>スイカやメロンは植物学上「果実的野菜」</b><br>草本植物に実るため野菜に分類されますが、消費形態から「果実的野菜」とも呼ばれます。"
        ),
        "query": (
            "「農林水産省の果実的野菜の定義と分類基準」について、詳しく解説してください。"
        ),
    },
    {
        "card": (
            "🐙 <b>タコの心臓は3つ、血液は青い</b><br>全身に血を送る心臓1つのほか、エラに血を送る鰓心臓（えにしんぞう）が2つあり、銅を含んだ血で酸素を運ぶため青く見えます。"
        ),
        "query": (
            "「タコの鰓心臓の役割とヘモシアニン（青い血液）の仕組み」について、詳しく解説してください。"
        ),
    },
]

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
  # 名前が空の場合は「探検者」または「ゲスト」にする
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
  st.session_state.user_name = ""  # ★初期値を空文字に変更！
if "last_send_time" not in st.session_state:
  st.session_state.last_send_time = time.time()
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0
if "trivia_seed" not in st.session_state:
  st.session_state.trivia_seed = random.randint(0, 1000)


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

  st.header("🎭 モード設定")
  mode = st.radio(
      "表示・対話モード",
      ["👦 こどもモード", "🧑 オトナモード"],
      index=0,
      help="オトナモードではルビがなくなり、大人も楽しめる少し詳しい解説になります。",
  )
  is_child = "こども" in mode

  st.divider()

  # 画面用ラベルの定義
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
  active_prompt = (
      CHILD_SYSTEM_PROMPT if is_child else ADULT_SYSTEM_PROMPT
  )

  # スレッド管理の初期化
  if "threads" not in st.session_state:
    init_id, init_thread = create_new_thread(active_prompt, is_child)
    st.session_state.threads = {init_id: init_thread}
    st.session_state.current_thread_id = init_id

  # ユーザー切り替え時の過去データ復元
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

  # ★ 1. 画面最上部に分かりやすい「お名前設定エリア」を配置（初期は空文字＆プレースホルダー）
  with st.container():
    st.markdown('<div class="user-card">', unsafe_allow_html=True)
    u_col1, u_col2 = st.columns([3, 1])
    with u_col1:
      input_name = st.text_input(
          "👤 まずは あなたの おなまえをおしえてね！"
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
      else "たんけんしゃ"
  )
  header_title = (
      "🔍 わくわく<ruby>理科<rt>りか</rt></ruby><ruby>探検<rt>たんけん</rt></ruby>チャット"
      " 🎓"
      if is_child
      else "🔍 大人も楽しむ理科探検チャット 🎓"
  )
  header_sub = (
      f"たんけんしゃ: {display_user_name} さん"
      if is_child
      else f"探検者: {display_user_name} さん（オトナモード）"
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

  # 💡 きょうの理科トリビア（3選）表示セクション
  trivia_db = TRIVIA_CHILD if is_child else TRIVIA_ADULT
  random.seed(st.session_state.trivia_seed)
  selected_trivia = random.sample(trivia_db, min(3, len(trivia_db)))

  t_col1, t_col2 = st.columns([4, 1])
  with t_col1:
    st.markdown(
        "<b>💡 きょうの 理科トリビア（3選）:</b>"
        if is_child
        else "<b>💡 本日の科学豆知識（3選）:</b>",
        unsafe_allow_html=True,
    )
  with t_col2:
    if st.button("🎲 シャッフル", help="別の雑学に入れ替えます"):
      st.session_state.trivia_seed = random.randint(0, 1000)
      st.rerun()

  # 3つのかわるがわる雑学カード ＋「詳しく聞く」ボタン
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

  # 履歴表示（システムメッセージ除く）
  non_system_msgs = [
      m for m in current_thread["messages"] if m["role"] != "system"
  ]
  for idx, msg in enumerate(non_system_msgs):
    avatar = "🎓" if msg["role"] == "assistant" else "👦"

    # ★最新のハカセ（assistant）回答の「冒頭（直前）」にジャンプ目印を設置
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

  # 🎯 最新の回答の冒頭（#latest-reply-start）へピッタリ滑らかジャンプするJavaScript
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