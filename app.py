import streamlit as st
import pandas as pd
import sqlite3
import os
import random
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & MAGICAL UI SETUP ---
st.set_page_config(page_title="Spelling Bee 2026", page_icon="✨", layout="wide")

# Injecting the Dark Purple Anime Style (Logic Preserved)
st.markdown("""
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Spline+Sans:wght@300;400;500;700;900&display=swap" rel="stylesheet">
    <style>
        .stApp {
            background-color: #1a1022;
            background-image: radial-gradient(circle, rgba(157, 37, 244, 0.15) 1px, transparent 1px);
            background-size: 30px 30px;
            color: white;
            font-family: 'Spline Sans', sans-serif;
        }
        /* Custom Magical Banner */
        .magical-banner {
            background-position:50% 50%; 
            background: linear-gradient(135deg, #9d25f4 0%, #6d28d9 100%);
            border-radius: 2rem;
            padding: 2.5rem;
            text-align: center;
            border: 4px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 0 40px rgba(157, 37, 244, 0.5);
            margin-bottom: 2rem;
            background-image: linear-gradient(to right, rgba(26, 16, 34, 0.9) 0%, rgba(26, 16, 34, 0.2) 60%, rgba(26, 16, 34, 0) 100%), url(https://lh3.googleusercontent.com/aida-public/AB6AXuCr7AYPvVeqUPBshUWTIWJ2iXIQ-8K8woQJVGZzn3gXZOsD91x8eOwU5k1T9eDH0b8uekjykG9rQWN9kNidIOCSsd7p06J8IQ-11QKISWUKktStRsvX6OMpfJvCsTRYpo0Od6Lo3PzYt_R-4ub7Qf8h2gF39R8zVmMyA__pbMkAN2-H2q9T7SHEMfm5ULKJ1bkUS8YXaE2PlMU-5ep8QL2i4x-7ScztKYKjlG8ZguBjXW60PcBOj9SX88vAxsPyEuuZpbcOYlkE3Uc);

        }
        /* Glass Cards for Content */
        .glass-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(157, 37, 244, 0.3);
            border-radius: 1.5rem;
            padding: 2rem;
            margin-bottom: 20px;
        }
        /* Input Styling */
        .stTextInput input {
            background: rgba(255, 255, 255, 0.07) !important;
            border: 2px solid rgba(157, 37, 244, 0.4) !important;
            border-radius: 1rem !important;
            color: white !important;
            font-size: 1.8rem !important;
            font-weight: 900 !important;
            text-align: center !important;
        }
        /* Button Styling */
        div.stButton > button {
            background: #9d25f4 !important;
            color: white !important;
            width: 100%;
            border-radius: 1rem !important;
            border: none !important;
            font-weight: 900 !important;
            box-shadow: 0 10px 20px rgba(157, 37, 244, 0.3) !important;
        }
        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            background-color: rgba(255,255,255,0.05);
            border-radius: 10px 10px 0 0;
            padding: 10px 20px;
            color: white;
        }
        .stTabs [aria-selected="true"] { background-color: #9d25f4 !important; }
        h1, h2, h3, p, span { color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC (UNTOUCHED FROM APP-SPELL.PY) ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
DAILY_EXAM_GOAL = 33

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

init_db()
words_df = load_words()

if "current_word" not in st.session_state: st.session_state.current_word = None
if "attempts" not in st.session_state: st.session_state.attempts = 0
if "last_result" not in st.session_state: st.session_state.last_result = None
if "exam_mode" not in st.session_state: st.session_state.exam_mode = "All Words"

# --- 3. HEADER & BANNER ---
st.markdown("""
    <div class="magical-banner">
        <h1 style="font-size: 3.5rem; font-weight: 900; italic; margin: 0; letter-spacing: -2px;">GO FOR THE GOLD, VIVIAN!</h1>
        <p style="font-weight: 700; italic; opacity: 0.9; font-size: 1.2rem; margin-top: 10px;">
            "Every word you master today is a step closer to the 2026 Trophy! ✨ 🏆 ✨"
        </p>
    </div>
""", unsafe_allow_html=True)

# --- 4. UI TABS ---
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Alphabetical Learn", "📊 My Progress"])

with tab_exam:
    col_l, col_r = st.columns([1, 2], gap="large")
    
    with col_l:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("### 🏆 Quest Status")
        modes = ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14))
        exam_group = st.selectbox("Exam Group:", options=modes, key="exam_selector")
        st.session_state.exam_mode = exam_group
        
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
            end_idx = start_idx + words_per_group if exam_group < 13 else len(words_df)
            available_words = words_df.iloc[start_idx:end_idx]
            
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        if not available_words.empty:
            if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
                st.session_state.current_word = available_words.sample(1).iloc[0]
                st.session_state.attempts = 0

            # Progress Calculation
            conn = get_db_connection()
            today_date = date.today().isoformat()
            row = conn.execute("SELECT correct_count FROM daily_exam_progress WHERE date = ?", (today_date,)).fetchone()
            score_today = row[0] if row else 0
            conn.close()
            
            st.markdown(f"**Daily Goal Progress: {score_today} / {DAILY_EXAM_GOAL}**")
            st.progress(min(score_today / DAILY_EXAM_GOAL, 1.0))

            # Audio
            word_to_spell = st.session_state.current_word["word"]
            audio_io = io.BytesIO()
            gTTS(text=str(word_to_spell), lang="en").write_to_fp(audio_io)
            st.audio(audio_io, format="audio/mp3")

            with st.form(key="spell_form", clear_on_submit=True):
                user_input = st.text_input("Type the word you hear:", placeholder="? ? ? ? ?")
                submit = st.form_submit_button("SUBMIT SPELLING ✨")
                if submit:
                    st.session_state.attempts += 1
                    is_correct = user_input.strip().lower() == str(word_to_spell).strip().lower()
                    conn = get_db_connection()
                    conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, ?)",
                                 (today_date, word_to_spell, int(is_correct), st.session_state.attempts))
                    st.session_state.last_result = {
                        "is_correct": is_correct, "word": word_to_spell,
                        "definition": st.session_state.current_word["definition"],
                        "sentence": st.session_state.current_word["sentence"]
                    }
                    if is_correct:
                        conn.execute("INSERT INTO daily_exam_progress (date, correct_count, total_attempted) VALUES (?, 1, 1) ON CONFLICT(date) DO UPDATE SET correct_count = correct_count + 1, total_attempted = total_attempted + 1", (today_date,))
                        st.session_state.current_word = available_words.sample(1).iloc[0]
                        st.session_state.attempts = 0
                    else:
                        conn.execute("INSERT INTO daily_exam_progress (date, total_attempted) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET total_attempted = total_attempted + 1", (today_date,))
                    conn.commit()
                    conn.close()
                    st.rerun()

            if st.session_state.last_result:
                res = st.session_state.last_result
                if res["is_correct"]: st.balloons(); st.success("✅ Correct! Magical!")
                else:
                    st.error(f"❌ Incorrect. Correct Spelling: {res['word']}")
                    st.info(f"**Meaning:** {res['definition']}\n\n**Sentence:** {res['sentence']}")
                if st.button("Next Word ➡️"):
                    st.session_state.last_result = None
                    st.rerun()
        else:
            st.info("No words found in this mode.")
        st.markdown('</div>', unsafe_allow_html=True)

with tab_learn:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.header("📖 Alphabetical Study Groups")
    group_num = st.selectbox("Select Learning Group (1-13):", range(1, 14), key="learn_group")
    words_per_group = max(1, len(words_df) // 13)
    start_idx = (group_num - 1) * words_per_group
    end_idx = start_idx + words_per_group if group_num < 13 else len(words_df)
    current_group = words_df.iloc[start_idx:end_idx]
    
    for idx, row in current_group.iterrows():
        with st.expander(f"Word {idx+1}: {mask_vowels(row['word'])}"):
            st.subheader(f"Full Spelling: :blue[{row['word']}]")
            st.write(f"**Definition:** {row['definition']}")
            st.write(f"**Example:** _{row['sentence']}_")
            if st.button(f"🔊 Listen", key=f"audio_btn_{idx}"):
                audio_io_learn = io.BytesIO()
                gTTS(text=str(row['word']), lang="en").write_to_fp(audio_io_learn)
                st.audio(audio_io_learn, format="audio/mp3")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_stats:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.header("📊 My Progress")
    conn = get_db_connection()
    try:
        st.subheader("❌ Words to Review")
        bad_df = pd.read_sql_query("SELECT word, COUNT(*) as mistakes, MAX(date) as last_fail FROM scores WHERE correctly_spelled = 0 GROUP BY word ORDER BY mistakes DESC", conn)
        if not bad_df.empty:
            st.dataframe(bad_df, use_container_width=True)
            if st.button("🎯 Practice Incorrect Words Now"):
                st.session_state.exam_mode = "❌ Incorrect Words Only"
                st.session_state.current_word = None
                st.rerun()
        else: st.success("No mistakes yet! Great job, Vivian!")
        
        st.divider()
        st.subheader("🗑️ Reset Data")
        confirm = st.checkbox("Confirm deletion of history")
        if st.button("Reset Everything", disabled=not confirm):
            conn.execute("DELETE FROM scores"); conn.execute("DELETE FROM daily_exam_progress"); conn.commit()
            st.rerun()
    finally: conn.close()
    st.markdown('</div>', unsafe_allow_html=True)


