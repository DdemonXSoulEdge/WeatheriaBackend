import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
import re
import sqlite3
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import googlemaps

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'tu_clave_secreta_super_fuerte')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(minutes=30)
jwt = JWTManager(app)

API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
if not API_KEY:
    raise ValueError("Clave de API no encontrada en variables de entorno")
gmaps = googlemaps.Client(key=API_KEY)

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# --------- BASE DE DATOS ------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            status INTEGER NOT NULL
        )
    ''')
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
    
    # Tabla para historial de reportes de inundación
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flood_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ubicacion TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            temperatura REAL NOT NULL,
            descripcion_clima TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            lat REAL,
            lng REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# --------- REGISTRO DE USUARIO ------------

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

# --------- LOGIN ------------

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password, status FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if not row or not check_password_hash(row[0], password):
        return jsonify({
            "statusCode": 401,
            "intData": {
                "message": "Credenciales incorrectas",
                "data": None
            }
        })
    if row[1] != 1:
        return jsonify({
            "statusCode": 403,
            "intData": {
                "message": "Usuario inactivo",
                "data": None
            }
        })
    access_token = create_access_token(identity=username)
    return jsonify({
        "statusCode": 200,
        "intData": {
            "message": "Login exitoso",
            "token": access_token
        }
    })

# --------- GEOCODIFICACIÓN ------------

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'message': 'Backend Google Maps API funcionando'})

@app.route('/geocode', methods=['POST'])
def geocode_address():
    data = request.get_json()
    address = data.get('address', '')
    if not address:
        return jsonify({'error': 'Dirección requerida'}), 400
    geocode_result = gmaps.geocode(address)
    if geocode_result and geocode_result[0]['geometry']:
        location = geocode_result[0]['geometry']['location']
        return jsonify({
            'status': 'success',
            'coordinates': {
                'lat': location['lat'],
                'lng': location['lng']
            },
            'formatted_address': geocode_result[0]['formatted_address']
        })
    else:
        return jsonify({'error': 'No se pudo geocodificar la dirección'}), 404

# --------- HISTORIAL DE REPORTES ------------

@app.route('/flood_history', methods=['GET'])
def get_flood_history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM flood_reports ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    reports = []
    for row in rows:
        reports.append({
            'id': row[0],
            'ubicacion': row[1],
            'fecha': row[2],
            'hora': row[3],
            'temperatura': row[4],
            'descripcion_clima': row[5],
            'mensaje': row[6],
            'lat': row[7],
            'lng': row[8],
            'created_at': row[9]
        })
    return jsonify({'statusCode': 200, 'intData': {'message': 'Historial obtenido exitosamente', 'data': reports}})

# --------- CORREO Y REPORTES ------------

@app.route('/report_flood', methods=['POST'])
def report_flood():
    data = request.get_json()
    ubicacion = data['ubicacion']
    fecha = data['fecha']
    temperatura = data['temperatura']
    descripcion_clima = data['descripcion_clima']
    mensaje = data['mensaje']
    hora = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"[DEBUG] Payload recibido en backend: {data}")
    
    # Extraer coordenadas de la ubicación si están en formato GPS
    lat = None
    lng = None
    match = re.search(r'GPS:\s*([\d.-]+),\s*([\d.-]+)', ubicacion)
    if match:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
        except ValueError:
            lat = None
            lng = None
    
    # Guardar en base de datos (siempre, independientemente del email)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO flood_reports (ubicacion, fecha, hora, temperatura, descripcion_clima, mensaje, lat, lng) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ubicacion, fecha, hora, temperatura, descripcion_clima, mensaje, lat, lng)
    )
    conn.commit()
    report_id = cursor.lastrowid
    conn.close()
    print(f"[DEBUG] Reporte guardado en BD con ID: {report_id}")
    
    # Configuración de email
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    company_email = os.environ.get('COMPANY_EMAIL')
    if not all([sender_email, sender_password, company_email]):
        return jsonify({"statusCode": 500, "intData": {"message": "Error configuración email", "data": None}})
    
    # Formatear ubicación para email
    if match and lat is not None and lng is not None:
        location_formatted = f"Ubicación reportada: {lat}, {lng}"
    else:
        location_formatted = f"Ubicación reportada: {ubicacion}"
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = company_email
    msg['Subject'] = "Reporte de Inundación - Weatheria App"
    body = f"""
Se ha recibido un reporte de inundación desde la app Weatheria.
Detalles:
- {location_formatted}
- Fecha: {fecha}
- Hora: {hora}
- Temperatura: {temperatura}
- Descripción del Clima: {descripcion_clima}
- Mensaje: {mensaje}
Verificar inmediatamente la zona reportada.
"""
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [company_email], msg.as_string())
        server.quit()
        return jsonify({"statusCode": 200, "intData": {"message": "Reporte enviado correctamente y guardado en historial", "data": None}})
    except Exception as e:
        return jsonify({"statusCode": 500, "intData": {"message": f"Error al enviar email: {str(e)}. Reporte guardado en BD.", "data": None}})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)