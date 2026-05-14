import json
import re
import logging
from bs4 import BeautifulSoup
from typing import Optional

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "apartamentos": "apartment",
    "apartamento": "apartment",
    "casas": "house",
    "casa": "house",
    "sobrados": "house",
    "sobrado": "house",
    "comercial": "commercial",
    "comerciais": "commercial",
    "salas comerciais": "commercial",
    "sala comercial": "commercial",
    "lojas": "commercial",
    "loja": "commercial",
    "galpões": "commercial",
    "galpão": "commercial",
    "galpao": "commercial",
    "terrenos": "land",
    "terreno": "land",
    "lotes": "land",
    "lote": "land",
    "condomínios": "condo",
    "condomínio": "condo",
    "condominio": "condo",
    "condominios": "condo",
    "rural": "rural",
    "chácaras": "rural",
    "chácara": "rural",
    "chacara": "rural",
    "sítios": "rural",
    "sítio": "rural",
    "sitio": "rural",
    "fazendas": "rural",
    "fazenda": "rural",
    "flat": "apartment",
    "flats": "apartment",
    "kitnet": "apartment",
    "kitnets": "apartment",
    "studio": "apartment",
    "studios": "apartment",
    "coberturas": "apartment",
    "cobertura": "apartment",
    "padrão": "apartment",
    "padrao": "apartment",
}

IND_TYPE_MAP = {
    "S": "for_sale",
    "L": "for_rent",
    "A": "for_sale_and_rent",
    "T": "for_sale_and_rent",
}


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_price(value) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
        if v <= 0:
            return ""
        return f"{v:.0f} BRL"
    except (ValueError, TypeError):
        return ""


def parse_price_text(raw: Optional[str]) -> str:
    if not raw:
        return ""
    numbers = re.findall(r"[\d.,]+", str(raw))
    if not numbers:
        return ""
    price_str = numbers[0].replace(".", "").replace(",", ".")
    try:
        value = float(price_str)
        return f"{value:.0f} BRL"
    except ValueError:
        return ""


def normalize_property_type(category: Optional[str], subcategory: Optional[str] = None) -> str:
    if not category:
        return ""
    key = category.strip().lower()
    if key in CATEGORY_MAP:
        return CATEGORY_MAP[key]
    if subcategory:
        sub_key = subcategory.strip().lower()
        if sub_key in CATEGORY_MAP:
            return CATEGORY_MAP[sub_key]
    for pattern, value in CATEGORY_MAP.items():
        if pattern in key:
            return value
    return key


def _find_property_in_next_data(obj, depth=0):
    if depth > 12:
        return None
    if isinstance(obj, dict):
        if "idtProperty" in obj:
            return obj
        for v in obj.values():
            r = _find_property_in_next_data(v, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _find_property_in_next_data(item, depth + 1)
            if r:
                return r
    return None


def _extract_from_og_description(desc: str) -> dict:
    result = {}
    m = re.search(r"(\d+)\s*quarto", desc, re.IGNORECASE)
    if m:
        result["bedrooms"] = m.group(1)
    m = re.search(r"(\d+)\s*banheiro[s]?", desc, re.IGNORECASE)
    if m:
        result["bathrooms"] = m.group(1)
    if not result.get("bathrooms"):
        m = re.search(r"(\d+)\s*su[ií]te", desc, re.IGNORECASE)
        if m:
            result["bathrooms"] = m.group(1)
    m = re.search(r"(\d+)\s*(?:garagem|garagens|vaga)", desc, re.IGNORECASE)
    if m:
        result["parking_spaces"] = m.group(1)
    m = re.search(r"(\d+)\s*su[ií]te", desc, re.IGNORECASE)
    if m:
        result["suites"] = m.group(1)
    return result


def _extract_area_from_html(soup: BeautifulSoup) -> str:
    for el in soup.find_all(string=re.compile(r"\d+[.,]?\d*\s*m[²2]")):
        text = el.strip()
        m = re.search(r"([\d.,]+)\s*m[²2]", text)
        if m:
            area_str = m.group(1).replace(",", ".")
            try:
                return str(int(float(area_str)))
            except ValueError:
                pass
    return ""


def get_meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def parse_property_page(html: str, url: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    if title_tag:
        title_text = (title_tag.text or "").lower()
        if any(kw in title_text for kw in ["não encontrad", "404", "removido", "indisponível", "erro"]):
            logger.info(f"Página inválida: {url}")
            return None

    data = {
        "id": "",
        "title": "",
        "description": "",
        "availability": "",
        "condition": "",
        "property_type": "",
        "listing_type": "",
        "price": "",
        "neighborhood": "",
        "city": "",
        "state": "",
        "bedrooms": "",
        "bathrooms": "",
        "parking_spaces": "",
        "area": "",
        "condo_fee": "",
        "iptu": "",
        "image_link": "",
        "additional_images": "",
        "property_url": url,
        "updated_at": "",
    }

    # --- Try __NEXT_DATA__ first ---
    prop = None
    next_script = soup.find("script", id="__NEXT_DATA__")
    if next_script and next_script.string:
        try:
            next_data = json.loads(next_script.string)
            prop = _find_property_in_next_data(next_data)
        except (json.JSONDecodeError, TypeError):
            pass

    if prop:
        data["id"] = str(prop.get("idtProperty", ""))

        data["neighborhood"] = prop.get("namDistrict", "")
        data["city"] = prop.get("namCity", "")
        data["state"] = prop.get("namState", "")

        data["property_type"] = normalize_property_type(
            prop.get("namCategory", ""),
            prop.get("namSubCategory", ""),
        )

        ind_type = prop.get("indType", "")
        data["listing_type"] = IND_TYPE_MAP.get(ind_type, "")

        data["price"] = format_price(prop.get("valSales") or prop.get("valLocation"))
        data["condo_fee"] = format_price(prop.get("valCondominium"))
        data["iptu"] = format_price(prop.get("valIptu"))
        data["updated_at"] = prop.get("dtaUpdate", "")

        data["parking_spaces"] = str(prop.get("totalGarages", "")) if prop.get("totalGarages") else ""

        data["bedrooms"] = str(prop.get("prop_char_5", "")) if prop.get("prop_char_5") else ""

        # --- Photos ---
        photos_raw = prop.get("jsonPhotos", "")
        images = []
        if photos_raw:
            try:
                photos = json.loads(photos_raw) if isinstance(photos_raw, str) else photos_raw
                for p in photos:
                    if isinstance(p, dict):
                        img = p.get("urlPhoto", "")
                        if img:
                            images.append(img)
            except (json.JSONDecodeError, TypeError):
                pass

    # --- Fallback/complement with meta tags ---
    if not data["id"]:
        data["id"] = get_meta(soup, "og:propertyRef")
    if not data["id"]:
        match = re.search(r"/(\d+)/?$", url)
        if match:
            data["id"] = match.group(1)

    og_title = get_meta(soup, "og:title")
    data["title"] = clean_text(og_title)
    if not data["title"]:
        h1 = soup.find("h1")
        if h1:
            data["title"] = clean_text(h1.get_text())

    og_desc = get_meta(soup, "og:description") or get_meta(soup, "description")
    data["description"] = clean_text(og_desc)

    if not data["neighborhood"]:
        data["neighborhood"] = get_meta(soup, "og:neighborhood")
    if not data["city"]:
        data["city"] = get_meta(soup, "og:locality")
    if not data["state"]:
        data["state"] = get_meta(soup, "og:state")

    # --- Extract features from og:description ---
    if og_desc:
        features = _extract_from_og_description(og_desc)
        if not data["bedrooms"]:
            data["bedrooms"] = features.get("bedrooms", "")
        if not data["bathrooms"]:
            data["bathrooms"] = features.get("bathrooms", "")
        if not data["parking_spaces"]:
            data["parking_spaces"] = features.get("parking_spaces", "")

    # --- Area from HTML ---
    if not data["area"]:
        data["area"] = _extract_area_from_html(soup)

    # --- Images fallback ---
    if not prop or not images:
        images = []
        og_image = get_meta(soup, "og:image")
        if og_image:
            images.append(og_image)

    images = [img if img.startswith("http") else f"https://galeriaimobiliaria.com.br{img}" for img in images if img]
    if images:
        data["image_link"] = images[0]
        data["additional_images"] = ",".join(images[1:]) if len(images) > 1 else ""

    # --- Listing type fallback ---
    if not data["listing_type"]:
        title_lower = data["title"].lower()
        if "locação" in title_lower or "aluguel" in title_lower or "alugar" in title_lower:
            data["listing_type"] = "for_rent"
        elif "venda" in title_lower or "comprar" in title_lower:
            data["listing_type"] = "for_sale"
        if "/aluguel" in url or "/locacao" in url or "/alugar" in url:
            data["listing_type"] = "for_rent"
        elif "/venda" in url or "/comprar" in url:
            data["listing_type"] = "for_sale"
        elif "/venda-e-locacao" in url:
            data["listing_type"] = "for_sale_and_rent"

    # --- Property type fallback ---
    if not data["property_type"] and data["title"]:
        data["property_type"] = normalize_property_type(data["title"])
    if not data["property_type"]:
        segments = url.split("/")
        for seg in segments:
            pt = normalize_property_type(seg)
            if pt:
                data["property_type"] = pt
                break

    # --- Availability ---
    if data["listing_type"] == "for_rent":
        data["availability"] = "for rent"
    elif data["listing_type"] == "for_sale":
        data["availability"] = "for sale"
    elif data["listing_type"] == "for_sale_and_rent":
        data["availability"] = "for sale and rent"
    else:
        data["availability"] = "available"

    if not data["id"] and not data["title"]:
        logger.warning(f"Dados insuficientes: {url}")
        return None

    return data
