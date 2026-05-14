import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom
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

        # --- Campos obrigatórios Meta Home Listings ---
        ET.SubElement(listing, "home_listing_id").text = str(prop.get("id", ""))
        ET.SubElement(listing, "name").text = prop.get("title", "")
        ET.SubElement(listing, "availability").text = _meta_availability(prop.get("listing_type", ""))
        ET.SubElement(listing, "description").text = prop.get("description", "")
        ET.SubElement(listing, "price").text = _meta_price(prop.get("price", ""))
        ET.SubElement(listing, "listing_type").text = "for_rent_by_agent"
        ET.SubElement(listing, "property_type").text = _meta_property_type(prop.get("property_type", ""))
        ET.SubElement(listing, "link").text = prop.get("property_url", "")

        image = ET.SubElement(listing, "image")
        ET.SubElement(image, "url").text = prop.get("image_link", "")

        # --- Localização ---
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

        # --- Imagens adicionais ---
        additional = prop.get("additional_images", "")
        if additional:
            imgs = [img.strip() for img in additional.split(",") if img.strip()]
            for img_url in imgs[:20]:
                ai = ET.SubElement(listing, "additional_image")
                ET.SubElement(ai, "url").text = img_url

        count += 1

    rough = ET.tostring(root, encoding="unicode", xml_declaration=False)
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8")

    with open(path, "wb") as f:
        f.write(pretty)

    logger.info(f"XML gerado: {path} ({count} imóveis)")
    return count


def save_partial(properties: List[dict], output_dir: str):
    if not properties:
        return
    csv_path = str(Path(output_dir) / "output_partial.csv")
    generate_csv(properties, csv_path)
    logger.info(f"Progresso parcial salvo: {len(properties)} imóveis")
