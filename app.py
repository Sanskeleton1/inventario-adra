import os
import sqlite3
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_NAME = "adra_sistema.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL,
            verificado INTEGER DEFAULT 1
        )
    """)

    # Tabla Inventario
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            unidad TEXT NOT NULL,
            stock_minimo INTEGER NOT NULL DEFAULT 10,
            ubicacion TEXT
        )
    """)

    # Tabla Personal / RRHH
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            cargo TEXT NOT NULL,
            area TEXT NOT NULL,
            telefono TEXT,
            estado TEXT DEFAULT 'Activo'
        )
    """)

    # Tabla Beneficiarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beneficiarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            comunidad TEXT NOT NULL,
            familiares INTEGER DEFAULT 1,
            telefono TEXT
        )
    """)

    # Tabla Entregas / Historial
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            beneficiario_id INTEGER,
            producto_id INTEGER,
            cantidad INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (beneficiario_id) REFERENCES beneficiarios (id),
            FOREIGN KEY (producto_id) REFERENCES inventario (id)
        )
    """)
    
    # Usuario Admin por defecto
    admin_pw = pwd_context.hash("admin123")
    cursor.execute("SELECT * FROM usuarios WHERE correo = ?", ("admin@adra.org",))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO usuarios (nombre, correo, password_hash, rol, verificado)
            VALUES (?, ?, ?, ?, 1)
        """, ("Administrador ADRA", "admin@adra.org", admin_pw, "admin"))

    # Datos iniciales para Inventario si está vacío
    cursor.execute("SELECT COUNT(*) as cant FROM inventario")
    if cursor.fetchone()["cant"] == 0:
        cursor.executemany("""
            INSERT INTO inventario (nombre, categoria, cantidad, unidad, stock_minimo, ubicacion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("Kit de Alimentos No Perecederos", "Alimentos", 120, "Cajas", 20, "Almacén Central - Estante A"),
            ("Botiquín Primeros Auxilios", "Salud", 8, "Kits", 15, "Almacén Central - Estante B"),
            ("Frazadas / Cobijas Térmicas", "Textil", 350, "Unidades", 50, "Almacén Sur"),
            ("Purificador de Agua Portátil", "Agua y Sanitización", 45, "Unidades", 10, "Almacén Central - Estante C")
        ])

    # Datos iniciales para Personal / RRHH si está vacío
    cursor.execute("SELECT COUNT(*) as cant FROM personal")
    if cursor.fetchone()["cant"] == 0:
        cursor.executemany("""
            INSERT INTO personal (documento, nombre, cargo, area, telefono, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("V-18239401", "María Delgado", "Coordinadora de Logística", "Operaciones", "0414-1234567", "Activo"),
            ("V-22194857", "Carlos Mendoza", "Médico General", "Salud y Emergencias", "0424-9876543", "Activo"),
            ("V-26839201", "Ana Gómez", "Voluntaria de Campo", "Atención Comunitaria", "0412-5551234", "Activo")
        ])

    conn.commit()
    conn.close()

init_db()

app = FastAPI(title="ADRA Sistema")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    elif os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor ADRA en ejecución</h1>"

# --- LOGIN ---
@app.post("/api/auth/login")
def login_usuario(correo: str = Form(...), password: str = Form(...)):
    correo_clean = correo.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE correo = ?", (correo_clean,))
    user = cursor.fetchone()
    conn.close()

    if not user or not pwd_context.verify(password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Correo o contraseña incorrectos")

    return {
        "status": "ok",
        "usuario": {
            "id": user["id"],
            "nombre": user["nombre"],
            "correo": user["correo"],
            "rol": user["rol"]
        }
    }

# --- METRICAS DASHBOARD ---
@app.get("/api/dashboard/summary")
def dashboard_summary():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM inventario")
    total_articulos = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as bajo FROM inventario WHERE cantidad <= stock_minimo")
    stock_critico = cursor.fetchone()["bajo"]
    
    cursor.execute("SELECT COUNT(*) as total FROM personal WHERE estado = 'Activo'")
    total_personal = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM beneficiarios")
    total_beneficiarios = cursor.fetchone()["total"]
    
    conn.close()
    return {
        "total_articulos": total_articulos,
        "stock_critico": stock_critico,
        "total_personal": total_personal,
        "total_beneficiarios": total_beneficiarios
    }

# --- INVENTARIO ---
@app.get("/api/inventario")
def listar_inventario():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventario ORDER BY id DESC")
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

@app.post("/api/inventario")
def crear_insumo(
    nombre: str = Form(...),
    categoria: str = Form(...),
    cantidad: int = Form(...),
    unidad: str = Form(...),
    stock_minimo: int = Form(10),
    ubicacion: str = Form("")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inventario (nombre, categoria, cantidad, unidad, stock_minimo, ubicacion)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nombre, categoria, cantidad, unidad, stock_minimo, ubicacion))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Insumo registrado correctamente"}

# --- RECURSOS HUMANOS / PERSONAL ---
@app.get("/api/personal")
def listar_personal():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM personal ORDER BY id DESC")
    personal = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return personal

@app.post("/api/personal")
def registrar_personal(
    documento: str = Form(...),
    nombre: str = Form(...),
    cargo: str = Form(...),
    area: str = Form(...),
    telefono: str = Form(""),
    estado: str = Form("Activo")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO personal (documento, nombre, cargo, area, telefono, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (documento, nombre, cargo, area, telefono, estado))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="El documento/cédula ya se encuentra registrado")
        
    conn.close()
    return {"status": "ok", "message": "Personal registrado correctamente"}

# --- BENEFICIARIOS ---
@app.get("/api/beneficiarios")
def listar_beneficiarios():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM beneficiarios ORDER BY id DESC")
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return data

@app.post("/api/beneficiarios")
def registrar_beneficiario(
    documento: str = Form(...),
    nombre: str = Form(...),
    comunidad: str = Form(...),
    familiares: int = Form(1),
    telefono: str = Form("")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO beneficiarios (documento, nombre, comunidad, familiares, telefono)
            VALUES (?, ?, ?, ?, ?)
        """, (documento, nombre, comunidad, familiares, telefono))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="El documento del beneficiario ya existe")
        
    conn.close()
    return {"status": "ok", "message": "Beneficiario registrado"}