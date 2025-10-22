import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
import re
import sqlite3
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Path to the SQLite database
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def init_db():
    """Initialize the database with the users table and initial data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            status INTEGER NOT NULL
        )
    ''')
    
    # Insert initial data if not already present
    initial_users = [
        ("username1", generate_password_hash("Hola.123"), 1),
        ("username2", generate_password_hash("Hola.123"), 1),
        ("username3", generate_password_hash("Hola.123"), 1),
        ("username4", generate_password_hash("Hola.123"), 1)
    ]
    
    for username, hashed_password, status in initial_users:
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, password, status) VALUES (?, ?, ?)",
            (username, hashed_password, status)
        )
    
    conn.commit()
    conn.close()

def validate_username(username: str) -> bool:
    return bool(username and 3 <= len(username) <= 50 and re.match(r'^[a-zA-Z0-9_]+$', username))

def validate_password(password: str) -> bool:
    return bool(password and len(password) >= 8)

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.get_json()
    
    required_fields = ['username', 'password', 'status']
    if not all(field in data for field in required_fields):
        return jsonify({
            "statusCode": 400,
            "intData": {
                "message": "Todos los campos son requeridos",
                "data": None
            }
        })
    
    username = data['username']
    password = data['password']
    status = data['status']
    
    if not validate_username(username):
        return jsonify({
            "statusCode": 400,
            "intData": {
                "message": "Nombre de usuario inválido (3-50 caracteres, solo letras, números y guiones bajos)",
                "data": None
            }
        })
    if not validate_password(password):
        return jsonify({
            "statusCode": 400,
            "intData": {
                "message": "La contraseña debe tener al menos 8 caracteres",
                "data": None
            }
        })
    
    hashed_password = generate_password_hash(password)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password, status) VALUES (?, ?, ?)",
            (username, hashed_password, status)
        )
        conn.commit()
        return jsonify({
            "statusCode": 201,
            "intData": {
                "message": "Usuario registrado exitosamente",
                "data": None
            }
        })
    except sqlite3.IntegrityError:
        return jsonify({
            "statusCode": 400,
            "intData": {
                "message": "Nombre de usuario ya registrado",
                "data": None
            }
        })
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            "statusCode": 400,
            "intData": {
                "message": "Usuario y contraseña son requeridos",
                "data": None
            }
        })
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({
            "statusCode": 401,
            "intData": {
                "message": "Credenciales incorrectas",
                "data": None
            }
        })
    
    if not check_password_hash(row[0], password):
        return jsonify({
            "statusCode": 401,
            "intData": {
                "message": "Credenciales incorrectas",
                "data": None
            }
        })
    
    return jsonify({
        "statusCode": 200,
        "intData": {
            "message": "Login exitoso"
        }
    })

if __name__ == '__main__':
    init_db()
    app.run(port=5001, debug=True)