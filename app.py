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
    <div style=" background-position: 50% 60%;background-image: linear-gradient(to right, rgba(26, 16, 34, 0.9) 0%, rgba(26, 16, 34, 0.2) 60%, rgba(26, 16, 34, 0) 100%), url(https://lh3.googleusercontent.com/aida-public/AB6AXuCr7AYPvVeqUPBshUWTIWJ2iXIQ-8K8woQJVGZzn3gXZOsD91x8eOwU5k1T9eDH0b8uekjykG9rQWN9kNidIOCSsd7p06J8IQ-11QKISWUKktStRsvX6OMpfJvCsTRYpo0Od6Lo3PzYt_R-4ub7Qf8h2gF39R8zVmMyA__pbMkAN2-H2q9T7SHEMfm5ULKJ1bkUS8YXaE2PlMU-5ep8QL2i4x-7ScztKYKjlG8ZguBjXW60PcBOj9SX88vAxsPyEuuZpbcOYlkE3Uc); padding:20px; border-radius:15px; text-align:center; margin-bottom:25px; border: 2px solid #DAA520;">
        <h1 style="color:#fff; margin:0; font-family: 'Arial Black', sans-serif; text-align: left;">GO FOR THE GOLD, VIVIAN!</h1>
        <p style="color:#fff; font-size:1.2rem; font-weight:bold; margin:10px 0 0 0;text-align: left;">
            "Every word you master today is a step closer to the 2026 Trophy! 🐝✨"
        </p>
    </div>
""", unsafe_allow_html=True)

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
        return pd.DataFrame(columns=["word", "definition"])
    try:
        df = pd.read_excel(DATA_FILE)
        # Identify columns
        word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling"]), df.columns[0])
        def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "meaning", "desc"])), None)
        
        clean_rows = []
        for _, row in df.iterrows():
            if pd.isna(row[word_col]): continue
            clean_rows.append({
                "word": str(row[word_col]).strip(),
                "definition": str(row[def_col]).strip() if def_col and not pd.isna(row[def_col]) else "No definition available."
            })
        # Sort A-Z immediately for the Learn Tab
        return pd.DataFrame(clean_rows).sort_values("word").reset_index(drop=True)
    except:
        return pd.DataFrame(columns=["word", "definition"])

def mask_vowels(word):
    return "".join("_" if char.lower() in "aeiou" else char for char in word)

# --- APP INITIALIZATION ---
init_db()
words_df = load_words()

# Session State Initialization
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

# --- TAB 1: DAILY EXAM (UPDATED WITH SHUFFLED QUEUE) ---
with tab_exam:
    st.header("Daily Challenge")
    
    modes = ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14))
    
    if st.session_state.exam_mode not in modes:
        st.session_state.exam_mode = "All Words"
        
    exam_group = st.selectbox(
        "Select Exam Group or Practice Mode:",
        options=modes,
        index=modes.index(st.session_state.exam_mode),
        key="exam_mode_selector"
    )

    # --- QUEUE INITIALIZATION ---
    # We clear the queue if the user changes the group mode
    if "word_queue" not in st.session_state or st.session_state.exam_mode != exam_group:
        st.session_state.exam_mode = exam_group
        st.session_state.word_queue = [] # Reset deck

    # Filter Logic for the "Deck"
    if exam_group == "All Words":
        pool = words_df
    elif exam_group == "❌ Incorrect Words Only":
        conn = get_db_connection()
        bad_list = [row['word'] for row in conn.execute("SELECT DISTINCT word FROM scores WHERE correctly_spelled = 0").fetchall()]
        conn.close()
        pool = words_df[words_df['word'].isin(bad_list)]
    else:
        words_per_group = max(1, len(words_df) // 13)
        start_idx = (exam_group - 1) * words_per_group
        end_idx = start_idx + words_per_group if exam_group < 13 else len(words_df)
        pool = words_df.iloc[start_idx:end_idx]

    # --- DECK REPLENISHMENT ---
    # If the queue is empty, we "reshuffle the deck"
    if not pool.empty and len(st.session_state.word_queue) == 0:
        indices = pool.index.tolist()
        random.shuffle(indices)
        st.session_state.word_queue = indices
        # Set the first word from the new shuffled queue
        st.session_state.current_word = pool.loc[st.session_state.word_queue.pop(0)]
        st.session_state.attempts = 0

    if not pool.empty:
        # Progress Bar
        conn = get_db_connection()
        today_date = date.today().isoformat()
        row = conn.execute("SELECT correct_count FROM daily_exam_progress WHERE date = ?", (today_date,)).fetchone()
        score_today = row[0] if row else 0
        conn.close()
        
        st.progress(min(score_today / DAILY_EXAM_GOAL, 1.0))
        st.write(f"Daily Progress: **{score_today} / {DAILY_EXAM_GOAL}**")
        st.write(f"🎴 Words remaining in deck: **{len(st.session_state.word_queue)}**")

        # Audio
        word_to_spell = st.session_state.current_word["word"]
        audio_io = io.BytesIO()
        gTTS(text=str(word_to_spell), lang="en").write_to_fp(audio_io)
        st.audio(audio_io, format="audio/mp3")

        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word:")
            if st.form_submit_button("Check"):
                st.session_state.attempts += 1
                is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
                
                conn = get_db_connection()
                conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, ?)",
                             (today_date, word_to_spell, int(is_correct), st.session_state.attempts))
                
                st.session_state.last_result = {
                    "is_correct": is_correct, "word": word_to_spell,
                    "definition": st.session_state.current_word["definition"]
                }

                if is_correct:
                    conn.execute("INSERT INTO daily_exam_progress (date, correct_count, total_attempted) VALUES (?, 1, 1) ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1, total_attempted = total_attempted + 1", (today_date,))
                    # Draw NEXT word from deck if correct
                    if st.session_state.word_queue:
                        st.session_state.current_word = pool.loc[st.session_state.word_queue.pop(0)]
                    else:
                        st.session_state.current_word = None # Will trigger reshuffle next loop
                    st.session_state.attempts = 0
                else:
                    conn.execute("INSERT INTO daily_exam_progress (date, total_attempted) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET total_attempted = total_attempted + 1", (today_date,))
                
                conn.commit()
                conn.close()
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["is_correct"]: st.success("✅ Correct!")
            else:
                st.error("❌ Incorrect")
                st.subheader(f"Correct Spelling: :green[{res['word']}]")
                st.write(f"**Meaning:** {res['definition']}")
       
            if st.button("Next Word"):
                # If they want to skip the word they missed, we draw from deck
                if st.session_state.word_queue:
                    st.session_state.current_word = pool.loc[st.session_state.word_queue.pop(0)]
                    st.session_state.attempts = 0
                else:
                    st.session_state.current_word = None
                st.session_state.last_result = None
                st.rerun()
    else:
        st.info("No words found in this mode.")

# --- 2. MODIFIED TAB 2 CODE ---
with tab_learn:
    st.header("📖 Alphabetical Study Groups")
    
    group_num = st.selectbox("Select Learning Group (1-13):", range(1, 14), key="learn_group_choice")
    
    # Calculate group slice
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    
    current_group = words_df.iloc[start_idx:end_idx].reset_index(drop=True)
    
    st.divider()

    # Display words: 1 word per row
    for idx, row in current_group.iterrows():
        # Setup columns: Text on the left, Button on the right
        col_text, col_audio = st.columns([3, 1])
        
        word_to_read = str(row['word']).replace('.0', '').strip()

        with col_text:
            # Displays the Word as a header and the meaning underneath
            st.markdown(f"### {word_to_read}")
            st.write(f"**Meaning:** {row['definition']}")
        
        with col_audio:
            # The button is mapped to the specific word
            if st.button(f"🔊 Listen", key=f"study_btn_{idx}"):
                # Generate the sound for this specific word
                audio_io_learn = io.BytesIO()
                gTTS(text=word_to_read, lang="en").write_to_fp(audio_io_learn)
                
                # Autoplay=True makes it play the moment the button is clicked
                st.audio(audio_io_learn, format="audio/mp3", autoplay=True)
        
        st.divider()

# --- TAB 3: MY PROGRESS ---
with tab_stats:
    st.header("📊 My Progress")
    conn = get_db_connection()
    try:
        # Incorrect Words Table
        st.subheader("❌ Words to Review")
        bad_df = pd.read_sql_query("""
            SELECT word, COUNT(*) as mistakes, MAX(date) as last_fail 
            FROM scores WHERE correctly_spelled = 0 
            GROUP BY word ORDER BY mistakes DESC
        """, conn)

        if not bad_df.empty:
            st.dataframe(bad_df, use_container_width=True)
            if st.button("🎯 Practice These Incorrect Words Now"):
                st.session_state.exam_mode = "❌ Incorrect Words Only"
                st.session_state.current_word = None
                st.success("Practice mode updated! Switch to 'Daily Exam' to begin.")
        else:
            st.success("No mistakes yet! You're doing great, Vivian!")

        # Reset Progress
        st.divider()
        st.subheader("🗑️ Reset All Data")
        confirm = st.checkbox("I am sure I want to delete all my history.")
        if st.button("Reset Everything", disabled=not confirm):
            conn.execute("DELETE FROM scores")
            conn.execute("DELETE FROM daily_exam_progress")
            conn.commit()
            st.rerun()
    finally:
        conn.close()

















