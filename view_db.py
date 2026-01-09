"""
Simple script to view and interact with the SQLite database.
Usage: python view_db.py
"""
import sqlite3
import sys
from datetime import datetime

DB_PATH = "scores.db"

def view_all_scores():
    """Display all scores in the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM scores ORDER BY date DESC, id DESC")
    rows = cursor.fetchall()
    
    if not rows:
        print("No scores found in the database.")
        return
    
    print(f"\nTotal records: {len(rows)}\n")
    print(f"{'ID':<5} {'Date':<12} {'Word':<25} {'Correct':<10} {'Attempts':<10}")
    print("-" * 70)
    
    for row in rows:
        correct_str = "Yes" if row['correctly_spelled'] else "No"
        print(f"{row['id']:<5} {row['date']:<12} {row['word']:<25} {correct_str:<10} {row['attempts']:<10}")
    
    conn.close()

def view_stats():
    """Display summary statistics."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total records
    cursor.execute("SELECT COUNT(*) as count FROM scores")
    total = cursor.fetchone()['count']
    
    # Correct vs incorrect
    cursor.execute("SELECT SUM(correctly_spelled) as correct, COUNT(*) as total FROM scores")
    result = cursor.fetchone()
    correct_count = result['correct']
    total_count = result['total']
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
    
    # Date range
    cursor.execute("SELECT MIN(date) as min_date, MAX(date) as max_date FROM scores")
    date_range = cursor.fetchone()
    
    print("\n=== Database Statistics ===")
    print(f"Total records: {total}")
    print(f"Correct answers: {correct_count}")
    print(f"Incorrect answers: {total_count - correct_count}")
    print(f"Accuracy: {accuracy:.1f}%")
    if date_range['min_date']:
        print(f"Date range: {date_range['min_date']} to {date_range['max_date']}")
    
    conn.close()

def run_query(query):
    """Run a custom SQL query."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if rows:
            # Print column names
            print("\n" + " | ".join(rows[0].keys()))
            print("-" * 70)
            
            # Print rows
            for row in rows:
                print(" | ".join(str(val) for val in row))
        else:
            print("No results found.")
            
    except sqlite3.Error as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def interactive_mode():
    """Interactive mode to run queries."""
    print("\n=== Interactive SQLite Query Mode ===")
    print("Enter SQL queries (or 'exit' to quit, 'help' for examples)")
    print("Example: SELECT * FROM scores WHERE date = '2026-01-15'")
    
    while True:
        try:
            query = input("\nSQL> ").strip()
            
            if query.lower() == 'exit':
                break
            elif query.lower() == 'help':
                print("\nExample queries:")
                print("  SELECT * FROM scores LIMIT 10")
                print("  SELECT date, COUNT(*) FROM scores GROUP BY date")
                print("  SELECT word, COUNT(*) as attempts FROM scores GROUP BY word ORDER BY attempts DESC")
                print("  SELECT * FROM scores WHERE correctly_spelled = 1")
                continue
            elif not query:
                continue
            
            run_query(query)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "stats":
            view_stats()
        elif command == "query" and len(sys.argv) > 2:
            run_query(" ".join(sys.argv[2:]))
        elif command == "interactive":
            interactive_mode()
        else:
            print("Usage:")
            print("  python view_db.py              # View all scores")
            print("  python view_db.py stats        # View statistics")
            print("  python view_db.py query 'SQL'  # Run a query")
            print("  python view_db.py interactive  # Interactive mode")
    else:
        view_all_scores()
        view_stats()
        print("\nTip: Use 'python view_db.py interactive' for custom queries")

