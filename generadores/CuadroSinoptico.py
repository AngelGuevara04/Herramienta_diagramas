import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# Configuración de diseño
PX_PER_CHAR = 7.0
LINE_H = 17
PADDING_V = 20
TOP_MARGIN = 40
LEFT_MARGIN = 40
SIBLING_GAP = 10
SPACE_LABEL_TO_BRACE = 5
SPACE_BRACE_TO_CONTENT = 5
BRACE_W = 14
TOP_MIN_LABEL_W = 100
MIN_LABEL_W = 10
MAX_LABEL_W = 250
MAX_ITEM_W = 250
BRACE_THICK = 1
LABEL_ONLY_MIN_H = 30

# Configuración de estilo
BRACE_STYLE = "rounded"
FONT_FAMILY = "Times New Roman"
FONT_COLOR = "#415D66"
BRACE_COLOR = "#4A4861"

def _new_id():
    _new_id.counter += 1
    return _new_id.counter
_new_id.counter = 1

def new_cell(parent, id_, value, style, vertex=True, edge=False, x=0, y=0, w=0, h=0):
    cell = ET.SubElement(parent, "mxCell", {
        "id": str(id_),
        "value": value if value is not None else "",
        "style": style,
        "vertex": "1" if vertex else "0",
        "edge": "1" if edge else "0",
        "parent": "1",
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(x),
        "y": str(y),
        "width": str(w),
        "height": str(h),
        "as": "geometry",
    })
    return cell

def _escape_drawio_value(text: str) -> str:
    s = str(text)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    return s

def add_text(parent, text, x, y, w, h, align="left", valign="middle"):
    style = f"text;html=1;whiteSpace=wrap;align={align};verticalAlign={valign};"
    if FONT_FAMILY:
        style += f"fontFamily={FONT_FAMILY};"
    if FONT_COLOR:
        style += f"fontColor={FONT_COLOR};"
    safe_text = _escape_drawio_value(text)
    return new_cell(parent, _new_id(), safe_text, style, x=x, y=y, w=w, h=h)

def _compose_brace_style(base_style: str, direction: str, stroke_width: int, stroke_color: str = None) -> str:
    if "html=1" not in base_style:
        base_style += ";html=1"
    if "whiteSpace=wrap" not in base_style:
        base_style += ";whiteSpace=wrap"
    parts = [
        p for p in base_style.strip(";").split(";")
        if p and not p.startswith("direction=") and not p.startswith("strokeWidth=") and not p.startswith("strokeColor=")
    ]
    parts += [f"direction={direction}", f"strokeWidth={stroke_width}"]
    if stroke_color:
        parts += [f"strokeColor={stroke_color}"]
    return ";".join(parts) + ";"

def add_brace_rounded(parent, x, y, w, h, direction="east"):
    base = "shape=curlyBracket;rounded=1;whiteSpace=wrap;html=1;"
    style = _compose_brace_style(base, direction=direction, stroke_width=BRACE_THICK, stroke_color=BRACE_COLOR)
    return new_cell(parent, _new_id(), "", style, x=x, y=y, w=w, h=h)

def add_brace(parent, x, y, w, h, direction="east"):
    return add_brace_rounded(parent, x, y, w, h, direction)

def text_width(text, min_w, max_w):
    est = int(len(text) * PX_PER_CHAR) + 18
    return min(max(min_w, est), max_w)

def items_width(items):
    if not items:
        return 200
    est = max(int(len(s) * PX_PER_CHAR) + 18 for s in items)
    return min(max(200, est), MAX_ITEM_W)

def estimate_item_lines(text, box_width):
    chars_per_line = max(10, int(box_width / PX_PER_CHAR))
    return max(1, math.ceil(len(text) / chars_per_line))

def list_block_height(items, box_width):
    if not items:
        return LABEL_ONLY_MIN_H + PADDING_V
    total = 0
    for s in items:
        total += estimate_item_lines(s, box_width) * LINE_H
    return max(LINE_H, total) + PADDING_V

def node_height(node):
    if isinstance(node, list):
        width = items_width(node)
        return list_block_height(node, width)
    elif isinstance(node, dict):
        h = 0
        first = True
        for _, child in node.items():
            ch = node_height(child)
            if not first:
                h += SIBLING_GAP
            h += ch
            first = False
        return h + 20
    else:
        return list_block_height([str(node)], items_width([str(node)]))

def render_node(root, label, node, x, y, level=1):
    min_w = TOP_MIN_LABEL_W if level == 0 else MIN_LABEL_W
    label_w = text_width(label, min_w=min_w, max_w=MAX_LABEL_W)

    content_h = node_height(node)
    brace_x = x + label_w + SPACE_LABEL_TO_BRACE
    brace_y = y

    draw_self_brace = not (isinstance(node, list) and len(node) == 0)
    if draw_self_brace:
        add_brace(root, brace_x, brace_y, BRACE_W, content_h, direction="east")

    label_h = 28 if level == 0 else 24
    label_y = brace_y + (content_h - label_h) / 2
    add_text(root, label, x, label_y, label_w, label_h)

    content_x = brace_x + (BRACE_W if draw_self_brace else 0) + SPACE_BRACE_TO_CONTENT
    current_y = brace_y + 10

    if isinstance(node, list):
        if len(node) == 0:
            return (content_x - x), content_h
        max_w = items_width(node)
        for s in node:
            lines = estimate_item_lines(s, max_w)
            add_text(root, "• " + s, content_x, current_y, max_w, lines * LINE_H)
            current_y += lines * LINE_H
        return (content_x - x) + max_w, content_h
    elif isinstance(node, dict):
        max_child_right = 0
        first = True
        for child_label, child_node in node.items():
            if not first:
                current_y += SIBLING_GAP
            w_child, h_child = render_node(
                root, child_label, child_node, content_x, current_y, level + 1
            )
            current_y += h_child
            max_child_right = max(max_child_right, w_child)
            first = False
        return max_child_right + (content_x - x), content_h
    else:
        w = items_width([str(node)])
        lines = estimate_item_lines(str(node), w)
        add_text(root, "• " + str(node), content_x, current_y, w, lines * LINE_H)
        return (content_x - x) + w, content_h

def generar_cuadro_sinoptico(chart_dict):
    _new_id.counter = 1
    
    mxfile = ET.Element(
        "mxfile",
        {
            "modified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent": "Web Generator",
            "version": "24.7.7",
        },
    )
    diagram = ET.SubElement(mxfile, "diagram", {"name": "Cuadro Sinóptico"})
    mxGraphModel = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1220",
            "dy": "730",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "2200",
            "pageHeight": "1400",
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(mxGraphModel, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    if chart_dict:
        # Render the first key-value pair as root
        render_node(root, list(chart_dict.keys())[0], list(chart_dict.values())[0], LEFT_MARGIN, TOP_MARGIN, level=0)

    ET.indent(mxfile, space="  ")
    xml_str = ET.tostring(mxfile, encoding="unicode", xml_declaration=False)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
