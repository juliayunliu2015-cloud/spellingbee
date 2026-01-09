import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="Vivian's Spelling Bee 2026", page_icon="🏆", layout="centered")

# Custom CSS for a "Golden" look and better buttons
st.markdown("""
    <style>
    .main { background-color: #fdfbf7; }
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        border: 2px solid #DAA520;
        background-color: white;
        color: #B8860B;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #FFD700;
        color: black;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #FFD700;
        border-radius: 10px;
        background-color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENCOURAGEMENT HEADER ---
st.markdown("""
    <div style="background: linear-gradient(135deg, #FFD700 0%, #FDB931 100%); 
                padding:25px; border-radius:15px; text-align:center; 
                margin-bottom:25px; border: 3px solid #DAA520;
                box-shadow: 0 10px 20px rgba(0,0,0,0.1);">
        <h1 style="color:#000; margin:0; font-family: 'Arial Black', sans-serif; letter-spacing: 2px;">
            🏆 GO FOR THE GOLD, VIVIAN! 🏆
        </h1>
        <p style="color:#333; font-size:1.2rem; font-weight:bold; margin:10px 0 0 0;">
            "Every word you master today is a step closer to the 2026 Trophy! 🐝✨"
        </p>
    </div>
""", unsafe_allow_html=True)

# --- 3. CORE LOGIC (DB & DATA) ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS scores (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, word TEXT, correctly_spelled INTEGER, attempts INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS daily_exam_progress (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE, correct_count INTEGER DEFAULT 0, total_attempted INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

@st.cache_data
def load_words():
    if not os.path.exists(DATA_FILE): return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        df = pd.read_excel(DATA_FILE)
        # Standardizing columns
        df.columns = [c.lower() for c in df.columns]
        word_col = next((c for c in df.columns if "word" in c or "spelling" in c), df.columns[0])
        def_col = next((c for c in df.columns if "def" in c or "meaning" in c), None)
        sent_col = next((c for c in df.columns if "sent" in c or "example" in c), None)
        
        df = df.rename(columns={word_col: "word", def_col: "definition", sent_col: "sentence"})
        df['word'] = df['word'].astype(str).str.strip()
        return df.sort_values("word").reset_index(drop=True)
    except: return pd.DataFrame(columns=["word", "definition", "sentence"])

def mask_vowels(word):
    return "".join("_" if char.lower() in "aeiou" else char for char in word)

init_db()
words_df = load_words()

# --- 4. SESSION STATE ---
if "exam_mode" not in st.session_state: st.session_state.exam_mode = "All Words"
if "current_word" not in st.session_state: st.session_state.current_word = None
if "last_result" not in st.session_state: st.session_state.last_result = None

# --- 5. TABS ---
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Alphabetical Learn", "📊 My Progress"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    st.subheader("Targeted Practice")
    
    # Mode Selector
    modes = ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14))
    exam_group = st.selectbox("Choose Your Practice Mode:", modes, index=0 if st.session_state.exam_mode == "All Words" else modes.index(st.session_state.exam_mode))
    st.session_state.exam_mode = exam_group

    # Word Selection Logic
    if exam_group == "All Words": available = words_df
    elif exam_group == "❌ Incorrect Words Only":
        conn = get_db_connection()
        bad_list = [r['word'] for r in conn.execute("SELECT DISTINCT word FROM scores WHERE correctly_spelled = 0").fetchall()]
        conn.close()
        available = words_df[words_df['word'].isin(bad_list)]
    else:
        chunk = max(1, len(words_df) // 13)
        available = words_df.iloc[(exam_group-1)*chunk : exam_group*chunk]

    if not available.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available["word"].values:
            st.session_state.current_word = available.sample(1).iloc[0]

        # Audio & Input
        word = st.session_state.current_word["word"]
        audio_io = io.BytesIO()
        gTTS(text=str(word), lang="en").write_to_fp(audio_io)
        st.audio(audio_io, format="audio/mp3")

        with st.form(key="spell_form", clear_on_submit=True):
            user_in = st.text_input("Spelling:", placeholder="Type here...")
            if st.form_submit_button("Check Spelling"):
                correct = user_in.strip().lower() == word.lower()
                # Save to DB
                today = date.today().isoformat()
                conn = get_db_connection()
                conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, 1)", (today, word, int(correct)))
                if correct:
                    conn.execute("INSERT INTO daily_exam_progress (date, correct_count) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1", (today,))
                    st.session_state.current_word = None # Trigger new word
                st.session_state.last_result = {"correct": correct, "word": word, "def": st.session_state.current_word["definition"], "sent": st.session_state.current_word["sentence"]}
                conn.commit()
                conn.close()
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["correct"]: st.success("🌟 Correct! Great job, Vivian!")
            else:
                st.error(f"❌ Not quite! The word was: **{res['word']}**")
                st.info(f"**Meaning:** {res['def']}\n\n**Sentence:** {res['sent']}")
    else:
        st.info("No words to practice in this mode! Choose another group.")

# --- TAB 2: ALPHABETICAL LEARN ---
with tab_learn:
    st.subheader("📖 Flashcards (A-Z)")
    group_choice = st.slider("Select Group", 1, 13, 1)
    chunk = max(1, len(words_df) // 13)
    learn_group = words_df.iloc[(group_choice-1)*chunk : group_choice*chunk]
    
    for i, row in learn_group.iterrows():
        with st.expander(f"Word: {mask_vowels(row['word'])}"):
            st.write(f"### {row['word']}")
            st.write(f"**Meaning:** {row['definition']}")
            st.write(f"*\"{row['sentence']}\"*")
            if st.button("🔊 Hear It", key=f"snd_{i}"):
                a_io = io.BytesIO()
                gTTS(text=str(row['word']), lang="en").write_to_fp(a_io)
                st.audio(a_io)

# --- TAB 3: MY PROGRESS ---
with tab_stats:
    st.subheader("📊 Your Achievement Gallery")
    conn = get_db_connection()
    mistakes = pd.read_sql_query("SELECT word, COUNT(*) as errors FROM scores WHERE correctly_spelled = 0 GROUP BY word ORDER BY errors DESC", conn)
    
    if not mistakes.empty:
        st.write("### 🚩 Words to Review")
        st.dataframe(mistakes, use_container_width=True)
        if st.button("🎯 Practice These Now"):
            st.session_state.exam_mode = "❌ Incorrect Words Only"
            st.session_state.current_word = None
            st.rerun()
    else:
        st.success("No incorrect words! You're a spelling superstar! 🌟")
    
    st.divider()
    if st.checkbox("Show Danger Zone"):
        if st.button("Reset All Progress"):
            conn.execute("DELETE FROM scores; DELETE FROM daily_exam_progress;")
            conn.commit()
            st.rerun()
    conn.close()
