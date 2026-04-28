import os
from flask import Flask, jsonify, request
from mssql_python import connect
from flask_cors import CORS
import resend

app = Flask(__name__)
CORS(app)

def get_connection():
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "1433")

    if not server or not database or not username or not password:
        raise ValueError("Faltan credenciales de la base de datos en las variables de entorno.")

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
        "RESEND_API_KEY_EXISTS": bool(os.getenv("RESEND_API_KEY"))
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


@app.route("/enviar-alerta", methods=["POST"])
def enviar_alerta():
    print("🚀 Petición POST recibida en /enviar-alerta (vía Resend)", flush=True) 

    try:
        data = request.get_json()
        destino = data.get("to")
        asunto = data.get("subject", "Notificación")
        mensaje = data.get("message", "Mensaje desde Render")

        if not destino or not asunto or not mensaje:
            print("⚠️ Error: Faltan datos en el JSON", flush=True)
            return jsonify({
                "success": False,
                "message": "Faltan datos"
            }), 400

        # Validar variables de entorno de Resend
        resend_api_key = os.getenv("RESEND_API_KEY")
        if not resend_api_key:
            raise ValueError("La variable RESEND_API_KEY no está configurada en Render.")
        
        resend.api_key = resend_api_key
        from_email = os.getenv("MAIL_RESEND", "onboarding@resend.dev")

        print(f"📧 Intentando enviar correo a: {destino}...", flush=True)
        
        # Ejecutar el envío a través de la API de Resend
        respuesta = resend.Emails.send({
            "from": from_email,
            "to": destino,
            "subject": asunto,
            "html": f"<p>{mensaje}</p>"
        })
        
        print(f"✅ Correo enviado con éxito. ID de Resend: {respuesta.get('id')}", flush=True)
        
        return jsonify({
            "success": True,
            "message": "Correo enviado exitosamente"
        })

    except Exception as e:
        print(f"🔥🔥🔥 ERROR FATAL EN RESEND: {str(e)} 🔥🔥🔥", flush=True) 
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)