from flask import Flask, request, jsonify, render_template
import os
import sqlite3
import pdfplumber
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar base de datos
def init_db():
    with sqlite3.connect('database.db') as con:
        c = con.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS clientes (
                        id TEXT PRIMARY KEY,
                        mayoreo TEXT
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS tablas (
                        cliente_id TEXT,
                        tipo TEXT,
                        modelo TEXT,
                        color TEXT,
                        qty INTEGER
                     )''')
        con.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cliente.html')
def cliente_html():
    return render_template('cliente.html')

@app.route('/clientes', methods=['GET', 'POST', 'PUT'])
def clientes():
    con = sqlite3.connect('database.db')
    c = con.cursor()

    if request.method == 'GET':
        clientes = c.execute('SELECT * FROM clientes').fetchall()
        return jsonify([{"id": row[0], "mayoreo": row[1]} for row in clientes])

    data = request.get_json()

    if request.method == 'POST':
        try:
            c.execute('INSERT INTO clientes (id, mayoreo) VALUES (?, ?)', (data['id'], data['mayoreo']))
            con.commit()
            return jsonify({"status": "ok"})
        except sqlite3.IntegrityError:
            return jsonify({"error": "Cliente ya existe"}), 400

    if request.method == 'PUT':
        c.execute('DELETE FROM clientes')
        for cli in data:
            c.execute('INSERT INTO clientes (id, mayoreo) VALUES (?, ?)', (cli['id'], cli['mayoreo']))
        con.commit()
        return jsonify({"status": "ok"})

@app.route('/guardar_tabla/<cliente_id>', methods=['POST'])
def guardar_tabla(cliente_id):
    data = request.get_json()
    con = sqlite3.connect('database.db')
    c = con.cursor()

    c.execute('DELETE FROM tablas WHERE cliente_id = ?', (cliente_id,))
    for tipo in ['activos', 'seleccionados']:
        for item in data.get(tipo, []):
            c.execute('INSERT INTO tablas (cliente_id, tipo, modelo, color, qty) VALUES (?, ?, ?, ?, ?)',
                      (cliente_id, tipo, item['modelo'], item['color'], item['qty']))
    con.commit()
    return jsonify({"status": "ok"})

@app.route('/leer_tabla/<cliente_id>')
def leer_tabla(cliente_id):
    con = sqlite3.connect('database.db')
    c = con.cursor()
    datos = {"activos": [], "seleccionados": []}
    for tipo in ['activos', 'seleccionados']:
        rows = c.execute('SELECT modelo, color, qty FROM tablas WHERE cliente_id = ? AND tipo = ?', (cliente_id, tipo)).fetchall()
        datos[tipo] = [{"modelo": r[0], "color": r[1], "qty": r[2]} for r in rows]
    return jsonify(datos)

@app.route('/subir_pdf/<cliente_id>', methods=['POST'])
def subir_pdf(cliente_id):
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename.endswith('.pdf'):
        return jsonify({'error': 'Archivo no válido'}), 400

    nombre = secure_filename(f"{cliente_id}.pdf")
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre)
    archivo.save(ruta)

    datos = extraer_tabla_pdf(ruta)
    return jsonify({'cliente_id': cliente_id, 'datos': datos})

@app.route('/obtener_tabla/<cliente_id>')
def obtener_tabla(cliente_id):
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], f"{cliente_id}.pdf")
    if not os.path.exists(ruta):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    return jsonify({'cliente_id': cliente_id, 'datos': extraer_tabla_pdf(ruta)})

def extraer_tabla_pdf(ruta_pdf):
    resultados = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for i, page in enumerate(pdf.pages):
            tabla = page.extract_table()
            if tabla:
                filas = tabla[1:] if i == 0 else tabla
                for fila in filas:
                    if fila and len(fila) >= 5:
                        resultados.append({
                            "modelo": fila[2].strip(),
                            "color": fila[3].strip(),
                            "talla": fila[4].strip(),
                            "precio": fila[-2].strip()
                        })
    return resultados

if __name__ == '__main__':
    app.run(debug=True)
