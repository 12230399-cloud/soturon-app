import streamlit as st
import pandas as pd
import json
import os

st.set_page_config(page_title="探検チャット 管理者ダッシュボード", layout="wide", page_icon="⚙️")

# 1. 簡易パスワード認証（実験参加者に見られないようにするため）
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    st.title("🔒 管理者ログイン")
    st.info("評価実験のログデータ閲覧・ダウンロード画面です。")
    password = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        # ⚠️ パスワードは好きなものに変更してください
        if password == "admin123": 
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# 2. メイン画面
st.title("📊 管理者ダッシュボード（評価実験用）")
st.markdown("アプリに記録されたすべてのログを閲覧し、卒業論文の分析用にCSVとしてダウンロードできます。")

tab1, tab2, tab3 = st.tabs(["💬 チャットログ (CSV)", "🎯 クイズ成績 (JSON)", "🔥 継続記録 (JSON)"])

# --- タブ1: チャットログ ---
with tab1:
    st.subheader("ユーザーのチャット履歴 (user_stats.csv)")
    if os.path.exists("user_stats.csv"):
        df = pd.read_csv("user_stats.csv")
        # 新しい順に並び替え
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp', ascending=False)
        
        st.dataframe(df, use_container_width=True)
        
        # Excelで文字化けしないように utf-8-sig でエンコード
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 チャットログをCSVで一括ダウンロード",
            data=csv,
            file_name='user_stats_export.csv',
            mime='text/csv'
        )
        
        st.caption("💡 卒論での活用法: ユーザーがAIの深掘り質問に対してどう答えたか（概念的理解のプロセス）をテキスト分析するのに使います。")
    else:
        st.warning("まだチャットの記録がありません。")

# --- タブ2: クイズ成績 ---
with tab2:
    st.subheader("クイズ成績 (quiz_stats.json)")
    if os.path.exists("quiz_stats.json"):
        with open("quiz_stats.json", "r", encoding="utf-8") as f:
            quiz_data = json.load(f)
        
        if quiz_data:
            # JSONをCSV形式の表に変換
            df_quiz = pd.DataFrame.from_dict(quiz_data, orient='index').reset_index()
            df_quiz.columns = ['ユーザー名', '総挑戦回数', '正解数', '現在の連続正解']
            df_quiz['正答率(%)'] = (df_quiz['正解数'] / df_quiz['総挑戦回数'] * 100).round(1)
            
            st.dataframe(df_quiz, use_container_width=True)
            
            csv_quiz = df_quiz.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 クイズ成績をCSVでダウンロード", data=csv_quiz, file_name='quiz_stats_export.csv', mime='text/csv')
        else:
            st.info("データが空です。")
    else:
        st.warning("まだクイズの記録がありません。")

# --- タブ3: 継続記録 ---
with tab3:
    st.subheader("継続記録 (user_streaks.json)")
    if os.path.exists("user_streaks.json"):
        with open("user_streaks.json", "r", encoding="utf-8") as f:
            streak_data = json.load(f)
        
        if streak_data:
            df_streak = pd.DataFrame.from_dict(streak_data, orient='index').reset_index()
            df_streak.columns = ['ユーザー名', '現在の連続日数', '最終アクセス日']
            
            st.dataframe(df_streak, use_container_width=True)
            
            csv_streak = df_streak.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 継続記録をCSVでダウンロード", data=csv_streak, file_name='user_streaks_export.csv', mime='text/csv')
        else:
            st.info("データが空です。")
    else:
        st.warning("まだ継続の記録がありません。")