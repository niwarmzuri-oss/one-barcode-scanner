import os
import time
import sqlite3
import logging
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class SQLiteFileHandler(FileSystemEventHandler):
    """
    Handles filesystem events for the watched SQLite database file.
    """
    def __init__(self, db_path: str, callback):
        super().__init__()
        self.db_path = Path(db_path).resolve()
        self.callback = callback
        self.last_triggered = 0.0
        self.debounce_seconds = 1.5  # Avoid multiple triggers in short sequence

    def on_modified(self, event):
        event_path = Path(event.src_path).resolve()
        
        is_db = event_path == self.db_path
        is_wal = event_path == self.db_path.with_name(self.db_path.name + "-wal")
        is_journal = event_path == self.db_path.with_name(self.db_path.name + "-journal")
        
        if is_db or is_wal or is_journal:
            now = time.time()
            if now - self.last_triggered > self.debounce_seconds:
                self.last_triggered = now
                threading.Thread(target=self.callback, daemon=True).start()


class DatabaseWatcher:
    """
    Background worker that runs a watchdog observer (for SQLite) or a polling thread 
    (for MS SQL Server) and parses the database when it changes.
    """
    def __init__(self, db_path: str, query_config: dict, sync_callback, log_callback=None):
        self.query_config = query_config
        self.engine = query_config.get("engine", "sqlite")
        
        if self.engine == "sqlite" and db_path:
            self.db_path = Path(db_path).resolve()
        else:
            self.db_path = None
            
        self.sync_callback = sync_callback
        self.log_callback = log_callback
        self.observer = None
        self.is_running = False
        self.polling_thread = None
        
        # In-memory database cache to track price modifications (prevents payload explosion)
        self.cached_inventory = {}  # {barcode: (product_name, price_iqd)}
        self.is_first_scan = True

    def log(self, msg: str, level=logging.INFO):
        """Thread-safe logging helper that propagates logs to GUI console if available."""
        if level == logging.ERROR:
            logging.error(msg)
        else:
            logging.info(msg)
            
        if self.log_callback:
            self.log_callback(msg)

    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        
        if self.engine == "mssql":
            self.log(f"Started monitoring SQL Server DB: {self.query_config.get('database', 'MEDUSAPOS')}")
            # Start background polling thread
            self.polling_thread = threading.Thread(target=self._mssql_polling_loop, daemon=True)
            self.polling_thread.start()
        else:
            if not self.db_path or not self.db_path.exists():
                self.log(f"Cannot start watcher: SQLite file does not exist: {self.db_path}", level=logging.ERROR)
                self.is_running = False
                return
            
            db_dir = self.db_path.parent
            event_handler = SQLiteFileHandler(self.db_path, self._on_db_changed)
            
            self.observer = Observer()
            self.observer.schedule(event_handler, path=str(db_dir), recursive=False)
            self.observer.start()
            self.log(f"Started monitoring SQLite DB at: {self.db_path}")
            
            # Initial ingestion of current database state
            self._on_db_changed()

    def stop(self):
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.engine == "sqlite" and self.observer:
            try:
                self.observer.stop()
                self.observer.join()
            except Exception:
                pass
        
        self.log("Stopped database monitoring.")

    def _mssql_polling_loop(self):
        # Initial scan to load inventory cache
        self._on_db_changed()
        
        # Poll every 5 seconds for changes in background
        while self.is_running:
            # Poll sleep in small chunks so we can terminate quickly on stop()
            for _ in range(5):
                if not self.is_running:
                    return
                time.sleep(1)
            
            if self.is_running:
                self._on_db_changed()

    def _on_db_changed(self):
        """
        Triggered when the database is modified or polled. Identifies changes and syncs them.
        """
        if self.engine == "sqlite":
            time.sleep(0.5)
        
        records = self.fetch_records()
        if not records:
            return

        updates = {}
        for r in records:
            barcode = r["barcode"]
            val_tuple = (r["product_name"], r["price_iqd"])
            
            if barcode not in self.cached_inventory:
                self.cached_inventory[barcode] = val_tuple
                if not self.is_first_scan:
                    updates[barcode] = r
            elif self.cached_inventory[barcode] != val_tuple:
                self.cached_inventory[barcode] = val_tuple
                updates[barcode] = r
                
        update_list = list(updates.values())
                
        if self.is_first_scan:
            self.is_first_scan = False
            self.log(f"Initial ingestion: cached {len(self.cached_inventory)} keys in-memory. Executing full sync.")
            self.sync_callback(records)
        elif update_list:
            self.log(f"State diff: identified {len(update_list)} modified or new records. Directing delta-sync.")
            for item in update_list:
                self.log(f"  -> Updated [{item['barcode']}]: '{item['product_name']}' = {item['price_iqd']} IQD")
            self.sync_callback(update_list)
        else:
            self.log("Database checked, but product details remain unchanged. Sync skipped.")

    def fetch_records(self) -> list[dict]:
        """
        Safely connects to SQLite or MS SQL Server to retrieve database records.
        """
        table = self.query_config.get("table", "products")
        barcode_col = self.query_config.get("barcode", "barcode")
        name_col = self.query_config.get("product_name", "product_name")
        price_col = self.query_config.get("price_iqd", "price_iqd")

        if self.engine == "mssql":
            server = self.query_config.get("server", ".")
            database = self.query_config.get("database", "MEDUSAPOS")
            
            conn_str = f"Driver={{SQL Server}};Server={server};Database={database};Trusted_Connection=yes;"
            query = f"SELECT {barcode_col}, {name_col}, {price_col} FROM {table} WITH (NOLOCK)"
            
            conn = None
            try:
                import pyodbc
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                
                records_map = {}
                for row in rows:
                    if len(row) < 3 or row[0] is None:
                        continue
                    
                    barcode_str = str(row[0]).strip().replace('"', '').replace("'", '').split('.')[0]
                    if not barcode_str:
                        continue
                    
                    name_str = str(row[1]).strip() if row[1] is not None else "Unnamed Product"
                    
                    price_num = 0
                    if row[2] is not None:
                        try:
                            val_str = str(row[2]).replace(',', '').replace('IQD', '').replace('ID', '').replace(' ', '').strip()
                            price_num = int(round(float(val_str)))
                        except ValueError:
                            pass
                    
                    if barcode_str not in records_map:
                        records_map[barcode_str] = {
                            "barcode": barcode_str,
                            "product_name": name_str,
                            "price_iqd": price_num
                        }
                    else:
                        existing = records_map[barcode_str]
                        if price_num > existing["price_iqd"] or (price_num == existing["price_iqd"] and name_str > existing["product_name"]):
                            records_map[barcode_str] = {
                                "barcode": barcode_str,
                                "product_name": name_str,
                                "price_iqd": price_num
                            }
                return list(records_map.values())
            except Exception as e:
                self.log(f"SQL Server query failed: {e}", level=logging.ERROR)
                return []
            finally:
                if conn:
                    conn.close()
        else:
            # SQLite Implementation
            if not self.db_path or not self.db_path.exists():
                return []

            db_uri = f"{self.db_path.as_uri()}?mode=ro"
            query = f"SELECT {barcode_col}, {name_col}, {price_col} FROM {table}"
            
            retries = 3
            conn = None
            for attempt in range(retries):
                try:
                    conn = sqlite3.connect(db_uri, uri=True)
                    cursor = conn.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    
                    records_map = {}
                    for row in rows:
                        if len(row) < 3 or row[0] is None:
                            continue
                        
                        barcode_str = str(row[0]).strip().replace('"', '').replace("'", '').split('.')[0]
                        if not barcode_str:
                            continue
                        
                        name_str = str(row[1]).strip() if row[1] is not None else "Unnamed Product"
                        
                        price_num = 0
                        if row[2] is not None:
                            try:
                                price_num = int(round(float(row[2])))
                            except ValueError:
                                pass
                        
                        if barcode_str not in records_map:
                            records_map[barcode_str] = {
                                "barcode": barcode_str,
                                "product_name": name_str,
                                "price_iqd": price_num
                            }
                        else:
                            existing = records_map[barcode_str]
                            if price_num > existing["price_iqd"] or (price_num == existing["price_iqd"] and name_str > existing["product_name"]):
                                records_map[barcode_str] = {
                                    "barcode": barcode_str,
                                    "product_name": name_str,
                                    "price_iqd": price_num
                                }
                    return list(records_map.values())
                except sqlite3.OperationalError as e:
                    self.log(f"Database lock collision (Attempt {attempt+1}/{retries}): {e}", level=logging.WARNING)
                    time.sleep(0.3)
                finally:
                    if conn:
                        conn.close()
            
            self.log("Failed to read SQLite database records after maximum retries due to active locks.", level=logging.ERROR)
            return []
