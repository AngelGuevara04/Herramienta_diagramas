import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.request
import urllib.parse
import json

class MapaMentalGenerator:
    def __init__(self):
        self.id_counter = 2
        self.node_width = 160
        self.node_height = 80
        self.horizontal_spacing = 220
        self.vertical_spacing = 20
    
    def fetch_image_url(self, query):
        clean_query = query.split(":")[0].strip()
        if len(clean_query) > 50:
            clean_query = clean_query[:50]
            
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"intitle:{clean_query} OR {clean_query}",
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
                            return pages[page_id]['imageinfo'][0]['url']
        except Exception as e:
            pass
        return None

    def _convert_dict_to_tree(self, node_dict, level=0):
        result = []
        for key, value in node_dict.items():
            node = {
                'concept': str(key),
                'children': [],
                'level': level,
                'image_url': self.fetch_image_url(str(key))
            }
            if isinstance(value, dict):
                node['children'] = self._convert_dict_to_tree(value, level + 1)
            elif isinstance(value, list):
                for item in value:
                    node['children'].append({
                        'concept': str(item),
                        'children': [],
                        'level': level + 1,
                        'image_url': self.fetch_image_url(str(item))
                    })
            elif value:
                node['children'].append({
                    'concept': str(value),
                    'children': [],
                    'level': level + 1,
                    'image_url': self.fetch_image_url(str(value))
                })
            result.append(node)
        return result

    def calculate_subtree_height(self, node):
        if not node.get('children'):
            return self.node_height
        children_height = sum(self.calculate_subtree_height(child) for child in node['children'])
        total_spacing = (len(node['children']) - 1) * self.vertical_spacing
        return max(self.node_height, children_height + total_spacing)

    def draw_node(self, cells, node, x, y):
        concept = node.get('concept', '')
        image_url = node.get('image_url')
        node_id = self.id_counter
        self.id_counter += 1
        
        # El centro tiene un color diferente
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
        
        if image_url:
            html_value = f'<div style="text-align:center"><img src="{image_url}" width="40" height="40" style="border-radius:5px; margin-bottom:5px;"/><br><b>{concept}</b></div>'
        else:
            html_value = f'<div style="text-align:center"><b>{concept}</b></div>'
            
        # Forma más elíptica o redondeada para los mapas mentales
        rounded_style = "rounded=1;arcSize=30;" if node.get('level',0) > 0 else "shape=ellipse;"
        
        cell.set('style', f'{rounded_style}whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor={stroke_color};strokeWidth=2;align=center;verticalAlign=middle;')
        cell.set('value', html_value)
        cell.set('vertex', '1')
        cell.set('parent', '1')
        
        geom = ET.SubElement(cell, 'mxGeometry')
        geom.set('x', str(x))
        geom.set('y', str(y))
        
        # El nodo central puede ser un poco más grande
        if node.get('level', 0) == 0:
            geom.set('width', str(self.node_width + 40))
            geom.set('height', str(self.node_height + 20))
        else:
            geom.set('width', str(self.node_width))
            geom.set('height', str(self.node_height))
        geom.set('as', 'geometry')
        
        return node_id, stroke_color

    def draw_connector(self, cells, source_id, target_id, sx, sy, tx, ty, stroke_color):
        line_id = self.id_counter
        self.id_counter += 1
        line_cell = ET.SubElement(cells, 'mxCell')
        line_cell.set('id', str(line_id))
        # Curvo como un mapa mental
        line_cell.set('style', f'edgeStyle=bezierEdgeStyle;rounded=1;html=1;strokeWidth=2;strokeColor={stroke_color};')
        line_cell.set('edge', '1')
        line_cell.set('parent', '1')
        line_cell.set('source', str(source_id))
        line_cell.set('target', str(target_id))
        
        line_geom = ET.SubElement(line_cell, 'mxGeometry')
        line_geom.set('relative', '1')
        line_geom.set('as', 'geometry')

    def process_branch(self, children_list, start_x, center_y, cells, parent_id, direction=1):
        """ direction: 1 para crecer a la derecha, -1 para crecer a la izquierda """
        if not children_list:
            return
            
        children_heights = [self.calculate_subtree_height(child) for child in children_list]
        total_height = sum(children_heights) + (len(children_list) - 1) * self.vertical_spacing
        
        current_y = center_y - total_height // 2
        
        for i, child in enumerate(children_list):
            child_height = children_heights[i]
            child_y = current_y + child_height // 2 - self.node_height // 2
            
            # Dibujar nodo
            child_id, s_color = self.draw_node(cells, child, start_x, child_y)
            
            # Dibujar conector desde padre
            self.draw_connector(cells, parent_id, child_id, 0, 0, 0, 0, s_color)
            
            # Recursion para los nietos, misma dirección
            if child.get('children'):
                next_x = start_x + (self.horizontal_spacing * direction)
                self.process_branch(child['children'], next_x, child_y + self.node_height//2, cells, child_id, direction)
                
            current_y += child_height + self.vertical_spacing

    def generate_drawio_xml(self, dict_structure):
        self.id_counter = 2
        root_elem = ET.Element('mxfile')
        root_elem.set('version', '22.0.0')
        
        diagram = ET.SubElement(root_elem, 'diagram')
        diagram.set('name', 'Mapa Mental')
        
        model = ET.SubElement(diagram, 'mxGraphModel')
        model.set('dx', '1422')
        model.set('dy', '794')
        model.set('grid', '1')
        model.set('gridSize', '10')
        model.set('guides', '1')
        model.set('tooltips', '1')
        model.set('connect', '1')
        model.set('arrows', '1')
        model.set('fold', '1')
        model.set('page', '1')
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
            
            # Centro del sol
            center_x = 800
            center_y = 600
            
            root_id, _ = self.draw_node(root_cell, root_node, center_x, center_y)
            
            children = root_node.get('children', [])
            
            # Dividir los hijos mitad a la derecha y mitad a la izquierda
            mid = (len(children) + 1) // 2
            right_children = children[:mid]
            left_children = children[mid:]
            
            # Procesar derecha
            if right_children:
                self.process_branch(
                    right_children, 
                    center_x + self.node_width + 40 + self.horizontal_spacing - 100, 
                    center_y + self.node_height // 2, 
                    root_cell, 
                    root_id, 
                    direction=1
                )
                
            # Procesar izquierda
            if left_children:
                self.process_branch(
                    left_children, 
                    center_x - self.horizontal_spacing, 
                    center_y + self.node_height // 2, 
                    root_cell, 
                    root_id, 
                    direction=-1
                )
            
        xml_str = ET.tostring(root_elem, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent='  ')

def generar_mapa_mental(chart_dict):
    generator = MapaMentalGenerator()
    return generator.generate_drawio_xml(chart_dict)
