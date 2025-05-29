from flask import Flask, request, jsonify, send_from_directory
import os
import json
import pdfplumber
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

DATA_DIR = 'data'
TABLAS_DIR = os.path.join(DATA_DIR, 'tablas')
CLIENTES_FILE = os.path.join(DATA_DIR, 'clientes.json')
ARCHIVOS_FILE = os.path.join(DATA_DIR, 'archivos.json')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(TABLAS_DIR, exist_ok=True)
if not os.path.exists(CLIENTES_FILE):
    with open(CLIENTES_FILE, 'w') as f:
        json.dump([], f)
if not os.path.exists(ARCHIVOS_FILE):
    with open(ARCHIVOS_FILE, 'w') as f:
        json.dump({}, f)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def cargar_json(ruta):
    if not os.path.exists(ruta):
        return [] if 'clientes' in ruta else {}
    try:
        with open(ruta, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, (list, dict)) else []
    except:
        return [] if 'clientes' in ruta else {}

def guardar_json(ruta, datos):
    with open(ruta, 'w') as f:
        json.dump(datos, f, indent=2)

@app.route('/')
def serve_index():
    return send_from_directory('templates', 'index.html')

@app.route('/cliente.html')
def serve_cliente():
    return send_from_directory('templates', 'cliente.html')

@app.route('/clientes', methods=['GET', 'POST', 'PUT'])
def clientes_route():
    if request.method == 'GET':
        return jsonify(cargar_json(CLIENTES_FILE))
    elif request.method == 'POST':
        data = request.json
        clientes = cargar_json(CLIENTES_FILE)
        if any(c['id'] == data['id'] for c in clientes):
            return jsonify({'error': 'Cliente ya existe'}), 400
        clientes.append(data)
        guardar_json(CLIENTES_FILE, clientes)
        return jsonify({'status': 'ok'})
    elif request.method == 'PUT':
        data = request.json
        if isinstance(data, list):
            guardar_json(CLIENTES_FILE, data)
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'Formato inválido'}), 400

@app.route('/guardar_tabla/<cliente_id>', methods=['POST'])
def guardar_tabla(cliente_id):
    data = request.json
    ruta = os.path.join(TABLAS_DIR, f'{cliente_id}.json')
    guardar_json(ruta, data)
    return jsonify({'status': 'ok'})

@app.route('/leer_tabla/<cliente_id>', methods=['GET'])
def leer_tabla(cliente_id):
    ruta = os.path.join(TABLAS_DIR, f'{cliente_id}.json')
    if not os.path.exists(ruta):
        return jsonify({})
    return jsonify(cargar_json(ruta))

@app.route('/subir_pdf/<cliente_id>', methods=['POST'])
def subir_pdf(cliente_id):
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    if archivo and allowed_file(archivo.filename):
        filename = secure_filename(f"{cliente_id}.pdf")
        ruta = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(ruta)
        archivos = cargar_json(ARCHIVOS_FILE)
        archivos[cliente_id] = archivo.filename
        guardar_json(ARCHIVOS_FILE, archivos)
        datos = extraer_tabla_pdf(ruta)
        return jsonify({'cliente_id': cliente_id, 'datos': datos})
    return jsonify({'error': 'Archivo no permitido'}), 400

@app.route('/obtener_tabla/<cliente_id>', methods=['GET'])
def obtener_tabla(cliente_id):
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], f"{cliente_id}.pdf")
    if not os.path.exists(ruta):
        return jsonify({'datos': []})  # para evitar fallo JS
    datos = extraer_tabla_pdf(ruta)
    return jsonify({'cliente_id': cliente_id, 'datos': datos})

def extraer_tabla_pdf(ruta_pdf):
    resultados = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for i, page in enumerate(pdf.pages):
            tabla = page.extract_table()
            if tabla:
                filas = tabla[1:] if i == 0 else tabla
                for fila in filas:
                    if not fila or len(fila) < 5:
                        continue
                    resultados.append({
                        "modelo": fila[2].strip(),
                        "color": fila[3].strip(),
                        "talla": fila[4].strip(),
                        "precio": fila[-2].strip()
                    })
    return resultados

if __name__ == '__main__':
    app.run(debug=True)
