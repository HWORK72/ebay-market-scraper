import asyncio
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv
from models import ProductItem
from scraper import EbayScraper

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger: logging.Logger = logging.getLogger(__name__)

TARGET_URL: str = os.getenv("TARGET_URL", "https://www.ebay.com/sch/i.html?_nkw=iphone+15+pro")
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "2"))
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "results")
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "25"))

def save_to_csv(items: List[ProductItem], target_path: Path) -> None:
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: List[str] = ["title", "price", "shipping", "condition", "item_url"]
        with open(target_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow(item.to_dict())
        logger.info(f"Persisted dataset to CSV: {target_path.resolve()}")
    except Exception as exc:
        logger.error(f"Failed exporting dataset to CSV: {exc}", exc_info=True)
        raise

def save_to_json(items: List[ProductItem], target_path: Path) -> None:
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        serialized_data: List[Dict[str, Any]] = [item.to_dict() for item in items]
        with open(target_path, mode="w", encoding="utf-8") as file:
            json.dump(serialized_data, file, ensure_ascii=False, indent=2)
        logger.info(f"Persisted dataset to JSON: {target_path.resolve()}")
    except Exception as exc:
        logger.error(f"Failed exporting dataset to JSON: {exc}", exc_info=True)
        raise

async def run() -> None:
    try:
        logger.info(f"Starting pipeline for target: {TARGET_URL}")
        scraper: EbayScraper = EbayScraper(timeout=REQUEST_TIMEOUT)
        collected_items: List[ProductItem] = await scraper.scrape_target(
            base_url=TARGET_URL,
            max_pages=MAX_PAGES
        )
        if not collected_items:
            logger.warning("Scraping completed with 0 items captured. Verify network or target.")
            return
        results_dir: Path = Path(OUTPUT_DIR)
        csv_file_path: Path = results_dir / "ebay_products.csv"
        json_file_path: Path = results_dir / "ebay_products.json"
        save_to_csv(collected_items, csv_file_path)
        save_to_json(collected_items, json_file_path)
        logger.info(f"Pipeline executed successfully. Total records stored: {len(collected_items)}")
    except Exception as exc:
        logger.critical(f"Fatal error during execution: {exc}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run())