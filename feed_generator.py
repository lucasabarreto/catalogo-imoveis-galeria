import csv
import xml.etree.ElementTree as ET
import logging
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "id", "title", "description", "availability", "condition", "price",
    "property_type", "listing_type", "city", "neighborhood", "state",
    "bedrooms", "bathrooms", "parking_spaces", "area", "link", "image_link",
]

META_PROPERTY_TYPE_MAP = {
    "apartment": "apartment",
    "house": "house",
    "condo": "condo",
    "land": "land",
    "commercial": "other",
    "rural": "other",
}


def _meta_property_type(raw: str) -> str:
    return META_PROPERTY_TYPE_MAP.get(raw, "other")


def _meta_price(raw: str) -> str:
    if not raw:
        return "0 BRL"
    return raw


def _meta_availability(listing_type: str) -> str:
    if listing_type == "for_rent":
        return "for_rent"
    if listing_type == "for_sale":
        return "for_sale"
    return "for_rent"


def generate_csv(properties: List[dict], output_path: str) -> int:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for prop in properties:
            row = {}
            for col in CSV_COLUMNS:
                if col == "link":
                    row[col] = prop.get("property_url", "")
                else:
                    row[col] = prop.get(col, "")
            writer.writerow(row)
            count += 1

    logger.info(f"CSV gerado: {path} ({count} imóveis)")
    return count


def generate_xml(properties: List[dict], output_path: str) -> int:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("listings")
    count = 0

    for prop in properties:
        listing = ET.SubElement(root, "listing")

        # --- Campos obrigatórios Meta (nomes planos) ---
        ET.SubElement(listing, "id").text = str(prop.get("id", ""))
        ET.SubElement(listing, "home_listing_id").text = str(prop.get("id", ""))
        ET.SubElement(listing, "title").text = prop.get("title", "")
        ET.SubElement(listing, "name").text = prop.get("title", "")
        ET.SubElement(listing, "description").text = prop.get("description", "")
        ET.SubElement(listing, "availability").text = _meta_availability(prop.get("listing_type", ""))
        ET.SubElement(listing, "condition").text = "used"
        ET.SubElement(listing, "price").text = _meta_price(prop.get("price", ""))
        ET.SubElement(listing, "link").text = prop.get("property_url", "")
        ET.SubElement(listing, "image_link").text = prop.get("image_link", "")
        ET.SubElement(listing, "listing_type").text = "for_rent_by_agent"
        ET.SubElement(listing, "property_type").text = _meta_property_type(prop.get("property_type", ""))

        # --- Localização (campos planos) ---
        ET.SubElement(listing, "address").text = prop.get("neighborhood", "")
        ET.SubElement(listing, "city").text = prop.get("city", "")
        ET.SubElement(listing, "region").text = prop.get("state", "")
        ET.SubElement(listing, "country").text = "BR"
        ET.SubElement(listing, "neighborhood").text = prop.get("neighborhood", "")

        # --- Detalhes do imóvel ---
        ET.SubElement(listing, "num_beds").text = str(prop.get("bedrooms", ""))
        ET.SubElement(listing, "num_baths").text = str(prop.get("bathrooms", ""))
        ET.SubElement(listing, "num_units").text = str(prop.get("parking_spaces", ""))
        ET.SubElement(listing, "area_size").text = str(prop.get("area", ""))
        ET.SubElement(listing, "area_unit").text = "sq_m" if prop.get("area") else ""

        # --- Imagens adicionais (planas, separadas por vírgula) ---
        additional = prop.get("additional_images", "")
        if additional:
            imgs = [img.strip() for img in additional.split(",") if img.strip()]
            ET.SubElement(listing, "additional_image_link").text = ",".join(imgs[:20])

        count += 1

    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    with open(path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    logger.info(f"XML gerado: {path} ({count} imóveis)")
    return count


GOOGLE_ADS_COLUMNS = [
    "Listing ID", "Listing name", "Final URL", "Image URL", "City name",
    "Description", "Price", "Property type", "Listing type",
    "Contextual keywords", "Address", "Tracking template", "Custom parameter",
    "Final mobile URL", "Android app link", "iOS app link", "iOS app store ID",
    "Formatted price",
]

GOOGLE_PROPERTY_TYPE_MAP = {
    "apartment": "apartment",
    "house": "house",
    "condo": "apartment",
    "land": "land",
    "commercial": "commercial",
    "rural": "other",
}


def _google_property_type(raw: str) -> str:
    return GOOGLE_PROPERTY_TYPE_MAP.get(raw, "other")


def _google_description(prop: dict) -> str:
    parts = []
    pt = prop.get("property_type", "")
    pt_labels = {
        "apartment": "Apartamento",
        "house": "Casa",
        "commercial": "Comercial",
        "land": "Terreno",
        "condo": "Condomínio",
        "rural": "Rural",
    }
    parts.append(pt_labels.get(pt, pt.capitalize()))
    beds = prop.get("bedrooms", "")
    if beds:
        parts.append(f"{beds} quartos")
    neighborhood = prop.get("neighborhood", "")
    if neighborhood:
        parts.append(neighborhood.title())
    area = prop.get("area", "")
    if area:
        parts.append(f"{area}m²")
    city = prop.get("city", "")
    if city:
        parts.append(city.title())
    return " - ".join(parts)


def _google_keywords(prop: dict) -> str:
    kws = []
    pt = prop.get("property_type", "")
    pt_labels = {
        "apartment": "apartamento",
        "house": "casa",
        "commercial": "comercial",
        "land": "terreno",
        "condo": "condomínio",
        "rural": "rural",
    }
    if pt:
        kws.append(pt_labels.get(pt, pt))
    kws.append("locação")
    beds = prop.get("bedrooms", "")
    if beds:
        kws.append(f"{beds} quartos")
    neighborhood = prop.get("neighborhood", "")
    if neighborhood:
        kws.append(neighborhood.lower())
    city = prop.get("city", "")
    if city:
        kws.append(city.lower())
    return ";".join(kws)


def _google_address(prop: dict) -> str:
    parts = [
        prop.get("neighborhood", ""),
        prop.get("city", ""),
        prop.get("state", ""),
    ]
    return ", ".join(p for p in parts if p)


def _google_formatted_price(raw: str) -> str:
    if not raw:
        return ""
    try:
        value = float(raw.replace(" BRL", "").replace("BRL", "").strip())
        formatted = f"{value:,.0f}".replace(",", ".")
        return f"R$ {formatted}/mês"
    except (ValueError, TypeError):
        return ""


def generate_google_ads_csv(properties: List[dict], output_path: str) -> int:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GOOGLE_ADS_COLUMNS)
        writer.writeheader()
        for prop in properties:
            row = {
                "Listing ID": str(prop.get("id", "")),
                "Listing name": prop.get("title", ""),
                "Final URL": prop.get("property_url", ""),
                "Image URL": prop.get("image_link", ""),
                "City name": prop.get("city", ""),
                "Description": _google_description(prop),
                "Price": prop.get("price", ""),
                "Property type": _google_property_type(prop.get("property_type", "")),
                "Listing type": "rent",
                "Contextual keywords": _google_keywords(prop),
                "Address": _google_address(prop),
                "Tracking template": "",
                "Custom parameter": "",
                "Final mobile URL": "",
                "Android app link": "",
                "iOS app link": "",
                "iOS app store ID": "",
                "Formatted price": _google_formatted_price(prop.get("price", "")),
            }
            writer.writerow(row)
            count += 1

    logger.info(f"Google Ads CSV gerado: {path} ({count} imóveis)")
    return count


def save_partial(properties: List[dict], output_dir: str):
    if not properties:
        return
    csv_path = str(Path(output_dir) / "output_partial.csv")
    generate_csv(properties, csv_path)
    logger.info(f"Progresso parcial salvo: {len(properties)} imóveis")
