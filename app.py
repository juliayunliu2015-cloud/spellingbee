import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & ACCESSIBILITY SETUP ---
st.set_page_config(page_title="Spelling Bee 2026", page_icon="✨", layout="wide")

# High-contrast CSS for accessibility and visibility
st.markdown("""
    <style>
        .stApp {
            background-color: #1a1022;
            color: #FFFFFF;
            font-family: 'Spline Sans', sans-serif;
        }
        /* Hero Banner */
        .magical-banner {
            background: linear-gradient(135deg, #7e22ce 0%, #581c87 100%);
            border-radius: 1.5rem;
            padding: 2.5rem;
            text-align: center;
            border: 2px solid #a855f7;
            margin-bottom: 2rem;
        }
        /* Input Visibility: Deep purple background with bright white text */
        .stTextInput input {
            background-color: #2d1b3d !important;
            color: #FFFFFF !important;
            border: 2px solid #9d25f4 !important;
            border-radius: 0.75rem !important;
            font-size: 1.5rem !important;
            padding: 1rem !important;
            text-align: center !important;
        }
        /* Button Visibility: Solid Purple with High Contrast White Text */
        div.stButton > button {
            background-color: #9d25f4 !important;
            color: #FFFFFF !important;
            border: 2px solid #c084fc !important;
            border-radius: 0.75rem !important;
            font-weight: 800 !important;
            font-size: 1.1rem !important;
            padding: 0.8rem !important;
            width: 100%;
        }
        /* Ensure all text labels are white */
        h1, h2, h3, p, label, span, div { color: #FFFFFF !important; }
        
        /* Hide the default audio player visually */
        div[data-testid="stAudio"] {
            display: none;
        }
        
        /* Expander Styling */
        .streamlit-expanderHeader {
            background-color: #2d1b3d !important;
            color: white !important;
            border-radius: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE AND DATA LOGIC ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

def init_db():
    """Initializes the database using a secure context manager."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                date TEXT, 
                word TEXT, 
                correctly_spelled INTEGER, 
                attempts INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_exam_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                date TEXT UNIQUE, 
                correct_count INTEGER DEFAULT 0, 
                total_attempted INTEGER DEFAULT 0
            )
        """)

@st.cache_data
def load_words():
    """Loads and cleans the spelling list from Excel with SMART COLUMN DETECTION."""
    if not os.path.exists(DATA_FILE): 
        return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        df = pd.read_excel(DATA_FILE)
        
        # --- FIXED: SMART COLUMN DETECTION ---
        # 1. Find Word Column (looks for 'word', 'spelling', etc.)
        word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling"]), df.columns[0])
        
        # 2. Find Definition Column (looks for 'def', 'meaning', 'description')
        def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "meaning", "desc"])), None)
        
        # 3. Find Sentence Column (looks for 'sentence', 'example', 'usage')
        sent_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["sentence", "example", "sample", "usage"])), None)
        
        clean_rows = []
        for _, row in df.iterrows():
            if pd.isna(row[word_col]): continue
            
            # Extract data using the found column names
            w = str(row[word_col]).strip()
            d = str(row[def_col]).strip() if def_col and not pd.isna(row[def_col]) else "No definition available."
            s = str(row[sent_col]).strip() if sent_col and not pd.isna(row[sent_col]) else "No sample sentence available."
            
            clean_rows.append({"word": w, "definition": d, "sentence": s})
            
        return pd.DataFrame(clean_rows).sort_values("word").reset_index(drop=True)
    except Exception as e:
        # Fallback if file read fails completely
        print(f"Error loading Excel: {e}")
        return pd.DataFrame(columns=["word", "definition", "sentence"])

def mask_vowels(word):
    return "".join("_" if char.lower() in "aeiou" else char for char in word)

init_db()
words_df = load_words()

# Session State Management
if "current_word" not in st.session_state: st.session_state.current_word = None
if "last_result" not in st.session_state: st.session_state.last_result = None
if "play_trigger" not in st.session_state: st.session_state.play_trigger = False
if "learn_audio" not in st.session_state: st.session_state.learn_audio = None

# --- 3. UI DISPLAY ---
st.markdown("""
    <div class="magical-banner">
        <h1 style="font-size: 3rem; font-weight: 900; margin: 0;">GO FOR THE GOLD, VIVIAN!</h1>
        <p style="font-weight: 600; font-style: italic; margin-top: 10px; color: #f3e8ff !important;">
            "Every word you master today is a step closer to the 2026 Trophy! ✨ 🏆 ✨"
        </p>
    </div>
""", unsafe_allow_html=True)

# TABS
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Study Room", "📊 Progress"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    exam_group = st.selectbox("Select Study Group:", ["All Words"] + list(range(1, 14)))
    
    # Word Filtering Logic
    if exam_group == "All Words": 
        available_words = words_df
    else:
        words_per_group = max(1, len(words_df) // 13)
        start_idx = (exam_group - 1) * words_per_group
        available_words = words_df.iloc[start_idx : start_idx + words_per_group]

    if not available_words.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
            st.session_state.current_word = available_words.sample(1).iloc[0]

        word_to_spell = st.session_state.current_word["word"]
        definition = st.session_state.current_word["definition"]
        sentence = st.session_state.current_word["sentence"]
        
        # Audio Interaction (Hidden Player)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🪄 CAST SPELL (Hear Word)"):
                st.session_state.play_trigger = True
        with col_b:
            if st.button("🔄 RE-PLAY SOUND"):
                st.session_state.play_trigger = True

        if st.session_state.play_trigger:
            audio_io = io.BytesIO()
            gTTS(text=str(word_to_spell), lang="en").write_to_fp(audio_io)
            st.audio(audio_io, format="audio/mp3", autoplay=True)
            st.session_state.play_trigger = False

        # Form Logic for Spelling Submission
        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word you hear:", placeholder="Enter spelling here...")
            if st.form_submit_button("SUBMIT SPELLING"):
                is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
                today_str = date.today().isoformat()
                
                # Transactional database update
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        INSERT INTO scores (date, word, correctly_spelled, attempts) 
                        VALUES (?, ?, ?, ?)
                    """, (today_str, word_to_spell, int(is_correct), 1))
                    
                    if is_correct:
                        conn.execute("""
                            INSERT INTO daily_exam_progress (date, correct_count) 
                            VALUES (?, 1) 
                            ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1
                        """, (today_str,))
                
                # SAVE DEFINITION AND SENTENCE TO DISPLAY AFTER CHECK
                st.session_state.last_result = {
                    "correct": is_correct, 
                    "word": word_to_spell,
                    "definition": definition,
                    "sentence": sentence
                }
                
                if is_correct: 
                    st.session_state.current_word = available_words.sample(1).iloc[0]
                st.rerun()

        # Feedback Section (Now shows Meaning & Sentence)
        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["correct"]: 
                st.balloons()
                st.success("✨ Excellent! That's correct.")
            else: 
                st.error(f"❌ Not quite. The word was: {res['word']}")
            
            # SHOW MEANING AND SENTENCE
            st.markdown(f"""
                <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; margin-top: 10px;">
                    <p><strong>📖 Meaning:</strong> {res['definition']}</p>
                    <p><strong>🗣️ Example:</strong> <em>"{res['sentence']}"</em></p>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("Next Word ➡️"):
                st.session_state.last_result = None
                st.rerun()
    else:
        st.info("No words found for this selection.")

# --- TAB 2: STUDY ROOM (RESTORED) ---
with tab_learn:
    st.header("📖 Alphabetical Study Room")
    learn_group = st.selectbox("Select Group to Study:", range(1, 14), key="learn_group_select")
    
    # Logic to split words into groups
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (learn_group - 1) * words_per_group
    end_idx = start_idx + words_per_group if learn_group < 13 else len(words_df)
    study_words = words_df.iloc[start_idx:end_idx]

    # Handle Audio for Learn Tab
    if st.session_state.learn_audio:
        audio_io = io.BytesIO()
        gTTS(text=str(st.session_state.learn_audio), lang="en").write_to_fp(audio_io)
        st.audio(audio_io, format="audio/mp3", autoplay=True)
        st.session_state.learn_audio = None # Reset

    for idx, row in study_words.iterrows():
        # Masked title to encourage guessing before revealing
        with st.expander(f"{idx+1}. {mask_vowels(row['word'])}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### 🔤 {row['word']}")
                st.write(f"**Meaning:** {row['definition']}")
                st.write(f"**Sentence:** *{row['sentence']}*")
            with col2:
                # Unique key for every button to prevent conflicts
                if st.button("🔊 Listen", key=f"btn_learn_{idx}"):
                    st.session_state.learn_audio = row['word']
                    st.rerun()

# --- TAB 3: PROGRESS ---
with tab_stats:
    st.header("📊 My Progress")
    with sqlite3.connect(DB_PATH) as conn:
        bad_df = pd.read_sql_query("""
            SELECT word, COUNT(*) as mistakes 
            FROM scores 
            WHERE correctly_spelled = 0 
            GROUP BY word 
            ORDER BY mistakes DESC
        """, conn)
        
        if not bad_df.empty:
            st.write("### ❌ Words to Review")
            st.dataframe(bad_df, use_container_width=True)
        else:
            st.success("No mistakes yet! You're doing a magical job, Vivian!")
