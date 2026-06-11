import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
import urllib.request
import urllib.parse
import json

class MapaMentalGenerator:
    def __init__(self):
        self.id_counter = 2
        self.node_width = 160
        self.node_height = 80
        self.vertical_spacing = 180
        self.horizontal_spacing = 200
    
    def fetch_image_url(self, query):
        """Fetches an image URL from Wikimedia Commons using the query text."""
        # Limpiar query
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
                            img_url = pages[page_id]['imageinfo'][0]['url']
                            return img_url
        except Exception as e:
            pass
        return None

    def _convert_dict_to_tree(self, node_dict, level=0):
        """Convierte un dict a un árbol de nodos internamente"""
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
        total_spacing = (len(node['children']) - 1) * 20
        return max(self.node_height, children_height + total_spacing)

    def process_node_horizontal(self, node, x, y, cells, is_root=False):
        concept = node.get('concept', '')
        image_url = node.get('image_url')
        node_id = self.id_counter
        self.id_counter += 1
        
        colors = ['#f5f5f5', '#dae8fc', '#d5e8d4', '#fff2cc', '#ffe6cc', '#f8cecc']
        strokes = ['#666666', '#6c8ebf', '#82b366', '#d6b656', '#d79b00', '#b85450']
        level = node.get('level', 0)
        
        fill_color = colors[min(level, len(colors) - 1)]
        stroke_color = strokes[min(level, len(strokes) - 1)]
        
        cell = ET.SubElement(cells, 'mxCell')
        cell.set('id', str(node_id))
        
        # HTML label to include image
        if image_url:
            html_value = f'<div style="text-align:center"><img src="{image_url}" width="40" height="40" style="border-radius:5px; margin-bottom:5px;"/><br><b>{concept}</b></div>'
        else:
            html_value = f'<div style="text-align:center"><b>{concept}</b></div>'
            
        cell.set('value', html_value)
        cell.set('style', f'rounded=1;whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor={stroke_color};strokeWidth=2;align=center;verticalAlign=middle;')
        cell.set('vertex', '1')
        cell.set('parent', '1')
        
        geometry = ET.SubElement(cell, 'mxGeometry')
        geometry.set('x', str(x))
        geometry.set('y', str(y))
        geometry.set('width', str(self.node_width))
        geometry.set('height', str(self.node_height))
        geometry.set('as', 'geometry')
        
        if node.get('children'):
            num_children = len(node['children'])
            child_x = x + self.horizontal_spacing
            
            children_heights = [self.calculate_subtree_height(child) for child in node['children']]
            total_height = sum(children_heights) + (num_children - 1) * 20
            
            start_y = y + self.node_height // 2 - total_height // 2
            current_y = start_y
            
            for i, child in enumerate(node['children']):
                child_height = children_heights[i]
                child_y = current_y + child_height // 2 - self.node_height // 2
                
                # Curvy line connector
                line_id = self.id_counter
                self.id_counter += 1
                line_cell = ET.SubElement(cells, 'mxCell')
                line_cell.set('id', str(line_id))
                line_cell.set('style', f'edgeStyle=bezierEdgeStyle;rounded=1;html=1;strokeWidth=2;strokeColor={stroke_color};')
                line_cell.set('edge', '1')
                line_cell.set('parent', '1')
                
                line_geom = ET.SubElement(line_cell, 'mxGeometry')
                line_geom.set('relative', '1')
                line_geom.set('as', 'geometry')
                
                source = ET.SubElement(line_geom, 'mxPoint')
                source.set('x', str(x + self.node_width))
                source.set('y', str(y + self.node_height // 2))
                source.set('as', 'sourcePoint')
                
                target = ET.SubElement(line_geom, 'mxPoint')
                target.set('x', str(child_x))
                target.set('y', str(child_y + self.node_height // 2))
                target.set('as', 'targetPoint')
                
                self.process_node_horizontal(child, child_x, child_y, cells, False)
                
                current_y += child_height + 20

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
            # Render starting at 50, 50
            # Root is usually the first element in the tree
            self.process_node_horizontal(tree[0], 50, 300, root_cell, True)
            
        xml_str = ET.tostring(root_elem, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent='  ')

def generar_mapa_mental(chart_dict):
    generator = MapaMentalGenerator()
    return generator.generate_drawio_xml(chart_dict)
