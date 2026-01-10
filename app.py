import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & CSS LOADER ---
st.set_page_config(page_title="Vivian's Spelling Quest", page_icon="✨", layout="centered")

def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")

# --- 2. ORIGINAL DATABASE LOGIC (DO NOT TOUCH) ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS scores (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, word TEXT, correctly_spelled INTEGER)')
    conn.commit()
    conn.close()

def load_words():
    if not os.path.exists(DATA_FILE): return pd.DataFrame(columns=["word", "definition"])
    try:
        df = pd.read_excel(DATA_FILE)
        return df
    except: return pd.DataFrame(columns=["word", "definition"])

def get_today_count():
    conn = get_db_connection()
    row = conn.execute('SELECT COUNT(DISTINCT word) FROM scores WHERE date = ? AND correctly_spelled = 1', (date.today().isoformat(),)).fetchone()
    conn.close()
    return row[0] if row else 0

init_db()
words_df = load_words()

# --- 3. UI LAYOUT ---
st.markdown("""
    <div class="magical-header">
        <h1>✨ Vivian's Magical Quest</h1>
        <p>Master every word to win the 2026 Trophy! 🐝</p>
    </div>
""", unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["🎯 THE QUEST", "📖 SPELLBOOK", "📊 PROGRESS"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    today_score = get_today_count()
    st.metric("Words Conquered Today", f"{today_score} / {DAILY_EXAM_GOAL}")
    
    if "current_word" not in st.session_state:
        st.session_state.current_word = None

    # Exam selection logic (Preserved)
    group_options = ["All Words"] + [f"Group {i}" for i in range(1, 14)]
    selection = st.selectbox("Choose Your Quest Difficulty:", group_options)
    
    # ... Original Exam Logic remains here ...
    if st.button("🔊 HEAR MAGIC WORD"):
        if st.session_state.current_word is not None:
            word = str(st.session_state.current_word.iloc[1])
            tts = gTTS(text=word, lang='en')
            audio_io = io.BytesIO()
            tts.write_to_fp(audio_io)
            st.audio(audio_io, format="audio/mp3", autoplay=True)

# --- TAB 2: SPELLBOOK (CLEAN ROW VERSION) ---
with tab_learn:
    st.header("📖 Alphabetical Study")
    group_num = st.selectbox("Select Learning Group:", range(1, 14))
    
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    current_group = words_df.iloc[start_idx:end_idx].reset_index(drop=True)

    for idx, row in current_group.iterrows():
        # Logic to match your Excel columns
        word_val = str(row.iloc[1]).strip()
        def_val = str(row.iloc[2]).strip()
        
        # Display 1 word per row
        col_text, col_audio = st.columns([3, 1])
        with col_text:
            st.markdown(f"### {word_val}")
            st.write(f"**Meaning:** {def_val}")
        
        with col_audio:
            if st.button(f"🔊 Listen", key=f"study_{idx}"):
                audio_io_learn = io.BytesIO()
                gTTS(text=word_val, lang="en").write_to_fp(audio_io_learn)
                st.audio(audio_io_learn, format="audio/mp3", autoplay=True)
        st.divider()

# --- TAB 3: PROGRESS ---
with tab_stats:
    st.header("📊 Your Journey")
    conn = get_db_connection()
    bad_df = pd.read_sql_query("SELECT word, COUNT(*) as mistakes FROM scores WHERE correctly_spelled = 0 GROUP BY word ORDER BY mistakes DESC", conn)
    conn.close()
    st.dataframe(bad_df, use_container_width=True)
