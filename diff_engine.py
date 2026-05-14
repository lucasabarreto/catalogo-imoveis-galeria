import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
REPORTS_DIR = Path(__file__).parent / "reports"

PREVIOUS_PATH = DATA_DIR / "previous_properties.json"
CURRENT_PATH = DATA_DIR / "current_properties.json"

TRACKED_FIELDS = ("price", "title", "description", "image_link")

CSV_COLUMNS = [
    "id", "title", "description", "availability", "condition", "price",
    "property_type", "listing_type", "city", "neighborhood", "state",
    "bedrooms", "bathrooms", "parking_spaces", "area", "link", "image_link",
]

UPDATED_CSV_COLUMNS = [
    "id", "field", "old_value", "new_value", "link",
]


def _prop_to_link(prop: dict) -> str:
    return prop.get("property_url", prop.get("link", ""))


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
        return {str(p["id"]): p for p in items if p.get("id")}
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning(f"Falha ao ler {path}, tratando como vazio")
        return {}


def _save_json(properties: List[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(properties, f, ensure_ascii=False, indent=2)


def _write_csv(rows: List[dict], columns: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = {}
            for col in columns:
                if col == "link":
                    out[col] = _prop_to_link(row)
                else:
                    out[col] = row.get(col, "")
            writer.writerow(out)


def rotate_snapshots(current_properties: List[dict]):
    if CURRENT_PATH.exists():
        content = CURRENT_PATH.read_text(encoding="utf-8")
        PREVIOUS_PATH.write_text(content, encoding="utf-8")
        logger.info(f"Snapshot anterior salvo em {PREVIOUS_PATH}")

    _save_json(current_properties, CURRENT_PATH)
    logger.info(f"Snapshot atual salvo em {CURRENT_PATH} ({len(current_properties)} imóveis)")


def compare_and_report(current_properties: List[dict]) -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    previous = _load_json(PREVIOUS_PATH)
    current = {str(p["id"]): p for p in current_properties if p.get("id")}

    prev_ids = set(previous.keys())
    curr_ids = set(current.keys())

    new_ids = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids
    kept_ids = curr_ids & prev_ids

    new_props = [current[pid] for pid in sorted(new_ids)]
    removed_props = [previous[pid] for pid in sorted(removed_ids)]

    updated_rows = []
    for pid in sorted(kept_ids):
        old = previous[pid]
        new = current[pid]
        for field in TRACKED_FIELDS:
            old_val = str(old.get(field, ""))
            new_val = str(new.get(field, ""))
            if old_val != new_val:
                updated_rows.append({
                    "id": pid,
                    "field": field,
                    "old_value": old_val,
                    "new_value": new_val,
                    "link": _prop_to_link(new),
                })

    updated_ids = {r["id"] for r in updated_rows}

    _write_csv(new_props, CSV_COLUMNS, REPORTS_DIR / "new_properties.csv")
    _write_csv(removed_props, CSV_COLUMNS, REPORTS_DIR / "removed_properties.csv")
    _write_csv(updated_rows, UPDATED_CSV_COLUMNS, REPORTS_DIR / "updated_properties.csv")

    stats = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "previous_total": len(prev_ids),
        "current_total": len(curr_ids),
        "new": len(new_ids),
        "removed": len(removed_ids),
        "kept": len(kept_ids),
        "updated": len(updated_ids),
        "update_changes": len(updated_rows),
    }

    summary = _build_summary(stats, new_props, removed_props, updated_rows)
    summary_path = REPORTS_DIR / "summary.txt"
    summary_path.write_text(summary, encoding="utf-8")

    logger.info(f"Relatório salvo em {REPORTS_DIR}/")
    logger.info(
        f"Comparação: {stats['new']} novos | {stats['removed']} removidos | "
        f"{stats['updated']} atualizados | {stats['kept']} mantidos"
    )

    return stats


def _build_summary(stats: dict, new_props: list, removed_props: list, updated_rows: list) -> str:
    lines = [
        "=" * 60,
        "RELATÓRIO DE ATUALIZAÇÃO DO CATÁLOGO",
        f"Data: {stats['timestamp']}",
        "=" * 60,
        "",
        f"Execução anterior:  {stats['previous_total']} imóveis",
        f"Execução atual:     {stats['current_total']} imóveis",
        "",
        f"Novos:              {stats['new']}",
        f"Removidos:          {stats['removed']}",
        f"Mantidos:           {stats['kept']}",
        f"Atualizados:        {stats['updated']} ({stats['update_changes']} campos alterados)",
        "",
    ]

    if stats["previous_total"] == 0:
        lines.append("(Primeira execução — sem dados anteriores para comparar)")
        lines.append("")

    if new_props:
        lines.append("-" * 40)
        lines.append(f"NOVOS IMÓVEIS ({len(new_props)})")
        lines.append("-" * 40)
        for p in new_props[:20]:
            lines.append(f"  [{p.get('id')}] {p.get('title', '')[:70]}")
        if len(new_props) > 20:
            lines.append(f"  ... e mais {len(new_props) - 20}")
        lines.append("")

    if removed_props:
        lines.append("-" * 40)
        lines.append(f"IMÓVEIS REMOVIDOS ({len(removed_props)})")
        lines.append("-" * 40)
        for p in removed_props[:20]:
            lines.append(f"  [{p.get('id')}] {p.get('title', '')[:70]}")
        if len(removed_props) > 20:
            lines.append(f"  ... e mais {len(removed_props) - 20}")
        lines.append("")

    if updated_rows:
        lines.append("-" * 40)
        lines.append(f"IMÓVEIS ATUALIZADOS ({stats['updated']} imóveis, {len(updated_rows)} alterações)")
        lines.append("-" * 40)
        for r in updated_rows[:30]:
            old_short = r["old_value"][:40]
            new_short = r["new_value"][:40]
            lines.append(f"  [{r['id']}] {r['field']}: {old_short} -> {new_short}")
        if len(updated_rows) > 30:
            lines.append(f"  ... e mais {len(updated_rows) - 30} alterações")
        lines.append("")

    lines.append("=" * 60)
    lines.append("Arquivos gerados:")
    lines.append("  reports/new_properties.csv")
    lines.append("  reports/removed_properties.csv")
    lines.append("  reports/updated_properties.csv")
    lines.append("  reports/summary.txt")
    lines.append("=" * 60)

    return "\n".join(lines)
