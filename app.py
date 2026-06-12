import os
import ast
import json
from flask import Flask, request, render_template, jsonify
from io import BytesIO

from generadores.CuadroSinoptico import generar_cuadro_sinoptico
from generadores.MapaConceptual import generar_mapa_conceptual
from generadores.MapaMental import generar_mapa_mental

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generar_manual', methods=['POST'])
def generar_manual():
    tipo = request.json.get('tipo')
    contenido_str = request.json.get('json_str')
    
    if not tipo or not contenido_str:
        return jsonify({"error": "Faltan datos"}), 400
        
    xml_generado = None
    
    try:
        if tipo in ['mapa_mental', 'cuadro_sinoptico']:
            try:
                # Try JSON first
                estructura = json.loads(contenido_str)
            except Exception as e_json:
                try:
                    # Fallback to Python dictionary evaluation (supports comments and single quotes)
                    estructura = ast.literal_eval(contenido_str)
                except Exception as e_ast:
                    return jsonify({"error": f"Formato inválido. No es JSON válido ({str(e_json)}) ni diccionario Python válido ({str(e_ast)})"}), 400
                
            if tipo == 'mapa_mental':
                xml_generado = generar_mapa_mental(estructura)
            else:
                xml_generado = generar_cuadro_sinoptico(estructura)
                
        elif tipo == 'mapa_conceptual':
            xml_generado = generar_mapa_conceptual(contenido_str)
            
    except Exception as e:
        return jsonify({"error": f"Error al generar: {str(e)}"}), 500
        
    if xml_generado:
        xml_clean = xml_generado.strip()
        if xml_clean.startswith('<?xml'):
            xml_clean = xml_clean.split('?>', 1)[-1].strip()
        return jsonify({"xml": xml_clean})
        
    return jsonify({"error": "Tipo de diagrama no soportado"}), 400

@app.route('/buscar_imagen', methods=['POST'])
def buscar_imagen():
    concepto = request.json.get('concepto')
    if not concepto:
        return jsonify({"error": "Falta el concepto"}), 400
        
    from generadores.MapaMental import MapaMentalGenerator
    gen = MapaMentalGenerator()
    
    # We load image into cache by asking for prefetch of single concept
    gen.prefetch_images({concepto: {}}) 
    img_url = gen.image_cache.get(concepto)
    
    return jsonify({"image_url": img_url})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
