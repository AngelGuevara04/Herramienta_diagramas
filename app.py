import os
import ast
import io
import google.generativeai as genai
from flask import Flask, request, render_template, send_file, jsonify

from generadores.CuadroSinoptico import generar_cuadro_sinoptico
from generadores.MapaConceptual import generar_mapa_conceptual
from generadores.MapaMental import generar_mapa_mental

app = Flask(__name__)

# Configuración de Gemini
# Se recomienda usar variables de entorno en Render para esto.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

@app.route('/')
def index():
    return render_template('index.html', has_api_key=bool(GEMINI_API_KEY))

@app.route('/generar_manual', methods=['POST'])
def generar_manual():
    tipo = request.form.get('tipo')
    contenido = request.form.get('contenido')
    
    if not tipo or not contenido:
        return "Faltan datos", 400
        
    try:
        if tipo == 'cuadro_sinoptico':
            # Evaluamos el string como diccionario
            chart_dict = ast.literal_eval(contenido)
            xml_data = generar_cuadro_sinoptico(chart_dict)
            filename = 'cuadro_sinoptico.drawio'
            
        elif tipo == 'mapa_conceptual':
            # Texto directo
            xml_data = generar_mapa_conceptual(contenido)
            filename = 'mapa_conceptual.drawio'
            
        elif tipo == 'mapa_mental':
            # Evaluamos el string como diccionario
            chart_dict = ast.literal_eval(contenido)
            xml_data = generar_mapa_mental(chart_dict)
            filename = 'mapa_mental.drawio'
            
        else:
            return "Tipo no válido", 400
            
        mem = io.BytesIO()
        mem.write(xml_data.encode('utf-8'))
        mem.seek(0)
        
        return send_file(
            mem,
            mimetype='application/xml',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return f"Error al procesar: {str(e)}", 500

@app.route('/generar_ia', methods=['POST'])
def generar_ia():
    if not GEMINI_API_KEY:
        return jsonify({"error": "No hay API Key configurada"}), 500
        
    genai.configure(api_key=GEMINI_API_KEY)
    
    tipo = request.json.get('tipo')
    texto = request.json.get('texto')
    
    if not tipo or not texto:
        return jsonify({"error": "Faltan datos"}), 400
        
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if tipo == 'mapa_conceptual':
            prompt = f"""
            Convierte el siguiente texto en una estructura estricta para un mapa conceptual.
            Formato requerido:
            Concepto Principal
            --conector1--> Concepto Hijo 1
              --subconector--> Subconcepto 2.1
            
            Usa exclusivamente ese formato de indentación (2 espacios por nivel) y las flechas --conector-->.
            No agregues código markdown (como ```), solo texto plano.
            
            Texto a procesar:
            {texto}
            """
        else: # Cuadro sinoptico o Mapa mental (usan dict de Python)
            prompt = f"""
            Convierte el siguiente texto en un diccionario de Python estricto (JSON-like pero válido en Python).
            El diccionario debe representar un árbol jerárquico de los conceptos.
            
            Reglas:
            - Solo devuelve el diccionario, empezando por {{ y terminando por }}.
            - No uses markdown (sin ```python ni ```).
            - No escribas nada más antes ni después.
            - Las hojas finales deben tener como valor un diccionario vacío {{}} o una cadena.
            
            Texto a procesar:
            {texto}
            """
            
        response = model.generate_content(prompt)
        resultado = response.text.strip()
        
        # Limpiar posibles bloques markdown si la IA los pone a pesar de la instrucción
        if resultado.startswith("```"):
            lineas = resultado.split('\\n')
            if lineas[0].startswith("```"): lineas = lineas[1:]
            if lineas[-1].startswith("```"): lineas = lineas[:-1]
            resultado = "\\n".join(lineas)
            
        return jsonify({"resultado": resultado})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
