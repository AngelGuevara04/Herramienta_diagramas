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

AVAILABLE_MODELS = None

@app.route('/generar_ia', methods=['POST'])
def generar_ia():
    global AVAILABLE_MODELS
    
    if not GEMINI_API_KEY:
        return jsonify({"error": "No hay API Key configurada"}), 500
        
    genai.configure(api_key=GEMINI_API_KEY)
    
    tipo = request.json.get('tipo')
    texto = request.json.get('texto')
    
    if not tipo or not texto:
        return jsonify({"error": "Faltan datos"}), 400
        
    try:
        if tipo == 'mapa_conceptual':
            prompt = f"""
            Convierte el siguiente texto en una estructura estricta para un mapa conceptual.
            Formato requerido:
            Concepto Principal
            --conector1--> Concepto Hijo 1
              --subconector--> Subconcepto 2.1
            
            INSTRUCCIÓN ESPECIAL: TU TAREA ES EXPANDIR Y DESARROLLAR estos puntos. Si el usuario te da un tema y 5 subtemas, debes crear sub-subtemas y descripciones breves, logrando de 2 a 3 niveles de profundidad para que el diagrama quede rico en información pero muy conciso.
            
            Usa exclusivamente ese formato de indentación (2 espacios por nivel) y las flechas --conector-->.
            No agregues código markdown (como ```), solo texto plano.
            
            Texto a procesar:
            {texto}
            """
        else: # Cuadro sinoptico o Mapa mental (usan dict de Python)
            prompt = f"""
            Convierte el siguiente texto en un diccionario de Python estricto (JSON-like pero válido en Python).
            El diccionario debe representar un árbol jerárquico de los conceptos.
            
            INSTRUCCIÓN ESPECIAL: TU TAREA ES EXPANDIR Y DESARROLLAR estos puntos. Si el usuario te da un tema y 5 subtemas, debes crear sub-subtemas y ramas adicionales para cada uno, logrando 2 o 3 niveles de profundidad. Mantén los textos de los nodos cortos y directos.
            
            Reglas:
            - Solo devuelve el diccionario, empezando por {{ y terminando por }}.
            - No uses markdown (sin ```python ni ```).
            - No escribas nada más antes ni después.
            - Las hojas finales deben tener como valor un diccionario vacío {{}} o una cadena.
            
            Texto a procesar:
            {texto}
            """
            
        if AVAILABLE_MODELS is None:
            try:
                model_info = genai.list_models()
                AVAILABLE_MODELS = [m.name for m in model_info if 'generateContent' in m.supported_generation_methods]
            except Exception as e:
                return jsonify({"error": f"Error verificando tu API Key: {str(e)}"}), 500
            
        resultado = None
        errores = []
        working_model = None
        
        # Filtramos para usar solo los modelos de texto puros
        text_models = [m for m in AVAILABLE_MODELS if "vision" not in m and "embedding" not in m and "aqa" not in m]
        
        # Le damos prioridad a flash y pro
        text_models.sort(key=lambda x: (1 if 'flash' in x else (2 if 'pro' in x else 3)))
        
        for m_name in text_models:
            try:
                model = genai.GenerativeModel(m_name)
                response = model.generate_content(prompt)
                resultado = response.text.strip()
                working_model = m_name
                break
            except Exception as e:
                errores.append(f"{m_name}: {str(e)}")
                continue
                
        if not resultado:
            detalles = " | ".join(errores[:2])
            return jsonify({"error": f"No se pudo generar con ninguno de los modelos. Detalles: {detalles}"}), 500
        
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
