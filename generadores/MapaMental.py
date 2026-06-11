import math
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse
import json

class MapaMentalGenerator:
    def __init__(self):
        self.id_counter = 2
        self.node_width = 120
        self.node_height = 120
        self.radius_step = 250
        self.image_cache = {}
        
        # Configuramos Gemini de manera segura
        self.gemini_model = None
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Buscamos un modelo de texto válido dinámicamente
                model_info = genai.list_models()
                available_models = [m.name for m in model_info if 'generateContent' in m.supported_generation_methods]
                text_models = [m for m in available_models if "vision" not in m and "embedding" not in m and "aqa" not in m]
                text_models.sort(key=lambda x: (1 if 'flash' in x else (2 if 'pro' in x else 3)))
                
                if text_models:
                    self.gemini_model = genai.GenerativeModel(text_models[0])
            except:
                pass

    def get_search_query(self, concept):
        # Si tenemos IA, traducimos el concepto a un objeto visual concreto en inglés
        if self.gemini_model:
            try:
                prompt = f'Translate this abstract concept into a single, concrete, highly visual physical object noun in English for an image search. Concept: "{concept}". Just return the noun (1-2 words max), no quotes or punctuation.'
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
            except:
                pass
        
        # Si falla la IA, tomamos solo las primeras 2 palabras para tener más chance de encontrar algo
        words = concept.split()
        return " ".join(words[:2]).strip(":")

    def fetch_image_url(self, query):
        if query in self.image_cache:
            return self.image_cache[query]
            
        clean_query = self.get_search_query(query)
        if len(clean_query) > 50:
            clean_query = clean_query[:50]
            
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"intitle:{clean_query} OR {clean_query}",
            "gsrnamespace": 6,  # 6 es el namespace para Archivos/Imágenes en Wikipedia
            "gsrlimit": 1,
            "prop": "imageinfo",
            "iiprop": "url"
        }
        
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        
        try:
            req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                if 'query' in data and 'pages' in data['query']:
                    pages = data['query']['pages']
                    for page_id in pages:
                        if 'imageinfo' in pages[page_id]:
                            img_url = pages[page_id]['imageinfo'][0]['url']
                            self.image_cache[query] = img_url
                            return img_url
        except Exception as e:
            pass
            
        self.image_cache[query] = None
        return None

    def _convert_dict_to_tree(self, node_dict, level=0):
        result = []
        for i, (key, value) in enumerate(node_dict.items()):
            
            # Imágenes seguras en el tema principal y primer nivel.
            # En subtemas profundos, aplicamos imagen cada 3 cuadros para cumplir "cada 2 o 3 cuadros" y evitar timeout
            image_url = None
            if level <= 1 or (level > 1 and i % 3 == 0):
                image_url = self.fetch_image_url(str(key))
                
            node = {
                'concept': str(key),
                'children': [],
                'level': level,
                'image_url': image_url
            }
            if isinstance(value, dict):
                node['children'] = self._convert_dict_to_tree(value, level + 1)
            elif isinstance(value, list):
                for j, item in enumerate(value):
                    child_image = None
                    if (level + 1) <= 1 or ((level + 1) > 1 and j % 3 == 0):
                        child_image = self.fetch_image_url(str(item))
                    node['children'].append({
                        'concept': str(item),
                        'children': [],
                        'level': level + 1,
                        'image_url': child_image
                    })
            elif value:
                # Si es un valor simple hijo directo (raro en el dict generado por IA, pero posible)
                child_image = None
                if (level + 1) <= 1:
                    child_image = self.fetch_image_url(str(value))
                node['children'].append({
                    'concept': str(value),
                    'children': [],
                    'level': level + 1,
                    'image_url': child_image
                })
            result.append(node)
        return result

    def draw_node(self, cells, node, cx, cy):
        concept = node.get('concept', '')
        image_url = node.get('image_url')
        node_id = self.id_counter
        self.id_counter += 1
        
        if node.get('level', 0) == 0:
            fill_color = '#ffe6cc'
            stroke_color = '#d79b00'
        else:
            colors = ['#f5f5f5', '#dae8fc', '#d5e8d4', '#e1d5e7', '#f8cecc']
            strokes = ['#666666', '#6c8ebf', '#82b366', '#9673a6', '#b85450']
            lvl = node.get('level', 1) - 1
            fill_color = colors[lvl % len(colors)]
            stroke_color = strokes[lvl % len(strokes)]
        
        cell = ET.SubElement(cells, 'mxCell')
        cell.set('id', str(node_id))
        
        # Usamos shape=image si hay imagen, de lo contrario ellipse
        if image_url:
            style = f'shape=image;image={image_url};verticalLabelPosition=bottom;verticalAlign=top;align=center;fillColor={fill_color};strokeColor={stroke_color};'
            html_value = concept
        else:
            style = f'shape=ellipse;whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor={stroke_color};strokeWidth=2;align=center;verticalAlign=middle;'
            html_value = concept
            
        cell.set('style', style)
        cell.set('value', html_value)
        cell.set('vertex', '1')
        cell.set('parent', '1')
        
        geom = ET.SubElement(cell, 'mxGeometry')
        # Ajuste de tamaño
        w = self.node_width
        h = self.node_height
        is_root = node.get('level', 0) == 0
        if is_root:
            w += 40
            h += 40
            
        # Si es imagen, reducimos el área geométrica para la imagen
        if image_url:
            img_size = 90 if is_root else 60
            geom.set('width', str(img_size))
            geom.set('height', str(img_size))
            geom.set('x', str(cx - img_size//2))
            geom.set('y', str(cy - img_size//2))
        else:
            geom.set('x', str(cx - w//2))
            geom.set('y', str(cy - h//2))
            geom.set('width', str(w))
            geom.set('height', str(h))
            
        geom.set('as', 'geometry')
        
        return node_id, stroke_color

    def draw_connector(self, cells, source_id, target_id, stroke_color):
        line_id = self.id_counter
        self.id_counter += 1
        line_cell = ET.SubElement(cells, 'mxCell')
        line_cell.set('id', str(line_id))
        line_cell.set('style', f'edgeStyle=bezierEdgeStyle;rounded=1;html=1;strokeWidth=2;strokeColor={stroke_color};')
        line_cell.set('edge', '1')
        line_cell.set('parent', '1')
        line_cell.set('source', str(source_id))
        line_cell.set('target', str(target_id))
        
        line_geom = ET.SubElement(line_cell, 'mxGeometry')
        line_geom.set('relative', '1')
        line_geom.set('as', 'geometry')

    def process_radial_branch(self, node_list, center_x, center_y, cells, parent_id, angle_start, angle_end, current_radius):
        """ Distribuye los nodos dentro del sector circular definido por angle_start y angle_end """
        n = len(node_list)
        if n == 0: return
        
        # El ángulo total disponible para estos hermanos
        total_angle = angle_end - angle_start
        # Dividimos el sector en N sub-sectores iguales
        angle_step = total_angle / n
        
        for i, child in enumerate(node_list):
            # El sector para este hijo
            child_angle_start = angle_start + i * angle_step
            child_angle_end = child_angle_start + angle_step
            
            # El ángulo exacto donde se ubica es el medio de su sector
            mid_angle = (child_angle_start + child_angle_end) / 2
            
            # Calcular X e Y con trigonometría
            child_x = center_x + current_radius * math.cos(mid_angle)
            child_y = center_y + current_radius * math.sin(mid_angle)
            
            # Dibujar nodo
            child_id, s_color = self.draw_node(cells, child, child_x, child_y)
            
            # Dibujar conector al padre
            self.draw_connector(cells, parent_id, child_id, s_color)
            
            # Recursion para los nietos:
            # Usan el sector [child_angle_start, child_angle_end] y aumentan el radio
            if child.get('children'):
                # Dejamos un margen del 10% en los bordes del sector para que no choquen con ramas vecinas
                margin = angle_step * 0.1
                self.process_radial_branch(
                    child['children'], 
                    center_x, center_y, # El centro del universo sigue siendo el mismo para polar
                    cells, 
                    child_id, 
                    child_angle_start + margin, 
                    child_angle_end - margin, 
                    current_radius + self.radius_step
                )

    def generate_drawio_xml(self, dict_structure):
        self.id_counter = 2
        root_elem = ET.Element('mxfile')
        root_elem.set('version', '22.0.0')
        
        diagram = ET.SubElement(root_elem, 'diagram')
        diagram.set('name', 'Mapa Mental')
        
        model = ET.SubElement(diagram, 'mxGraphModel')
        model.set('dx', '2000')
        model.set('dy', '2000')
        model.set('grid', '1')
        model.set('gridSize', '10')
        model.set('guides', '1')
        model.set('tooltips', '1')
        model.set('connect', '1')
        model.set('arrows', '1')
        model.set('fold', '1')
        model.set('page', '0') # Infinito
        model.set('pageScale', '1')
        
        root_cell = ET.SubElement(model, 'root')
        cell0 = ET.SubElement(root_cell, 'mxCell')
        cell0.set('id', '0')
        cell1 = ET.SubElement(root_cell, 'mxCell')
        cell1.set('id', '1')
        cell1.set('parent', '0')
        
        tree = self._convert_dict_to_tree(dict_structure)
        if tree:
            root_node = tree[0]
            
            # Centro absoluto del sol
            center_x = 2000
            center_y = 2000
            
            root_id, _ = self.draw_node(root_cell, root_node, center_x, center_y)
            
            children = root_node.get('children', [])
            
            if children:
                # Todo el círculo: de 0 a 2*PI (360 grados)
                self.process_radial_branch(
                    children, 
                    center_x, center_y, 
                    root_cell, 
                    root_id, 
                    0, 2 * math.pi, 
                    self.radius_step
                )
            
        xml_str = ET.tostring(root_elem, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent='  ')

def generar_mapa_mental(chart_dict):
    generator = MapaMentalGenerator()
    return generator.generate_drawio_xml(chart_dict)
