import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
import re
import base64
import zlib

class DrawioEnricher:
    def __init__(self):
        self.image_cache = {}
        self.gemini_model = None
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                model_info = genai.list_models()
                available_models = [m.name for m in model_info if 'generateContent' in m.supported_generation_methods]
                text_models = [m for m in available_models if "vision" not in m and "embedding" not in m and "aqa" not in m]
                text_models.sort(key=lambda x: (1 if 'flash' in x else (2 if 'pro' in x else 3)))
                
                if text_models:
                    self.gemini_model = genai.GenerativeModel(text_models[0])
            except:
                pass

    def clean_html(self, raw_html):
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext.strip()

    def process_xml(self, xml_string):
        if xml_string.startswith('<?xml'):
            xml_string = re.sub(r'<\?xml.*?\?>', '', xml_string, count=1).strip()
            
        root = ET.fromstring(xml_string)
        
        # 1. Descomprimir diagramas si vienen en formato cifrado/deflate (típico de draw.io guardado a mano)
        for diagram in root.findall('.//diagram'):
            if len(list(diagram)) == 0 and diagram.text and len(diagram.text.strip()) > 10:
                try:
                    b = base64.b64decode(diagram.text)
                    decompressed = urllib.parse.unquote(zlib.decompress(b, -15).decode('utf-8'))
                    model_root = ET.fromstring(decompressed)
                    diagram.text = ""
                    diagram.append(model_root)
                except Exception as e:
                    pass

        # 2. Encontrar todos los nodos con texto
        cells = root.findall('.//mxCell[@vertex="1"]')
        
        nodes_to_process = []
        concepts_to_fetch = set()
        
        for cell in cells:
            value = cell.get('value')
            if not value:
                continue
            
            clean_text = self.clean_html(value)
            
            # Evitar buscar imágenes para textos muy cortos o nodos estructurales
            if len(clean_text) > 3:
                nodes_to_process.append((cell, clean_text))
        
        # 3. Limitar a máximo 20 imágenes y agarrar intercalados si son muchos
        target_nodes = []
        if len(nodes_to_process) > 20:
            target_nodes = nodes_to_process[::2][:20]
        else:
            target_nodes = nodes_to_process
            
        for _, text in target_nodes:
            concepts_to_fetch.add(text)
            
        concepts_list = list(concepts_to_fetch)
        
        if not concepts_list:
            # Si no hay conceptos, devolver el XML de todos modos (quizás ya fue descomprimido)
            return ET.tostring(root, encoding='utf-8').decode('utf-8')
            
        # 4. Traducción en lote
        translations = {}
        if self.gemini_model:
            try:
                prompt = "Translate the following abstract concepts into single, concrete, highly visual physical object nouns in English for Wikipedia image searches. Return ONLY a valid JSON dictionary where keys are the exact concepts and values are the English nouns. No markdown.\n\n"
                prompt += json.dumps(concepts_list)
                response = self.gemini_model.generate_content(prompt)
                
                text = response.text.strip()
                if text.startswith("```json"): text = text[7:]
                if text.startswith("```"): text = text[3:]
                if text.endswith("```"): text = text[:-3]
                translations = json.loads(text.strip())
            except:
                pass
                
        # 5. Fetch concurrente en Wikipedia
        def fetch_wiki(concept):
            clean_query = translations.get(concept)
            if not clean_query:
                clean_query = " ".join(concept.split()[:2]).strip(":")
                
            if len(clean_query) > 50:
                clean_query = clean_query[:50]
                
            url = "https://commons.wikimedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"intitle:{clean_query} OR {clean_query}",
                "gsrnamespace": 6,
                "gsrlimit": 5,
                "prop": "imageinfo",
                "iiprop": "url"
            }
            
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
            
            try:
                req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode())
                    if 'query' in data and 'pages' in data['query']:
                        pages = data['query']['pages']
                        valid_exts = ('.jpg', '.jpeg', '.png', '.svg', '.gif')
                        for page_id in pages:
                            if 'imageinfo' in pages[page_id]:
                                img_url = pages[page_id]['imageinfo'][0]['url']
                                if img_url.lower().endswith(valid_exts):
                                    self.image_cache[concept] = img_url
                                    return
            except Exception:
                pass
            self.image_cache[concept] = None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(fetch_wiki, concepts_list)
            
        # 6. Inyectar imágenes al XML
        for cell, clean_text in target_nodes:
            img_url = self.image_cache.get(clean_text)
            if img_url:
                style = cell.get('style', '')
                
                # Evitar romper si ya tiene imagen explícita
                if 'shape=image' in style or 'image=' in style:
                    continue
                    
                # Remover propiedad shape original para reemplazarla por image
                new_style_parts = []
                parts = style.split(';')
                for p in parts:
                    if p.startswith('shape=') or not p:
                        continue 
                    new_style_parts.append(p)
                    
                new_style = ";".join(new_style_parts)
                # Formato drawio para imágenes con texto debajo
                new_style = f"shape=image;image={img_url};verticalLabelPosition=bottom;verticalAlign=top;" + new_style
                if not new_style.endswith(';'):
                    new_style += ';'
                    
                cell.set('style', new_style)
                
        return ET.tostring(root, encoding='utf-8').decode('utf-8')

def enriquecer_xml(xml_string):
    enricher = DrawioEnricher()
    return enricher.process_xml(xml_string)
