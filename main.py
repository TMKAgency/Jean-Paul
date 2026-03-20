from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import random
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
import psycopg2
import os
from fastapi.responses import FileResponse


# =========================
# DB CONNECTION
# =========================

conn = None
cursor = None

try:
    DATABASE_URL = os.getenv("DATABASE_URL")

    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )

    cursor = conn.cursor()
    print("✅ DB conectada")

except Exception as e:
    print("❌ Error DB:", e)

# =========================
# CREATE TABLES + USERS
# =========================

if cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        reset_code TEXT,
        code_expiration TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Tasks (
        id SERIAL PRIMARY KEY,
        assigned_to TEXT,
        assigned_by TEXT,
        task_text TEXT,
        completed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    INSERT INTO Users (email) VALUES
    ('andrew@tmk-agency.com'),
    ('danielaalvarez@tmk-agency.com'),
    ('fabricio@tmk-agency.com'),
    ('katherinemora@tmk-agency.com'),
    ('marcolamugue@tmk-agency.com'),
    ('michelle@tmk-agency.com'),
    ('valeriars@tmk-agency.com')
    ON CONFLICT (email) DO NOTHING;
    """)

    conn.commit()

# =========================
# DATA
# =========================

employees = {
    "alanys": "alanyssoto@tmk-agency.com",
    "andrew": "andrew@tmk-agency.com",
    "clifton": "andrew@tmk-agency.com",
    "fabricio": "fabricio@tmk-agency.com",
    "katherine": "katherinemora@tmk-agency.com",
    "michelle": "michelle@tmk-agency.com",
    "valeria": "valeriars@tmk-agency.com"
}

allowed_emails = [
    "andrew@tmk-agency.com",
    "danielaalvarez@tmk-agency.com",
    "fabricio@tmk-agency.com",
    "katherinemora@tmk-agency.com",
    "marcolamugue@tmk-agency.com",
    "michelle@tmk-agency.com",
    "valeriars@tmk-agency.com"
]

supervisors = [
    "marcolamugue@tmk-agency.com",
    "danielaalvarez@tmk-agency.com",
]

# =========================
# OPENAI
# =========================

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# FASTAPI
# =========================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# UTILS
# =========================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =========================
# REGISTER
# =========================

@app.post("/register")
def register(data: dict):

    email = data["email"]
    password = hash_password(data["password"])

    cursor.execute("SELECT email FROM Users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user:
        cursor.execute(
            "UPDATE Users SET password_hash=%s WHERE email=%s",
            (password, email)
        )
    else:
        cursor.execute(
            "INSERT INTO Users (email, password_hash) VALUES (%s, %s)",
            (email, password)
        )

    conn.commit()

    return {"message": "Usuario listo"}

# =========================
# LOGIN
# =========================

@app.post("/login")
def login(data: dict):

    email = data["email"]
    password = data["password"]

    cursor.execute(
        "SELECT password_hash FROM Users WHERE email=%s",
        (email,)
    )

    row = cursor.fetchone()

    if not row:
        return {"success": False, "message": "Correo no autorizado"}

    db_password = row[0]

    if not db_password:
        return {"success": False, "message": "Debes crear contraseña primero"}

    if db_password == hash_password(password):
        return {"success": True}

    return {"success": False, "message": "Contraseña incorrecta"}

# =========================
# SEND CODE
# =========================

@app.post("/send-code")
def send_code(data: dict):

    if not cursor:
        return {"message": "DB no disponible"}

    email = data["email"]

    if email not in allowed_emails:
        return {"message": "Correo no autorizado"}

    code = str(random.randint(100000, 999999))

    cursor.execute(
        "UPDATE Users SET reset_code=%s WHERE email=%s",
        (code, email)
    )

    conn.commit()

    try:
        msg = MIMEText(f"Tu código de recuperación es: {code}")
        msg["Subject"] = "Recuperación de contraseña"
        msg["From"] = os.getenv("EMAIL_USER")
        msg["To"] = email

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(
            os.getenv("EMAIL_USER"),
            os.getenv("EMAIL_PASS")
        )

        server.send_message(msg)
        server.quit()

    except Exception as e:
        print("❌ Error enviando correo:", e)
        return {"message": "Error enviando correo"}

    return {"message": "Código enviado correctamente"}

# =========================
# VERIFY CODE
# =========================

@app.post("/verify-code")
def verify_code(data: dict):

    email = data["email"]
    code = data["code"]

    cursor.execute(
        "SELECT reset_code FROM Users WHERE email=%s",
        (email,)
    )

    row = cursor.fetchone()

    if not row:
        return {"valid": False}

    return {"valid": row[0] == code}

# =========================
# RESET PASSWORD
# =========================

@app.post("/reset-password")
def reset_password(data: dict):

    email = data["email"]
    code = data["code"]
    password = hash_password(data["password"])

    cursor.execute(
        "SELECT reset_code FROM Users WHERE email=%s",
        (email,)
    )

    row = cursor.fetchone()

    if not row:
        return {"message": "Usuario no encontrado"}

    if row[0] == code:
        cursor.execute(
            "UPDATE Users SET password_hash=%s, reset_code=NULL WHERE email=%s",
            (password, email)
        )
        conn.commit()
        return {"message": "Contraseña actualizada"}

    return {"message": "Código incorrecto"}

# =========================
# IA
# =========================

knowledge = """
Eres Jean Paul, IA de TMK Agency.
"""

@app.post("/ai")
def ai(data: dict):

    message = data["message"]
    user_email = data["email"]
    lower_msg = message.lower()

    if user_email in supervisors:
        for name, email in employees.items():
            if name in lower_msg:
                cursor.execute(
                    "INSERT INTO Tasks (assigned_to, assigned_by, task_text) VALUES (%s,%s,%s)",
                    (email, user_email, message)
                )
                conn.commit()
                return {"response": f"Tarea asignada a {name}"}

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=message
    )

    return {"response": response.output[0].content[0].text}

# =========================
# TASKS
# =========================

@app.post("/get-tasks")
def get_tasks(data: dict):

    email = data["email"]

    cursor.execute(
        "SELECT id, task_text, completed FROM Tasks WHERE assigned_to=%s",
        (email,)
    )

    rows = cursor.fetchall()

    return {
        "tasks": [
            {"id": r[0], "task": r[1], "completed": r[2]}
            for r in rows
        ]
    }

@app.post("/complete-task")
def complete_task(data: dict):

    task_id = data["task_id"]
    email = data["email"]

    cursor.execute(
        "SELECT assigned_to FROM Tasks WHERE id=%s",
        (task_id,)
    )

    row = cursor.fetchone()

    if not row:
        return {"message": "No existe"}

    if row[0] != email:
        return {"message": "No autorizado"}

    cursor.execute(
        "UPDATE Tasks SET completed=TRUE WHERE id=%s",
        (task_id,)
    )

    conn.commit()

    return {"message": "Completada"}

@app.post("/delete-task")
def delete_task(data: dict):

    task_id = data["task_id"]
    email = data["email"]

    cursor.execute(
        "SELECT assigned_to FROM Tasks WHERE id=%s",
        (task_id,)
    )

    row = cursor.fetchone()

    if not row:
        return {"message": "No existe"}

    if email not in supervisors and email != row[0]:
        return {"message": "No autorizado"}

    cursor.execute(
        "DELETE FROM Tasks WHERE id=%s",
        (task_id,)
    )

    conn.commit()

    return {"message": "Eliminada"}



@app.get("/")
def home():
    return FileResponse("index.html")