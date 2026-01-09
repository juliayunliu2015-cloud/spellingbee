# from flask import Flask, render_template, request, redirect, url_for, session
import os
import random
import sqlite3
from datetime import datetime, date, timedelta

import pandas as pd
from gtts import gTTS

# app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Path to the Excel file in the project root
BASE_DIR = os.path.dirname(__file__)
DATA_FILE = os.path.join(BASE_DIR, "Spelling bee 2026.xlsx")

# Folder to store generated audio files inside the static directory
STATIC_AUDIO_FOLDER = os.path.join(BASE_DIR, "static", "audio")
os.makedirs(STATIC_AUDIO_FOLDER, exist_ok=True)

# SQLite database for scores
DB_PATH = os.path.join(BASE_DIR, "scores.db")

# Daily exam goal
DAILY_EXAM_GOAL = 33


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the scores table if it doesn't exist."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                word TEXT NOT NULL,
                correctly_spelled INTEGER NOT NULL,
                attempts INTEGER NOT NULL,
                mode TEXT DEFAULT 'exam'
            )
            """
        )
        # Add mode column if it doesn't exist (for existing databases)
        try:
            conn.execute("ALTER TABLE scores ADD COLUMN mode TEXT DEFAULT 'exam'")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create table for daily exam progress
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_exam_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                correct_count INTEGER DEFAULT 0,
                total_attempted INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def load_words_dataframe():
    """
    Load the Excel file into a DataFrame.
    Assumes that there is a column containing the words named 'word' (case-insensitive).
    Also looks for a definition column - checks all columns more thoroughly.
    """
    df = pd.read_excel(DATA_FILE)

    # Try to find a column that likely contains the word
    possible_cols = [c for c in df.columns if str(c).strip().lower() in ("word", "words", "spelling", "term")]
    if not possible_cols:
        # Fallback: just take the first column
        word_col = df.columns[0]
    else:
        word_col = possible_cols[0]

    # Try to find a definition column - check all columns more thoroughly
    # Look for any column that might contain definitions (not the word column)
    def_col = None
    for col in df.columns:
        col_lower = str(col).strip().lower()
        # Skip the word column
        if col == word_col:
            continue
        # Check if it might be a definition column
        if any(keyword in col_lower for keyword in ["definition", "def", "meaning", "meanings", "description", "desc", "explanation", "explain"]):
            def_col = col
            break
    
    # If still no definition column found, try the second column (common pattern)
    if def_col is None and len(df.columns) > 1:
        # Check if second column has text that looks like definitions
        second_col = df.columns[1]
        if second_col != word_col:
            # Sample a few rows to see if it looks like definitions
            sample_values = df[second_col].dropna().head(5)
            if len(sample_values) > 0:
                # If values are strings and longer than typical words, might be definitions
                avg_length = sample_values.astype(str).str.len().mean()
                if avg_length > 20:  # Definitions are usually longer
                    def_col = second_col

    # Create result dataframe
    if def_col:
        df_words = df[[word_col, def_col]].dropna(subset=[word_col])
        df_words.columns = ["word", "definition"]
        # Clean up definitions - remove NaN and convert to string
        df_words["definition"] = df_words["definition"].fillna("").astype(str)
    else:
        df_words = df[[word_col]].dropna()
        df_words.columns = ["word"]
        df_words["definition"] = ""  # Empty definitions if not available

    return df_words


def mask_vowels(word: str) -> str:
    """
    Replace all vowels (A, E, I, O, U) with underscores, preserving capitalization.
    """
    vowels = "AEIOUaeiou"
    result = ""
    for char in word:
        if char in vowels:
            result += "_"
        else:
            result += char
    return result


def get_alphabet_group(word: str) -> int:
    """
    Group words alphabetically (case-insensitive) into 13 groups.
    Group 1: A-B, Group 2: C-D, Group 3: E-F, Group 4: G-H, Group 5: I-J,
    Group 6: K-L, Group 7: M-N, Group 8: O-P, Group 9: Q-R, Group 10: S-T,
    Group 11: U-V, Group 12: W-X, Group 13: Y-Z
    """
    if not word:
        return 1
    
    first_char = word[0].upper()
    
    # Map letters to groups (2 letters per group)
    if first_char in 'AB':
        return 1
    elif first_char in 'CD':
        return 2
    elif first_char in 'EF':
        return 3
    elif first_char in 'GH':
        return 4
    elif first_char in 'IJ':
        return 5
    elif first_char in 'KL':
        return 6
    elif first_char in 'MN':
        return 7
    elif first_char in 'OP':
        return 8
    elif first_char in 'QR':
        return 9
    elif first_char in 'ST':
        return 10
    elif first_char in 'UV':
        return 11
    elif first_char in 'WX':
        return 12
    else:  # Y-Z
        return 13


def group_words_by_alphabet(df):
    """
    Group words evenly into 13 groups (approximately 33 words per group).
    Words are sorted alphabetically first, then divided evenly.
    Returns a dictionary with group numbers as keys.
    """
    # Sort words alphabetically (case-insensitive)
    df_sorted = df.copy()
    df_sorted['sort_key'] = df_sorted['word'].str.lower()
    df_sorted = df_sorted.sort_values('sort_key').reset_index(drop=True)
    df_sorted = df_sorted.drop('sort_key', axis=1)
    
    total_words = len(df_sorted)
    words_per_group = total_words // 13
    remainder = total_words % 13
    
    groups = {}
    start_idx = 0
    
    for group_num in range(1, 14):
        # Distribute remainder words to first groups
        group_size = words_per_group + (1 if group_num <= remainder else 0)
        end_idx = start_idx + group_size
        
        group_words = df_sorted.iloc[start_idx:end_idx].to_dict('records')
        groups[group_num] = group_words
        
        start_idx = end_idx
    
    return groups


# Load words once at startup and initialize DB
WORDS_DF = load_words_dataframe()
init_db()


def get_audio_filename(word: str) -> str:
    """
    Generate a consistent filename for a word based on its content.
    This allows caching - same word = same filename.
    """
    import hashlib
    # Create a hash of the word (case-sensitive to preserve capitalization)
    word_hash = hashlib.md5(word.encode('utf-8')).hexdigest()[:12]
    # Sanitize word for filename (keep only alphanumeric and common chars)
    safe_word = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in word[:20])
    return f"{safe_word}_{word_hash}.mp3"


def generate_audio_for_word(word: str, force_regenerate: bool = False) -> str:
    """
    Generate an MP3 file for the given word and return the relative URL path.
    Uses caching - if the file already exists, returns it without regenerating.
    """
    filename = get_audio_filename(word)
    filepath = os.path.join(STATIC_AUDIO_FOLDER, filename)
    
    # If file exists and we're not forcing regeneration, return it
    if os.path.exists(filepath) and not force_regenerate:
        return f"/static/audio/{filename}"
    
    # Generate new audio file
    try:
        tts = gTTS(text=str(word), lang="en")
        tts.save(filepath)
    except Exception as e:
        # If generation fails, return empty string or handle error
        print(f"Error generating audio for '{word}': {e}")
        return ""
    
    return f"/static/audio/{filename}"


@app.route("/play")
def play_redirect():
    """Redirect old /play route to exam mode."""
    return redirect(url_for("exam"))


@app.route("/")
def index():
    # Main page with 3 tabs
    word_groups = group_words_by_alphabet(WORDS_DF)
    
    # Get today's exam progress
    conn = get_db_connection()
    today = date.today().isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT correct_count, total_attempted FROM daily_exam_progress WHERE date = ?",
            (today,)
        )
        progress = cursor.fetchone()
        if progress:
            correct_count, total_attempted = progress
        else:
            correct_count, total_attempted = 0, 0
    finally:
        conn.close()
    
    # Get incorrect words for the tab
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT word, COUNT(*) as total_incorrect
            FROM scores
            WHERE correctly_spelled = 0
            GROUP BY word
            ORDER BY total_incorrect DESC, word
        """)
        unique_rows = cursor.fetchall()
        unique_words = [{'word': row[0], 'total_incorrect': row[1]} for row in unique_rows]
    finally:
        conn.close()
    
    return render_template("index.html",
                         word_groups=word_groups,
                         correct_count=correct_count,
                         total_attempted=total_attempted,
                         daily_goal=DAILY_EXAM_GOAL,
                         unique_words=unique_words)


@app.route("/exam", methods=["GET", "POST"])
def exam():
    """
    Exam mode: Random words with audio, track daily goal of 33 correct words.
    Shows word and definition after checking.
    """
    if WORDS_DF.empty:
        return redirect(url_for("index"))

    feedback = None
    is_correct = None
    current_word_obj = None
    word_meaning = None
    current_word_definition = None

    # Handle form submission first
    if request.method == "POST":
        submitted = request.form.get("spelling", "").strip()
        current_word = session.get("current_word")
        current_definition = session.get("current_definition", "")

        if not current_word:
            feedback = "Session expired or no active word. Please try again."
        else:
            # Increment attempts for this session/word
            attempts = session.get("attempts", 0) + 1
            session["attempts"] = attempts

            is_correct = int(submitted.lower() == str(current_word).strip().lower())
            word_meaning = current_definition
            
            if is_correct:
                feedback = f"Correct! The word was '{current_word}'."
            else:
                feedback = f"Incorrect. The correct spelling is '{current_word}'."

            # Log result to the database
            conn = get_db_connection()
            today = date.today().isoformat()
            try:
                conn.execute(
                    "INSERT INTO scores (date, word, correctly_spelled, attempts, mode) VALUES (?, ?, ?, ?, ?)",
                    (today, str(current_word), is_correct, attempts, "exam"),
                )
                
                # Update daily exam progress
                if is_correct:
                    conn.execute("""
                        INSERT INTO daily_exam_progress (date, correct_count, total_attempted)
                        VALUES (?, 1, 1)
                        ON CONFLICT(date) DO UPDATE SET
                            correct_count = correct_count + 1,
                            total_attempted = total_attempted + 1
                    """, (today,))
                else:
                    conn.execute("""
                        INSERT INTO daily_exam_progress (date, correct_count, total_attempted)
                        VALUES (?, 0, 1)
                        ON CONFLICT(date) DO UPDATE SET
                            total_attempted = total_attempted + 1
                    """, (today,))
                
                conn.commit()
            finally:
                conn.close()
            
            current_word_obj = current_word

    # Always select a (new) word for the next round and generate its audio
    word_row = WORDS_DF.sample(1).iloc[0]
    word = word_row["word"]
    definition = str(word_row.get("definition", "")).strip()
    if not definition or definition == "nan":
        definition = ""
    
    session["current_word"] = word
    session["current_definition"] = definition
    session["attempts"] = 0

    audio_url = generate_audio_for_word(word)
    
    # Get today's progress
    conn = get_db_connection()
    today = date.today().isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT correct_count, total_attempted FROM daily_exam_progress WHERE date = ?",
            (today,)
        )
        progress = cursor.fetchone()
        if progress:
            correct_count, total_attempted = progress
        else:
            correct_count, total_attempted = 0, 0
    finally:
        conn.close()

    # Show definition only after checking (word_meaning contains the definition of the word that was just checked)
    return render_template(
        "exam.html",
        audio_url=audio_url,
        feedback=feedback,
        is_correct=is_correct,
        current_word=current_word_obj,
        word_meaning=word_meaning,  # Definition of word that was just checked (shown after submission)
        correct_count=correct_count,
        total_attempted=total_attempted,
        daily_goal=DAILY_EXAM_GOAL,
    )


@app.route("/learn/<int:group_num>")
def learn_group(group_num):
    """Learn mode: Show words in a specific group with vowel masking."""
    # Redirect to main page - groups are now loaded via API
    return redirect(url_for("index"))


@app.route("/api/learn/group/<int:group_num>")
def api_learn_group(group_num):
    """API endpoint to get words for a specific group."""
    if group_num < 1 or group_num > 13:
        return {"success": False, "error": "Invalid group number"}, 400
    
    word_groups = group_words_by_alphabet(WORDS_DF)
    words = word_groups.get(group_num, [])
    
    # Add masked versions only - don't generate audio upfront (too slow!)
    for word_obj in words:
        word_obj['masked'] = mask_vowels(word_obj['word'])
        # Ensure definition is a string
        if 'definition' not in word_obj or not word_obj['definition']:
            word_obj['definition'] = ''
        else:
            word_obj['definition'] = str(word_obj['definition']).strip()
    
    return {
        "success": True,
        "words": words,
        "group_num": group_num
    }


@app.route("/api/audio/<path:word>")
def get_audio(word):
    """
    API endpoint to generate audio for a word on-demand.
    Returns the audio URL. Uses caching.
    """
    # Decode URL-encoded word
    from urllib.parse import unquote
    word = unquote(word)
    
    audio_url = generate_audio_for_word(word)
    if audio_url:
        return {"audio_url": audio_url, "success": True}
    else:
        return {"audio_url": "", "success": False}, 500


@app.route("/api/exam/progress")
def api_exam_progress():
    """API endpoint to get current exam progress."""
    conn = get_db_connection()
    today = date.today().isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT correct_count, total_attempted FROM daily_exam_progress WHERE date = ?",
            (today,)
        )
        progress = cursor.fetchone()
        if progress:
            correct_count, total_attempted = progress
        else:
            correct_count, total_attempted = 0, 0
    finally:
        conn.close()
    
    return {
        "success": True,
        "correct_count": correct_count,
        "total_attempted": total_attempted,
        "daily_goal": DAILY_EXAM_GOAL
    }


@app.route("/api/exam/word")
def api_exam_word():
    """API endpoint to get a new word for exam."""
    if WORDS_DF.empty:
        return {"success": False, "error": "No words available"}, 400
    
    # Select a random word
    word_row = WORDS_DF.sample(1).iloc[0]
    word = word_row["word"]
    definition = str(word_row.get("definition", "")).strip()
    if not definition or definition == "nan":
        definition = ""
    
    session["current_word"] = word
    session["current_definition"] = definition
    session["attempts"] = 0
    
    audio_url = generate_audio_for_word(word)
    
    return {
        "success": True,
        "audio_url": audio_url
    }


@app.route("/api/exam/check", methods=["POST"])
def api_exam_check():
    """API endpoint to check spelling in exam mode."""
    if WORDS_DF.empty:
        return {"success": False, "error": "No words available"}, 400
    
    submitted = request.form.get("spelling", "").strip()
    current_word = session.get("current_word")
    current_definition = session.get("current_definition", "")
    
    if not current_word:
        return {"success": False, "error": "Session expired. Please refresh."}, 400
    
    # Increment attempts
    attempts = session.get("attempts", 0) + 1
    session["attempts"] = attempts
    
    is_correct = int(submitted.lower() == str(current_word).strip().lower())
    word_meaning = current_definition
    
    if is_correct:
        feedback = f"Correct! The word was '{current_word}'."
    else:
        feedback = f"Incorrect. The correct spelling is '{current_word}'."
    
    # Log result to database
    conn = get_db_connection()
    today = date.today().isoformat()
    try:
        conn.execute(
            "INSERT INTO scores (date, word, correctly_spelled, attempts, mode) VALUES (?, ?, ?, ?, ?)",
            (today, str(current_word), is_correct, attempts, "exam"),
        )
        
        # Update daily exam progress
        if is_correct:
            conn.execute("""
                INSERT INTO daily_exam_progress (date, correct_count, total_attempted)
                VALUES (?, 1, 1)
                ON CONFLICT(date) DO UPDATE SET
                    correct_count = correct_count + 1,
                    total_attempted = total_attempted + 1
            """, (today,))
        else:
            conn.execute("""
                INSERT INTO daily_exam_progress (date, correct_count, total_attempted)
                VALUES (?, 0, 1)
                ON CONFLICT(date) DO UPDATE SET
                    total_attempted = total_attempted + 1
            """, (today,))
        
        conn.commit()
        
        # Get updated progress
        cursor = conn.cursor()
        cursor.execute(
            "SELECT correct_count, total_attempted FROM daily_exam_progress WHERE date = ?",
            (today,)
        )
        progress = cursor.fetchone()
        if progress:
            correct_count, total_attempted = progress
        else:
            correct_count, total_attempted = 0, 0
    finally:
        conn.close()
    
    return {
        "success": True,
        "is_correct": bool(is_correct),
        "feedback": feedback,
        "current_word": current_word,
        "word_meaning": word_meaning,
        "correct_count": correct_count,
        "total_attempted": total_attempted,
        "daily_goal": DAILY_EXAM_GOAL
    }


@app.route("/check_word", methods=["POST"])
def check_word():
    """Check a word in learn mode."""
    data = request.json
    word = data.get("word", "")
    submitted = data.get("spelling", "").strip()
    
    is_correct = int(submitted.lower() == str(word).strip().lower())
    
    # Get definition from dataframe
    word_row = WORDS_DF[WORDS_DF["word"].str.lower() == word.lower()]
    if not word_row.empty:
        definition = str(word_row["definition"].iloc[0]).strip()
        if not definition or definition == "nan":
            definition = ""
    else:
        definition = ""
    
    return {
        "correct": bool(is_correct),
        "definition": definition
    }


@app.route("/stats")
def stats():
    """
    Display daily average correctness over the last 30 days.
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT date, correctly_spelled FROM scores", conn)
    finally:
        conn.close()

    if df.empty:
        daily_stats = []
    else:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        cutoff = date.today() - timedelta(days=30)
        df = df[df["date"] >= cutoff]
        if df.empty:
            daily_stats = []
        else:
            grouped = df.groupby("date")["correctly_spelled"].mean().reset_index()
            grouped["correctness_percent"] = (grouped["correctly_spelled"] * 100).round(1)
            daily_stats = grouped.to_dict(orient="records")

    return render_template("stats.html", daily_stats=daily_stats)


@app.route("/incorrect")
def incorrect_words():
    """
    Display all words that were spelled incorrectly.
    """
    conn = get_db_connection()
    try:
        # Get all incorrect words with their details
        cursor = conn.cursor()
        cursor.execute("""
            SELECT word, date, attempts, COUNT(*) as times_incorrect
            FROM scores
            WHERE correctly_spelled = 0
            GROUP BY word, date, attempts
            ORDER BY date DESC, word
        """)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        incorrect_words_list = []
        for row in rows:
            incorrect_words_list.append({
                'word': row[0],
                'date': row[1],
                'attempts': row[2],
                'times_incorrect': row[3]
            })
        
        # Also get unique words with total incorrect count
        cursor.execute("""
            SELECT word, COUNT(*) as total_incorrect
            FROM scores
            WHERE correctly_spelled = 0
            GROUP BY word
            ORDER BY total_incorrect DESC, word
        """)
        unique_rows = cursor.fetchall()
        
        unique_words = []
        for row in unique_rows:
            unique_words.append({
                'word': row[0],
                'total_incorrect': row[1]
            })
            
    finally:
        conn.close()

    return render_template("incorrect_words.html", 
                         incorrect_words=incorrect_words_list,
                         unique_words=unique_words)


if __name__ == "__main__":
    # For local development
    app.run(debug=True)

