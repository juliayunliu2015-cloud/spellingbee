import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
import hashlib
from datetime import date, datetime, timedelta
from gtts import gTTS

# --- CONFIGURATION & PAGE SETUP ---
st.set_page_config(
    page_title="Spelling Bee 2026",
    page_icon="🐝",
    layout="centered"
)

# Constants
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

# --- DATABASE FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite database tables."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            word TEXT NOT NULL,
            correctly_spelled INTEGER NOT NULL,
            attempts INTEGER NOT NULL,
            mode TEXT DEFAULT 'exam'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_exam_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            correct_count INTEGER DEFAULT 0,
            total_attempted INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# --- DATA LOADING ---
@st.cache_data
def load_words():
    """Loads and cleans the word list from Excel."""
    if not os.path.exists(DATA_FILE):
        st.error(f"Error: '{DATA_FILE}' not found in the project directory.")
        return pd.DataFrame(columns=["word", "definition"])
    
    try:
        df = pd.read_excel(DATA_FILE)
        # Identify the word column
        word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling", "term"]), df.columns[0])
        # Identify definition column
        def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "mean", "desc"])), None)
        
        df_clean = df[[word_col]].copy()
        df_clean.columns = ["word"]
        df_clean["definition"] = df[def_col].fillna("").astype(str) if def_col else ""
        return df_clean.dropna(subset=["word"])
    except Exception as e:
        st.error(f"Failed to read Excel file: {e}")
        return pd.DataFrame(columns=["word", "definition"])

# --- HELPER FUNCTIONS ---
def mask_vowels(word: str) -> str:
    vowels = "AEIOUaeiou"
    return "".join("_" if char in vowels else char for char in word)

def get_audio_bytes(word: str):
    """Generates gTTS audio in memory."""
    try:
        tts = gTTS(text=str(word), lang="en")
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        return audio_fp
    except Exception as e:
        st.error(f"Audio generation error: {e}")
        return None

# --- APP INITIALIZATION ---
init_db()
words_df = load_words()

if "current_word" not in st.session_state:
    st.session_state.current_word = words_df.sample(1).iloc[0] if not words_df.empty else None
if "attempts" not in st.session_state:
    st.session_state.attempts = 0
if "feedback" not in st.session_state:
    st.session_state.feedback = None

# --- UI TABS ---
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Alphabetical Learn", "📊 Performance"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    st.header("Daily Spelling Challenge")
    
    # Progress Bar
    conn = get_db_connection()
    today = date.today().isoformat()
    progress_row = conn.execute("SELECT correct_count FROM daily_exam_progress WHERE date = ?", (today,)).fetchone()
    score_today = progress_row[0] if progress_row else 0
    conn.close()

    st.progress(min(score_today / DAILY_EXAM_GOAL, 1.0))
    st.write(f"Daily Progress: **{score_today} / {DAILY_EXAM_GOAL}** correct words.")

    if st.session_state.current_word is not None:
        word_to_spell = st.session_state.current_word["word"]
        
        # Audio Playback
        audio_data = get_audio_bytes(word_to_spell)
        if audio_data:
            st.audio(audio_data, format="audio/mp3")
        
        # Input Form
        with st.form(key="exam_form", clear_on_submit=True):
            user_input = st.text_input("Listen and type the word:")
            submit_btn = st.form_submit_button("Submit")

        if submit_btn:
            st.session_state.attempts += 1
            is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
            
            # Database Logging
            conn = get_db_connection()
            conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts, mode) VALUES (?, ?, ?, ?, ?)",
                         (today, word_to_spell, int(is_correct), st.session_state.attempts, 'exam'))
            
            if is_correct:
                conn.execute("""
                    INSERT INTO daily_exam_progress (date, correct_count, total_attempted)
                    VALUES (?, 1, 1) ON CONFLICT(date) DO UPDATE SET 
                    correct_count = correct_count + 1, total_attempted = total_attempted + 1
                """, (today,))
                st.success(f"✅ Correct! The word was: **{word_to_spell}**")
                if st.session_state.current_word["definition"]:
                    st.info(f"**Meaning:** {st.session_state.current_word['definition']}")
                
                # Setup next word
                st.session_state.current_word = words_df.sample(1).iloc[0]
                st.session_state.attempts = 0
                st.button("Next Word ➡️")
            else:
                st.error("❌ Incorrect. Listen again and try your best!")
            
            conn.commit()
            conn.close()
    else:
        st.warning("Word list is empty. Please check your Excel file.")

# --- TAB 2: ALPHABETICAL LEARN ---
with tab_learn:
    st.header("Learning Groups")
    st.write("Words are split into 13 alphabetical groups (~33 words each).")
    
    # Sort and Group Logic
    df_sorted = words_df.sort_values("word").reset_index(drop=True)
    group_num = st.selectbox("Select Group (1-13):", range(1, 14))
    
    words_per_group = len(df_sorted) // 13
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(df_sorted)
    
    group_df = df_sorted.iloc[start_idx:end_idx]
    
    for _, row in group_df.iterrows():
        with st.expander(f"Word: {mask_vowels(row['word'])}"):
            st.write(f"**Full Word:** {row['word']}")
            if row['definition']:
                st.write(f"*Definition:* {row['definition']}")
            if st.button(f"🔊 Listen", key=f"audio_{row['word']}"):
                audio_learn = get_audio_bytes(row['word'])
                st.audio(audio_learn, format="audio/mp3")

# --- TAB 3: PERFORMANCE ---
with tab_stats:
    st.header("Your Progress")
    conn = get_db_connection()
    try:
        stats_df = pd.read_sql_query("SELECT date, correctly_spelled FROM scores", conn)
        if not stats_df.empty:
            stats_df["date"] = pd.to_datetime(stats_df["date"])
            daily_performance = stats_df.groupby("date")["correctly_spelled"].mean() * 100
            
            st.subheader("Daily Accuracy (%)")
            st.line_chart(daily_performance)
            
            st.subheader("Words to Review")
            failed_words = conn.execute("""
                SELECT word, COUNT(*) as fails FROM scores 
                WHERE correctly_spelled = 0 GROUP BY word ORDER BY fails DESC LIMIT 5
            """).fetchall()
            for row in failed_words:
                st.write(f"⚠️ **{row['word']}** (Failed {row['fails']} times)")
        else:
            st.info("No data yet. Complete some exams to see your stats!")
    finally:
        conn.close()
