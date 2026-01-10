import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- 1. DARK PURPLE ANIME STYLESHEET ---
st.set_page_config(page_title="Vivian's Spelling Quest", page_icon="🔮", layout="wide")

st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #0d001a 0%, #1b0033 100%); color: #dcbfff; }
        .anime-header {
            background: linear-gradient(90deg, #4b0082, #8a2be2);
            padding: 2rem; border-radius: 0 0 30px 30px; border-bottom: 4px solid #ff00ff;
            text-align: center; box-shadow: 0 0 20px rgba(255, 0, 255, 0.3); margin-bottom: 2rem;
        }
        .anime-header h1 { color: #ffffff !important; text-shadow: 2px 2px #ff00ff; font-weight: 900; }
        div.stButton > button {
            background: linear-gradient(45deg, #4b0082, #9400d3) !important;
            border: 2px solid #ff00ff !important; color: white !important;
            border-radius: 12px !important; font-weight: 800 !important;
        }
        .anime-card {
            background: rgba(20, 0, 40, 0.8); border: 2px solid #8a2be2;
            border-radius: 15px; padding: 20px; border-left: 8px solid #ff00ff;
        }
        .stTextInput input { background-color: #1a0033 !important; border: 2px solid #8a2be2 !important; color: #00ffcc !important; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA & FUNCTIONAL LOGIC ---
DB_PATH = "scores.db"
DATA_FILE = "Spelling bee 2026.xlsx"
GOAL = 33

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                date TEXT, 
                word TEXT, 
                correctly_spelled INTEGER
            )
        """)

def load_words():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["word", "definition", "sentence"])
    try:
        df = pd.read_excel(DATA_FILE)
        clean_rows = []
        for _, row in df.iterrows():
            # CHANGE HERE: We assume Col 0 is ID, Col 1 is Word, Col 2 is Def, Col 3 is Sentence
            # If your Excel has NO ID column, change these back to 0, 1, 2
            word_val = str(row.iloc[1]).strip() 
            if word_val.lower() != "nan" and not word_val.isdigit():
                clean_rows.append({
                    "word": word_val,
                    "definition": str(row.iloc[2]).strip() if len(row) > 2 else "...",
                    "sentence": str(row.iloc[3]).strip() if len(row) > 3 else ""
                })
        return pd.DataFrame(clean_rows)
    except:
        return pd.DataFrame(columns=["word", "definition", "sentence"])

def get_mistakes():
    with sqlite3.connect(DB_PATH) as conn:
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

# --- 3. SESSION STATE ---
if "current_word" not in st.session_state: st.session_state.current_word = None
if "last_result" not in st.session_state: st.session_state.last_result = None

# --- UI ---
st.markdown('<div class="anime-header"><h1>🔮 VIVIAN\'S SPELLING QUEST</h1></div>', unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["🏹 THE QUEST", "📖 SPELLBOOK", "📊 POWER LEVEL"])

with tab_exam:
    today_score = get_today_count()
    st.metric("WORDS CONQUERED", f"{today_score} / {GOAL}")

    group_options = ["All Words", "❌ Mistake Review"] + [f"Group {i}" for i in range(1, 14)]
    selection = st.selectbox("Quest Difficulty:", group_options)

    if selection == "All Words": pool = words_df
    elif selection == "❌ Mistake Review": pool = words_df[words_df['word'].isin(get_mistakes())]
    else:
        num = int(selection.split()[-1])
        size = len(words_df) // 13
        pool = words_df.iloc[(num-1)*size : num*size]

    if not pool.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in pool["word"].values:
            st.session_state.current_word = pool.sample(1).iloc[0]

        curr = st.session_state.current_word
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔊 SUMMON SOUND"):
                # Clean word to ensure gTTS reads text only
                clean_text = str(curr['word']).replace('.0', '')
                tts = gTTS(text=clean_text, lang='en')
                audio_io = io.BytesIO()
                tts.write_to_fp(audio_io)
                st.audio(audio_io, format="audio/mp3", autoplay=True)
        with col2:
            if st.button("⏭️ SEEK NEW WORD"):
                st.session_state.current_word = pool.sample(1).iloc[0]
                st.session_state.last_result = None
                st.rerun()

        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word precisely:")
            if st.form_submit_button("🔥 CAST SPELL"):
                is_correct = user_input.strip().lower() == str(curr['word']).strip().lower()
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO scores (date, word, correctly_spelled) VALUES (?, ?, ?)", 
                                 (date.today().isoformat(), curr["word"], int(is_correct)))
                st.session_state.last_result = {"correct": is_correct, "word": curr["word"], "def": curr["definition"], "sent": curr["sentence"]}
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["correct"]: st.success("✅ PERFECT CAST!")
            else: st.error(f"❌ FAILED! Correct spelling: {res['word']}")
            st.markdown(f'<div class="anime-card"><b>Meaning:</b> {res["def"]}<br><i>"{res["sent"]}"</i></div>', unsafe_allow_html=True)

with tab_learn:
    for i in range(0, len(words_df), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(words_df):
                row = words_df.iloc[i + j]
                with cols[j]:
                    st.markdown(f'<div class="anime-card">✨ <b>{row["word"]}</b><br><small>{row["definition"]}</small></div>', unsafe_allow_html=True)
                    if st.button(f"🔊 Listen", key=f"snd_{i+j}"):
                        tts = gTTS(text=str(row['word']), lang='en')
                        audio_io_s = io.BytesIO()
                        tts.write_to_fp(audio_io_s)
                        st.audio(audio_io_s, format="audio/mp3", autoplay=True)

with tab_stats:
    with sqlite3.connect(DB_PATH) as conn:
        bad_df = pd.read_sql_query("SELECT word, COUNT(*) as Mistakes FROM scores WHERE correctly_spelled = 0 GROUP BY word ORDER BY Mistakes DESC", conn)
    st.dataframe(bad_df, use_container_width=True)
