import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
import re
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

users = {}

def validate_username(username: str) -> bool:
    return bool(username and 3 <= len(username) <= 50 and re.match(r'^[a-zA-Z0-9_]+$', username))

def validate_password(password: str) -> bool:
    return bool(password and len(password) >= 8)

def init_db():
    users_data = [
        {"username": "username1", "password": generate_password_hash("Hola.123"), "status": 1},
        {"username": "username2", "password": generate_password_hash("Hola.123"), "status": 1},
        {"username": "username3", "password": generate_password_hash("Hola.123"), "status": 1},
        {"username": "username4", "password": generate_password_hash("Hola.123"), "status": 1}
    ]
    for user_data in users_data:
        if user_data["username"] not in users:
            users[user_data["username"]] = user_data

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
    
    if username in users:
        return jsonify({
            "statusCode": 400,
            "intData": {
                "message": "Nombre de usuario ya registrado",
                "data": None
            }
        })
    
    hashed_password = generate_password_hash(password)
    
    users[username] = {
        "username": username,
        "password": hashed_password,
        "status": status
    }
    
    return jsonify({
        "statusCode": 201,
        "intData": {
            "message": "Usuario registrado exitosamente",
            "data": None
        }
    })

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
    
    user = users.get(username)
    
    if not user or not check_password_hash(user["password"], password):
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