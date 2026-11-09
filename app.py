import base64
from datetime import datetime, date
import io
import os
import random
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

# --- 学年別 おうち実験データベース（1日5分） ---
EXPERIMENTS = {
    "小学低学年": [
        {"title": "💧 逃げるコショウ", "desc": "お皿に水を張り、コショウをふりかけます。指先に1滴だけ食器用洗剤をつけて水面を触ってみよう！"},
        {"title": "🎈 くっつく風船", "desc": "ふくらませた風船を髪の毛や服で10秒こすってから、壁や天井にくっつけてみよう！"},
        {"title": "🍅 浮く野菜、沈む野菜", "desc": "水を張ったボウルに、ミニトマトやピーマンなどの野菜を入れてみよう。浮くものと沈むものの違いは？"},
        {"title": "👽 かたくり粉スライム", "desc": "片栗粉と水を「2:1」で混ぜます。ぎゅっと握ると固くなるのに、パッと離すとドロドロになる不思議な感触（ダイラタンシー）を楽しもう！"},
        {"title": "📞 音のつたわりかた", "desc": "紙コップとタコ糸で「糸電話」を作ろう。糸をピンと張ったときと、たるませたときで声の聞こえ方はどう変わる？"},
        {"title": "🍊 みかんの皮のヒミツ", "desc": "ふくらませた風船に、みかんの皮の汁を飛ばしてみよう！どうなるかな？（※汁が目に入らないように注意！）"},
        {"title": "💨 ペットボトル空気砲", "desc": "ペットボトルの底を切り取り、風船をかぶせてテープでとめます。風船を引っ張って離すと、空気が飛び出すよ！的当てゲームをしよう。"}
    ],
    "小学高学年": [
        {"title": "🥚 浮く卵", "desc": "コップに水を入れて卵を沈めます。そこに塩を大さじずつ溶かしていくと、卵はどうなる？"},
        {"title": "🌈 水の虹", "desc": "ティッシュに水性ペンで点を並べて描き、下の端を少しだけ水につけておくとどうなる？"},
        {"title": "🧊 氷の糸釣り", "desc": "水に浮かべた氷の上にタコ糸を置き、その上から塩をひとつまみかけます。1分後に糸を持ち上げると？"},
        {"title": "✨ 10円玉ピカピカ大作戦", "desc": "黒ずんだ10円玉に、お酢、レモン汁、ケチャップなどを塗って5分置いてみよう。どれが一番きれいになる？"},
        {"title": "🧈 手作りバター", "desc": "生クリーム（動物性の脂肪分45%以上のもの）をペットボトルに入れ、ひたすら強く振ってみよう！バターと水分に分かれるよ。"},
        {"title": "🛁 シュワシュワ手作りバスボム", "desc": "重曹「2」：クエン酸「1」の割合で混ぜ、少しずつ水をスプレーして丸めます。乾かしてから水に入れるとどうなる？"},
        {"title": "🎨 ペーパークロマトグラフィー", "desc": "コーヒーフィルターに黒の水性ペンで点を描き、その下を少し水に浸します。黒いインクから色々な色が分かれてくるのを観察しよう。"}
    ],
    "中学生以上": [
        {"title": "🔋 コイン電池", "desc": "10円玉と1円玉の間に、塩水で濡らしたティッシュを挟んで層を作ります。テスターで電圧を測ってみよう。"},
        {"title": "❄️ 瞬間氷結（過冷却）", "desc": "未開封の炭酸水を冷凍庫でギリギリ凍らない程度（約3時間半）冷やし、お皿に注いだ氷に当ててみよう。"},
        {"title": "🧪 紫キャベツ液のpH判定", "desc": "紫キャベツの汁（お湯で煮出したもの）に、レモン汁や重曹、石鹸水を入れて色の変化（酸性・アルカリ性）を観察しよう。"},
        {"title": "☁️ ペットボトルの中に雲を作る", "desc": "炭酸用ペットボトルに少量の水と線香の煙（凝結核）を入れ、キャップをして強く潰してから急に離すと、中に白い雲ができます。"},
        {"title": "🪙 消えるコイン", "desc": "透明なコップの下にコインを置き、コップに水を入れると横から見たときにコインが消えて見えます。光の全反射の実験です。"},
        {"title": "🧬 ブロッコリーのDNA抽出", "desc": "すりつぶしたブロッコリーに中性洗剤と塩水を混ぜてろ過し、冷えた無水エタノールを静かに注ぐと、白いDNAが浮き上がります。"},
        {"title": "⚡ 備長炭電池", "desc": "備長炭に塩水で濡らしたクッキングペーパーを巻き、その上からアルミホイルを巻きます。モーターにつなぐとどうなるか確認しよう。"}
    ]
}

# --- 分野別 豆知識データベース ---
TRIVIA = {
    "🍎 物理": [
        "光は1秒間に地球を約7回り半（約30万km）も進むことができるんだ！",
        "音は空気中よりも、水の中のほうが約4倍も速く伝わるんだよ。",
        "宇宙空間には空気が無いので、どんなに大きな爆発が起きても音は全く聞こえないんだ。",
        "自転車が倒れないのは、車輪が回ることで姿勢を保とうとする「ジャイロ効果」のおかげもあるんだ。",
        "宇宙空間のような無重力の場所でろうそくに火をつけると、炎は上にとんがらず、丸いドーム型になるんだよ！",
        "雷がピカッと光ってから音が聞こえるまでの秒数で、雷までの距離がわかるよ。（3秒なら約1km先！）",
        "宇宙に行くと、背骨の間の軟骨が重力から解放されて広がるため、身長が1〜2cmほど伸びるんだ。"
    ],
    "🧪 化学": [
        "水（H2O）はお湯のときよりも、氷のときのほうが体積が大きくなる、とても珍しい物質なんだ。",
        "ダイヤモンドと鉛筆の芯（黒鉛）は、見た目は全然違うけれど、どちらも同じ「炭素」という成分からできているよ！",
        "鉄が錆びるとき、実はほんの少しだけ熱を出しているんだ。（カイロはこの仕組みを利用しているよ）",
        "玉ねぎを切ると涙が出るのは「硫化アリル」という成分のせい。玉ねぎを冷やしてから切ると涙が出にくくなるよ。",
        "硬いことで有名なダイヤモンドだけど、「ハンマーで叩く」ような衝撃には弱くて、意外と簡単に粉々に割れてしまうんだ。",
        "ガラスは固体のように見えるけれど、実は非常にゆっくりと流れる「液体（非晶質）」の仲間だという考え方もあるんだよ。",
        "レモンの皮の汁には「リモネン」という成分が含まれていて、発泡スチロールや風船のゴムを溶かす性質があるんだ！"
    ],
    "🌿 生物": [
        "人間の血管をすべて一本につなぎ合わせると、なんと地球を約2周半（約10万km）もする長さになるんだ！",
        "タコの心臓は3つ、脳は9つもあるんだよ！",
        "バナナはDNA（遺伝子の設計図）の約60%が人間と同じなんだって。",
        "キリンの睡眠時間はとても短く、1日にまとめて寝るのはたったの20分程度！残りは立ったままうたた寝をしているんだ。",
        "フラミンゴの羽がピンク色なのは、エサとして食べているエビやプランクトンに含まれる赤い色素（アスタキサンチン）のせいなんだよ。",
        "人間の赤ちゃんは生まれたとき骨が約300個あるけど、大人になるにつれてくっつき合い、約206個に減るんだ。",
        "深海に住む魚には、自分の体より大きなエサを丸飲みできるように、風船のように大きく膨らむ胃袋を持つものがいるよ。"
    ],
    "🌍 地学・宇宙": [
        "地球にある水のうち、私たちが飲み水として使える淡水は、全体のたった「0.01%」しかないんだ。",
        "太陽は地球の約109倍の大きさで、太陽の中に地球が約130万個もスッポリ入ってしまうんだよ！",
        "雷の温度は、なんと太陽の表面よりも熱い約3万度にもなるんだ。",
        "月は毎年、地球から約3.8センチずつ遠ざかっているんだ。大昔の月は、今よりもずっと大きく見えていたはずだよ。",
        "金星の「1日（自転）」は、金星の「1年（公転）」よりも長いんだ！金星では、1日が終わる前に1年が過ぎてしまう計算になるね。",
        "宇宙空間の中心にはラズベリーのような成分があり、宇宙飛行士の服からは「焼けたステーキ」や「金属」のような匂いがするそうだよ。",
        "地球の重力はどこでも同じではなく、赤道に近づくほど遠心力の影響でわずかに軽くなるんだ。（体重計の数字もほんの少し変わるよ！）"
    ]
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
if "daily_seed" not in st.session_state: st.session_state.daily_seed = int(date.today().strftime("%Y%m%d"))
if "suggested_questions" not in st.session_state: st.session_state.suggested_questions = []
if "auto_send_msg" not in st.session_state: st.session_state.auto_send_msg = None

def create_new_thread(system_prompt, grade_name):
    new_id = str(uuid.uuid4())
    thread_count = len(st.session_state.get("threads", {})) + 1
    is_child = "小学" in grade_name
    default_title = f"あたらしい おはなし {thread_count}" if is_child else f"新しいテーマ {thread_count}"
    greeting = f"こんにちは！【{grade_name}】向けの 探検スタートだよ！🎓\nどんなことを ハカセに 聞いてみる？" if is_child else f"こんにちは！探検ハカセです🎓【{grade_name}】モードで解説します。"
    return new_id, {"title": default_title, "messages": [{"role": "system", "content": system_prompt}, {"role": "assistant", "content": greeting}]}

# CSSスタイル
st.markdown("""
    <style>
    .stApp { background-color: #FFFDE7 !important; color: #212121 !important; }
    .user-card, .exp-card, .trivia-card { background-color: #FFFFFF; border: 2px solid #FFB74D; border-radius: 15px; padding: 12px 18px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    .exp-card { border-color: #4CAF50; background-color: #F1F8E9; }
    .trivia-card { border-color: #64B5F6; background-color: #E3F2FD; }
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
            st.success(f"🔥 実験れんぞく: {get_streak(st.session_state.user_name)} 日目！")
    st.markdown("</div>", unsafe_allow_html=True)

    # 日替わり要素の決定 (乱数シードを日付で固定)
    random.seed(st.session_state.daily_seed)
    
    # 1. 学年別 1日5分 おうち実験
    exp_cat = get_grade_category(st.session_state.selected_grade)
    todays_exp = random.choice(EXPERIMENTS[exp_cat])
    
    # 2. 分野別 豆知識
    trivia_categories = list(TRIVIA.keys())
    todays_trivia_cat = random.choice(trivia_categories)
    todays_trivia = random.choice(TRIVIA[todays_trivia_cat])

    # 実験と豆知識のカード表示
    st.markdown(f"""
        <div class="exp-card">
            <h4 style="margin-top:0;">⏱️ 1日5分！本日のおうち実験（{exp_cat}向け）</h4>
            <b>{todays_exp["title"]}</b><br>{todays_exp["desc"]}<br>
            <span style="font-size: 13px; color: #555;">※実験をやったら、下の入力欄に「実験できた！」「結果は〇〇だった！」と報告して連続記録をのばそう！</span>
        </div>
        <div class="trivia-card">
            <h4 style="margin-top:0;">💡 今日の豆知識【{todays_trivia_cat}】</h4>
            {todays_trivia}
        </div>
    """, unsafe_allow_html=True)

    # チャット履歴表示
    non_system_msgs = [m for m in current_thread["messages"] if m["role"] != "system"]
    for msg in non_system_msgs:
        with st.chat_message(msg["role"], avatar="🎓" if msg["role"] == "assistant" else "👦"):
            if "image" in msg and msg["image"]: st.image(msg["image"], use_container_width=True)
            content = msg["content"]
            if msg["role"] == "assistant" and "---" in content:
                content = content.split("---")[0].strip() # 質問候補部分を分離して表示
            st.markdown(content, unsafe_allow_html=True)

    # 質問候補ボタン
    if st.session_state.suggested_questions:
        st.caption("💡 ハカセからの おすすめの質問（タップで聞けるよ！）")
        q_cols = st.columns(min(len(st.session_state.suggested_questions), 3))
        for i, q in enumerate(st.session_state.suggested_questions[:3]):
            if q_cols[i].button(q, key=f"sug_q_{i}"):
                st.session_state.auto_send_msg = q
                st.rerun()

    uploaded_file = st.file_uploader("📷 しゃしんを えらぶ", type=["jpg", "jpeg", "png"], key=f"uploader_{st.session_state.uploader_key}")
    user_input = st.chat_input("ここに メッセージや しつもんを かこう！")
    
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

            if any(word in user_input for word in ["実験", "できた", "結果", "やった"]):
                if st.session_state.user_name.strip():
                    update_streak(st.session_state.user_name)
                    st.toast("🔥 実験クリア！れんぞく記録がのびたよ！", icon="🎉")

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
        st.success(f"🔥 現在の実験連続記録: {get_streak(st.session_state.user_name)} 日目！")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("総メッセージ数", f"{len(df)} 回")
        col2.metric("総入力文字数", f"{df['char_count'].sum()} 文字")
        col3.metric("平均タイピング速度", f"{round(df['typing_speed'].mean(), 1)} 文字/分")
        
        st.subheader("📝 これまでの会話データ")
        st.dataframe(df.tail(20).sort_values("timestamp", ascending=False))