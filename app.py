import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
from datetime import date
from gtts import gTTS

# --- CONFIGURATION & PAGE SETUP ---
st.set_page_config(page_title="Spelling Bee 2026", page_icon="🐝", layout="centered")

DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

# --- DATABASE FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            word TEXT NOT NULL,
            correctly_spelled INTEGER NOT NULL,
            attempts INTEGER NOT NULL
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
    if not os.path.exists(DATA_FILE):
        st.error(f"File {DATA_FILE} not found!")
        return pd.DataFrame(columns=["word", "definition", "sentence"])
    
    df = pd.read_excel(DATA_FILE)
    
    # Identify Columns
    word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling"]), df.columns[0])
    def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "meaning", "desc"])), None)
    # Search for a sentence/example column
    sent_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["sentence", "example", "sample"])), None)
    
    df_clean = df[[word_col]].copy()
    df_clean.columns = ["word"]
    df_clean["definition"] = df[def_col].fillna("").astype(str) if def_col else "No definition available."
    df_clean["sentence"] = df[sent_col].fillna("").astype(str) if sent_col else "No sample sentence available."
    
    return df_clean.dropna(subset=["word"]).sort_values("word").reset_index(drop=True)

def mask_vowels(word):
    return "".join("_" if char.lower() in "aeiou" else char for char in word)

# --- APP INITIALIZATION ---
init_db()
words_df = load_words()

# Initialize Session State
if "current_word" not in st.session_state:
    st.session_state.current_word = None
if "attempts" not in st.session_state:
    st.session_state.attempts = 0
if "last_result" not in st.session_state:
    st.session_state.last_result = None # Stores (is_correct, word, definition, sentence)

# --- UI TABS ---
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Alphabetical Learn", "📊 My Progress"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    st.header("Daily Challenge")
    
    exam_group = st.selectbox(
        "Select Exam Group (1-13) or Practice All:",
        options=["All Words"] + list(range(1, 14)),
        index=0
    )

    # Filter words
    if exam_group == "All Words":
        available_words = words_df
    else:
        words_per_group = len(words_df) // 13
        start_idx = (exam_group - 1) * words_per_group
        end_idx = start_idx + words_per_group if exam_group < 13 else len(words_df)
        available_words = words_df.iloc[start_idx:end_idx]

    # Pick a word if needed
    if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
        st.session_state.current_word = available_words.sample(1).iloc[0]
        st.session_state.attempts = 0
        st.session_state.last_result = None

    # Progress Info
    conn = get_db_connection()
    today = date.today().isoformat()
    row = conn.execute("SELECT correct_count FROM daily_exam_progress WHERE date = ?", (today,)).fetchone()
    score_today = row[0] if row else 0
    conn.close()

    st.progress(min(score_today / DAILY_EXAM_GOAL, 1.0))
    st.write(f"Daily Goal: **{score_today} / {DAILY_EXAM_GOAL}**")

    # Word Audio
    word_to_spell = st.session_state.current_word["word"]
    tts = gTTS(text=str(word_to_spell), lang="en")
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    st.audio(audio_fp, format="audio/mp3")

    # Spelling Form
    with st.form(key="spell_form", clear_on_submit=True):
        user_input = st.text_input("Type the word you hear:")
        submit = st.form_submit_button("Check Spelling")

    if submit:
        st.session_state.attempts += 1
        is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
        
        # Log to DB
        conn = get_db_connection()
        conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, ?)",
                     (today, word_to_spell, int(is_correct), st.session_state.attempts))
        
        # Save result info to session state for display
        st.session_state.last_result = {
            "is_correct": is_correct,
            "word": word_to_spell,
            "definition": st.session_state.current_word["definition"],
            "sentence": st.session_state.current_word["sentence"]
        }

        if is_correct:
            conn.execute("""
                INSERT INTO daily_exam_progress (date, correct_count, total_attempted)
                VALUES (?, 1, 1) ON CONFLICT(date) DO UPDATE SET 
                correct_count = correct_count + 1, total_attempted = total_attempted + 1
            """, (today,))
            # Refresh for next word
            st.session_state.current_word = available_words.sample(1).iloc[0]
            st.session_state.attempts = 0
        else:
            conn.execute("""
                INSERT INTO daily_exam_progress (date, total_attempted)
                VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET 
                total_attempted = total_attempted + 1
            """, (today,))
        
        conn.commit()
        conn.close()
        st.rerun()

    # --- DISPLAY FEEDBACK ---
    if st.session_state.last_result:
        res = st.session_state.last_result
        if res["is_correct"]:
            st.success(f"✅ Correct!")
        else:
            st.error(f"❌ Incorrect")
            st.subheader(f"Correct Spelling: :green[{res['word']}]")
            st.markdown(f"**Meaning:** {res['definition']}")
            st.markdown(f"**Sample Sentence:** _{res['sentence']}_")
        
        if st.button("Try Next Word"):
            st.session_state.last_result = None
            st.rerun()

# --- TAB 2 & 3 (Same as previous provided code) ---
with tab_learn:
    st.header("Learn by Groups")
    group_num = st.selectbox("Select Learning Group (1-13):", range(1, 14), key="learn_group")
    words_per_group = len(words_df) // 13
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    current_group_df = words_df.iloc[start_idx:end_idx]
    
    for _, row in current_group_df.iterrows():
        col1, col2 = st.columns([1, 2])
        with col1: st.write(f"**{mask_vowels(row['word'])}**")
        with col2:
            if st.button(f"Hear/See", key=f"btn_{row['word']}"):
                st.write(f"Word: **{row['word']}**")
                if row['definition']: st.write(f"_{row['definition']}_")

with tab_stats:
    st.header("Performance Stats")
    conn = get_db_connection()
    try:
        stats_df = pd.read_sql_query("SELECT date, correctly_spelled FROM scores", conn)
        if not stats_df.empty:
            stats_df["date"] = pd.to_datetime(stats_df["date"])
            daily_avg = stats_df.groupby("date")["correctly_spelled"].mean() * 100
            st.line_chart(daily_avg)
    finally:
        conn.close()
