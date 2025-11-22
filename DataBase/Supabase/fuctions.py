import os
import csv
import json
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path


# ==========================
#   LOAD ENV
# ==========================

# The .env file is in the project root, 3 levels up from this script.
# (fuctions.py -> Supabase -> DataBase -> project root)
from dotenv import load_dotenv
from pathlib import Path

# Buscar .env automáticamente recorriendo hacia arriba
def find_env_file():
    current = Path(__file__).resolve().parent
    root = Path(current.anchor)

    # Recorre cada nivel hacia arriba
    while current != root:
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent
    return None

ENV_PATH = find_env_file()
print("Usando .env en:", ENV_PATH)

if ENV_PATH:
    load_dotenv(ENV_PATH)
else:
    raise FileNotFoundError("No se encontró el archivo .env en ningún nivel superior.")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Endpoint para Admin-API (gestión de tablas)
HEADERS_ADMIN = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json"
}
POSTGREST_URL = f"{SUPABASE_URL}/rest/v1"

# ==========================
#   TABLE MANAGEMENT
# ==========================

def create_table(name: str, columns: dict):
    """
    Crea una tabla usando SQL via Admin API.
    columns = {"id": "uuid primary key", "name": "text", "age": "int"}
    """
    cols = ", ".join([f"{col} {typ}" for col, typ in columns.items()])
    sql = f"CREATE TABLE IF NOT EXISTS {name} ({cols});"

    url = f"{SUPABASE_URL}/rest/v1/rpc"
    payload = {"query": sql}

    r = requests.post(f"{SUPABASE_URL}/pg/sql", headers=HEADERS_ADMIN, json={"query": sql})
    return r.json() if r.content else {"status": r.status_code}


def delete_table(name: str):
    sql = f"DROP TABLE IF EXISTS {name} CASCADE;"
    r = requests.post(f"{SUPABASE_URL}/pg/sql", headers=HEADERS_ADMIN, json={"query": sql})
    return r.json() if r.content else {"status": r.status_code}


def alter_table(name: str, alter_sql: str):
    """
    alter_sql ejemplo: "ADD COLUMN edad int"
    """
    sql = f"ALTER TABLE {name} {alter_sql};"
    r = requests.post(f"{SUPABASE_URL}/pg/sql", headers=HEADERS_ADMIN, json={"query": sql})
    return r.json() if r.content else {"status": r.status_code}


# ==========================
#   CRUD OPERATIONS
# ==========================

def insert_row(table: str, data: dict):
    """ Inserta una sola fila """
    return supabase.table(table).insert(data).execute()

def insert_rows(table: str, rows: list):
    """ Inserta múltiples filas """
    return supabase.table(table).insert(rows).execute()

def update_row(table: str, match_column: str, value, new_data: dict):
    """ Actualiza una fila """
    return supabase.table(table).update(new_data).eq(match_column, value).execute()

def update_rows(table: str, match_dict: dict, new_data: dict):
    """ Actualiza múltiples filas """
    q = supabase.table(table).update(new_data)
    for col, val in match_dict.items():
        q = q.eq(col, val)
    return q.execute()

def delete_row(table: str, match_column: str, value):
    """ Borra una fila """
    return supabase.table(table).delete().eq(match_column, value).execute()

def delete_rows(table: str, match_dict: dict):
    """ Borra múltiples filas """
    q = supabase.table(table).delete()
    for col, val in match_dict.items():
        q = q.eq(col, val)
    return q.execute()


# ==========================
#   DOWNLOAD TABLE
# ==========================

def download_table_json(table: str, filepath: str):
    """ Descarga una tabla completa en JSON """
    data = supabase.table(table).select("*").execute().data
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return filepath


def download_table_csv(table: str, filepath: str):
    """ Descarga una tabla completa en CSV """
    data = supabase.table(table).select("*").execute().data
    if not data:
        return None

    keys = data[0].keys()

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)

    return filepath


# ==========================
#   TEST (opcional)
# ==========================


def check_connection():
    """
    Comprueba si la conexión a la base de datos de Supabase funciona correctamente.
    Intenta ejecutar una consulta simple.
    Devuelve True si funciona, False si no.
    """
    try:
        resp = requests.get(f"{SUPABASE_URL}/auth/v1/health",
                            headers={"apikey": SUPABASE_ANON_KEY})
        return resp.status_code == 200
    except Exception as e:
        print("Error check:", e)
        return False

if __name__ == "__main__":
    print("Probando conexión con Supabase...")
    if check_connection():
        print("Conexión exitosa a Supabase.")
    else:
        print("Error en la conexión a Supabase.")

