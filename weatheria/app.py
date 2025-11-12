import requests
import json
import time
import csv
import os
import threading
from datetime import datetime
from firebase import firebase

API_KEY = "c64e8a47b0f348298e8a47b0f3f829cd"
STATION_ID = "ISANTI245"
FIREBASE_URL = "https://weatheriadx-default-rtdb.firebaseio.com/"

db = firebase.FirebaseApplication(FIREBASE_URL, None)
LAST_TS_FILE = "last_timestamp.txt"
JSON_FILE = "registros.json"
OUTPUT_DIR = "history"


def get_data():
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
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error en la solicitud: {e}")
        return None


def fb_upload(datos):
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
    except Exception as e:
        print("Error al subir datos a Firebase:", e)


def task_weather_upload():
    print("🌦 Iniciando obtención de datos meteorológicos...")
    while True:
        datos = get_data()
        if datos:
            fb_upload(datos)
        time.sleep(900)  # cada 15 minutos


def load_last_timestamp():
    if os.path.exists(LAST_TS_FILE):
        with open(LAST_TS_FILE, "r") as f:
            return f.read().strip()
    return ""


def save_last_timestamp(timestamp):
    with open(LAST_TS_FILE, "w") as f:
        f.write(timestamp)


def get_firebase_data():
    try:
        data = db.get("/registros", None)
        if data is None:
            return []
        registros = list(data.values())
        registros.sort(key=lambda x: x.get("timestamp", ""))
        return registros
    except Exception as e:
        print(f"Error al leer Firebase: {e}")
        return []


def clear_firebase():
    try:
        db.delete("/", "registros")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🧹 Firebase limpiado.")
    except Exception as e:
        print(f"Error al limpiar Firebase: {e}")


def save_to_csv(new_records):
    if not new_records:
        return

    registros_por_dia = {}
    for reg in new_records:
        if "preassure" in reg and "pressure" not in reg:
            reg["pressure"] = reg.pop("preassure")

        try:
            fecha = datetime.fromisoformat(reg["timestamp"]).strftime("%Y-%m-%d")
        except Exception:
            try:
                fecha = datetime.strptime(reg["timestamp"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
            except:
                fecha = datetime.now().strftime("%Y-%m-%d")

        registros_por_dia.setdefault(fecha, []).append(reg)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for fecha, registros_dia in registros_por_dia.items():
        filename = os.path.join(OUTPUT_DIR, f"{fecha}.csv")
        file_exists = os.path.exists(filename)

        all_fields = set()
        for r in registros_dia:
            all_fields.update(r.keys())
        fieldnames = sorted(list(all_fields))

        with open(filename, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for reg in registros_dia:
                filtered = {k: v for k, v in reg.items() if k in fieldnames}
                writer.writerow(filtered)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Guardados {len(registros_dia)} registros en {filename}")


def save_to_json(new_records):
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as jsonfile:
            json.dump(new_records, jsonfile, indent=4, ensure_ascii=False)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Datos guardados en {JSON_FILE}")

        db.put("/", "json_data", new_records)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Datos JSON subidos a Firebase (/json_data)")

    except Exception as e:
        print(f"Error al guardar/subir JSON: {e}")


def task_data_sync():
    print("🔁 Iniciando sincronización con Firebase...")
    last_timestamp = load_last_timestamp()

    while True:
        registros = get_firebase_data()
        if registros:
            nuevos = [r for r in registros if r.get("timestamp", "") > last_timestamp]
            if nuevos:
                print(f"Nuevos registros detectados: {len(nuevos)}")
                save_to_csv(nuevos)
                save_to_json(nuevos)
                last_timestamp = nuevos[-1].get("timestamp", last_timestamp)
                save_last_timestamp(last_timestamp)
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No hay registros nuevos.")

            if len(registros) >= 60:
                clear_firebase()
                last_timestamp = ""
                save_last_timestamp(last_timestamp)
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No hay registros en Firebase.")
        time.sleep(900) 


if __name__ == "__main__":
    print("Sistema Weatheria iniciado.")
    thread1 = threading.Thread(target=task_weather_upload, daemon=True)
    thread2 = threading.Thread(target=task_data_sync, daemon=True)

    thread1.start()
    thread2.start()

    while True:
        time.sleep(1)
