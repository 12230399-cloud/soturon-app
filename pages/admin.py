import streamlit as st
import pandas as pd
import os
import json
import time

st.set_page_config(page_title="管理者ダッシュボード", page_icon="👑", layout="wide")

# ==========================================
# 設定と関数
# ==========================================
ADMIN_PW = st.secrets.get("ADMIN_PASSWORD", "admin")
STATS_FILE = "user_stats.csv"
STREAK_FILE = "user_streaks.json"
QUIZ_STATS_FILE = "quiz_stats.json"

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

# ==========================================
# ログイン画面
# ==========================================
st.title("👑 管理者専用ダッシュボード")

if not st.session_state.admin_auth:
    st.info("先生・研究者向けの管理画面です。パスワードを入力してください。")
    pw = st.text_input("パスワード (デフォルト: admin)", type="password")
    if st.button("ログイン"):
        if pw == ADMIN_PW:
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()

# ==========================================
# 管理者メイン画面（タブ切り替え）
# ==========================================
if st.button("🚪 ログアウト", key="logout_btn"):
    st.session_state.admin_auth = False
    st.rerun()

tab1, tab2, tab3 = st.tabs(["📝 チャットログ", "🎯 クイズ成績", "⚙️ データ管理"])

with tab1:
    st.subheader("ユーザー別 チャット利用状況")
    if os.path.exists(STATS_FILE):
        df_chat = pd.read_csv(STATS_FILE, encoding="utf-8-sig")
        
        if not df_chat.empty:
            char_counts = df_chat.groupby("user_name")["char_count"].sum()
            st.markdown("##### 📊 合計入力文字数")
            st.bar_chart(char_counts)
        
        st.dataframe(df_chat, use_container_width=True)
        with open(STATS_FILE, "rb") as f:
            st.download_button("📥 チャットログ(CSV)をダウンロード", f, file_name="user_stats.csv", mime="text/csv")
    else:
        st.write("まだチャットの記録がありません。")

with tab2:
    st.subheader("ユーザー別 クイズ成績")
    if os.path.exists(QUIZ_STATS_FILE):
        q_data = load_json(QUIZ_STATS_FILE)
        if q_data:
            df_quiz = pd.DataFrame.from_dict(q_data, orient='index')
            
            st.markdown("##### 📊 正解数 / 挑戦回数")
            if 'correct' in df_quiz.columns and 'total' in df_quiz.columns:
                st.bar_chart(df_quiz[['correct', 'total']])
                
            st.dataframe(df_quiz, use_container_width=True)
        else:
            st.write("データが空です。")
    else:
        st.write("まだクイズの記録がありません。")

with tab3:
    st.subheader("⚙️ データリセット操作")
    st.warning("⚠️ ボタンを押すと研究データが消去されます。必要なデータは事前にダウンロードしてください。")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🗑️ チャットログを全消去", use_container_width=True):
            if os.path.exists(STATS_FILE):
                os.remove(STATS_FILE)
                st.success("チャットログを消去しました。")
                time.sleep(1)
                st.rerun()
    with col2:
        if st.button("🗑️ クイズ成績を全消去", use_container_width=True):
            if os.path.exists(QUIZ_STATS_FILE):
                os.remove(QUIZ_STATS_FILE)
                st.success("クイズ成績を消去しました。")
                time.sleep(1)
                st.rerun()
    with col3:
        if st.button("🗑️ ログイン記録を全消去", use_container_width=True):
            if os.path.exists(STREAK_FILE):
                os.remove(STREAK_FILE)
                st.success("連続ログイン記録を消去しました。")
                time.sleep(1)
                st.rerun()
