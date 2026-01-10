import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
from gtts import gTTS

# --- STEP 1: THE DATA CLEANER ---
def get_clean_data():
    excel_file = "Spelling bee 2026.xlsx"
    
    if not os.path.exists(excel_file):
        st.error(f"❌ Could not find '{excel_file}'. Please make sure it is in the same folder as app.py")
        return pd.DataFrame(columns=["word", "definition", "sentence"])

    try:
        # Read Excel
        df = pd.read_excel(excel_file)
        
        # Extract first 3 columns and clean them
        clean_df = pd.DataFrame({
            "word": df.iloc[:, 0].astype(str).str.strip(),
            "definition": df.iloc[:, 1].astype(str).str.strip(),
            "sentence": df.iloc[:, 2].astype(str).str.strip()
        })
        
        # Remove 'nan' strings or empty rows
        clean_df = clean_df[clean_df["word"].str.lower() != "nan"]
        return clean_df
    except Exception as e:
        st.error(f"Error cleaning Excel: {e}")
        return pd.DataFrame(columns=["word", "definition", "sentence"])

# --- STEP 2: APP SETUP ---
st.set_page_config(page_title="Vivian's Spelling Bee", page_icon="🐝", layout="wide")

# Database Setup (Uses a fresh name to avoid old IntegrityErrors)
DB_NAME = "study_history.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT,
                status TEXT,
                date_attempted TEXT
            )
        """)

init_db()
words_df = get_clean_data()

# --- STEP 3: UI TABS ---
st.title("✨ Vivian's Spelling Adventure")
tab1, tab2, tab3 = st.tabs(["🎯 Exam", "📖 Study Room", "📊 Progress"])

with tab1:
    st.subheader("Daily Spelling Test")
    if not words_df.empty:
        st.write(f"✅ Loaded {len(words_df)} words from your Excel file.")
        # Your exam logic goes here...
    else:
        st.warning("No words found. Please check your Excel file.")

with tab2:
    st.subheader("Study Your Words")
    # Your 3-per-row grid logic goes here...
    if not words_df.empty:
        for i in range(0, len(words_df), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(words_df):
                    row = words_df.iloc[i + j]
                    with cols[j]:
                        st.info(f"**{row['word']}**")
                        st.caption(f"Meaning: {row['definition']}")

with tab3:
    st.subheader("Your Progress")
    # Your mistake tracking logic goes here...
