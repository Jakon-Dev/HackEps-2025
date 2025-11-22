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
#   UPLOAD TABLE
# ==========================

def detect_column_type(values):
    """
    Recibe una lista de valores de una columna y devuelve un tipo SQL:
    - integer
    - float
    - boolean
    - text
    """
    has_float = False
    has_text = False

    for v in values:
        if v is None or v == "":
            continue

        v_lower = str(v).lower()

        if v_lower in ("true", "false"):
            continue  # boolean

        # integer
        if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
            continue

        # float
        try:
            float(v)
            has_float = True
            continue
        except:
            pass

        has_text = True
        break

    if has_text:
        return "text"

    if has_float:
        return "float"

    # boolean si todos son true/false o vacío
    if all((str(v).lower() in ("true", "false", "") for v in values)):
        return "boolean"

    return "integer"


def progress_bar(current, total, bar_length=40):
    ratio = current / total
    filled = int(bar_length * ratio)
    bar = "#" * filled + "-" * (bar_length - filled)
    print(f"\r[{bar}] {int(ratio * 100)}%", end="")

def upload_csv_to_supabase():
    from pathlib import Path
    import csv

    # 1. Encontrar root (donde está .env)
    project_root = ENV_PATH.parent
    print(f"Buscando CSV en: {project_root}")

    csv_files = list(project_root.rglob("*.csv"))
    if not csv_files:
        print("No se encontraron archivos CSV.")
        return

    # 2. Mostrar lista
    print("CSV encontrados:")
    for i, f in enumerate(csv_files, start=1):
        print(f"{i}. {f.relative_to(project_root)}")

    # 3. Pedir selección
    while True:
        try:
            choice = int(input("Selecciona un CSV por número: "))
            if 1 <= choice <= len(csv_files):
                break
        except:
            pass
        print("Número inválido.")

    csv_path = csv_files[choice - 1]
    table_name = csv_path.stem.lower().replace("-", "_").replace(" ", "_")

    print(f"Archivo seleccionado: {csv_path}")
    print(f"Nombre asignado de tabla: {table_name}")

    # 4. Leer datos
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("El CSV está vacío.")
        return

    columns = reader.fieldnames
    print(f"Columnas detectadas: {columns}")

    # 5. Autodetección de tipos
    print("Detectando tipos de columnas:")
    col_values = {col: [] for col in columns}

    for row in rows:
        for col in columns:
            col_values[col].append(row[col])

    column_types = {col: detect_column_type(col_values[col]) for col in columns}

    for c, t in column_types.items():
        print(f"  {c}: {t}")

    # Convertir tipos Python->SQL
    sql_types_map = {
        "integer": "int",
        "float": "float8",
        "boolean": "boolean",
        "text": "text",
    }

    col_sql = {c: sql_types_map[column_types[c]] for c in columns}

    # 6. Verificar si tabla existe
    try:
        existing = supabase.table("pg_tables").select("tablename").execute()
        exists = any(t["tablename"] == table_name for t in existing.data)
    except:
        exists = False

    if exists:
        print(f"La tabla '{table_name}' ya existe.")
        print("1. Reemplazar tabla")
        print("2. Crear nueva con sufijo numérico")
        option = input("Elige opción (1 o 2): ")

        if option == "1":
            delete_table(table_name)
            print(f"Tabla '{table_name}' eliminada.")
        else:
            i = 1
            new_name = f"{table_name}_{i}"
            while any(t["tablename"] == new_name for t in existing.data):
                i += 1
                new_name = f"{table_name}_{i}"
            table_name = new_name
            print(f"Usando nombre alternativo: {table_name}")

    # 7. Crear tabla
    print("Creando tabla...")
    create_table(table_name, col_sql)

    # 8. Subir datos con barra de progreso
    print("Subiendo datos...")

    batch = []
    total = len(rows)
    for i, row in enumerate(rows, start=1):
        batch.append(row)

        # enviar cada 500 para evitar overload
        if len(batch) >= 500:
            insert_rows(table_name, batch)
            batch = []
        progress_bar(i, total)

    if batch:
        insert_rows(table_name, batch)

    print("\nCarga completada.")


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

