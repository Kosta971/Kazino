
from flask import Flask, request, jsonify
import sqlite3
import secrets

app = Flask(__name__)
DB = 'casino.db'

# Инициализация базы
def init_db():
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                balance REAL DEFAULT 1000,
                token TEXT
            )
        ''')
        con.commit()

init_db()

# 🔐 Middleware — получить пользователя по токену
def get_user(token):
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("SELECT id, username, balance FROM users WHERE token = ?", (token,))
        row = cur.fetchone()
        if row:
            return {"id": row[0], "username": row[1], "balance": row[2]}
    return None

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    token = secrets.token_hex(16)
    try:
        with sqlite3.connect(DB) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO users (username, password, token) VALUES (?, ?, ?)", (username, password, token))
            con.commit()
            return jsonify({"token": token})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("SELECT token FROM users WHERE username=? AND password=?", (username, password))
        row = cur.fetchone()
        if row:
            return jsonify({"token": row[0]})
        else:
            return jsonify({"error": "Invalid credentials"}), 401

@app.route('/balance', methods=['GET'])
def balance():
    token = request.args.get("token")
    user = get_user(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 403
    return jsonify({"balance": user["balance"]})

@app.route('/deposit', methods=['POST'])
def deposit():
    data = request.json
    token = data.get("token")
    amount = float(data.get("amount", 0))
    if amount <= 0: return jsonify({"error": "Invalid amount"}), 400
    user = get_user(token)
    if not user: return jsonify({"error": "Invalid token"}), 403
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user["id"]))
        con.commit()
    return jsonify({"message": "Deposited", "new_balance": user["balance"] + amount})

@app.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    token = data.get("token")
    amount = float(data.get("amount", 0))
    if amount <= 0: return jsonify({"error": "Invalid amount"}), 400
    user = get_user(token)
    if not user: return jsonify({"error": "Invalid token"}), 403
    if user["balance"] < amount:
        return jsonify({"error": "Insufficient funds"}), 400
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user["id"]))
        con.commit()
    return jsonify({"message": "Withdrawn", "new_balance": user["balance"] - amount})

@app.route('/play/<game>', methods=['POST'])
def play(game):
    import random
    data = request.json
    token = data.get("token")
    user = get_user(token)
    if not user: return jsonify({"error": "Invalid token"}), 403

    # Стоимость игры и выплаты
    rules = {
        "slot": {"cost": 50, "win": 300},
        "dice": {"cost": 20, "win": 100},
        "coin": {"cost": 30, "win": 60},
        "roulette": {"cost": 40, "win": 80, "win_green": 500}
    }

    if game not in rules:
        return jsonify({"error": "Unknown game"}), 400

    r = rules[game]
    if user["balance"] < r["cost"]:
        return jsonify({"error": "Not enough balance"}), 400

    win = False
    result = ""

    if game == "slot":
        symbols = ["🍒", "🍋", "🔔", "💎"]
        roll = [random.choice(symbols) for _ in range(3)]
        result = " ".join(roll)
        win = roll[0] == roll[1] == roll[2]
    elif game == "dice":
        roll = random.randint(1, 6)
        result = f"Rolled {roll}"
        win = roll >= 5
    elif game == "coin":
        flip = random.choice(["Heads", "Tails"])
        result = f"Flip: {flip}"
        win = flip == data.get("choice", "Heads")
    elif game == "roulette":
        color = random.choices(["Red", "Black", "Green"], weights=[47, 47, 6])[0]
        result = f"Landed on {color}"
        bet = data.get("bet", "Red")
        if color == bet:
            win = True
            if color == "Green":
                r["win"] = r["win_green"]

    new_balance = user["balance"] - r["cost"]
    if win:
        new_balance += r["win"]

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
        con.commit()

    return jsonify({
        "result": result,
        "win": win,
        "new_balance": new_balance
    })

if __name__ == '__main__':
    app.run(debug=True)
