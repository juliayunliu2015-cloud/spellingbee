import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & CSS LOADER ---
st.set_page_config(page_title="Vivian's Magical Quest", page_icon="✨", layout="centered")

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Load the external CSS file
if os.path.exists("style.css"):
    local_css("style.css")

# --- 2. LOGIC & FUNCTIONS (PRESERVED) ---
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
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        # Assumes Column 1=Word, 2=Definition, 3=Sentence
        df = pd.read_excel(DATA_FILE)
        clean_rows = []
        for _, row in df.iterrows():
            word_val = str(row.iloc[1]).strip()
            if word_val.lower() != "nan" and not word_val.replace('.','',1).isdigit():
                clean_rows.append({
                    "word": word_val,
                    "definition": str(row.iloc[2]).strip() if len(row) > 2 else "...",
                    "sentence": str(row.iloc[3]).strip() if len(row) > 3 else ""
                })
        return pd.DataFrame(clean_rows)
    except:
        return pd.DataFrame(columns=["word", "definition", "sentence"])

def get_today_count():
    conn = get_db_connection()
    res = conn.execute("SELECT COUNT(DISTINCT word) FROM scores WHERE date = ? AND correctly_spelled = 1", (date.today().isoformat(),)).fetchone()
    conn.close()
    return res[0] if res else 0

init_db()
words_df = load_words()

# --- 3. UI LAYOUT ---
st.markdown('<div class="magical-banner"><h1>✨ Vivian\'s Magical Quest</h1><p>Master your words, unlock your magic!</p></div>', unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["🎯 THE QUEST", "📖 SPELLBOOK", "📊 PROGRESS"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    today_score = get_today_count()
    st.metric("Words Conquered Today", f"{today_score} / {DAILY_EXAM_GOAL}")
    
    if "current_word" not in st.session_state or st.session_state.current_word is None:
        if not words_df.empty:
            st.session_state.current_word = words_df.sample(1).iloc[0]

    if st.session_state.current_word is not None:
        curr = st.session_state.current_word
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔊 HEAR MAGIC WORD"):
                tts = gTTS(text=str(curr['word']), lang='en')
                audio_io = io.BytesIO()
                tts.write_to_fp(audio_io)
                st.audio(audio_io, format="audio/mp3", autoplay=True)
        with col2:
            if st.button("⏭️ NEXT QUEST WORD"):
                st.session_state.current_word = words_df.sample(1).iloc[0]
                st.rerun()

        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type your spell here:")
            if st.form_submit_button("🔥 CAST SPELL"):
                is_correct = user_input.strip().lower() == str(curr['word']).strip().lower()
                conn = get_db_connection()
                conn.execute("INSERT INTO scores (date, word, correctly_spelled) VALUES (?, ?, ?)", 
                             (date.today().isoformat(), curr["word"], int(is_correct)))
                conn.commit()
                conn.close()
                if is_correct: st.success("✨ Correct! Perfectly Spelled.")
                else: st.error(f"❌ Spell Fizzled! The word was: {curr['word']}")

# --- TAB 2: SPELLBOOK (CLEAN ROW VERSION) ---
with tab_learn:
    st.header("📖 Alphabetical Spellbook")
    group_num = st.selectbox("Select Page:", range(1, 14), key="learn_group")
    
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    current_group = words_df.iloc[start_idx:end_idx].reset_index(drop=True)
    
    for idx, row in current_group.iterrows():
        col_text, col_audio = st.columns([4, 1])
        word_to_read = str(row['word']).replace('.0', '').strip()

        with col_text:
            st.markdown(f"### {word_to_read}")
            st.write(f"**Meaning:** {row['definition']}")
        
        with col_audio:
            if st.button("🔊 Listen", key=f"study_btn_{idx}"):
                audio_io_learn = io.BytesIO()
                gTTS(text=word_to_read, lang="en").write_to_fp(audio_io_learn)
                st.audio(audio_io_learn, format="audio/mp3", autoplay=True)
        st.divider()

# --- TAB 3: PROGRESS ---
with tab_stats:
    st.header("📊 Progress Report")
    conn = get_db_connection()
    bad_df = pd.read_sql_query("SELECT word, COUNT(*) as Mistakes FROM scores WHERE correctly_spelled = 0 GROUP BY word ORDER BY Mistakes DESC", conn)
    conn.close()
    st.dataframe(bad_df, use_container_width=True)
