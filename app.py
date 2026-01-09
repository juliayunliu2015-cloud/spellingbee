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
# --- ENCOURAGEMENT HEADER ---
st.markdown("""

""", unsafe_allow_input=True)

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

@st.cache_data
def load_words():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        df = pd.read_excel(DATA_FILE)
        word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling"]), df.columns[0])
        def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "meaning", "desc"])), None)
        sent_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["sentence", "example", "sample"])), None)
        
        clean_rows = []
        for _, row in df.iterrows():
            if pd.isna(row[word_col]): continue
            clean_rows.append({
                "word": str(row[word_col]).strip(),
                "definition": str(row[def_col]).strip() if def_col and not pd.isna(row[def_col]) else "No definition available.",
                "sentence": str(row[sent_col]).strip() if sent_col and not pd.isna(row[sent_col]) else "No sample sentence available."
            })
        return pd.DataFrame(clean_rows).sort_values("word").reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["word", "definition", "sentence"])

def mask_vowels(word):
    return "".join("_" if char.lower() in "aeiou" else char for char in word)

# --- APP INITIALIZATION ---
init_db()
words_df = load_words()

if "current_word" not in st.session_state:
    st.session_state.current_word = None
if "attempts" not in st.session_state:
    st.session_state.attempts = 0
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "exam_mode" not in st.session_state:
    st.session_state.exam_mode = "All Words"

# --- UI TABS ---
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Alphabetical Learn", "📊 My Progress"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    st.header("Daily Challenge")
    
    # Mode Selector
    modes = ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14))
    
    # Handle the "Practice Now" button redirect
    default_index = modes.index(st.session_state.exam_mode) if st.session_state.exam_mode in modes else 0
    
    exam_group = st.selectbox(
        "Select Exam Group or Practice Mode:",
        options=modes,
        index=default_index,
        key="exam_mode_selector"
    )
    st.session_state.exam_mode = exam_group

    # FILTERING LOGIC
    if exam_group == "All Words":
        available_words = words_df
    elif exam_group == "❌ Incorrect Words Only":
        conn = get_db_connection()
        bad_words_list = [row['word'] for row in conn.execute("SELECT DISTINCT word FROM scores WHERE correctly_spelled = 0").fetchall()]
        conn.close()
        available_words = words_df[words_df['word'].isin(bad_words_list)]
    else:
        words_per_group = max(1, len(words_df) // 13)
        start_idx = (exam_group - 1) * words_per_group
        end_idx = start_idx + words_per_group if exam_group < 13 else len(words_df)
        available_words = words_df.iloc[start_idx:end_idx]

    # Pick word
    if not available_words.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
            st.session_state.current_word = available_words.sample(1).iloc[0]
            st.session_state.attempts = 0
            st.session_state.last_result = None

        word_to_spell = st.session_state.current_word["word"]
        audio_fp = io.BytesIO()
        gTTS(text=str(word_to_spell), lang="en").write_to_fp(audio_fp)
        st.audio(audio_fp, format="audio/mp3")

        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word:")
            if st.form_submit_button("Submit"):
                st.session_state.attempts += 1
                is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
                
                today = date.today().isoformat()
                conn = get_db_connection()
                conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, ?)",
                             (today, word_to_spell, int(is_correct), st.session_state.attempts))
                
                st.session_state.last_result = {
                    "is_correct": is_correct, "word": word_to_spell,
                    "definition": st.session_state.current_word["definition"],
                    "sentence": st.session_state.current_word["sentence"]
                }

                if is_correct:
                    conn.execute("INSERT INTO daily_exam_progress (date, correct_count, total_attempted) VALUES (?, 1, 1) ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1, total_attempted = total_attempted + 1", (today,))
                    st.session_state.current_word = available_words.sample(1).iloc[0] if not available_words.empty else None
                    st.session_state.attempts = 0
                else:
                    conn.execute("INSERT INTO daily_exam_progress (date, total_attempted) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET total_attempted = total_attempted + 1", (today,))
                
                conn.commit()
                conn.close()
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["is_correct"]: st.success("✅ Correct!")
            else:
                st.error("❌ Incorrect")
                st.subheader(f"Correct Spelling: :green[{res['word']}]")
                st.write(f"**Meaning:** {res['definition']}\n\n**Sentence:** _{res['sentence']}_")
            if st.button("Next Word"):
                st.session_state.last_result = None
                st.rerun()
    else:
        st.info("No words found for this mode. Try another group!")

# --- TAB 2: LEARN (Omitted for brevity, keep your current code) ---
with tab_learn:
    st.header("Alphabetical Groups")
    # ... your existing learning code ...

# --- TAB 3: MY PROGRESS ---
with tab_stats:
    st.header("Performance Stats")
    conn = get_db_connection()
    try:
        # 1. Incorrect Words List
        st.subheader("❌ Words to Review")
        bad_words_df = pd.read_sql_query("""
            SELECT word, COUNT(*) as mistakes, MAX(date) as last_fail 
            FROM scores WHERE correctly_spelled = 0 
            GROUP BY word ORDER BY mistakes DESC
        """, conn)

        if not bad_words_df.empty:
            st.dataframe(bad_words_df, use_container_width=True)
            
            # --- NEW: PRACTICE BUTTON ---
            if st.button("🎯 Practice These Incorrect Words Now"):
                st.session_state.exam_mode = "❌ Incorrect Words Only"
                st.session_state.current_word = None # Force a new word pick
                st.success("Mode set! Click the 'Daily Exam' tab at the top to start.")
        else:
            st.success("No incorrect words yet! Keep it up.")

        # 2. Reset Button
        st.divider()
        st.subheader("Danger Zone")
        confirm = st.checkbox("Confirm: Delete all my scores and history.")
        if st.button("Reset Everything", disabled=not confirm):
            conn.execute("DELETE FROM scores")
            conn.execute("DELETE FROM daily_exam_progress")
            conn.commit()
            st.rerun()
    finally:
        conn.close()


