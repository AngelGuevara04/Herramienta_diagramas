import xml.etree.ElementTree as ET
from xml.dom import minidom

class MapaConceptualGenerator:
    def __init__(self):
        self.id_counter = 2
        self.node_width = 160
        self.node_height = 60
        self.vertical_spacing = 180
        self.horizontal_spacing = 350
        
    def _convert_dict_to_tree(self, node_dict, level=0):
        # We can accept a dict or a string. If string, we build it directly.
        pass
        
    def parse_content(self, text):
        lines = [line.rstrip() for line in text.split('\n') if line.strip()]
        if not lines:
            return {}
        root = {'concept': '', 'children': [], 'level': 0}
        stack = [root]
        
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            indent_count = len(line) - len(stripped)
            level = indent_count // 2
            
            if i == 0:
                root['concept'] = stripped
                continue
            
            if '--' in stripped and '-->' in stripped:
                parts = stripped.split('-->', 1)
                connector = parts[0].replace('--', '').strip()
                concept = parts[1].strip() if len(parts) > 1 else ''
            else:
                connector = ''
                concept = stripped.lstrip('-* ').strip()
            
            while len(stack) > level + 1:
                stack.pop()
            
            new_node = {
                'concept': concept,
                'connector': connector,
                'children': [],
                'level': level
            }
            
            parent = stack[-1]
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(new_node)
            
            stack.append(new_node)
        
        return root

    def create_connector_line(self, x1, y1, x2, y2, label, cells):
        line_id = self.id_counter
        self.id_counter += 1
        
        line_cell = ET.SubElement(cells, 'mxCell')
        line_cell.set('id', str(line_id))
        line_cell.set('value', label)
        line_cell.set('style', 'edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;fontSize=11;fontColor=#000000;labelBackgroundColor=#ffffff;labelBorderColor=#cccccc;spacingTop=2;spacingBottom=2;spacingLeft=4;spacingRight=4;')
        line_cell.set('edge', '1')
        line_cell.set('parent', '1')
        
        geometry = ET.SubElement(line_cell, 'mxGeometry')
        geometry.set('relative', '1')
        geometry.set('as', 'geometry')
        
        source = ET.SubElement(geometry, 'mxPoint')
        source.set('x', str(x1))
        source.set('y', str(y1))
        source.set('as', 'sourcePoint')
        
        target = ET.SubElement(geometry, 'mxPoint')
        target.set('x', str(x2))
        target.set('y', str(y2))
        target.set('as', 'targetPoint')
        
        return line_id
    
    def calculate_subtree_width(self, node):
        if not node.get('children'):
            return self.node_width
        children_widths = sum(self.calculate_subtree_width(child) for child in node['children'])
        total_spacing = (len(node['children']) - 1) * self.horizontal_spacing
        return max(self.node_width, children_widths + total_spacing)
    
    def process_node(self, node, x, y, cells, is_root=False):
        concept = node.get('concept', '')
        node_id = self.id_counter
        self.id_counter += 1
        
        colors = ['#dae8fc', '#d5e8d4', '#fff2cc', '#ffe6cc', '#f8cecc']
        strokes = ['#6c8ebf', '#82b366', '#d6b656', '#d79b00', '#b85450']
        level = node.get('level', 0)
        
        fill_color = colors[min(level, len(colors) - 1)]
        stroke_color = strokes[min(level, len(strokes) - 1)]
        font_size = 14 if is_root else 12
        
        cell = ET.SubElement(cells, 'mxCell')
        cell.set('id', str(node_id))
        cell.set('value', concept)
        cell.set('style', f'rounded=1;whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor={stroke_color};strokeWidth=2;fontSize={font_size};fontStyle=1;align=center;verticalAlign=middle;')
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
            child_y = y + self.vertical_spacing
            
            if num_children == 1:
                child = node['children'][0]
                child_x = x
                connector_label = child.get('connector', '')
                self.create_connector_line(
                    x + self.node_width // 2, 
                    y + self.node_height,
                    child_x + self.node_width // 2, 
                    child_y,
                    connector_label,
                    cells
                )
                self.process_node(child, child_x, child_y, cells, False)
            else:
                children_widths = [self.calculate_subtree_width(child) for child in node['children']]
                total_width = sum(children_widths) + (num_children - 1) * self.horizontal_spacing
                start_x = x + self.node_width // 2 - total_width // 2
                
                current_x = start_x
                for i, child in enumerate(node['children']):
                    child_width = children_widths[i]
                    child_x = current_x + child_width // 2 - self.node_width // 2
                    connector_label = child.get('connector', '')
                    self.create_connector_line(
                        x + self.node_width // 2,
                        y + self.node_height,
                        child_x + self.node_width // 2,
                        child_y,
                        connector_label,
                        cells
                    )
                    self.process_node(child, child_x, child_y, cells, False)
                    current_x += child_width + self.horizontal_spacing
    
    def generate_drawio_xml(self, structure):
        root = ET.Element('mxfile')
        root.set('version', '22.0.0')
        diagram = ET.SubElement(root, 'diagram')
        diagram.set('name', 'Mapa Conceptual')
        
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
        
        root_elem = ET.SubElement(model, 'root')
        cell0 = ET.SubElement(root_elem, 'mxCell')
        cell0.set('id', '0')
        cell1 = ET.SubElement(root_elem, 'mxCell')
        cell1.set('id', '1')
        cell1.set('parent', '0')
        
        if structure:
            tree_width = self.calculate_subtree_width(structure)
            start_x = max(100, (1169 - tree_width) // 2)
            start_y = 50
            self.process_node(structure, start_x, start_y, root_elem, True)
        
        xml_str = ET.tostring(root, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent='  ')

def generar_mapa_conceptual(texto):
    generator = MapaConceptualGenerator()
    structure = generator.parse_content(texto)
    return generator.generate_drawio_xml(structure)
