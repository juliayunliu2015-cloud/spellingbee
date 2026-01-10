import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & ACCESSIBLE UI SETUP ---
st.set_page_config(page_title="Spelling Bee 2026", page_icon="✨", layout="wide")
# Enhanced CSS for Visibility and Accessibility
st.markdown("""
    <style>
        .stApp {
            background-color: #1a1022;
            color: #FFFFFF;
            font-family: 'Spline Sans', sans-serif;
        }
        /* Banner Style */
        .magical-banner {
            background: linear-gradient(135deg, #7e22ce 0%, #581c87 100%);
            border-radius: 1.5rem;
            padding: 2rem;
            text-align: center;
            border: 2px solid #a855f7;
            margin-bottom: 2rem;
        }
        /* INPUT VISIBILITY: Deep purple bg, White text */
        .stTextInput input {
            background-color: #2d1b3d !important;
            color: #FFFFFF !important;
            border: 2px solid #9d25f4 !important;
            font-size: 1.5rem !important;
            text-align: center !important;
        }
        /* BUTTON VISIBILITY: Bright Purple bg, White text */
        div.stButton > button {
            background-color: #9d25f4 !important;
            color: #FFFFFF !important;
            border: 2px solid #c084fc !important;
            font-weight: 800 !important;
            width: 100%;
        }
        h1, h2, h3, p, label { color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC (DB & DATA) ---
# --- 2. LOGIC & DATABASE ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS scores (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, word TEXT, correctly_spelled INTEGER, attempts INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS daily_exam_progress (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE, correct_count INTEGER DEFAULT 0, total_attempted INTEGER DEFAULT 0)")

@st.cache_data
def load_words():
    if not os.path.exists(DATA_FILE): return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        df = pd.read_excel(DATA_FILE)
        word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling"]), df.columns[0])
        clean_rows = [{"word": str(row[word_col]).strip(), "definition": str(row.get("definition", "N/A")), "sentence": str(row.get("sentence", "N/A"))} for _, row in df.iterrows() if not pd.isna(row[word_col])]
        return pd.DataFrame(clean_rows).sort_values("word").reset_index(drop=True)
    except: return pd.DataFrame(columns=["word", "definition", "sentence"])

init_db()
words_df = load_words()

if "current_word" not in st.session_state: st.session_state.current_word = None
if "last_result" not in st.session_state: st.session_state.last_result = None

# --- 3. UI LAYOUT ---
st.markdown('<div class="magical-banner"><h1>GO FOR THE GOLD, VIVIAN! 🏆</h1></div>', unsafe_allow_html=True)

tab_exam, tab_stats = st.tabs(["🎯 Daily Exam", "📊 Progress"])

with tab_exam:
    exam_group = st.selectbox("Select Study Group:", ["All Words"] + list(range(1, 14)))
    
    # Filtering Logic
    if exam_group == "All Words": available_words = words_df
    else:
        words_per_group = max(1, len(words_df) // 13)
        start_idx = (exam_group - 1) * words_per_group
        available_words = words_df.iloc[start_idx : start_idx + words_per_group]

    if not available_words.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
            st.session_state.current_word = available_words.sample(1).iloc[0]

        word_to_spell = st.session_state.current_word["word"]
        
        # Audio System (Manual Play)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🪄 HEAR WORD"):
                audio_io = io.BytesIO()
                gTTS(text=str(word_to_spell), lang="en").write_to_fp(audio_io)
                st.audio(audio_io, format="audio/mp3", autoplay=True)
        with col_b:
            st.write("Click to hear spelling")

        # Input Form
        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word you hear:", placeholder="Enter spelling...")
            if st.form_submit_button("SUBMIT SPELLING"):
                is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
                today = date.today().isoformat()
                
                # FIXED: Database Transaction
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, 1)", (today, word_to_spell, int(is_correct), 1))
                    if is_correct:
                        conn.execute("INSERT INTO daily_exam_progress (date, correct_count) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1", (today,))
                
                st.session_state.last_result = {"correct": is_correct, "word": word_to_spell}
                if is_correct: st.session_state.current_word = available_words.sample(1).iloc[0]
                st.rerun()

        if st.session_state.last_result:
            if st.session_state.last_result["correct"]: st.balloons(); st.success("Correct! ✨")
            else: st.error(f"Incorrect. The word was: {st.session_state.last_result['word']}")
            if st.button("Next Word ➡️"):
                st.session_state.last_result = None
                st.rerun()




# --- 4. TABS ---
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Study Room", "📊 Progress"])

with tab_exam:
    # Sidebar-style selection without the extra card
    exam_group = st.selectbox("Select Study Group:", ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14)))
    
    # Filter Logic
    if exam_group == "All Words": available_words = words_df
    elif exam_group == "❌ Incorrect Words Only":
        conn = get_db_connection()
        bad_list = [row['word'] for row in conn.execute("SELECT DISTINCT word FROM scores WHERE correctly_spelled = 0").fetchall()]
        conn.close()
        available_words = words_df[words_df['word'].isin(bad_list)]
    else:
        words_per_group = max(1, len(words_df) // 13)
        start_idx = (exam_group - 1) * words_per_group
        available_words = words_df.iloc[start_idx : start_idx + words_per_group]

    if not available_words.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
            st.session_state.current_word = available_words.sample(1).iloc[0]

        # Progress Section
        conn = get_db_connection()
        today = date.today().isoformat()
        res = conn.execute("SELECT correct_count FROM daily_exam_progress WHERE date = ?", (today,)).fetchone()
        score = res[0] if res else 0
        conn.close()
        
        st.write(f"### 🏆 Daily Goal: {score} / {DAILY_EXAM_GOAL}")
        st.progress(min(score / DAILY_EXAM_GOAL, 1.0))

        # --- AUDIO BUTTONS (No Auto-play) ---
        col_a, col_b = st.columns(2)
        word_to_spell = st.session_state.current_word["word"]
        
        def play_audio():
            audio_io = io.BytesIO()
            gTTS(text=str(word_to_spell), lang="en").write_to_fp(audio_io)
            st.audio(audio_io, format="audio/mp3", autoplay=True)

        with col_a:
            if st.button("🪄 CAST SPELL (Hear Word)"):
                play_audio()
        with col_b:
            if st.button("🔄 RE-PLAY SOUND"):
                play_audio()

        # Input Section
        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word you hear:", placeholder="Enter spelling here...")
            submit = st.form_submit_button("SUBMIT SPELLING")
            
            if submit:
                is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
                conn = get_db_connection()
                conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, 1)", (today, word_to_spell, int(is_correct), 1))
                if is_correct:
                    conn.execute("INSERT INTO daily_exam_progress (date, correct_count) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1", (today,))
                    st.session_state.current_word = available_words.sample(1).iloc[0]
                conn.commit()
                conn.close()
                st.session_state.last_result = {"correct": is_correct, "word": word_to_spell}
                st.rerun()

        if st.session_state.last_result:
            if st.session_state.last_result["correct"]:
                st.balloons()
                st.success("✨ Excellent! That's correct.")
            else:
                st.error(f"❌ Not quite. The word was: {st.session_state.last_result['word']}")
            if st.button("Next Word ➡️"):
                st.session_state.last_result = None
                st.rerun()

with tab_learn:
    st.header("📖 Alphabetical Study")
    # Clean list display without cards for better readability
    for idx, row in words_df.head(20).iterrows(): # Show first 20 as example
        with st.expander(f"Word: {row['word'][0]}..."):
            st.write(f"**Full Word:** {row['word']}")
            st.write(f"**Meaning:** {row['definition']}")

with tab_stats:
    st.header("📊 My Progress")
    # Logic for progress preserved.
