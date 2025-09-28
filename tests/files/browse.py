# browse.py
import sqlite3
from flask import Flask, render_template_string, g, request

app = Flask(__name__)
DATABASE = "results.sqlite"  # default, or pass via CLI

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>abvio results</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 0.5em; }
        th { background: #eee; }
    </style>
</head>
<body>
    <h1>Jobs Table</h1>
    <form method="get">
        Search: <input type="text" name="q" value="{{ query }}">
        <input type="submit" value="Go">
    </form>
    <table>
        <tr>
            <th>ID</th>
            <th>Directory</th>
            <th>Formula</th>
            <th>Energy</th>
            <th>nsteps</th>
        </tr>
        {% for row in rows %}
        <tr>
            <td>{{ row['id'] }}</td>
            <td>{{ row['directory'] }}</td>
            <td>{{ row['formula'] }}</td>
            <td>{{ row['energy'] }}</td>
            <td>{{ row['nsteps'] }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

@app.route("/")
def index():
    q = request.args.get("q", "")
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT * FROM jobs WHERE directory LIKE ? OR formula LIKE ? ORDER BY id DESC",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    return render_template_string(HTML, rows=rows, query=q)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("db", help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    DATABASE = args.db
    app.run(host=args.host, port=args.port, debug=True)

