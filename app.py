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
        /* Base Theme */
        .stApp {
            background: linear-gradient(135deg, #0d001a 0%, #1b0033 100%);
            color: #dcbfff;
        }

        /* Anime Header */
        .anime-header {
            background: linear-gradient(90deg, #4b0082, #8a2be2);
            padding: 2.5rem;
            border-radius: 0 0 50px 50px;
            border-bottom: 4px solid #ff00ff;
            text-align: center;
            box-shadow: 0 0 25px rgba(255, 0, 255, 0.3);
            margin-bottom: 2rem;
        }
        
        .anime-header h1 {
            color: #ffffff !important;
            text-shadow: 2px 2px #ff00ff, 0 0 15px #ffffff;
            font-family: 'Inter', sans-serif;
            font-weight: 900;
            letter-spacing: 3px;
        }

        /* Navigation Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 15px;
            padding: 10px;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(138, 43, 226, 0.1);
            border: 1px solid #4b0082;
            border-radius: 10px;
            color: #dcbfff !important;
            padding: 10px 25px;
            font-weight: bold;
        }

        .stTabs [aria-selected="true"] {
            background: #8a2be2 !important;
            border-color: #ff00ff !important;
            box-shadow: 0 0 10px #ff00ff;
        }

        /* Action Buttons */
        div.stButton > button {
            background: linear-gradient(45deg, #4b0082, #9400d3) !important;
            border: 2px solid #ff00ff !important;
            color: white !important;
            border-radius: 15px !important;
            padding: 0.8rem 2rem !important;
            font-weight: 800 !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
        }

        div.stButton > button:hover {
            transform: scale(1.05);
            box-shadow: 0 0 20px #ff00ff;
        }

        /* Anime "Card" for Word details */
        .anime-card {
            background: rgba(20, 0, 40, 0.8);
            border: 2px solid #8a2be2;
            border-radius: 20px;
            padding: 25px;
            margin-top: 1.5rem;
            box-shadow: 0 10px 20px rgba(0,0,0,0.5);
            border-left: 8px solid #ff00ff;
        }

        /* Inputs */
        .stTextInput input {
            background-color: #1a0033 !important;
            border: 2px solid #8a2be2 !important;
            color: #00ffcc !important;
            border-radius: 10px !important;
            font-size: 1.3rem !important;
            text-align: center;
        }
        
        .stTextInput input:focus {
            border-color: #ff00ff !important;
            box-shadow: 0 0 15px #ff00ff !important;
        }

        /* Progress Bar (Metric) */
        [data-testid="stMetricValue"] {
            color: #ff00ff !important;
            font-weight: 900 !important;
            text-shadow: 0 0 5px rgba(255,0,255,0.5);
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA & FUNCTIONAL LOGIC (UNTOUCHED) ---
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
            if not pd.isna(row.iloc[0]):
                clean_rows.append({
                    "word": str(row.iloc[0]).strip(),
                    "definition": str(row.iloc[1]).strip() if len(row) > 1 else "...",
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

# --- UI HEADER ---
st.markdown('<div class="anime-header"><h1>🔮 VIVIAN\'S SPELLING QUEST</h1></div>', unsafe_allow_html=True)

tab_exam, tab_learn, tab_stats = st.tabs(["🏹 THE QUEST", "📖 SPELLBOOK", "📊 POWER LEVEL"])

# --- TAB 1: DAILY EXAM ---
with tab_exam:
    today_score = get_today_count()
    col_m, col_e = st.columns([1, 2])
    with col_m:
        st.metric("WORDS CONQUERED", f"{today_score} / {GOAL}")

    if today_score >= GOAL:
        st.balloons()
        st.success("✨ MISSION COMPLETE! Vivian is a Legendary Sorceress of Words! 👑")

    # Selection Logic
    group_options = ["All Words", "❌ Mistake Review"] + [f"Group {i}" for i in range(1, 14)]
    selection = st.selectbox("Choose Your Quest Difficulty:", group_options)

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
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("🔊 SUMMON SOUND"):
                tts = gTTS(text=curr['word'], lang='en')
                audio_io = io.BytesIO()
                tts.write_to_fp(audio_io)
                st.audio(audio_io, format="audio/mp3", autoplay=True)
        
        with col_act2:
            if st.button("⏭️ SEEK NEW WORD"):
                st.session_state.current_word = pool.sample(1).iloc[0]
                st.session_state.last_result = None
                st.rerun()

        # Spell Form
        with st.form(key="spell_form", clear_on_submit=True):
            user_input = st.text_input("Type the word precisely:")
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
                st.markdown('<p style="color:#00ffcc; font-size:1.5rem; font-weight:bold;">✅ PERFECT CAST!</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p style="color:#ff0033; font-size:1.5rem; font-weight:bold;">❌ SPELL FAILED! The correct form was: {res["word"]}</p>', unsafe_allow_html=True)
            
            st.markdown(f"""
                <div class="anime-card">
                    <h3 style="color:#ff9900; margin:0;">📜 Spell Insight</h3>
                    <p style="margin: 10px 0;"><b>Meaning:</b> {res['def']}</p>
                    <p style="font-style: italic; color: #cbd5e1;">"{res['sent']}"</p>
                </div>
            """, unsafe_allow_html=True)

# --- TAB 2: STUDY ROOM ---
with tab_learn:
    st.subheader("🔮 Ancient Spellbook")
    study_sel = st.selectbox("Page Number (Group):", ["All"] + [str(i) for i in range(1, 14)])
    
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
                        <div class="anime-card" style="min-height: 200px;">
                            <h4 style="color:#ff00ff; border-bottom:1px solid #ff00ff;">✨ {row['word']}</h4>
                            <p style="font-size:0.9rem;">{row['definition']}</p>
                            <p style="font-size:0.8rem; font-style:italic; color:#8a2be2;">"{row['sentence']}"</p>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"🔊 Listen", key=f"snd_{i+j}"):
                        tts = gTTS(text=row['word'], lang='en')
                        audio_io_s = io.BytesIO()
                        tts.write_to_fp(audio_io_s)
                        st.audio(audio_io_s, format="audio/mp3", autoplay=True)

# --- TAB 3: STATS ---
with tab_stats:
    st.subheader("📊 Your Hero's Power Level")
    with sqlite3.connect(DB_PATH) as conn:
        bad_df = pd.read_sql_query("""
            SELECT word as 'Word', COUNT(*) as 'Mistakes' 
            FROM scores WHERE correctly_spelled = 0 
            GROUP BY word ORDER BY Mistakes DESC
        """, conn)
        
    if not bad_df.empty:
        st.write("Target these words to restore your mana:")
        st.dataframe(bad_df, use_container_width=True, hide_index=True)
        
        st.divider()
        if st.checkbox("Danger: Wipe Adventure History"):
            if st.button("RESET PROGRESS"):
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("DELETE FROM scores")
                st.rerun()
    else:
        st.success("Legendary! No mistakes found in your path! ⚔️")
