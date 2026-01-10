import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & ACCESSIBILITY SETUP ---
st.set_page_config(page_title="Spelling Bee 2026", page_icon="✨", layout="wide")

st.markdown("""
    <style>
        .stApp { background-color: #1a1022; color: #FFFFFF; font-family: 'Spline Sans', sans-serif; }
        .magical-banner {
            background: linear-gradient(135deg, #7e22ce 0%, #581c87 100%);
            border-radius: 1.5rem; padding: 2.5rem; text-align: center;
            border: 2px solid #a855f7; margin-bottom: 2rem;
        }
        .stTextInput input {
            background-color: #2d1b3d !important; color: #FFFFFF !important;
            border: 2px solid #9d25f4 !important; border-radius: 0.75rem !important;
            font-size: 1.5rem !important; padding: 1rem !important; text-align: center !important;
        }
        div.stButton > button {
            background-color: #9d25f4 !important; color: #FFFFFF !important;
            border: 2px solid #c084fc !important; border-radius: 0.75rem !important;
            font-weight: 800 !important; font-size: 1.1rem !important; padding: 0.8rem !important; width: 100%;
        }
        h1, h2, h3, p, label, span, div { color: #FFFFFF !important; }
        div[data-testid="stAudio"] { display: none; }
        
        .study-card {
            background: rgba(255, 255, 255, 0.05);
            border-left: 5px solid #9d25f4;
            padding: 15px;
            margin-bottom: 25px;
            border-radius: 10px;
            min-height: 180px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE AND DATA LOGIC ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
GOAL = 33

def init_db():
    """Initializes the database and clears old UNIQUE constraints that cause IntegrityErrors."""
    with sqlite3.connect(DB_PATH) as conn:
        # Check if the table has the old 'UNIQUE' index on 'word'
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='scores'")
        schema = cursor.fetchone()
        
        if schema and "UNIQUE" in schema[0].upper():
            # If the old restrictive schema exists, drop it to fix the app
            conn.execute("DROP TABLE scores")
            
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                date TEXT, 
                word TEXT, 
                correctly_spelled INTEGER
            )
        """)

@st.cache_data
def load_words():
    if not os.path.exists(DATA_FILE): return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        df = pd.read_excel(DATA_FILE)
        word_col = next((c for c in df.columns if str(c).lower() in ["word", "spelling"]), df.columns[0])
        def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "meaning", "desc"])), None)
        sent_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["sentence", "example", "usage"])), None)
        clean_rows = [{"word": str(row[word_col]).strip(), "definition": str(row[def_col]).strip() if def_col else "N/A", "sentence": str(row[sent_col]).strip() if sent_col else "N/A"} for _, row in df.iterrows() if not pd.isna(row[word_col])]
        return pd.DataFrame(clean_rows).sort_values("word").reset_index(drop=True)
    except: return pd.DataFrame(columns=["word", "definition", "sentence"])

def get_incorrect_words():
    with sqlite3.connect(DB_PATH) as conn:
        # A word is only 'incorrect' if the last time you spelled it, you got it wrong.
        cursor = conn.execute("""
            SELECT word FROM (
                SELECT word, correctly_spelled, MAX(id) FROM scores GROUP BY word
            ) WHERE correctly_spelled = 0
        """)
        return [row[0] for row in cursor.fetchall()]

def get_today_count():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT COUNT(DISTINCT word) FROM scores WHERE date = ? AND correctly_spelled = 1", (date.today().isoformat(),))
        return cursor.fetchone()[0]

init_db()
words_df = load_words()

# Session States
if "current_word" not in st.session_state: st.session_state.current_word = None
if "last_result" not in st.session_state: st.session_state.last_result = None
if "play_trigger" not in st.session_state: st.session_state.play_trigger = False

st.markdown('<div class="magical-banner"><h1>GO FOR THE GOLD, VIVIAN! 🏆</h1></div>', unsafe_allow_html=True)
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Study Room", "📊 Progress"])

group_options = ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14))

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    today_score = get_today_count()
    st.subheader(f"Progress Today: {today_score} / {GOAL} words")
    
    if today_score >= GOAL:
        st.snow()
        st.balloons()
        st.success(f"🎊 AMAZING! You've mastered {GOAL} words today! Vivian is a Spelling Queen! 👑")
    
    exam_group = st.selectbox("Select Exam Group:", group_options)
    
    if exam_group == "All Words": 
        available_words = words_df
    elif exam_group == "❌ Incorrect Words Only":
        available_words = words_df[words_df['word'].isin(get_incorrect_words())]
    else:
        words_per_group = max(1, len(words_df) // 13)
        available_words = words_df.iloc[(exam_group-1)*words_per_group : exam_group*words_per_group]

    if not available_words.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
            st.session_state.current_word = available_words.sample(1).iloc[0]

        curr = st.session_state.current_word
        is_ready_for_next = st.session_state.last_result and st.session_state.last_result["correct"]
        btn_label = "✨ CAST THE NEXT SPELL" if is_ready_for_next else "🪄 CAST SPELL (Hear Word)"
        
        if st.button(btn_label):
            if is_ready_for_next:
                st.session_state.current_word = available_words.sample(1).iloc[0]
                st.session_state.last_result = None
                st.rerun()
            else:
                st.session_state.play_trigger = True

        if st.session_state.play_trigger:
            audio_io = io.BytesIO()
            gTTS(text=str(curr["word"]), lang="en").write_to_fp(audio_io)
            st.audio(audio_io, format="audio/mp3", autoplay=True)
            st.session_state.play_trigger = False

        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word you hear:", placeholder="Spell here...")
            if st.form_submit_button("SUBMIT"):
                is_correct = user_input.strip().lower() == str(curr["word"]).strip().lower()
                with sqlite3.connect(DB_PATH) as conn:
                    # 'INSERT OR IGNORE' handles any edge cases
                    conn.execute("INSERT OR IGNORE INTO scores (date, word, correctly_spelled) VALUES (?, ?, ?)", 
                                 (date.today().isoformat(), curr["word"], int(is_correct)))
                st.session_state.last_result = {"correct": is_correct, "word": curr["word"], "definition": curr["definition"], "sentence": curr["sentence"]}
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["correct"]: st.success("✨ Correct!")
            else: st.error(f"❌ Incorrect. The word was: {res['word']}")
            st.markdown(f"""<div class="study-card"><strong>📖 Meaning:</strong> {res['definition']}<br><strong>🗣️ Example:</strong> <em>"{res['sentence']}"</em></div>""", unsafe_allow_html=True)
    else: st.info("No words found in this group!")

# --- TAB 2: STUDY ROOM ---
with tab_learn:
    study_group = st.selectbox("Select Group to Study:", group_options, key="study_select")
    
    if study_group == "All Words": study_list = words_df
    elif study_group == "❌ Incorrect Words Only":
        study_list = words_df[words_df['word'].isin(get_incorrect_words())]
    else:
        words_per_group = max(1, len(words_df) // 13)
        study_list = words_df.iloc[(study_group-1)*words_per_group : study_group*words_per_group]

    rows = [study_list.iloc[i:i+3] for i in range(0, len(study_list), 3)]
    for row_data in rows:
        cols = st.columns(3)
        for i, (idx, row) in enumerate(row_data.iterrows()):
            with cols[i]:
                if st.button(f"🔊 {row['word']}", key=f"s_btn_{idx}"):
                    audio_io_s = io.BytesIO()
                    gTTS(text=str(row['word']), lang="en").write_to_fp(audio_io_s)
                    st.audio(audio_io_s, format="audio/mp3", autoplay=True)
                
                st.markdown(f"""
                    <div class="study-card">
                        <small><strong>Meaning:</strong> {row['definition']}</small><br>
                        <small><em>"{row['sentence']}"</em></small>
                    </div>
                """, unsafe_allow_html=True)

# --- TAB 3: PROGRESS ---
with tab_stats:
    st.header("📊 My Progress")
    with sqlite3.connect(DB_PATH) as conn:
        # We query for all unique words missed at least once
        bad_df = pd.read_sql_query("""
            SELECT word as 'Word', COUNT(*) as 'Mistakes' 
            FROM scores 
            WHERE correctly_spelled = 0 
            GROUP BY word 
            ORDER BY Mistakes DESC
        """, conn)
        
        if not bad_df.empty:
            st.subheader("❌ Words to Review")
            st.dataframe(bad_df, use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("⚠️ Danger Zone")
            confirm_reset = st.checkbox("I understand resetting deletes all history.")
            if st.button("RESET INCORRECT WORD LIST", disabled=not confirm_reset):
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("DELETE FROM scores")
                st.success("History cleared!")
                st.rerun()
        else: st.success("Perfect score so far! Vivian, you're a star! ✨")
