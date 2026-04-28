import os
import smtplib  # <-- ¡ESTA ES LA LÍNEA QUE FALTABA!
from email.message import EmailMessage
from flask import Flask, jsonify, request
from mssql_python import connect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_connection():
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "1433")

    if not server:
        raise ValueError("Falta DB_SERVER")
    if not database:
        raise ValueError("Falta DB_DATABASE")
    if not username:
        raise ValueError("Falta DB_USERNAME")
    if not password:
        raise ValueError("Falta DB_PASSWORD")

    connection_string = (
        f"Server=tcp:{server},{port};"
        f"Database={database};"
        f"Uid={username};"
        f"Pwd={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Authentication=SqlPassword;"
    )

    return connect(connection_string)


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "API Flask funcionando correctamente en Render"
    })


@app.route("/debug-env")
def debug_env():
    return jsonify({
        "DB_SERVER": os.getenv("DB_SERVER"),
        "DB_DATABASE": os.getenv("DB_DATABASE"),
        "DB_USERNAME": os.getenv("DB_USERNAME"),
        "DB_PASSWORD_EXISTS": bool(os.getenv("DB_PASSWORD")),
        "DB_PORT": os.getenv("DB_PORT"),
    })


@app.route("/test-db")
def test_db():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT GETDATE() AS fecha_servidor")
        row = cursor.fetchone()

        return jsonify({
            "success": True,
            "message": "Conexión a SQL Server exitosa",
            "server_date": str(row[0])
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al conectar con SQL Server",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/productos")
def listar_productos():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 20 id, nombre, precio, UrlImagen, stock
            FROM productos
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "nombre": row[1],
                "precio": float(row[2]) if row[2] is not None else None,
                "UrlImagen": row[3],
                "stock": row[4]
            })

        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al consultar productos",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def enviar_correo_alerta(asunto, mensaje, destino):
    # 1. Consumir las variables de entorno de Render
    remitente = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")

    if not remitente or not password:
        raise ValueError("Las credenciales de correo (EMAIL_USER o EMAIL_PASSWORD) no están configuradas en Render.")

    # 2. Construir la estructura del correo
    msg = EmailMessage()
    msg.set_content(mensaje)
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destino

    # 3. Configurar el servidor SMTP (Ejemplo para Gmail)
    # Si usas Outlook/Hotmail, cambia el host a "smtp.office365.com"
    smtp_host = "smtp.gmail.com"
    smtp_port = 587

    # 4. Conectar, autenticar y enviar
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()  # Iniciar conexión segura
        server.login(remitente, password)
        server.send_message(msg)


@app.route("/enviar-alerta", methods=["POST"])
def enviar_alerta():
    # 1. Este print nos dirá si la petición siquiera llega a entrar aquí
    print("🚀 Petición POST recibida en /enviar-alerta", flush=True) 

    try:
        data = request.get_json()
        destino = data.get("to")
        asunto = data.get("subject")
        mensaje = data.get("message")

        if not destino or not asunto or not mensaje:
            print("⚠️ Error: Faltan datos en el JSON", flush=True)
            return jsonify({
                "success": False,
                "message": "Faltan datos"
            }), 400

        print(f"📧 Intentando enviar correo a: {destino}...", flush=True)
        enviar_correo_alerta(asunto, mensaje, destino)
        
        print("✅ Correo enviado con éxito", flush=True)
        return jsonify({
            "success": True,
            "message": "Correo enviado exitosamente"
        })

    except Exception as e:
        # 2. El flush=True obliga a Render a mostrar este error inmediatamente
        print(f"🔥🔥🔥 ERROR FATAL: {str(e)} 🔥🔥🔥", flush=True) 
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)