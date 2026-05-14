import requests
import time
import logging
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from tqdm import tqdm

from parser import parse_property_page
from feed_generator import generate_csv, generate_xml, generate_google_ads_csv, save_partial
from diff_engine import rotate_snapshots, compare_and_report

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SITEMAP_URL = "https://galeriaimobiliaria.com.br/sitemaps/propertys.xml"
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

MAX_WORKERS = 5
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
PARTIAL_SAVE_INTERVAL = 50

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / f"scraper_{timestamp}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

error_logger = logging.getLogger("errors")
error_handler = logging.FileHandler(LOGS_DIR / f"errors_{timestamp}.log", encoding="utf-8")
error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
error_logger.addHandler(error_handler)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    adapter = requests.adapters.HTTPAdapter(
        max_retries=requests.adapters.Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_DELAY,
            status_forcelist=[429, 500, 502, 503, 504],
        ),
        pool_connections=MAX_WORKERS,
        pool_maxsize=MAX_WORKERS,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_page(session: requests.Session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 404:
            logger.info(f"404 - {url}")
            return None
        logger.warning(f"HTTP {resp.status_code} - {url}")
        return None
    except requests.exceptions.RequestException as e:
        error_logger.error(f"Request falhou: {url} - {e}")
        return None


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------
def fetch_sitemap_urls(session: requests.Session) -> list[str]:
    logger.info(f"Buscando sitemap: {SITEMAP_URL}")
    html = fetch_page(session, SITEMAP_URL)
    if not html:
        logger.error("Falha ao buscar sitemap")
        return []

    soup = BeautifulSoup(html, "lxml-xml")
    urls = []
    for loc in soup.find_all("loc"):
        url = loc.text.strip()
        if url:
            urls.append(url)

    urls = list(dict.fromkeys(urls))
    logger.info(f"Total de URLs encontradas no sitemap: {len(urls)}")
    return urls


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def process_url(session: requests.Session, url: str) -> dict | None:
    html = fetch_page(session, url)
    if not html:
        return None
    try:
        return parse_property_page(html, url)
    except Exception as e:
        error_logger.error(f"Erro ao parsear {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Galeria Imobiliária - Scraper iniciado")
    logger.info("=" * 60)

    session = create_session()
    urls = fetch_sitemap_urls(session)

    if not urls:
        logger.error("Nenhuma URL encontrada. Encerrando.")
        return

    properties = []
    errors = 0
    skipped = 0

    logger.info(f"Iniciando scraping de {len(urls)} imóveis com {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_url, session, url): url for url in urls}
        progress = tqdm(as_completed(futures), total=len(futures), desc="Scraping", unit="imóvel")

        for future in progress:
            url = futures[future]
            try:
                result = future.result()
                if result:
                    properties.append(result)
                    progress.set_postfix(ok=len(properties), err=errors, skip=skipped)
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                error_logger.error(f"Erro no worker: {url} - {e}")

            if len(properties) > 0 and len(properties) % PARTIAL_SAVE_INTERVAL == 0:
                save_partial(properties, str(OUTPUT_DIR))

    # --- Compare with previous execution ---
    diff_stats = compare_and_report(properties)

    # --- Rotate snapshots (previous -> current) ---
    rotate_snapshots(properties)

    # --- Generate feeds (always from scratch, sitemap is source of truth) ---
    csv_path = str(OUTPUT_DIR / "output.csv")
    xml_path = str(OUTPUT_DIR / "output.xml")

    google_path = str(OUTPUT_DIR / "google_ads_real_estate_feed.csv")

    csv_count = generate_csv(properties, csv_path)
    xml_count = generate_xml(properties, xml_path)
    google_count = generate_google_ads_csv(properties, google_path)

    # --- Cleanup partial ---
    partial_path = OUTPUT_DIR / "output_partial.csv"
    if partial_path.exists():
        partial_path.unlink()

    # --- Summary ---
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    summary = f"""
{'=' * 60}
RESUMO DA EXECUÇÃO
{'=' * 60}
Total de URLs no sitemap:  {len(urls)}
Imóveis coletados:         {len(properties)}
Imóveis ignorados/vazios:  {skipped}
Erros:                     {errors}
CSV gerado:                {csv_path} ({csv_count} registros)
XML Meta gerado:           {xml_path} ({xml_count} registros)
Google Ads CSV gerado:     {google_path} ({google_count} registros)
Tempo total:               {minutes}m {seconds}s

COMPARAÇÃO COM EXECUÇÃO ANTERIOR:
  Anterior:    {diff_stats['previous_total']} imóveis
  Atual:       {diff_stats['current_total']} imóveis
  Novos:       {diff_stats['new']}
  Removidos:   {diff_stats['removed']}
  Mantidos:    {diff_stats['kept']}
  Atualizados: {diff_stats['updated']} ({diff_stats['update_changes']} campos)
{'=' * 60}
"""
    logger.info(summary)

    summary_path = LOGS_DIR / f"summary_{timestamp}.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    logger.info(f"Resumo salvo em: {summary_path}")


if __name__ == "__main__":
    main()
