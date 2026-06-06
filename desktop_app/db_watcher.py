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
        self.db_dir = self.db_path.parent
        self.db_filename = self.db_path.name
        self.callback = callback
        self.last_triggered = 0.0
        self.debounce_seconds = 1.0  # Avoid multiple triggers in short sequence

    def on_modified(self, event):
        event_path = Path(event.src_path).resolve()
        
        # Check if the modified file matches our SQLite database path or its journal/WAL files
        is_db_file = event_path == self.db_path
        is_wal_file = event_path == self.db_path.with_name(self.db_path.name + "-wal")
        is_journal_file = event_path == self.db_path.with_name(self.db_path.name + "-journal")
        
        if is_db_file or is_wal_file or is_journal_file:
            now = time.time()
            if now - self.last_triggered > self.debounce_seconds:
                self.last_triggered = now
                logging.info(f"Database change detected via file modification: {event_path}")
                # Spawn callback in a separate thread to prevent blocking the watcher observer
                threading.Thread(target=self.callback, daemon=True).start()


class DatabaseWatcher:
    """
    Background worker that runs a watchdog observer and parses the SQLite database
    when it changes. Resolves file paths cross-platform.
    """
    def __init__(self, db_path: str, query_config: dict, sync_callback):
        self.db_path = Path(db_path).resolve()
        self.query_config = query_config  # {"table": "items", "barcode": "code", "name": "name", "price": "price"}
        self.sync_callback = sync_callback
        
        self.observer = None
        self.is_running = False
        self.last_hash = None # To compare DB state and prevent redundant syncs

    def start(self):
        if self.is_running:
            return
        
        if not self.db_path.exists():
            logging.error(f"Cannot start watcher: SQLite file does not exist: {self.db_path}")
            return
        
        db_dir = self.db_path.parent
        event_handler = SQLiteFileHandler(self.db_path, self._on_db_changed)
        
        self.observer = Observer()
        self.observer.schedule(event_handler, path=str(db_dir), recursive=False)
        self.observer.start()
        self.is_running = True
        logging.info(f"Started monitoring SQLite DB at: {self.db_path}")
        
        # Initial scan
        self._on_db_changed()

    def stop(self):
        if not self.is_running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.is_running = False
        logging.info("Stopped SQLite DB monitoring.")

    def _on_db_changed(self):
        """
        Triggered when the file modifies. Reads database data and triggers sync_callback if changed.
        """
        # Wait a small delay to allow POS database locks to release
        time.sleep(0.5)
        
        records = self.fetch_records()
        if not records:
            return

        # Simple hash calculation of records list to see if anything actually changed
        current_hash = hash(frozenset((r["barcode"], r["product_name"], r["price_iqd"]) for r in records))
        if current_hash != self.last_hash:
            logging.info(f"Database data change verified. Unique hash updated from {self.last_hash} to {current_hash}.")
            self.last_hash = current_hash
            self.sync_callback(records)
        else:
            logging.info("Database file modified, but products data is unchanged. Skipping sync.")

    def fetch_records(self) -> list[dict]:
        """
        Safely connects to SQLite in read-only mode and queries the product table.
        """
        if not self.db_path.exists():
            return []

        # Connect in read-only mode using URI syntax to avoid locking active POS write operations
        # Must be absolute path resolved cleanly
        db_abs_path = str(self.db_path.resolve())
        
        # SQLite URI format: file:/path/to/file?mode=ro
        # On Windows, we need to ensure the URI format handles drive letters correctly.
        # Python's pathlib as_uri() is perfect for this:
        db_uri = f"{self.db_path.as_uri()}?mode=ro"
        
        table = self.query_config.get("table", "products")
        barcode_col = self.query_config.get("barcode", "barcode")
        name_col = self.query_config.get("product_name", "product_name")
        price_col = self.query_config.get("price_iqd", "price_iqd")

        query = f"SELECT {barcode_col}, {name_col}, {price_col} FROM {table}"
        
        conn = None
        try:
            conn = sqlite3.connect(db_uri, uri=True)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                if len(row) < 3:
                    continue
                
                raw_barcode, raw_name, raw_price = row[0], row[1], row[2]
                
                if raw_barcode is None:
                    continue
                
                # Format variables
                barcode_str = str(raw_barcode).strip().split('.')[0]
                if not barcode_str:
                    continue
                
                name_str = str(raw_name).strip() if raw_name is not None else "Unnamed Product"
                
                price_num = 0
                if raw_price is not None:
                    try:
                        price_num = int(round(float(raw_price)))
                    except ValueError:
                        pass
                
                records.append({
                    "barcode": barcode_str,
                    "product_name": name_str,
                    "price_iqd": price_num
                })
            
            return records
        except sqlite3.Error as e:
            logging.error(f"SQLite reading error: {e}")
            return []
        finally:
            if conn:
                conn.close()
