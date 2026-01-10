import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
from datetime import date
from gtts import gTTS

# --- 1. THEME ADAPTATION (FROM CODE.HTML) ---
st.set_page_config(page_title="Vivian's Magical Spelling Quest", page_icon="✨", layout="centered")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;700&family=Comfortaa:wght@400;700&display=swap');

        /* Background and Global Styles */
        .stApp {
            background-color: #FDFCFE; /* background-light from code.html */
            font-family: 'Comfortaa', sans-serif;
        }

        /* Magical Header Style */
        .magical-banner {
            background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
            border-radius: 1.5rem;
            padding: 2rem;
            text-align: center;
            color: white;
            box-shadow: 0 10px 25px -5px rgba(139, 92, 246, 0.3);
            margin-bottom: 2rem;
            border: 2px solid #FBBF24; /* Golden Accent */
        }

        .magical-banner h1 {
            font-family: 'Fredoka', sans-serif;
            font-weight: 700;
            color: white !important;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        /* Card Styling (Tailwind-like) */
        .quest-card {
            background: white;
            padding: 1.5rem;
            border-radius: 1rem;
            border: 1px solid #E5E7EB;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            margin-bottom: 1rem;
        }

        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #F3F4F6;
            padding: 6px;
            border-radius: 12px;
        }

        .stTabs [data-baseweb="tab"] {
            height: 45px;
            white-space: pre;
            background-color: transparent;
            border-radius: 8px;
            color: #6B7280;
        }

        .stTabs [aria-selected="true"] {
            background-color: white !important;
            color: #8B5CF6 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        }

        /* Button Styling (Magical Purple) */
        div.stButton > button {
            background-color: #8B5CF6 !important;
            color: white !important;
            border-radius: 0.75rem !important;
            border: none !important;
            padding: 0.6rem 1.5rem !important;
            font-weight: 700 !important;
            transition: all 0.2s;
        }

        div.stButton > button:hover {
            background-color: #7C3AED !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.4);
        }

        /* Audio Player Hider */
        div[data-testid="stAudio"] {
            display: none;
        }

        /* Success/Error Overrides */
        .stSuccess, .stError {
            border-radius: 1rem !important;
        }

        /* Metric/Score Styling */
        [data-testid="stMetricValue"] {
            color: #8B5CF6 !important;
            font-family: 'Fredoka', sans-serif;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIC & FUNCTIONS (UNCHANGED) ---
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
        # Using index 1 and 2 based on your previous logic
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
    except: return pd.DataFrame(columns=["word", "definition", "sentence"])

def get_today_count():
    conn = get_db_connection()
    res = conn.execute("SELECT COUNT(DISTINCT word) FROM scores WHERE date = ? AND correctly_spelled = 1", (date.today().isoformat(),)).fetchone()
    conn.close()
    return res[0] if res else 0

def get_mistakes():
    conn = get_db_connection()
    cursor = conn.execute("SELECT word FROM (SELECT word, correctly_spelled, MAX(id) FROM scores GROUP BY word) WHERE correctly_spelled = 0")
    mistakes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return mistakes

init_db()
words_df = load_words()

# --- 3. UI LAYOUT ---
st.markdown(f"""
    <div class="magical-banner">
        <h1>✨ Vivian's Magical Quest</h1>
        <p>Keep shining, Master Speller! 🐝</p>
    </div>
""", unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["🎯 THE QUEST", "📖 SPELLBOOK", "📊 PROGRESS"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    today_score = get_today_count()
    st.metric("Words Conquered Today", f"{today_score} / {DAILY_EXAM_GOAL}")
    
    if today_score >= DAILY_EXAM_GOAL:
        st.balloons()
        st.success("🌟 Perfect Cast! You've reached your daily goal!")

    group_options = ["All Words", "❌ Mistake Review"] + [f"Group {i}" for i in range(1, 14)]
    selection = st.selectbox("Choose Your Quest:", group_options)

    if selection == "All Words": pool = words_df
    elif selection == "❌ Mistake Review": pool = words_df[words_df['word'].isin(get_mistakes())]
    else:
        num = int(selection.split()[-1])
        size = len(words_df) // 13
        pool = words_df.iloc[(num-1)*size : num*size]

    if not pool.empty:
        if "current_word" not in st.session_state or st.session_state.current_word is None:
            st.session_state.current_word = pool.sample(1).iloc[0]

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
                st.session_state.current_word = pool.sample(1).iloc[0]
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
                st.markdown(f'<div class="quest-card"><b>Meaning:</b> {curr["definition"]}<br><i>"{curr["sentence"]}"</i></div>', unsafe_allow_html=True)

# --- TAB 2: SPELLBOOK (CLEAN ROW VERSION) ---
with tab_learn:
    st.subheader("📖 Alphabetical Spellbook")
    group_num = st.selectbox("Select Page:", range(1, 14), key="learn_group")
    
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    current_group = words_df.iloc[start_idx:end_idx].reset_index(drop=True)
    
    for idx, row in current_group.iterrows():
        # Text and Button in one clean row
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
    conn = get_db_connection()
    bad_df = pd.read_sql_query("SELECT word, COUNT(*) as Mistakes FROM scores WHERE correctly_spelled = 0 GROUP BY word ORDER BY Mistakes DESC", conn)
    conn.close()
    st.markdown('<div class="quest-card"><h3>📊 Power Level: Mistakes to Review</h3></div>', unsafe_allow_html=True)
    st.dataframe(bad_df, use_container_width=True)
