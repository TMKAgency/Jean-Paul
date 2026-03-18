from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import random
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
import os
from openai import OpenAI



import psycopg2
import os

conn = None
cursor = None

try:
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )
    cursor = conn.cursor()
    print("✅ DB conectada")
except Exception as e:
    print("❌ Error DB:", e)

    
# =========================
# CORREOS DE EMPLEADOS
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

# =========================
# CORREOS AUTORIZADOS
# =========================

allowed_emails = [
"andrew@tmk-agency.com",
"danielaalvarez@tmk-agency.com",
"fabricio@tmk-agency.com",
"katherinemora@tmk-agency.com",
"marcolamugue@tmk-agency.com",
"michelle@tmk-agency.com",
"valeriars@tmk-agency.com"
]

# =========================
# SUPERVISORES
# =========================

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
# SQL SERVER
# =========================

import psycopg2
import os

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
# HASH PASSWORD
# =========================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =========================
# REGISTER
# =========================

@app.post("/register")
def register(data: dict):

    # 🔒 Evita que la app crashee si no hay DB
    if not cursor:
        return {"error": "Base de datos no disponible"}

    email = data["email"]
    password = hash_password(data["password"])

    # 🔍 Verificar si el email existe
    cursor.execute("SELECT email FROM Users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        return {"message": "Correo no autorizado"}

    # 🔄 Actualizar contraseña
    cursor.execute(
        "UPDATE Users SET password_hash = ? WHERE email = ?",
        (password, email)
    )

    conn.commit()

    return {"message": "Contraseña creada correctamente"}

# =========================
# LOGIN
# =========================

@app.post("/login")
def login(data: dict):

    email = data["email"]
    password = data["password"]

    cursor.execute(
        "SELECT password_hash FROM Users WHERE email=?",
        email
    )

    row = cursor.fetchone()

    if not row:
        return {"success": False, "message": "Correo no autorizado"}

    db_password = row[0]

    # 🚨 NO TIENE CONTRASEÑA
    if not db_password:
        return {"success": False, "message": "Debes crear contraseña primero"}

    # 🔐 VALIDAR PASSWORD
    if db_password == hash_password(password):
        return {"success": True}

    return {"success": False, "message": "Contraseña incorrecta"}

# =========================
# ENVIAR CODIGO
# =========================

@app.post("/send-code")
def send_code(data: dict):

    email = data["email"]

    if email not in allowed_emails:
        return {"message": "Correo no autorizado"}

    code = str(random.randint(100000,999999))

    cursor.execute(
        "UPDATE Users SET reset_code=? WHERE email=?",
        code,
        email
    )

    conn.commit()

    msg = MIMEText(f"Tu código de recuperación es: {code}")
    msg["Subject"] = "Recuperación de contraseña"
    msg["From"] = "soporte@tmk-agency.com"
    msg["To"] = email

    server = smtplib.SMTP_SSL("smtp.gmail.com",465)
    server.login("TU_CORREO","TU_PASSWORD_APP")
    server.send_message(msg)
    server.quit()

    return {"message": "Código enviado"}

# =========================
# VERIFICAR CODIGO
# =========================

@app.post("/verify-code")
def verify_code(data: dict):

    email = data["email"]
    code = data["code"]

    cursor.execute(
        "SELECT reset_code FROM Users WHERE email=?",
        email
    )

    row = cursor.fetchone()

    if not row:
        return {"valid": False}

    db_code = row[0]

    return {"valid": db_code == code}

# =========================
# RESET PASSWORD
# =========================

@app.post("/reset-password")
def reset_password(data: dict):

    email = data["email"]
    code = data["code"]
    password = hash_password(data["password"])

    cursor.execute(
        "SELECT reset_code FROM Users WHERE email=?",
        email
    )

    row = cursor.fetchone()

    if not row:
        return {"message": "Usuario no encontrado"}

    db_code = row[0]

    if db_code == code:

        cursor.execute(
            "UPDATE Users SET password_hash=?, reset_code=NULL WHERE email=?",
            password,
            email
        )

        conn.commit()

        return {"message": "Contraseña actualizada"}

    return {"message": "Código incorrecto"}

# =========================
# CONOCIMIENTO IA
# =========================

knowledge = """
Tu nombre es Jean Paul.
Eres la inteligencia artificial de TMK Agency.

Puedes ayudar con marketing digital, tareas y gestión de equipo.

Si un supervisor pide asignar una tarea a un empleado debes hacerlo.
"""

# =========================
# IA JEAN PAUL
# =========================

@app.post("/ai")
def ai(data: dict):

    message = data["message"]
    user_email = data["email"]
    lower_msg = message.lower()

    # =========================
    # SOLO SUPERVISORES ASIGNAN
    # =========================

    if user_email in supervisors:

        for name, email in employees.items():

            if name in lower_msg:

                cursor.execute(
                    """
                    INSERT INTO Tasks (assigned_to, assigned_by, task_text)
                    VALUES (?,?,?)
                    """,
                    email,
                    user_email,
                    message
                )

                conn.commit()

                return {"response": f"Tarea asignada a {name.title()}"}

    # =========================
    # USUARIO NORMAL → SOLO CHAT
    # =========================

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role":"system","content": knowledge + f"\nUsuario: {user_email}"},
            {"role":"user","content": message}
        ]
    )

    respuesta = response.output[0].content[0].text

    return {"response": respuesta}

# =========================
# OBTENER TAREAS
# =========================

@app.post("/get-tasks")
def get_tasks(data: dict):

    email = data["email"]

    cursor.execute(
        "SELECT id, task_text, completed FROM Tasks WHERE assigned_to=?",
        email
    )

    rows = cursor.fetchall()

    tasks = []

    for r in rows:
        tasks.append({
            "id": r[0],
            "task": r[1],
            "completed": r[2]
        })

    return {"tasks": tasks}

# =========================
# COMPLETAR TAREA
# =========================

@app.post("/complete-task")
def complete_task(data: dict):

    task_id = data["task_id"]
    user_email = data["email"]

    cursor.execute(
        "SELECT assigned_to FROM Tasks WHERE id=?",
        task_id
    )
    row = cursor.fetchone()

    if not row:
        return {"message": "Tarea no existe"}

    owner = row[0]

    if user_email != owner:
        return {"message": "No autorizado"}

    cursor.execute(
        "UPDATE Tasks SET completed=1 WHERE id=?",
        task_id
    )

    conn.commit()

    return {"message": "Tarea completada"}

# =========================
# ELIMINAR TAREA
# =========================

@app.post("/delete-task")
def delete_task(data: dict):

    task_id = data["task_id"]
    user_email = data["email"]

    cursor.execute(
        "SELECT assigned_to FROM Tasks WHERE id=?",
        task_id
    )
    row = cursor.fetchone()

    if not row:
        return {"message": "Tarea no existe"}

    owner = row[0]

    # 🔒 VALIDACIÓN
    if user_email not in supervisors and user_email != owner:
        return {"message": "No autorizado"}

    cursor.execute(
        "DELETE FROM Tasks WHERE id=?",
        task_id
    )

    conn.commit()

    return {"message": "Tarea eliminada"}