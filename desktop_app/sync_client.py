import logging
from datetime import datetime, timezone
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class SyncClient:
    """
    Handles cloud synchronization using the official Supabase Python library.
    """
    def __init__(self, supabase_url: str = "", supabase_key: str = ""):
        self.supabase_url = supabase_url.strip().rstrip('/')
        self.supabase_key = supabase_key.strip()
        self.client = None
        self.is_configured = False
        self._init_client()

    def _init_client(self):
        if self.supabase_url and self.supabase_key:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
                self.is_configured = True
                logging.info("SyncClient: Connected to Supabase backend successfully.")
            except Exception as e:
                logging.error(f"SyncClient: Failed to connect to Supabase: {e}")
                self.client = None
                self.is_configured = False
        else:
            logging.warning("SyncClient: Supabase URL and/or Key not provided. Running in OFFLINE/DRY-RUN mode.")
            self.client = None
            self.is_configured = False

    def update_credentials(self, supabase_url: str, supabase_key: str):
        """Updates connection credentials at runtime and re-initializes client."""
        self.supabase_url = supabase_url.strip().rstrip('/')
        self.supabase_key = supabase_key.strip()
        self._init_client()

    def sync_product(self, barcode: str, product_name: str, price_iqd: float) -> bool:
        """
        Upserts a single product into the shop_prices table.
        """
        payload = {
            "barcode": str(barcode),
            "product_name": str(product_name),
            "price_iqd": int(round(float(price_iqd)))
        }
        return self.sync_batch([payload])

    def sync_batch(self, products: list[dict]) -> bool:
        """
        Upserts a list of products in chunks of 100 to the Supabase database.
        Each product dict must contain: 'barcode', 'product_name', 'price_iqd'.
        """
        if not products:
            return True

        if not self.is_configured or not self.client:
            logging.info(f"[DRY-RUN] Syncing batch of {len(products)} products: {products[:3]}...")
            return True

        now_iso = datetime.now(timezone.utc).isoformat()
        # Deduplicate by barcode, keeping the latest occurrence so the newest update wins
        deduped_map = {}
        for p in products:
            item = dict(p)
            item["updated_at"] = now_iso
            barcode_key = str(item.get("barcode", "")).strip().replace('"', '').replace("'", '')
            if barcode_key:
                item["barcode"] = barcode_key
                deduped_map[barcode_key] = item
        
        enriched_products = list(deduped_map.values())

        # Chunk uploads into groups of 100 items to avoid payload size/timeout limitations
        chunk_size = 100
        for i in range(0, len(enriched_products), chunk_size):
            chunk = enriched_products[i:i + chunk_size]
            try:
                self.client.table("shop_prices").upsert(chunk).execute()
                logging.info(f"Successfully synced chunk {i//chunk_size + 1} ({len(chunk)} products).")
            except Exception as e:
                logging.error(f"Supabase Client Error during chunk sync: {e}")
                # Raise exception so the GUI window displays the exact error message
                raise Exception(f"Sync failed at product {i+1} to {i+len(chunk)}. Error: {e}")
        
        return True
