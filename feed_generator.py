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

XML_FIELDS = [
    "id", "title", "description", "price", "property_type", "listing_type",
    "city", "neighborhood", "state", "bedrooms", "bathrooms", "parking_spaces",
    "area", "image_link", "additional_images", "link",
]


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
        for field in XML_FIELDS:
            el = ET.SubElement(listing, field)
            if field == "link":
                el.text = prop.get("property_url", "")
            else:
                el.text = str(prop.get(field, ""))
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
