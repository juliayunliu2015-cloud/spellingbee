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
        .streamlit-expanderHeader { background-color: #2d1b3d !important; color: white !important; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE AND DATA LOGIC ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"

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
        def_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["def", "meaning", "desc"])), None)
        sent_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["sentence", "example", "usage"])), None)
        
        clean_rows = []
        for _, row in df.iterrows():
            if pd.isna(row[word_col]): continue
            clean_rows.append({
                "word": str(row[word_col]).strip(),
                "definition": str(row[def_col]).strip() if def_col and not pd.isna(row[def_col]) else "No definition available.",
                "sentence": str(row[sent_col]).strip() if sent_col and not pd.isna(row[sent_col]) else "No sample sentence available."
            })
        return pd.DataFrame(clean_rows).sort_values("word").reset_index(drop=True)
    except: return pd.DataFrame(columns=["word", "definition", "sentence"])

def get_incorrect_words():
    with sqlite3.connect(DB_PATH) as conn:
        # Fetches words where the most recent attempt or any attempt was a failure
        cursor = conn.execute("SELECT DISTINCT word FROM scores WHERE correctly_spelled = 0")
        return [row[0] for row in cursor.fetchall()]

init_db()
words_df = load_words()

if "current_word" not in st.session_state: st.session_state.current_word = None
if "last_result" not in st.session_state: st.session_state.last_result = None
if "play_trigger" not in st.session_state: st.session_state.play_trigger = False

st.markdown('<div class="magical-banner"><h1>GO FOR THE GOLD, VIVIAN! 🏆</h1></div>', unsafe_allow_html=True)
tab_exam, tab_learn, tab_stats = st.tabs(["🎯 Daily Exam", "📖 Study Room", "📊 Progress"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    group_options = ["All Words", "❌ Incorrect Words Only"] + list(range(1, 14))
    exam_group = st.selectbox("Select Study Group:", group_options)
    
    if exam_group == "All Words": 
        available_words = words_df
    elif exam_group == "❌ Incorrect Words Only":
        inc_list = get_incorrect_words()
        available_words = words_df[words_df['word'].isin(inc_list)]
    else:
        words_per_group = max(1, len(words_df) // 13)
        start_idx = (exam_group - 1) * words_per_group
        available_words = words_df.iloc[start_idx : start_idx + words_per_group]

    if not available_words.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in available_words["word"].values:
            st.session_state.current_word = available_words.sample(1).iloc[0]

        curr = st.session_state.current_word
        btn_label = "✨ CAST THE NEXT SPELL" if st.session_state.last_result and st.session_state.last_result["correct"] else "🪄 CAST SPELL (Hear Word)"
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button(btn_label):
                if st.session_state.last_result and st.session_state.last_result["correct"]:
                    st.session_state.current_word = available_words.sample(1).iloc[0]
                    st.session_state.last_result = None
                    st.rerun()
                else:
                    st.session_state.play_trigger = True
        with col_b:
            if st.button("🔄 RE-PLAY"): st.session_state.play_trigger = True

        if st.session_state.play_trigger:
            audio_io = io.BytesIO()
            gTTS(text=str(curr["word"]), lang="en").write_to_fp(audio_io)
            st.audio(audio_io, format="audio/mp3", autoplay=True)
            st.session_state.play_trigger = False

        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word you hear:", placeholder="Spell here...")
            if st.form_submit_button("SUBMIT SPELLING"):
                is_correct = user_input.strip().lower() == str(curr["word"]).strip().lower()
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO scores (date, word, correctly_spelled, attempts) VALUES (?, ?, ?, ?)", (date.today().isoformat(), curr["word"], int(is_correct), 1))
                st.session_state.last_result = {"correct": is_correct, "word": curr["word"], "definition": curr["definition"], "sentence": curr["sentence"]}
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["correct"]: st.balloons(); st.success(f"✨ Correct! It's {res['word']}.")
            else: st.error(f"❌ Incorrect. The word was: {res['word']}")
            
            st.markdown(f"""
                <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px;">
                    <p><strong>📖 Meaning:</strong> {res['definition']}</p>
                    <p><strong>🗣️ Example:</strong> <em>"{res['sentence']}"</em></p>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No words found in this group yet!")

# --- TAB 2: STUDY ROOM ---
with tab_learn:
    st.header("📖 Alphabetical Study Room")
    # Clean listing for study
    for idx, row in words_df.head(100).iterrows():
        with st.expander(f"{row['word']}"):
            st.write(f"**Meaning:** {row['definition']}")
            st.write(f"**Sentence:** {row['sentence']}")

# --- TAB 3: PROGRESS (FIXED ERROR) ---
with tab_stats:
    st.header("📊 My Progress")
    with sqlite3.connect(DB_PATH) as conn:
        # Fixed logic: Aggregate mistakes correctly
        bad_df = pd.read_sql_query("""
            SELECT word as 'Word', COUNT(*) as 'Times Incorrect' 
            FROM scores 
            WHERE correctly_spelled = 0 
            GROUP BY word 
            ORDER BY COUNT(*) DESC
        """, conn)
        
        if not bad_df.empty:
            st.subheader("❌ Words to Review")
            st.write("These words will appear when you select 'Incorrect Words Only' in the Exam tab.")
            st.dataframe(bad_df, use_container_width=True, hide_index=True)
        else:
            st.success("Perfect score so far! No incorrect words to review. ✨")
