import os
import sys
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Add desktop_app to path to reuse components
sys.path.append(str(Path(__file__).parent / "desktop_app"))

from excel_parser import ExcelParser
from sync_client import SyncClient

def main():
    excel_path = "/Users/hardos/Downloads/One Market/Stok Listesi.xlsx"
    config_path = Path(__file__).parent / "desktop_app" / "config.json"
    
    if not os.path.exists(excel_path):
        logging.error(f"Excel file not found at: {excel_path}")
        return
        
    if not config_path.exists():
        logging.error(f"Config file not found at: {config_path}")
        return
        
    # Load credentials
    with open(config_path, "r") as f:
        config = json.load(f)
        
    supabase_url = config.get("supabase_url")
    supabase_key = config.get("supabase_key")
    
    if not supabase_url or not supabase_key:
        logging.error("Missing Supabase credentials in config.json")
        return
        
    logging.info(f"Initializing connection to Supabase: {supabase_url}")
    client = SyncClient(supabase_url=supabase_url, supabase_key=supabase_key)
    
    if not client.is_configured:
        logging.error("Failed to configure Supabase client")
        return
        
    logging.info("Parsing records from Excel...")
    mapping = {
        "barcode": "BARKOD",
        "product_name": "STOK ADI",
        "price_iqd": "SATIŞ FİYAT 1"
    }
    
    try:
        records = ExcelParser.parse_records(excel_path, mapping)
        total_records = len(records)
        logging.info(f"Successfully parsed {total_records} records.")
        
        # Deduplicate records by barcode (primary key) and filter out huge prices
        logging.info("Deduplicating records by barcode and filtering invalid values...")
        seen_barcodes = set()
        deduped_records = []
        for r in records:
            b = r["barcode"]
            p = r["price_iqd"]
            if p > 10000000:
                logging.warning(f"Skipping malformed row with abnormal price: {r}")
                continue
            if b not in seen_barcodes:
                seen_barcodes.add(b)
                deduped_records.append(r)
                
        logging.info(f"Deduplication finished. Reduced from {total_records} to {len(deduped_records)} unique barcodes.")
        total_records = len(deduped_records)
        
        logging.info("Starting optimized upload to Supabase in batches of 1,000...")
        chunk_size = 1000
        for i in range(0, total_records, chunk_size):
            chunk = deduped_records[i:i + chunk_size]
            client.client.table("shop_prices").upsert(chunk).execute()
            logging.info(f"Successfully synced chunk {i//chunk_size + 1} ({len(chunk)} / {total_records} products).")
            
        logging.info("Sync completed successfully!")
        
    except Exception as e:
        logging.error(f"Sync failed: {e}")

if __name__ == "__main__":
    main()
