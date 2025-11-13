import requests
import json
import time
import csv
import os
from datetime import datetime
from firebase import firebase

API_KEY = "c64e8a47b0f348298e8a47b0f3f829cd"
STATION_ID = "ISANTI245"
FIREBASE_URL = "https://weatheriadx-default-rtdb.firebaseio.com/"

db = firebase.FirebaseApplication(FIREBASE_URL, None)

# 🔧 BASE_DIR siempre apunta al directorio real donde está este archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LAST_TS_FILE = os.path.join(BASE_DIR, "last_timestamp.txt")
JSON_FILE = os.path.join(BASE_DIR, "registros.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "history")


def get_data():
    """Obtiene datos meteorológicos actuales desde Weather.com"""
    url = (
        f"https://api.weather.com/v2/pws/observations/current?"
        f"stationId={STATION_ID}&format=json&units=m&apiKey={API_KEY}"
    )

    try:
        response = requests.get(url)
        response.raise_for_status()
        datos = response.json()
        datos["local_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return datos
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] Error al obtener datos: {e}")
        return None


def process_and_upload(datos):
    """Procesa los datos y los sube a Firebase"""
    try:
        obs = datos["observations"][0]
        metric = obs["metric"]

        registro = {
            "temp": metric.get("temp"),
            "heatIndex": metric.get("heatIndex"),
            "dewpt": metric.get("dewpt"),
            "windChill": metric.get("windChill"),
            "windSpeed": metric.get("windSpeed"),
            "windGust": metric.get("windGust"),
            "humidity": obs.get("humidity"),
            "pressure": metric.get("pressure"),
            "precipRate": metric.get("precipRate"),
            "precipTotal": metric.get("precipTotal"),
            "timestamp": datos["local_timestamp"]
        }

        db.post("/registros", registro)
        print(f"[{registro['timestamp']}] Datos subidos a Firebase:", registro)
        return registro
    except Exception as e:
        print(f"[Error al subir datos a Firebase: {e}]")
        return None


def save_to_csv(registros):
    """Guarda los datos en CSV separados por día"""
    if not registros:
        return

    registros_por_dia = {}
    for reg in registros:
        try:
            fecha = datetime.fromisoformat(reg["timestamp"]).strftime("%Y-%m-%d")
        except Exception:
            fecha = datetime.now().strftime("%Y-%m-%d")

        registros_por_dia.setdefault(fecha, []).append(reg)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for fecha, registros_dia in registros_por_dia.items():
        filename = os.path.join(OUTPUT_DIR, f"{fecha}.csv")
        file_exists = os.path.exists(filename)

        fieldnames = sorted(list({k for r in registros_dia for k in r.keys()}))

        with open(filename, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(registros_dia)

        print(f"[{datetime.now()}] Guardados {len(registros_dia)} registros en {filename}")


def save_to_json(registros):
    """Guarda todos los datos en un JSON y lo sube a Firebase"""
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as jsonfile:
            json.dump(registros, jsonfile, indent=4, ensure_ascii=False)
        print(f"[{datetime.now()}] Guardados {len(registros)} registros en {JSON_FILE}")

        db.put("/", "json_data", registros)
        print(f"[{datetime.now()}] Datos JSON subidos a Firebase (/json_data)")
    except Exception as e:
        print(f"Error al guardar/subir JSON: {e}")


def load_existing_data():
    """Carga el JSON existente para no perder registros previos"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []


def main_loop():
    print("🌦️ Sistema Weatheria iniciado (sincronización cada 15 minutos).")
    all_records = load_existing_data()

    while True:
        datos = get_data()
        if datos:
            registro = process_and_upload(datos)
            if registro:
                all_records.append(registro)
                save_to_csv([registro])
                save_to_json(all_records)
        else:
            print(f"[{datetime.now()}] No se obtuvieron datos válidos, reintentando...")

        print("⏳ Esperando 15 minutos para la siguiente actualización...\n")
        time.sleep(900)  # 900 segundos = 15 minutos


if __name__ == "__main__":
    main_loop()
