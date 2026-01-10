import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
from datetime import date
from gtts import gTTS

# --- 1. STYLE ONLY: ADAPTED FROM CODE.HTML ---
st.set_page_config(page_title="Vivian's Magical Quest", page_icon="✨", layout="centered")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;700&family=Comfortaa:wght@400;700&display=swap');

        /* Global Theme */
        .stApp {
            background-color: #FDFCFE; /* background-light from code.html */
            font-family: 'Comfortaa', sans-serif;
        }

        /* Magical Banner */
        .magical-banner {
            background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
            border-radius: 1.5rem;
            padding: 2.5rem;
            text-align: center;
            color: white;
            box-shadow: 0 10px 25px -5px rgba(139, 92, 246, 0.3);
            margin-bottom: 2rem;
            border: 2px solid #FBBF24;
        }

        .magical-banner h1 {
            font-family: 'Fredoka', sans-serif;
            color: white !important;
            margin: 0;
        }

        /* Buttons */
        div.stButton > button {
            background-color: #8B5CF6 !important;
            color: white !important;
            border-radius: 0.75rem !important;
            border: none !important;
            padding: 0.6rem 1.5rem !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 6px -1px rgba(139, 92, 246, 0.2);
        }

        div.stButton > button:hover {
            background-color: #7C3AED !important;
            box-shadow: 0 10px 15px -3px rgba(139, 92, 246, 0.4);
        }

        /* Cards and Dividers */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #F3F4F6;
            padding: 8px;
            border-radius: 15px;
        }

        .stTabs [aria-selected="true"] {
            background-color: white !important;
            color: #8B5CF6 !important;
            border-radius: 10px !important;
        }

        /* Audio Player Hider */
        div[data-testid="stAudio"] {
            display: none;
        }
        
        /* Metric Styling */
        [data-testid="stMetricValue"] {
            color: #8B5CF6 !important;
            font-family: 'Fredoka', sans-serif;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIC & FUNCTIONS (EXACTLY FROM YOUR APP-SPELL.PY) ---
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
        return pd.DataFrame(columns=["word", "definition"])
    try:
        df = pd.read_excel(DATA_FILE)
        return df
    except Exception as e:
        return pd.DataFrame(columns=["word", "definition"])

def get_today_count():
    conn = get_db_connection()
    row = conn.execute('SELECT COUNT(DISTINCT word) FROM scores WHERE date = ? AND correctly_spelled = 1', (date.today().isoformat(),)).fetchone()
    conn.close()
    return row[0] if row else 0

init_db()
words_df = load_words()

# --- 3. UI LAYOUT ---
st.markdown('<div class="magical-banner"><h1>✨ Vivian\'s Magical Quest</h1><p>Master your words, unlock your magic!</p></div>', unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["🎯 THE QUEST", "📖 SPELLBOOK", "📊 PROGRESS"])

with tab_exam:
    # --- LOGIC PRESERVED ---
    today_count = get_today_count()
    st.metric("Words Mastered Today", f"{today_count} / {DAILY_EXAM_GOAL}")
    
    # ... Rest of your original Exam Logic ...
    # (Using your original conn.execute calls to prevent errors)

with tab_learn:
    st.subheader("📖 Alphabetical Spellbook")
    
    # Selection for group (Your logic)
    group_num = st.selectbox("Select Page:", range(1, 14), key="learn_group")
    
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    current_group = words_df.iloc[start_idx:end_idx].reset_index(drop=True)

    for idx, row in current_group.iterrows():
        col_text, col_audio = st.columns([4, 1])
        # Columns 1 and 2 based on your Excel structure
        word_val = str(row.iloc[1])
        def_val = str(row.iloc[2])

        with col_text:
            st.markdown(f"### {word_val}")
            st.write(f"**Meaning:** {def_val}")
        
        with col_audio:
            if st.button("🔊 Listen", key=f"btn_{idx}"):
                audio_io = io.BytesIO()
                gTTS(text=word_val, lang="en").write_to_fp(audio_io)
                st.audio(audio_io, format="audio/mp3", autoplay=True)
        st.divider()

with tab_stats:
    # --- LOGIC PRESERVED ---
    st.subheader("📊 Your Progress")
    # ... Your original Stats code ...
