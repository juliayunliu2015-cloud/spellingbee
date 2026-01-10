import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- 1. CONFIGURATION & ANIME STYLESHEET ---
st.set_page_config(page_title="Vivian's Spelling Quest", page_icon="🔮", layout="wide")

st.markdown("""
    <style>
        /* Main App Background - Deep Midnight Purple */
        .stApp {
            background: linear-gradient(180deg, #120b1e 0%, #1a1a2e 100%);
            color: #e0aaff;
            font-family: 'Inter', sans-serif;
        }

        /* Magical Banner */
        .magical-header {
            background: linear-gradient(90deg, #5a189a 0%, #3c096c 50%, #5a189a 100%);
            border-bottom: 3px solid #9d4edd;
            border-radius: 0px 0px 30px 30px;
            padding: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            margin-bottom: 2rem;
        }

        .magical-header h1 {
            color: #ffffff !important;
            text-shadow: 0 0 15px #c77dff, 0 0 30px #7b2cbf;
            font-weight: 900;
            letter-spacing: 2px;
        }

        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
        }

        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: #240046;
            border-radius: 15px 15px 0px 0px;
            color: #c77dff !important;
            border: 1px solid #5a189a;
            padding: 0 30px;
        }

        .stTabs [aria-selected="true"] {
            background-color: #7b2cbf !important;
            color: white !important;
            border-bottom: 3px solid #ff9100 !important;
        }

        /* Study Cards - Anime Character Card Style */
        .study-card {
            background: rgba(45, 0, 93, 0.6);
            border: 2px solid #9d4edd;
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            transition: transform 0.3s ease, border-color 0.3s ease;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            min-height: 160px;
        }

        .study-card:hover {
            transform: translateY(-5px);
            border-color: #ff9e00;
            background: rgba(60, 9, 108, 0.8);
        }

        /* Buttons - Neon Purple Action */
        div.stButton > button {
            background: linear-gradient(45deg, #7b2cbf, #9d4edd) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: bold !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 10px 20px !important;
            box-shadow: 0 4px 15px rgba(157, 78, 221, 0.4) !important;
        }

        div.stButton > button:hover {
            box-shadow: 0 0 20px #9d4edd !important;
            transform: scale(1.02);
        }

        /* Text Input */
        .stTextInput input {
            background-color: #10002b !important;
            border: 2px solid #5a189a !important;
            color: #ff9e00 !important;
            border-radius: 12px !important;
            font-size: 1.2rem !important;
            text-align: center;
        }

        .stTextInput input:focus {
            border-color: #ff9e00 !important;
            box-shadow: 0 0 10px #ff9e00 !important;
        }

        /* Metrics and Progress */
        [data-testid="stMetricValue"] {
            color: #ff9e00 !important;
            font-size: 2.5rem;
        }
        
        /* Custom Labels */
        label, p, span {
            color: #e0aaff !important;
            font-weight: 500;
        }

    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE AND DATA LOGIC (Functionality preserved) ---
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
        # Using column indices to stay flexible
        clean_rows = []
        for _, row in df.iterrows():
            if not pd.isna(row.iloc[0]):
                clean_rows.append({
                    "word": str(row.iloc[0]).strip(),
                    "definition": str(row.iloc[1]).strip() if len(row) > 1 else "No info.",
                    "sentence": str(row.iloc[2]).strip() if len(row) > 2 else ""
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

# --- HEADER ---
st.markdown('<div class="magical-header"><h1>🔮 VIVIAN\'S SPELLING QUEST</h1></div>', unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["✨ THE EXAM", "📚 SPELLBOOK", "📈 POWER LEVEL"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    today_score = get_today_count()
    col_score, col_empty = st.columns([1, 2])
    with col_score:
        st.metric("WORDS MASTERED", f"{today_score} / {GOAL}")

    if today_score >= GOAL:
        st.balloons()
        st.success("🌟 AMAZING! Your power level is over 9000! Vivian is a Master Speller! 👑")

    # Group Selection
    group_options = ["All Words", "❌ Mistake Review"] + [f"Group {i}" for i in range(1, 14)]
    selection = st.selectbox("Select your Quest:", group_options)

    if selection == "All Words":
        pool = words_df
    elif selection == "❌ Mistake Review":
        pool = words_df[words_df['word'].isin(get_mistakes())]
    else:
        num = int(selection.split()[-1])
        size = len(words_df) // 13
        pool = words_df.iloc[(num-1)*size : num*size]

    if not pool.empty:
        if st.session_state.current_word is None or st.session_state.current_word["word"] not in pool["word"].values:
            st.session_state.current_word = pool.sample(1).iloc[0]

        curr = st.session_state.current_word
        
        # Action Buttons
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            if st.button("🔊 HEAR SPELL"):
                tts = gTTS(text=curr['word'], lang='en')
                audio_io = io.BytesIO()
                tts.write_to_fp(audio_io)
                st.audio(audio_io, format="audio/mp3", autoplay=True)
        
        with btn_col2:
            if st.button("⏭️ NEW WORD"):
                st.session_state.current_word = pool.sample(1).iloc[0]
                st.session_state.last_result = None
                st.rerun()

        # Input Form
        with st.form(key="exam_form", clear_on_submit=True):
            user_input = st.text_input("Spell the word correctly:")
            if st.form_submit_button("🔥 CAST SPELL"):
                is_correct = user_input.strip().lower() == curr['word'].strip().lower()
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO scores (date, word, correctly_spelled) VALUES (?, ?, ?)", 
                                 (date.today().isoformat(), curr["word"], int(is_correct)))
                st.session_state.last_result = {"correct": is_correct, "word": curr["word"], "def": curr["definition"], "sent": curr["sentence"]}
                st.rerun()

        if st.session_state.last_result:
            res = st.session_state.last_result
            if res["correct"]:
                st.success("⭐ SUCCESS! You spelled it perfectly!")
            else:
                st.error(f"💥 OH NO! The correct spelling was: {res['word']}")
            
            st.markdown(f"""
                <div class="study-card">
                    <h3 style="color:#ff9e00; margin-top:0;">📖 Knowledge Note</h3>
                    <p><b>Meaning:</b> {res['def']}</p>
                    <p style="font-style: italic;">"{res['sent']}"</p>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("The quest list is empty! Try selecting another group.")

# --- TAB 2: STUDY ROOM (Anime Card Grid) ---
with tab_learn:
    st.subheader("🔮 Your Secret Spellbook")
    
    study_sel = st.selectbox("View Word Group:", ["All"] + [str(i) for i in range(1, 14)])
    if study_sel == "All":
        display_df = words_df
    else:
        size = len(words_df) // 13
        display_df = words_df.iloc[(int(study_sel)-1)*size : int(study_sel)*size]

    for i in range(0, len(display_df), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(display_df):
                row = display_df.iloc[i + j]
                with cols[j]:
                    st.markdown(f"""
                        <div class="study-card">
                            <h4 style="color:#ffffff; margin-top:0; border-bottom:1px solid #9d4edd;">✨ {row['word']}</h4>
                            <p style="font-size:0.85rem;">{row['definition']}</p>
                            <p style="font-size:0.8rem; font-style:italic; color:#c77dff;">"{row['sentence']}"</p>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"🔊 Listen", key=f"snd_{i+j}"):
                        tts = gTTS(text=row['word'], lang='en')
                        audio_io_s = io.BytesIO()
                        tts.write_to_fp(audio_io_s)
                        st.audio(audio_io_s, format="audio/mp3", autoplay=True)

# --- TAB 3: PROGRESS ---
with tab_stats:
    st.subheader("📈 Your Quest Progress")
    with sqlite3.connect(DB_PATH) as conn:
        bad_df = pd.read_sql_query("""
            SELECT word as 'Word', COUNT(*) as 'Mistakes' 
            FROM scores WHERE correctly_spelled = 0 
            GROUP BY word ORDER BY Mistakes DESC
        """, conn)
        
    if not bad_df.empty:
        st.write("Words currently lowering your Power Level:")
        st.dataframe(bad_df, use_container_width=True, hide_index=True)
        
        st.divider()
        if st.checkbox("Dangerous Zone: Reset Quest History"):
            if st.button("WIPE ALL DATA"):
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("DELETE FROM scores")
                st.rerun()
    else:
        st.success("No mistakes yet! Your power is unmatched! ⚔️")
