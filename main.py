from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import random
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
import psycopg2
import os
from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, RedirectResponse
from datetime import datetime, timedelta
import google.generativeai as genai

# =========================
# DB CONNECTION
# =========================


try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    GEMINI_AVAILABLE = True
    print("✅ Gemini activo")
except Exception as e:
    print("⚠️ Gemini no disponible:", e)
    GEMINI_AVAILABLE = False



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

    # =========================
    # USERS
    # =========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        reset_code TEXT,
        code_expiration TIMESTAMP
    );
    """)

    # =========================
    # TASKS
    # =========================
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

    # =========================
    # 🧠 CONVERSATIONS (HISTORIAL IA)
    # =========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Conversations (
        id SERIAL PRIMARY KEY,
        email TEXT NOT NULL,
        message TEXT,
        response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # =========================
    # ⚡ ÍNDICES (MEJOR RENDIMIENTO)
    # =========================
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_tasks_email
    ON Tasks (assigned_to);
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_conversations_email
    ON Conversations (email);
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_conversations_date
    ON Conversations (created_at DESC);
    """)

    # =========================
    # USERS DEFAULT
    # =========================
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

image_keywords = [
    "imagen", "foto", "dibujo", "genera", "crea", "hazme",
    "picture", "image", "draw", "generate"
]

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
# GEMINI
# =========================

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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

from fastapi.staticfiles import StaticFiles

app.mount("/tmp", StaticFiles(directory="/tmp"), name="tmp")

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
    expiration = datetime.utcnow() + timedelta(minutes=10)

    cursor.execute(
    "UPDATE Users SET reset_code=%s, code_expiration=%s WHERE email=%s",
    (code, expiration, email)
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
    "SELECT reset_code, code_expiration FROM Users WHERE email=%s",
    (email,)
)

    row = cursor.fetchone()

    if not row:
        return {"valid": False}

    saved_code, expiration = row

    if expiration is None or expiration < datetime.utcnow():
        return {"valid": False}

    return {"valid": saved_code == code}

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

    print("🧠 Mensaje:", lower_msg)

    # =========================
    # 🎯 DETECTAR IMAGEN
    # =========================
    wants_image = any(word in lower_msg for word in [
        "imagen", "foto", "dibujo", "crea", "genera", "hazme",
        "image", "picture", "draw"
    ])

    # =========================
    # 🧠 ASIGNAR TAREAS (ANTES)
    # =========================
    if user_email in supervisors:
        for name, email in employees.items():
            if name in lower_msg:
                cursor.execute(
                    "INSERT INTO Tasks (assigned_to, assigned_by, task_text) VALUES (%s,%s,%s)",
                    (email, user_email, message)
                )
                conn.commit()

                return {"response": f"Tarea asignada a {name}"}

    # =========================
    # 🎨 GENERACIÓN DE IMAGEN
    # =========================
    if wants_image:
        try:
            import base64

            # Gemini (solo intento)
            try:
                if GEMINI_AVAILABLE:
                    print("🎨 Intentando Gemini...")
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    model.generate_content(f"Describe visually: {message}")
            except Exception as e:
                print("Gemini falló:", e)

            print("🎨 Generando imagen OpenAI...")

            img = client.images.generate(
                model="gpt-image-1",
                prompt=message,
                size="1024x1024"
            )

            if not img.data or not img.data[0].b64_json:
                return {"response": "Error generando imagen"}

            image_base64 = img.data[0].b64_json
            filename = f"/tmp/image_{random.randint(1000,9999)}.png"

            with open(filename, "wb") as f:
                f.write(base64.b64decode(image_base64))

            # 💾 HISTORIAL
            cursor.execute(
                "INSERT INTO Conversations (email, message, response) VALUES (%s,%s,%s)",
                (user_email, message, filename)
            )
            conn.commit()

            return {
                "type": "image",
                "image_url": filename,
                "provider": "openai"
            }

        except Exception as err:
            print("❌ ERROR IMAGEN:", err)

            cursor.execute(
                "INSERT INTO Conversations (email, message, response) VALUES (%s,%s,%s)",
                (user_email, message, "Error generando imagen")
            )
            conn.commit()

            return {"response": "Error generando imagen"}

    # =========================
    # 🧠 TEXTO IA
    # =========================
    try:

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": f"""
Eres Jean Paul, IA de TMK Agency.

USA ESTA INFORMACIÓN:
{knowledge}

REGLAS:
- Responde SOLO con esta información
- Si no sabes responde EXACTAMENTE:
"No tengo esa información en el sistema"
"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        answer = response.output_text.strip()

        # =========================
        # 🔁 FALLBACK
        # =========================
        if "No tengo esa información" in answer:

            fallback = client.responses.create(
                model="gpt-4.1-mini",
                input=message
            )

            final_answer = fallback.output_text

        else:
            final_answer = answer

        # 💾 HISTORIAL
        cursor.execute(
            "INSERT INTO Conversations (email, message, response) VALUES (%s,%s,%s)",
            (user_email, message, final_answer)
        )
        conn.commit()

        return {
            "response": final_answer,
            "provider": "openai"
        }

    except Exception as e:
        print("❌ ERROR IA:", e)

        cursor.execute(
            "INSERT INTO Conversations (email, message, response) VALUES (%s,%s,%s)",
            (user_email, message, "Error con la IA")
        )
        conn.commit()

        return {"response": "Error con la IA"}