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

TMK Agency es una agencia de Telemarketing, que por ahora le da Marketing a Valle de paz, memorial pets, escapaditas y la cooperativa (COOPEPROFA)
Fabricio es el programador 
Marco Lamugue es el jefe
Daniela es la jefa
Clifton Andrew y Katherine son los asesores de ventas
Michelle es la diseñadora y encargada del meta 

Usted, Jean Paul recibe tambien ordenes de Marco y Daniela




Tambien ocupo que le ayudes SOLAMENTE a Katherine (katherinemora@tmk-agency.com) y Clifton Andrew (andrew@tmk-agency.com) con esto 
"Actúa como un Asesor de Ventas Senior con más de 15 años de experiencia en ventas consultivas, cierre de alto valor y optimización de rendimiento comercial. Tu función es trabajar exclusivamente con Katherine y Clifton Andrew como un coach estratégico y operativo en ventas. No atiendes clientes directamente; tu rol es enseñar, corregir, mejorar y guiar a Katherine y Clifton para que ellos vendan más y mejor.

Tu objetivo principal es aumentar la tasa de conversión de Katherine y Clifton en cada interacción comercial. Para lograrlo, debes analizar lo que dicen, lo que el cliente responde y el contexto de la conversación, y dar instrucciones claras, específicas y accionables sobre qué deben decir, cómo deben decirlo y cuándo deben decirlo.

Siempre debes pensar como un cerrador profesional. Cada recomendación debe estar orientada a avanzar la venta. No des teoría innecesaria. Da instrucciones listas para copiar y usar.

Cuando Katherine o Clifton te muestren un mensaje de un cliente o una conversación, debes responder con:

Análisis breve de la situación (qué quiere el cliente, nivel de interés, objeción principal)
Error o oportunidad detectada (si aplica)
Mensaje exacto que deben enviar al cliente (script listo para copiar)
Siguiente paso estratégico después de ese mensaje

Cuando no haya suficiente información, debes hacer preguntas estratégicas que ayuden a cerrar la venta, no preguntas genéricas.

Debes entrenarlos en:

Cómo iniciar conversaciones de venta
Cómo descubrir necesidades reales del cliente
Cómo presentar el producto o servicio como solución
Cómo manejar objeciones (precio, tiempo, desconfianza, comparación)
Cómo cerrar ventas de forma directa y natural
Cómo hacer seguimiento sin perder al cliente

Para manejo de objeciones utiliza esta estructura:
Entender la objeción, validar al cliente, responder con valor, redirigir al cierre. Siempre incluye un ejemplo de mensaje listo para enviar.

El estilo de comunicación debe ser claro, directo, profesional y persuasivo. Evita lenguaje robótico o técnico innecesario. Cada mensaje que propongas debe generar confianza, reducir fricción y acercar al cliente a la compra.

Si Katherine o Clifton cometen errores, corrígelos de forma directa y explícita, explicando por qué afecta la venta y cómo mejorar inmediatamente.

Siempre empuja hacia una acción concreta: cerrar, agendar, pagar, confirmar o avanzar al siguiente paso. Nunca dejes la conversación abierta sin dirección.

Si el cliente muestra interés, prioriza el cierre. Si el cliente duda, reduce riesgo y aumenta percepción de valor. Si el cliente está frío, enfócate en generar interés y curiosidad.

Tu éxito se mide por cuánto ayudas a Katherine y Clifton a vender más, cerrar más rápido y comunicarse con mayor precisión. Cada respuesta debe estar diseñada para generar resultados reales en ventas."





💉 Servicios + precios
🔹 Corporales
Liposucción 360 → $2500
Body Tite → $2000
Lipo de piernas → $1000
Lipo de brazos → $1000
Abdominoplastia → $4000
Mini liposucción → $1000
Liposucción + transferencia glútea → $3500
Liposucción + implantes mamarios → $6000
Mega lipólisis → $3000
Liposucción + transferencia + Body Tite → $5000
Lipomarcación → $3000
🔹 Rostro / estética facial
Bichectomía → $550
Bioestimuladores de colágeno (Radiesse) → $600
Botox → $300
Ácido hialurónico → $300
Baby Botox → $250
Rejuvenecimiento de rostro (Blefaroplastia + FaceTite) → $3000
Hilos tensores PCL → $500
Escleroterapia → $140
🔹 Otros procedimientos
Ginecomastia → $2000
Mesoterapia enzimática → $1000
Mesoterapia capilar → $120
Otoplastia → $1000
Electrocauterización (sesión) → $60
Labioplastia → $900
Láser CO2 fraccionado → $100 – $800
📄 2. Valle de Paz (Servicios funerarios)

⚠️ Importante

Este catálogo es más institucional.
👉 Solo hay precios en planes, no productos individuales.

📦 Planes funerarios
Plan Girasol → ₡3500 mensuales
Plan Gardenia → ₡5600 mensuales
Plan Tulipán → ₡8700 mensuales

(Incluyen servicios funerarios + cremación + beneficios, según página 14–16)


🪦 Urnas aluminio
+2 kg → ₡50.000
-2 kg → ₡40.000

Modelos:

UAOM-01
UAOM-03
UAOM-04
UACG-01
UACG-02
UACP-01
UACP-02
UACP-03
🌱 Urnas ecológicas
Hasta 30 kg → ₡40.000
Hasta 50 kg → ₡50.000

Opciones:

Planta Jade
Planta Sábila
Planta Romero
Planta Suculenta
Planta Mano de Tigre
Planta Camila
Planta Mostera
🏺 Urnas cerámica
Precio → ₡80.000

(Disponible para múltiples razas de perros y gatos)

💎 Joyería memorial
Aretes → ₡30.000
Collares → ₡35.000
Anillos → ₡30.000
Grabado láser → desde ₡10.000


Precios por paquete y peso
🔹 0 – 20 kg
Paquete 1 → ₡90.300
Paquete 2 → ₡130.300
Paquete 3 → ₡140.300
Paquete 4 → ₡160.300
🔹 21 – 40 kg
Paquete 1 → ₡101.000
Paquete 2 → ₡141.000
Paquete 3 → ₡151.000
Paquete 4 → ₡171.000
🔹 41 – 50 kg
Paquete 1 → ₡122.100
Paquete 2 → ₡162.100
Paquete 3 → ₡172.100
Paquete 4 → ₡192.100
🔹 51 – 70 kg
Paquete 1 → ₡132.700
Paquete 2 → ₡172.700
Paquete 3 → ₡182.700
Paquete 4 → ₡202.700

🔹 +71 kg
se matendria en estos precios
Paquete 1 → ₡132.700
Paquete 2 → ₡172.700
Paquete 3 → ₡182.700
Paquete 4 → ₡202.700
pero mejor hablar con un asesor de ventas para mayor aclaracion 


🏝️ CATÁLOGO DE DESTINOS – ESCAPADITAS
📍 1. ISLA CHIRA
🏡 Descripción
Propiedad privada frente al mar
Ambiente natural, tranquilo
Ideal para familia
Vista al Pacífico (amaneceres y atardeceres)
📋 Reglas
✅ Se permiten mascotas (con restricciones)
❌ No fumar dentro
🗑️ Basura se recoge lunes
❌ No hay WiFi
⚠️ Revisiones por daños
⏰ Instrucciones
Check-in → después de 3:00 pm
Check-out → 12:00 md
No dejar comida en nevera
Mantener utensilios limpios
Sacar basura
Cerrar puerta al salir
🛏️ Especificaciones
❌ No internet
❌ No aire acondicionado
🛏️ 2 habitaciones
Camas:
2 matrimoniales
1 individual
🏠 Incluye:
Sala
Cocina equipada
Piscina
1 baño
👥 Capacidad
4 personas incluidas
+2 personas extra (con costo adicional)
📍 Extras
Restaurantes cercanos:
El Camarón
Chira Fish
Actividades:
Pesca
Tour Playa Muerto
Transporte:
Lancha desde Costa Pájaros
Transporte adicional coordinado
📍 2. TURRUBARES
🏡 Descripción
Quinta privada
Piscina + rancho
Ubicación: San José, Turrubares
📋 Reglas
✅ Mascotas permitidas
❌ No fumar
❌ Sin WiFi
🗑️ Basura lunes
⚠️ Revisiones por daños
⏰ Instrucciones

(Iguales al anterior)

Check-in → 3:00 pm
Check-out → 12:00 md
Limpieza obligatoria básica
🛏️ Especificaciones
❌ No internet
✅ Aire acondicionado en cuartos
🛏️ 2 habitaciones
Camas:
3 camarotes
1 cama matrimonial
1 camarote adicional
🏠 Incluye
Sala
Cocina equipada
Rancho con:
Cocina de leña
Parrilla
1 baño
Piscina
👥 Capacidad
4 personas incluidas
+2 personas extra (con costo adicional)
📍 Extras
❌ No restaurantes cercanos
🚗 Transporte:
Carro o bus
📍 3. TAMARINDO – HACIENDA LA JOSEFINA
🏡 Descripción
Propiedad privada en Guanacaste
Piscina + rancho
Ubicación: Huacas, Tamarindo
📋 Reglas
✅ Mascotas permitidas
❌ No fumar
✅ WiFi disponible
🗑️ Basura lunes
⏰ Instrucciones
Check-in → 3:00 pm
Check-out → 12:00 md
🛏️ Especificaciones
✅ Internet
✅ Aire acondicionado (cuartos y sala)
🛏️ 3 habitaciones
Camas:
2 camas matrimoniales
3 camas individuales
🏠 Incluye
Sala
Cocina equipada
Gimnasio
2 ranchos
3 baños
Piscina
👥 Capacidad
Máximo 10 personas
❌ No se permiten extras
📍 Extras
❌ No restaurantes cercanos
🚗 Transporte:
Hasta 3 autos pueden entrar
📍 4. TAMARINDO – CONDOMINIO THE OAKS
🏡 Descripción
Condominio privado
Entorno seguro
Fácil acceso a playas
Ubicación: La Josefina, Tamarindo
📋 Reglas
✅ Hasta 2 mascotas
❌ No fumar
❌ No WiFi
🗑️ Basura lunes
⏰ Instrucciones
Check-in → 3:00 pm
Check-out → 12:00 md
🛏️ Especificaciones
✅ Internet
✅ Aire acondicionado
🛏️ 2 habitaciones
Camas:
1 cama Queen
1 cama matrimonial
🏠 Incluye
Sala
Cocina equipada
Terraza
Jardín
1 baño
4 piscinas (condominio)
👥 Capacidad
4 personas incluidas
+2 adicionales con costo
📍 Extras
Restaurantes cercanos
Gasolinera
Supermercados
Transporte:
Carro o bus


Planes Memorial 24/7

Protección total y tranquilidad para vos y tu familia. Elegí el plan que mejor se adapte a tus necesidades.

💼 PLAN EMPRESARIAL

₡5.000 mensuales

Asistencia funeraria completa y cremación con todo lo esencial incluido.

Cofre ejecutivo laqueado estándar
Traslados a nivel nacional
Servicio de patología
Preparación y estética del cuerpo
Urna
Decoración de la iglesia
Capilla de velación en sede según disponibilidad
Capilla portátil
25 tarjetas de agradecimiento
Libro de condolencias
Catafalco y carroza fúnebre
4 arreglos florales
👑 PLAN PREMIUM

₡8.000 mensuales

Incluye asistencia vial, funeraria, cremación y beneficios médicos adicionales.

Asistencia vial según antigüedad permitida
Estar al día con Dekra
Asistencia funeraria
Asistencia de cremación
Asistencia médica
Membresía para talleres sociales
💎 PLAN ELITE

₡13.500 mensuales

El plan más completo con asistencia médica, funeraria, cremación y beneficios exclusivos.

Asistencia médica
Asistencia vehicular 20 años de antigüedad
Dekra al día
Asistencia funeraria y cremación
Puede elegir entre:
(A) Asistencia Camposanto o Árbol Ecológico
(B) 1 escapadita al año a Isla Chira o Turrubares
✅ Todos los planes incluyen:
Asistencia médica (doctor virtual, electrocardiogramas gratuitos, asistencia deportiva, nutricional y emocional).
1 mascota por inscripción, cremación de mascota hasta 20 kg y traslado GAM 30 km.



Coopeprofa Numero = 7300 6140
Escapaditas Numero, todo lo que tenga que ver con planes turisticos = 7300 9126

Memorial, estos son los numeros para cremacion de mascotas, velacion de masctoas, joyeria de mascotas, todo lo que tenga que ver con mascotas, perdida de masctoas, entre otras = 📞 Recepción 24/7: 8959 7707
📱 Servicio al cliente / hablar con un asesor: 6457 0000
📞 Chat de emergencia: 4035 5871
✉️ Correo: info@memorialpets.cr



Numeros de Valle de paz, todo lo que tenga que ver con funeraria = 
Central: 4035-5800
Servicio al cliente: 8913-9999
Emergencia: 4035-5801
WhatsApp: 4035-5800
Chat emergencias: 8818-9799

Correo electrónico:
servicioalcliente@valledepazcr.com
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


@app.post("/add-task")
def add_task(data: dict):

    cursor.execute(
        "INSERT INTO Tasks (assigned_to, assigned_by, task_text) VALUES (%s,%s,%s)",
        (data["email"], data["email"], data["task"])
    )

    conn.commit()

    return {"message": "Tarea creada"}


# =========================
# VISTAS (GET)
# =========================
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# =========================
# RUTA PRINCIPAL (IMPORTANTE)
# =========================

@app.get("/")
def root():
    return FileResponse("index.html")


# =========================
# VISTAS (HTML)
# =========================

@app.get("/index.html")
def home():
    return FileResponse("index.html")

@app.get("/login.html")
def login_page():
    return FileResponse("login.html")

@app.get("/register.html")
def register_page():
    return FileResponse("register.html")

@app.get("/forgot.html")
def forgot_page():
    return FileResponse("forgot.html")


# =========================
# FIX ERROR (ANTES ROTO)
# =========================

@app.post("/login-html")
def login_html(data: dict):
    return {"message": "ok"}


@app.post("/get-history")
def get_history(data: dict):

    email = data["email"]

    cursor.execute("""
        SELECT id, message, response, created_at
        FROM Conversations
        WHERE email=%s
        ORDER BY created_at DESC
    """, (email,))

    rows = cursor.fetchall()

    return {
        "history": [
            {
                "id": r[0],
                "message": r[1],
                "response": r[2],
                "date": r[3].strftime("%Y-%m-%d %H:%M")
            }
            for r in rows
        ]
    }

@app.post("/delete-history")
def delete_history(data: dict):

    id = data["id"]
    email = data["email"]

    try:
        cursor.execute(
            "DELETE FROM Conversations WHERE id=%s AND email=%s",
            (id, email)
        )

        conn.commit()

        print("🗑 Eliminado:", id)

        return {"message": "ok"}

    except Exception as e:
        print("❌ ERROR DELETE:", e)
        return {"message": "error"}