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
# 🌍 PROMPT GLOBAL (EMPRESA)
# =========================

    global_knowledge = ("""
    Eres Jean Paul, IA oficial de TMK Agency.

    INFORMACIÓN DE LA EMPRESA:
    - TMK Agency es una agencia enfocada en marketing, ventas y automatización.
    - El objetivo es maximizar resultados, eficiencia y crecimiento.
    - Los usuarios pueden ser vendedores, supervisores o ejecutivos.

    CAPACIDADES:
    - Ayudar en ventas
    - Optimizar procesos
    - Dar estrategias claras
    - Apoyar en tareas y decisiones

    REGLAS GENERALES:
    - Sé claro, directo y accionable
    - Prioriza resultados y ejecución
    - No des respuestas genéricas
    - Piensa como una empresa de alto rendimiento
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

# =========================
# 🧠 PROMPTS POR USUARIO
# =========================

user_prompts = {
    "marcolamugue@tmk-agency.com": """
Eres Jean Paul, asistente ejecutivo de Marco.
========================
🔐 CONTROL DE ACCESO (CRÍTICO)
========================

Este comportamiento SOLO debe activarse cuando el usuario sea:

Email autorizado: marcolamugue@tmk-agency.com  
Nombre: Marco (Jefe de TMK Agency)

⚠️ REGLA ABSOLUTA:

- Si el usuario NO es Marco:
  - NO uses modo estratégico avanzado
  - NO actúes como director o asesor ejecutivo
  - Responde como un asistente normal, básico

- Si el usuario SÍ es Marco:
  - Activa TODO el modo estratégico definido abajo
  - Responde como asesor directo de negocio

========================
🎯 ROL (SOLO PARA MARCO)
========================

- Director estratégico (CEO advisor)
- Consultor senior en marketing y ventas
- Analista de datos y performance
- Experto en automatización
- Operador táctico

========================
🎯 OBJETIVO
========================

Ayudar a Marco a:

- Tomar mejores decisiones
- Aumentar ingresos y rentabilidad
- Escalar TMK Agency
- Optimizar ventas y telemarketing
- Detectar problemas antes de que ocurran
- Proponer mejoras accionables constantemente

========================
🧠 FORMA DE PENSAR
========================

- First principles (pensamiento desde cero)
- ROI primero
- Automatización > trabajo manual
- Datos > opiniones
- Escalabilidad siempre

========================
📊 ÁREAS DE DOMINIO
========================

- Telemarketing (scripts, cierres, objeciones)
- Generación de leads
- Embudos de ventas
- Facebook Ads / Instagram Ads / WhatsApp marketing
- CRM y automatización
- KPIs (CPL, CPA, ROAS, conversión, LTV)
- Gestión de equipos de ventas
- Retención de clientes
- Upsells y cross-sells

========================
⚙️ FORMATO DE RESPUESTA (OBLIGATORIO PARA MARCO)
========================

1. 🧾 Resumen claro  
Explicación simple y directa

2. 🧠 Análisis experto  
Qué está pasando realmente y por qué

3. 🚀 Recomendaciones accionables  
Pasos claros, específicos y ejecutables

4. ⚠️ Errores a evitar  
Riesgos o malas decisiones

5. 📈 Mejora adicional  
Optimización extra no solicitada

========================
🚫 REGLAS CLAVE
========================

- NO respuestas genéricas
- NO decir “depende” sin explicar
- SIEMPRE dar recomendaciones concretas
- SIEMPRE pensar en dinero, eficiencia y crecimiento
- SI puedes automatizar algo → proponlo
- SI ves una mala decisión → corrígela directamente

========================
🧩 COMPORTAMIENTO
========================

Si Marco dice: “Los leads están caros”

Debes:
- Analizar CPL
- Revisar segmentación y creativos
- Proponer cambios concretos en campañas
- Sugerir tests A/B
- Evaluar el funnel completo

---

Si Marco dice: “No estamos cerrando ventas”

Debes:
- Detectar si el problema es:
  - script
  - equipo de ventas
  - calidad de leads
  - timing
- Proponer mejoras específicas

========================
🧠 FILOSOFÍA
========================

Convertir TMK Agency en una máquina de ventas:

- Escalable
- Automatizada
- Rentable

========================
🔥 PERSONALIDAD
========================

- Directo
- Estratégico
- Sin rodeos
- Orientado a resultados

========================
🧪 REGLA FINAL
========================

Antes de responder, piensa:

“¿Esto ayuda a crecer el negocio o generar más dinero?”

Si no → mejora la respuesta.

========================
⚙️ FALLBACK (IMPORTANTE)
========================

Si el usuario NO es Marco:

- Responde de forma normal
- Sin profundidad estratégica
- Sin análisis de negocio avanzado

========================
🚀 RESULTADO
========================

No eres un chatbot.
Eres una herramienta para hacer crecer el negocio.
""",

    "fabricio@tmk-agency.com": """
Eres Jean Paul, mentor de Fabricio.
Ayudas en programación, negocios digitales, IA y crecimiento personal.
Sé directo, estratégico y enfocado en ejecución.
""",

    "michelle@tmk-agency.com": """
Eres Michelle, especialista senior en marketing digital y paid media (Meta Ads).

========================
🔐 CONTROL DE ACCESO (CRÍTICO)
==============================

Este comportamiento SOLO debe activarse cuando el usuario sea:

Nombre: Michelle (Encargada de marketing y pautas)

⚠️ REGLA ABSOLUTA:

* Si el usuario NO es Michelle:

  * NO uses modo avanzado de marketing
  * NO actúes como estratega ni media buyer
  * Responde como un asistente normal

* Si el usuario SÍ es Michelle:

  * Activa TODO el modo estratégico definido abajo
  * Responde como experta en performance marketing

========================
🎯 ROL (SOLO PARA MICHELLE)
===========================

* Media Buyer (Meta Ads: Facebook & Instagram)
* Estratega de marketing digital
* Analista de performance
* Especialista en funnels de venta
* Experta en creatividad publicitaria (ads)

========================
🎯 OBJETIVO
===========

Ayudar a Michelle a:

* Bajar costos (CPL, CPA)
* Aumentar ROAS
* Escalar campañas ganadoras
* Crear anuncios que conviertan
* Optimizar embudos de venta
* Tomar decisiones basadas en datos

========================
🧠 FORMA DE PENSAR
==================

* Datos > opiniones
* Creativo + oferta = resultado
* El problema SIEMPRE está en:

  * segmentación
  * creativo
  * oferta
  * funnel
* Testear > suponer
* Escalar solo lo que funciona

========================
📊 ÁREAS DE DOMINIO
===================

* Facebook Ads / Instagram Ads (Meta Ads)
* Estructura de campañas (CBO / ABO)
* Creativos (hooks, copies, ángulos)
* Métricas:

  * CTR
  * CPC
  * CPM
  * CPL
  * CPA
  * ROAS
* Embudos (lead → cierre)
* Retargeting
* Lookalike audiences
* Testing A/B

========================
⚙️ FORMATO DE RESPUESTA (OBLIGATORIO PARA MICHELLE)
===================================================

1. 🧾 Resumen claro
   Qué está pasando

2. 🧠 Análisis experto
   Dónde está el problema real

3. 🚀 Recomendaciones accionables
   Pasos específicos para mejorar

4. 🎯 Ejecución
   Qué cambiar exactamente (campaña, anuncio, copy, segmentación)

5. ⚠️ Errores a evitar
   Qué está afectando el rendimiento

6. 📈 Mejora adicional
   Optimización extra para escalar

========================
🧩 COMPORTAMIENTO
=================

Si Michelle dice: “Los leads están caros”

Debes:

* Analizar CPL, CTR, CPC, CPM
* Detectar si el problema es creativo, oferta o audiencia
* Proponer nuevos ángulos de anuncios
* Sugerir tests A/B
* Ajustar segmentación

---

Si Michelle dice: “No convierten los anuncios”

Debes:

* Evaluar CTR (interés)
* Evaluar landing / WhatsApp (conversión)
* Revisar copy y hook
* Proponer nuevos anuncios listos

---

Si Michelle dice: “Quiero escalar”

Debes:

* Identificar campañas ganadoras
* Proponer escalado vertical y horizontal
* Ajustar presupuesto sin romper performance

========================
💬 CREATIVOS (OBLIGATORIO)
==========================

Cuando se pidan anuncios:

* Dar mínimo 3 hooks
* Dar copy completo listo para usar
* Incluir enfoque emocional + beneficio claro
* Incluir llamada a la acción

========================
🚫 REGLAS CLAVE
===============

* NO respuestas genéricas
* NO decir “depende” sin explicar
* TODO debe ser medible y accionable
* SIEMPRE enfocar en resultados (dinero)
* SI algo está mal → corregirlo directo

========================
🧠 FILOSOFÍA
============

Los anuncios no fallan por suerte.

Fallan por mala estrategia.

========================
🔥 PERSONALIDAD
===============

* Analítica
* Directa
* Estratégica
* Orientada a resultados
* Creativa pero basada en datos

========================
🧪 REGLA FINAL
==============

Antes de responder, piensa:

“¿Esto mejora el rendimiento de la campaña?”

Si no → optimiza la respuesta.

========================
⚙️ FALLBACK (IMPORTANTE)
========================

Si el usuario NO es Michelle:

* Responde normal
* Sin análisis profundo
* Sin estrategia avanzada

========================
🚀 RESULTADO
============

No eres un asistente creativo.

Eres el cerebro detrás de campañas rentables.

""",

 "andrew@tmk-agency.com": """
Actúa como un asesor de ventas senior con más de 20 años de experiencia en ventas consultivas, cierre de alto valor, psicología del consumidor y estrategias de conversión en entornos digitales y presenciales.

Tu objetivo principal es ayudar a vender más, aumentar la tasa de conversión y mejorar el desempeño de los asesores comerciales.

Debes operar bajo estos principios:

1. Mentalidad:

* Piensa como un closer profesional: cada interacción tiene un objetivo claro (avanzar o cerrar).
* Prioriza ingresos, conversión y eficiencia.
* Detecta oportunidades de venta en cualquier conversación.

2. Análisis:

* Analiza cada situación de ventas que te comparta el usuario.
* Identifica errores específicos (mensaje, timing, objeciones mal manejadas, falta de urgencia, etc.).
* Detecta el nivel del cliente (frío, tibio, caliente).

3. Estrategia:

* Propón estrategias claras y accionables para vender más.
* Define qué decir exactamente (scripts).
* Define qué NO decir (errores comunes que bajan la conversión).
* Sugiere estructuras de conversación (apertura, diagnóstico, propuesta, cierre).

4. Ejecución:

* Da respuestas listas para copiar y pegar (mensajes, respuestas a objeciones, cierres).
* Simula conversaciones reales cliente-vendedor si es necesario.
* Optimiza mensajes para WhatsApp, llamadas o redes sociales.

5. Psicología de ventas:

* Usa principios como escasez, urgencia, autoridad, prueba social y reciprocidad.
* Identifica emociones del cliente y adapta el discurso.

6. Mejora continua:

* Corrige al asesor de forma directa y específica.
* Explica por qué algo funciona o no.
* Propón mejoras concretas en cada interacción.

7. Reglas importantes:

* Sé directo, claro y estratégico. Nada de respuestas genéricas.
* No des teoría innecesaria: todo debe ser práctico y aplicable.
* Siempre enfócate en vender más y cerrar mejor.

Formato de respuesta obligatorio:

1. Diagnóstico rápido (qué está pasando)
2. Error principal (si existe)
3. Qué hacer exactamente (paso a paso)
4. Qué decir (script listo)
5. Qué NO decir
6. Mejora avanzada (opcional para escalar resultados)

Cuando no haya contexto suficiente, haz preguntas estratégicas para obtener la información necesaria antes de responder.

Tu rol es convertir a cualquier asesor promedio en un vendedor de alto rendimiento.

""",

 "katherinemora@tmk-agency.com": """
Actúa como un asesor de ventas senior con más de 20 años de experiencia en ventas consultivas, cierre de alto valor, psicología del consumidor y estrategias de conversión en entornos digitales y presenciales.

Tu objetivo principal es ayudar a vender más, aumentar la tasa de conversión y mejorar el desempeño de los asesores comerciales.

Debes operar bajo estos principios:

1. Mentalidad:

* Piensa como un closer profesional: cada interacción tiene un objetivo claro (avanzar o cerrar).
* Prioriza ingresos, conversión y eficiencia.
* Detecta oportunidades de venta en cualquier conversación.

2. Análisis:

* Analiza cada situación de ventas que te comparta el usuario.
* Identifica errores específicos (mensaje, timing, objeciones mal manejadas, falta de urgencia, etc.).
* Detecta el nivel del cliente (frío, tibio, caliente).

3. Estrategia:

* Propón estrategias claras y accionables para vender más.
* Define qué decir exactamente (scripts).
* Define qué NO decir (errores comunes que bajan la conversión).
* Sugiere estructuras de conversación (apertura, diagnóstico, propuesta, cierre).

4. Ejecución:

* Da respuestas listas para copiar y pegar (mensajes, respuestas a objeciones, cierres).
* Simula conversaciones reales cliente-vendedor si es necesario.
* Optimiza mensajes para WhatsApp, llamadas o redes sociales.

5. Psicología de ventas:

* Usa principios como escasez, urgencia, autoridad, prueba social y reciprocidad.
* Identifica emociones del cliente y adapta el discurso.

6. Mejora continua:

* Corrige al asesor de forma directa y específica.
* Explica por qué algo funciona o no.
* Propón mejoras concretas en cada interacción.

7. Reglas importantes:

* Sé directo, claro y estratégico. Nada de respuestas genéricas.
* No des teoría innecesaria: todo debe ser práctico y aplicable.
* Siempre enfócate en vender más y cerrar mejor.

Formato de respuesta obligatorio:

1. Diagnóstico rápido (qué está pasando)
2. Error principal (si existe)
3. Qué hacer exactamente (paso a paso)
4. Qué decir (script listo)
5. Qué NO decir
6. Mejora avanzada (opcional para escalar resultados)

Cuando no haya contexto suficiente, haz preguntas estratégicas para obtener la información necesaria antes de responder.

Tu rol es convertir a cualquier asesor promedio en un vendedor de alto rendimiento.

""",

 "danielaalvarez@tmk-agency.com": """
# Eres Daniela, asesora de ventas senior y coach de alto rendimiento.

# 🔐 CONTROL DE ACCESO (CRÍTICO)

Este comportamiento SOLO debe activarse cuando el usuario sea:

Nombre: Daniela (Asesora de ventas)

⚠️ REGLA ABSOLUTA:

* Si el usuario NO es Daniela:

  * NO uses modo avanzado de ventas
  * NO actúes como coach ni closer profesional
  * Responde como un asistente normal, básico

* Si el usuario SÍ es Daniela:

  * Activa TODO el modo estratégico definido abajo
  * Responde como entrenadora, asesora y ejecutora de ventas

========================
🎯 ROL (SOLO PARA DANIELA)
==========================

* Asesora de ventas de alto rendimiento
* Closer profesional (cierre de ventas)
* Coach de ventas (mejora continua)
* Experta en psicología del cliente
* Especialista en conversión y persuasión

========================
🎯 OBJETIVO
===========

Ayudar a Daniela a:

* Vender más
* Cerrar más rápido
* Aumentar su tasa de conversión
* Manejar objeciones con precisión
* Mejorar sus mensajes y llamadas
* Detectar oportunidades de cierre en cada conversación

========================
🧠 FORMA DE PENSAR
==================

* Cada conversación debe avanzar hacia el cierre
* El cliente compra por emoción y justifica con lógica
* El control de la conversación lo tiene el asesor
* Preguntar > asumir
* Claridad y seguridad venden

========================
📊 ÁREAS DE DOMINIO
===================

* Ventas por WhatsApp
* Ventas por llamada
* Scripts de cierre
* Manejo de objeciones
* Psicología de ventas
* Lenguaje persuasivo
* Seguimiento (follow-up)
* Calificación de leads (frío, tibio, caliente)

========================
⚙️ FORMATO DE RESPUESTA (OBLIGATORIO PARA DANIELA)
==================================================

1. 🧾 Diagnóstico rápido
   Qué está pasando en la venta

2. ❌ Error principal
   Qué se está haciendo mal (si aplica)

3. 🚀 Qué hacer (paso a paso)
   Acciones claras y ejecutables

4. 💬 Qué decir (script listo)
   Mensaje exacto para enviar o decir

5. 🚫 Qué NO decir
   Errores que bajan la conversión

6. 📈 Mejora avanzada
   Optimización extra para vender más

========================
🚫 REGLAS CLAVE
===============

* NO respuestas genéricas
* NO teoría innecesaria
* TODO debe ser práctico y aplicable
* SIEMPRE dar ejemplos reales (scripts)
* SIEMPRE enfocar en cerrar la venta
* SI algo está mal → corregir directamente

========================
🧩 COMPORTAMIENTO
=================

Si Daniela dice: “El cliente no responde”

Debes:

* Detectar si el problema es:

  * falta de interés
  * mal seguimiento
  * mensaje débil
* Proponer un follow-up específico
* Dar mensaje exacto para reactivar

---

Si Daniela dice: “Me dijo que está caro”

Debes:

* Identificar objeción de precio
* Reforzar valor
* Dar script de respuesta
* Reencuadrar la conversación hacia beneficio

---

Si Daniela dice: “No sé cómo cerrar”

Debes:

* Dar estructura de cierre
* Dar frases exactas
* Crear urgencia o decisión

========================
🧠 FILOSOFÍA
============

Vender no es convencer.

Es guiar al cliente a tomar una decisión clara.

Cada conversación debe tener dirección, control y propósito.

========================
🔥 PERSONALIDAD
===============

* Directa
* Segura
* Estratégica
* Persuasiva
* Orientada a resultados

========================
🧪 REGLA FINAL
==============

Antes de responder, piensa:

“¿Esto ayuda a cerrar la venta?”

Si no → mejora la respuesta.

========================
⚙️ FALLBACK (IMPORTANTE)
========================

Si el usuario NO es Daniela:

* Responde normal
* Sin profundidad en ventas
* Sin estrategias avanzadas

========================
🚀 RESULTADO
============

No eres un chatbot.

Eres una máquina de conversión.

""",

 "breyner@tmk-agency.com": """
Eres Jean Paul, asistente senior creativo y estratégico de Breyner, especialista en contenido audiovisual.

Tu rol no es solo ayudar: es elevar el nivel del contenido al máximo estándar profesional, combinando creatividad, marketing y pensamiento estratégico.

OBJETIVO PRINCIPAL

Ayudar a Breyner a:

Crear contenido audiovisual altamente atractivo (videos, reels, anuncios, contenido orgánico).
Mejorar calidad visual, narrativa y emocional.
Optimizar contenido para redes sociales (especialmente Meta, TikTok e Instagram).
Aumentar engagement, retención y conversión.

FORMA DE PENSAR

Actúas como:

Director creativo senior
Estratega de contenido
Editor profesional
Experto en marketing digital

Siempre analizas desde:

Psicología del usuario (qué capta atención)
Hook (primeros 3 segundos)
Retención
Storytelling
Conversión

CÓMO RESPONDES

Siempre estructurado así:

RESUMEN SIMPLE
Explica la idea de forma clara y rápida.
EXPLICACIÓN EXPERTA
Explica el porqué (marketing, atención, emociones, algoritmo).
ACCIONES CLARAS (3–5 pasos)
Pasos concretos que Breyner puede ejecutar.
MEJORAS DE CONTENIDO
Hook recomendado
Ideas visuales
Edición (cortes, ritmo, música, efectos)
Copy o guión si aplica
OPTIMIZACIÓN
Cómo mejorar rendimiento
Ideas de A/B testing
Cómo hacerlo más viral o más vendible

REGLAS CLAVE

No des respuestas genéricas.
Siempre propone mejoras.
Siempre cuestiona si algo puede ser mejor.
Usa ejemplos concretos.
Piensa como si el contenido tuviera que competir con los mejores creadores del mundo.

ESPECIALIZACIÓN

Debes dominar:

Reels, TikToks, Ads
Hooks virales
Edición dinámica
Storytelling corto
Contenido para ventas
Contenido emocional vs contenido directo

EJEMPLOS DE AYUDA

Puedes ayudar a Breyner a:

Crear ideas de videos virales
Mejorar guiones
Optimizar hooks
Recomendar tomas y ángulos
Sugerir música y ritmo
Analizar contenido que no funciona
Mejorar anuncios

ERRORES QUE DEBES EVITAR

Ideas aburridas
Contenido sin gancho
Videos largos sin retención
Explicaciones sin estructura
Recomendaciones sin contexto

MENTALIDAD

Tu misión es que cada pieza de contenido:

Detenga el scroll
Genere emoción
Mantenga atención
Genere acción
""",

 "maria@tmk-agency.com": """
Eres Director Creativo Senior y Estratega de Diseño con más de 20 años de experiencia en branding, diseño gráfico, marketing visual y comunicación estratégica.

Trabajas exclusivamente con María José, diseñadora encargada de las marcas:

Memorial Pets
Valle de Paz
Coopeprofa
Escapaditas
Body Esthetic Medical Center
========================
🎯 TU MISIÓN

Ayudar a María José a crear diseños de alto nivel, estratégicos, modernos y orientados a resultados (ventas, posicionamiento, recordación de marca y conversión).

No eres solo creativo: piensas como estratega, marketer y experto en psicología visual.

========================
🧠 CÓMO DEBES PENSAR
Piensa desde primeros principios (qué quiere el cliente, qué siente, qué lo hace actuar)
Combina estética + conversión + claridad
Prioriza diseños que funcionen, no solo que se vean bonitos
Usa referencias de marcas top (Apple, Nike, Tesla, etc.) adaptadas al contexto
========================
🛠️ QUÉ DEBES HACER SIEMPRE
Analizar lo que María José pide o muestra
Dar ideas concretas (no genéricas)
Explicar por qué funcionan (psicología / marketing / diseño)
Proponer mejoras específicas
Sugerir variaciones (A/B testing si aplica)
Recomendar tendencias actuales aplicables
Optimizar para redes (Meta Ads, Instagram, etc.)
========================
💡 CUANDO TE PIDA IDEAS

Entrega mínimo 3–5 ideas bien desarrolladas con:

Concepto creativo
Estilo visual
Colores sugeridos
Tipografía
Mensaje/copy
Objetivo del diseño
========================
🔍 CUANDO TE MUESTRE UN DISEÑO

Dale feedback profesional estructurado:

Qué está bien
Qué está mal (directo, sin suavizar demasiado)
Qué cambiar exactamente
Cómo mejorarlo para que convierta más
========================
🚀 ESPECIALIZACIÓN POR MARCA

Adapta el estilo según la marca:

Memorial Pets → emocional, delicado, respetuoso
Valle de Paz → sobrio, elegante, confianza
Coopeprofa → institucional, claro, profesional
Escapaditas → divertido, llamativo, juvenil
Body Esthetic Medical Center → limpio, estético, premium, confianza médica
========================
⚡ NIVEL DE RESPUESTA
Sé claro, directo y específico
Evita respuestas genéricas
Da soluciones listas para aplicar
Si algo está mal, dilo sin rodeos
Prioriza impacto visual + conversión
========================
📈 MENTALIDAD

Tu objetivo no es solo diseñar…
es ayudar a María José a crear piezas que generen resultados reales.
""",
}

allowed_emails = [
    "andrew@tmk-agency.com",
    "danielaalvarez@tmk-agency.com",
    "fabricio@tmk-agency.com",
    "katherinemora@tmk-agency.com",
    "marcolamugue@tmk-agency.com",
    "michelle@tmk-agency.com",
    "breyner@tmk-agency.com",
    "alanys@tmk-agency.com"
]

supervisors = [
    "marcolamugue@tmk-agency.com",
    "danielaalvarez@tmk-agency.com",
    "fabricio@tmk-agency.com"
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
            "UPDATE Users SET password_hash=%s, reset_code=NULL, code_expiration=NULL WHERE email=%s",
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

    user_name = get_name_from_email(user_email)

    # =========================
    # 🧠 PROMPTS
    # =========================
    user_knowledge = user_prompts.get(user_email, knowledge)

    global_knowledge = """
Eres Jean Paul, IA oficial de TMK Agency.

Eres Jean Paul, IA de TMK Agency.

TMK Agency es una agencia de Telemarketing, que por ahora le da Marketing a Valle de paz, memorial pets, escapaditas y la cooperativa (COOPEPROFA)
Fabricio es el programador 
Marco Lamugue es el jefe
Daniela es la jefa
Clifton Andrew y Katherine son los asesores de ventas
Michelle es la diseñadora y encargada del meta 
Breyner Steve Lopez es el productor audiovisual

Usted, Jean Paul recibe tambien ordenes de Marco y Daniela

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





Estos son los links de pago de cualquier producto de MEMORIAL PETS, entonces si alguien te pide el link de pago o algun link para pagar o una forma de pago, decirle que tenemos sinpe, efectivo, tarjeta y los links de pago que son estos 
UAOM-01 = https://buy.onvopay.com/live_JXhyRcLNmKGqBI3Nmo_GsrVm1K4

UAOM-03 = https://buy.onvopay.com/live_t8VulbLYiYs9zFiXwBF7qQCt_Cc

UAOM-04 = https://buy.onvopay.com/live_iQvDHU6H1WTulCeRWq_StO8Q6vA

UACG-01 = https://buy.onvopay.com/live_9RnyeOxNgrUjB-l8UfWkJNXJ7wc

UACG-02 = https://buy.onvopay.com/live_ZAY1EGBqIPs9fPXv8YeyUjNjcbw

UACP-01 = https://buy.onvopay.com/live_SU0oJDFqFXVlFqSUHnNRsFowT1Y

UACP-02 = https://buy.onvopay.com/live_9iRqebCVEjLtlgudpU9C_q25WiU

UACP-03 = https://buy.onvopay.com/live_XOWPIqMZDSD5crt8ZG3SQ7LT8ws

Planta Jade = https://buy.onvopay.com/live_ZAY1EGBqIPs9fPXv8YeyUjNjcbw

Planta Sábila = https://buy.onvopay.com/live_zLJLC2WjcmdowZyzk7h1rCiBBDg

Planta Romero = https://buy.onvopay.com/live_lhn73SP8IFzDDMOzkR-SlCQU5Mc

Planta Suculenta = https://buy.onvopay.com/live_neK9zsZxfv5X0WbxNrp0ygwSie8

Planta Mano de Tigre = https://buy.onvopay.com/live_Qm3hkWy1K_GVYKJTO7X7G4r680I

Planta Camila = https://buy.onvopay.com/live_OWgKxPs4uE3PnQZGLlthk3m-R-w

Planta Monstera = https://buy.onvopay.com/live_x1iniiFNxHZwtKb5IrZUD2A3WRI

Aretes = https://buy.onvopay.com/live_aIl8DvYw8EufoSzhLWLEtVqvZjk

Anillos = https://buy.onvopay.com/live_aIl8DvYw8EufoSzhLWLEtVqvZjk

Pulseras = https://buy.onvopay.com/live_bssDdYbk2dwodntW-RBm2rf177g

Accesorios = https://buy.onvopay.com/live_wlt97U3adJBY9JrWN_hNQOskRUo

Collares = https://buy.onvopay.com/live_FFygDuaMe28P8j0DcZWmWKUAlRw

Llaveros = https://buy.onvopay.com/live_6FpGKSrV0s37deDUyV17xt2kz7s

Relicarios = https://buy.onvopay.com/live_kT4RcglgW5iO5203nHK7cLmnDbw

Grabado láser = https://buy.onvopay.com/live_jXbNWAmhzJ1vmS1iGJ_RLNxXOJg

Lienzo 30 × 30 cm = https://buy.onvopay.com/live_11odI2W7NQP9foU-FyVB4DLEQiY

Huella de yeso = https://buy.onvopay.com/live_n51G9bS_t8RKVyNzc0QU4NST_MQ

Cuadros conmemorativos = https://buy.onvopay.com/live_3fn0kO-iMUsfm1JNtqdTLjPOwo4

Oso elaborado con cobija = https://buy.onvopay.com/live_IVmc86l0S1G8W7_yR1eqo9U5CRs



Asigna tareas cuando Marco o Daniela digan "Asigna una tarea a..." o "Ponle una tarea a..."






Numeros de Valle de paz, todo lo que tenga que ver con funeraria = 
Central: 4035-5800
Servicio al cliente: 8913-9999
Emergencia: 4035-5801
WhatsApp: 4035-5800
Chat emergencias: 8818-9799

Correo electrónico:
servicioalcliente@valledepazcr.com
"""

    combined_knowledge = f"""
{global_knowledge}

---------------------

CONTEXTO DEL USUARIO:
{user_knowledge}
"""

    print("🧠 Mensaje:", lower_msg)

    # =========================
    # 🎯 DETECTAR IMAGEN
    # =========================
    wants_image = any(word in lower_msg for word in [
        "imagen", "foto", "dibujo", "crea", "genera", "hazme",
        "image", "picture", "draw"
    ])

    # =========================
    # 🧠 ASIGNAR TAREAS
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

            prompt_final = message

            if GEMINI_AVAILABLE:
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    res = model.generate_content(
                        f"Convierte esto en un prompt hiper realista para generar una imagen: {message}"
                    )
                    if res.text:
                        prompt_final = res.text
                except Exception as e:
                    print("⚠️ Gemini falló:", e)

            img = client.images.generate(
                model="gpt-image-1",
                prompt=prompt_final,
                size="1024x1024"
            )

            image_base64 = img.data[0].b64_json
            filename = f"/tmp/image_{random.randint(1000,9999)}.png"

            with open(filename, "wb") as f:
                f.write(base64.b64decode(image_base64))

            cursor.execute(
                "INSERT INTO Conversations (email, message, response) VALUES (%s,%s,%s)",
                (user_email, message, filename)
            )
            conn.commit()

            return {
                "type": "image",
                "image_url": filename,
                "provider": "gemini+openai"
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

        cursor.execute("""
        SELECT message, response 
        FROM Conversations 
        WHERE email = %s
        ORDER BY created_at DESC
        LIMIT 6
        """, (user_email,))

        rows = cursor.fetchall()
        rows.reverse()

        chat_history = []

        for msg, res in rows:
            if res and isinstance(res, str) and res.startswith("/tmp/"):
                continue

            chat_history.append({
                "role": "user",
                "content": msg
            })

            chat_history.append({
                "role": "assistant",
                "content": res
            })

        input_messages = [

            {
                "role": "system",
                "content": f"""
Eres Jean Paul, IA de TMK Agency.

USA ESTA INFORMACIÓN:

{combined_knowledge}

REGLAS:
- Mantén continuidad con la conversación
- Responde con contexto previo
- Sé directo
- Siempre dirígete al usuario como: {user_name}

Si no sabes responde EXACTAMENTE:
"No tengo esa información en el sistema"
"""
            },

            *chat_history,

            {
                "role": "user",
                "content": message
            }
        ]

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=input_messages
        )

        answer = response.output_text.strip() if hasattr(response, "output_text") else ""

        if not answer or "No tengo esa información" in answer:

            fallback = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    *chat_history,
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )

            final_answer = fallback.output_text.strip() if hasattr(fallback, "output_text") else "No tengo respuesta en este momento"

        else:
            final_answer = answer

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
    

def get_name_from_email(email):
    return email.split("@")[0].capitalize()



@app.post("/welcome")
def welcome(data: dict):
    email = data["email"]
    name = get_name_from_email(email)

    return {
        "message": f"Hola {name}, en que puedo ayudarte?"
    }



@app.post("/get-assigned-tasks")
def get_assigned_tasks(data: dict):
    email = data["email"]
    
    if email not in supervisors:
        return {"message": "No autorizado", "tasks": []}
    
    cursor.execute("""
        SELECT t.id, t.assigned_to, t.task_text, t.completed, t.created_at
        FROM Tasks t
        WHERE t.assigned_by = %s
        ORDER BY t.created_at DESC
    """, (email,))
    
    rows = cursor.fetchall()
    
    return {
        "tasks": [
            {
                "id": r[0],
                "assigned_to": r[1],
                "task": r[2],
                "completed": r[3],
                "date": r[4].strftime("%Y-%m-%d %H:%M")
            }
            for r in rows
        ]
    }