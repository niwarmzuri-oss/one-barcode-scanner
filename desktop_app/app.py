import os
import sys
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QLineEdit, QPushButton, QFileDialog, 
    QPlainTextEdit, QFrame, QGridLayout, QDialog, QComboBox, QMessageBox
)
from PySide6.QtGui import QFont, QIcon

from sync_client import SyncClient
from db_watcher import DatabaseWatcher
from excel_parser import ExcelParser

# Setup basic configuration for application logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def get_config_path() -> Path:
    # Use standard application data directory based on platform
    if getattr(sys, 'frozen', False):
        if sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support" / "OneBarcode"
        elif sys.platform == "win32":
            base_dir = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "OneBarcode"
        else:
            base_dir = Path.home() / ".config" / "OneBarcode"
            
        base_dir.mkdir(parents=True, exist_ok=True)
        config_path = base_dir / "config.json"
        
        # If compiled app config doesn't exist, try to copy initial one from bundle resources
        if not config_path.exists():
            bundle_config = Path(sys._MEIPASS) / "config.json" if hasattr(sys, '_MEIPASS') else None
            if bundle_config and bundle_config.exists():
                try:
                    import shutil
                    shutil.copy(bundle_config, config_path)
                except Exception:
                    pass
        return config_path
    else:
        # Developer mode fallback to local file
        return Path("config.json")

CONFIG_FILE = get_config_path()

# Modern QSS stylesheet for dark mode UI
DARK_THEME_QSS = """
QMainWindow {
    background-color: #0d0e15;
}
QWidget {
    color: #e5e7eb;
    font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}
QFrame#card {
    background-color: #161824;
    border: 1px solid #272a3d;
    border-radius: 12px;
}
QTabWidget::pane {
    border: 1px solid #1f2235;
    background: #11121c;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: #161824;
    border: 1px solid #272a3d;
    border-bottom-color: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    color: #9ca3af;
}
QTabBar::tab:selected {
    background: #11121c;
    border-color: #1f2235;
    color: #ffffff;
    font-weight: bold;
}
QTabBar::tab:hover {
    background: #1f2235;
    color: #ffffff;
}
QLineEdit {
    background-color: #07080c;
    border: 1px solid #272a3d;
    border-radius: 6px;
    padding: 8px;
    color: #f3f4f6;
}
QLineEdit:focus {
    border: 1px solid #5850ec;
}
QPushButton {
    background-color: #1f2235;
    border: 1px solid #272a3d;
    border-radius: 6px;
    padding: 8px 16px;
    color: #f3f4f6;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #272a3d;
}
QPushButton:pressed {
    background-color: #11121c;
}
QPushButton#primaryBtn {
    background-color: #5850ec;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #6366f1;
}
QPushButton#primaryBtn:pressed {
    background-color: #4f46e5;
}
QPushButton#dangerBtn {
    background-color: #f43f5e;
    border: none;
}
QPushButton#dangerBtn:hover {
    background-color: #fda4af;
}
QPlainTextEdit {
    background-color: #07080c;
    border: 1px solid #272a3d;
    border-radius: 8px;
    color: #a5f3fc;
    font-family: 'Consolas', 'Courier New', monospace;
    padding: 10px;
}
QComboBox {
    background-color: #07080c;
    border: 1px solid #272a3d;
    border-radius: 6px;
    padding: 6px;
    color: #f3f4f6;
}
QComboBox::drop-down {
    border: none;
}
"""

# Modern QSS stylesheet for light mode UI
LIGHT_THEME_QSS = """
QMainWindow {
    background-color: #f3f4f6;
}
QWidget {
    color: #1f2937;
    font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}
QTabWidget::pane {
    border: 1px solid #e5e7eb;
    background: #ffffff;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: #e5e7eb;
    border: 1px solid #d1d5db;
    border-bottom-color: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    color: #4b5563;
}
QTabBar::tab:selected {
    background: #ffffff;
    border-color: #e5e7eb;
    color: #111827;
    font-weight: bold;
}
QTabBar::tab:hover {
    background: #f3f4f6;
    color: #111827;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px;
    color: #1f2937;
}
QLineEdit:focus {
    border: 1px solid #4f46e5;
}
QPushButton {
    background-color: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 16px;
    color: #1f2937;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #e5e7eb;
}
QPushButton:pressed {
    background-color: #d1d5db;
}
QPushButton#primaryBtn {
    background-color: #4f46e5;
    border: none;
    color: #ffffff;
}
QPushButton#primaryBtn:hover {
    background-color: #4338ca;
}
QPushButton#primaryBtn:pressed {
    background-color: #3730a3;
}
QPushButton#dangerBtn {
    background-color: #f43f5e;
    border: none;
    color: #ffffff;
}
QPushButton#dangerBtn:hover {
    background-color: #e11d48;
}
QPlainTextEdit {
    background-color: #f9fafb;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    color: #0f766e;
    font-family: 'Consolas', 'Courier New', monospace;
    padding: 10px;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px;
    color: #1f2937;
}
QComboBox::drop-down {
    border: none;
}
"""

class GUIThreadBridge(QObject):
    """
    Bridge object to emit thread-safe signals from background file watchers
    to update the GUI widgets safely on the main Qt thread.
    """
    log_signal = Signal(str)
    sync_trigger_signal = Signal(list)


class WatcherSyncWorker(QThread):
    """
    Worker thread that runs the Supabase network requests in the background,
    keeping the main PySide6 event loop responsive.
    """
    finished = Signal(bool, str) # success state, display message

    def __init__(self, sync_client, records):
        super().__init__()
        self.sync_client = sync_client
        self.records = records

    def run(self):
        if not self.records:
            self.finished.emit(True, "Zero records to sync.")
            return
            
        try:
            # Performs the network request in background
            success = self.sync_client.sync_batch(self.records)
            if success:
                self.finished.emit(True, f"Sync complete. Successfully synced {len(self.records)} products to Supabase.")
            else:
                self.finished.emit(False, "Failed to upload data batch to cloud.")
        except Exception as e:
            self.finished.emit(False, f"Upload error: {str(e)}")


class OneBarcodeAdminApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # MainWindow window settings
        self.setWindowTitle("One Barcode - Retail Admin Sync (Cross-Platform)")
        self.resize(900, 700)
        self.setMinimumSize(850, 600)

        # Thread Safety Bridge
        self.bridge = GUIThreadBridge()
        self.bridge.log_signal.connect(self.write_log)
        self.bridge.sync_trigger_signal.connect(self.process_background_sync)

        # Application state
        self.config = {
            "supabase_url": "",
            "supabase_key": "",
            "theme": "light",
            "db_engine": "sqlite",
            "db_server": ".",
            "db_name": "MEDUSAPOS",
            "db_path": "",
            "db_table": "shop_prices",
            "db_col_barcode": "barcode",
            "db_col_name": "product_name",
            "db_col_price": "price_iqd"
        }
        
        self.watcher = None
        self.sync_client = None
        self.sync_worker = None
        self.pending_sync_records = {}
        self.load_config()

        # Initialize Sync Client
        self.sync_client = SyncClient(
            supabase_url=self.config.get("supabase_url", ""),
            supabase_key=self.config.get("supabase_key", "")
        )

        # Setup GUI elements
        self.setup_ui()
        self.update_sync_status()

    def load_config(self):
        """Loads configuration from JSON file safely."""
        config_path = Path(CONFIG_FILE)
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except Exception as e:
                logging.error(f"Failed to load config: {e}")

    def save_config(self):
        """Saves configuration to JSON file safely."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def setup_ui(self):
        theme = self.config.get("theme", "light")
        self.setStyleSheet(DARK_THEME_QSS if theme == "dark" else LIGHT_THEME_QSS)

        # Central layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Create Tab Widget
        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Build tabs
        self.setup_sqlite_tab()
        self.setup_excel_tab()
        self.setup_settings_tab()

    # ----------------------------------------------------
    # UI Tabs Setup
    # ----------------------------------------------------

    def setup_sqlite_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header Title
        title = QLabel("POS Database Real-Time Sync", tab)
        title.setFont(QFont("Outfit", 18, QFont.Bold))
        layout.addWidget(title)

        # 1. Database Engine Selector Card
        engine_card = QFrame(tab)
        engine_card.setObjectName("card")
        engine_layout = QHBoxLayout(engine_card)
        engine_layout.setContentsMargins(15, 15, 15, 15)
        
        engine_layout.addWidget(QLabel("Select POS Database Engine:", engine_card))
        self.combo_engine = QComboBox(engine_card)
        self.combo_engine.addItems(["SQLite Database File", "Microsoft SQL Server (Medusa POS)"])
        
        # Set selection from config
        if self.config.get("db_engine", "sqlite") == "mssql":
            self.combo_engine.setCurrentIndex(1)
        else:
            self.combo_engine.setCurrentIndex(0)
            
        self.combo_engine.currentIndexChanged.connect(self.on_engine_changed)
        engine_layout.addWidget(self.combo_engine, 1)
        layout.addWidget(engine_card)

        # 2. SQLite Selection Card
        self.sqlite_card = QFrame(tab)
        self.sqlite_card.setObjectName("card")
        sqlite_layout = QHBoxLayout(self.sqlite_card)
        sqlite_layout.setContentsMargins(15, 15, 15, 15)

        self.btn_select_db = QPushButton("Select SQLite DB", self.sqlite_card)
        self.btn_select_db.setObjectName("primaryBtn")
        self.btn_select_db.clicked.connect(self.browse_sqlite_db)
        sqlite_layout.addWidget(self.btn_select_db)

        self.lbl_db_path = QLabel(self.config["db_path"] or "No POS SQLite database file selected.", self.sqlite_card)
        self.lbl_db_path.setWordWrap(True)
        sqlite_layout.addWidget(self.lbl_db_path, 1)
        layout.addWidget(self.sqlite_card)

        # 3. SQL Server Connection Card
        self.mssql_card = QFrame(tab)
        self.mssql_card.setObjectName("card")
        mssql_layout = QGridLayout(self.mssql_card)
        mssql_layout.setContentsMargins(15, 15, 15, 15)
        mssql_layout.setSpacing(10)
        
        mssql_layout.addWidget(QLabel("SQL Server Instance:", self.mssql_card), 0, 0)
        self.entry_mssql_server = QLineEdit(self.mssql_card)
        self.entry_mssql_server.setText(self.config.get("db_server", "."))
        mssql_layout.addWidget(self.entry_mssql_server, 0, 1)
        
        mssql_layout.addWidget(QLabel("Database Name:", self.mssql_card), 0, 2)
        self.entry_mssql_db = QLineEdit(self.mssql_card)
        self.entry_mssql_db.setText(self.config.get("db_name", "MEDUSAPOS"))
        mssql_layout.addWidget(self.entry_mssql_db, 0, 3)
        layout.addWidget(self.mssql_card)

        # 4. Schema Mapping Card
        schema_card = QFrame(tab)
        schema_card.setObjectName("card")
        schema_layout = QVBoxLayout(schema_card)
        schema_layout.setContentsMargins(15, 15, 15, 15)

        schema_title = QLabel("Database Table & Columns Settings:", schema_card)
        schema_title.setFont(QFont("Inter", 12, QFont.Bold))
        schema_layout.addWidget(schema_title)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Table Name:", schema_card), 0, 0)
        self.entry_db_table = QLineEdit(schema_card)
        self.entry_db_table.setText(self.config["db_table"])
        grid.addWidget(self.entry_db_table, 0, 1)

        grid.addWidget(QLabel("Barcode Column:", schema_card), 0, 2)
        self.entry_col_barcode = QLineEdit(schema_card)
        self.entry_col_barcode.setText(self.config["db_col_barcode"])
        grid.addWidget(self.entry_col_barcode, 0, 3)

        grid.addWidget(QLabel("Product Name Column:", schema_card), 1, 0)
        self.entry_col_name = QLineEdit(schema_card)
        self.entry_col_name.setText(self.config["db_col_name"])
        grid.addWidget(self.entry_col_name, 1, 1)

        grid.addWidget(QLabel("Price Column (IQD):", schema_card), 1, 2)
        self.entry_col_price = QLineEdit(schema_card)
        self.entry_col_price.setText(self.config["db_col_price"])
        grid.addWidget(self.entry_col_price, 1, 3)

        schema_layout.addLayout(grid)
        layout.addWidget(schema_card)

        # Controls Switch Bar
        control_layout = QHBoxLayout()
        self.btn_toggle_watcher = QPushButton("Start Sync Watcher", tab)
        self.btn_toggle_watcher.setObjectName("primaryBtn")
        self.btn_toggle_watcher.clicked.connect(self.toggle_db_watcher)
        control_layout.addWidget(self.btn_toggle_watcher)

        self.lbl_watcher_status = QLabel("Watcher Status: STOPPED", tab)
        self.lbl_watcher_status.setStyleSheet("color: #f43f5e; font-weight: bold;")
        control_layout.addWidget(self.lbl_watcher_status)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # Console Logs Display
        layout.addWidget(QLabel("Sync Console Logs:", tab))
        self.log_text = QPlainTextEdit(tab)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)

        self.tab_widget.addTab(tab, "POS Database Sync")
        
        # Trigger initial view layout setup based on config value
        self.on_engine_changed()

    def on_engine_changed(self):
        if self.combo_engine.currentIndex() == 1:
            self.sqlite_card.hide()
            self.mssql_card.show()
            # Auto-populate Medusa POS defaults if table is still default SQLite
            if self.entry_db_table.text() == "shop_prices" or self.entry_db_table.text() == "":
                self.entry_db_table.setText("STOK")
                self.entry_col_barcode.setText("BARKOD")
                self.entry_col_name.setText("STOKADI")
                self.entry_col_price.setText("SATISFIYAT1")
        else:
            self.sqlite_card.show()
            self.mssql_card.hide()
            # Auto-populate SQLite defaults for market_pos db
            if self.entry_db_table.text() in ["STOK", "shop_prices", ""]:
                self.entry_db_table.setText("urunler")
                self.entry_col_barcode.setText("barkod")
                self.entry_col_name.setText("ad")
                self.entry_col_price.setText("satis_fiyati")

    def setup_excel_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Excel Products Bulk Sync", tab)
        title.setFont(QFont("Outfit", 18, QFont.Bold))
        layout.addWidget(title)

        excel_card = QFrame(tab)
        excel_card.setObjectName("card")
        excel_layout = QHBoxLayout(excel_card)
        excel_layout.setContentsMargins(15, 15, 15, 15)

        self.btn_select_excel = QPushButton("Select Excel File (.xlsx)", excel_card)
        self.btn_select_excel.setObjectName("primaryBtn")
        self.btn_select_excel.clicked.connect(self.import_excel_file)
        excel_layout.addWidget(self.btn_select_excel)

        self.lbl_excel_path = QLabel("No Excel inventory spreadsheet file loaded.", excel_card)
        excel_layout.addWidget(self.lbl_excel_path, 1)

        layout.addWidget(excel_card)

        # Excel Console
        layout.addWidget(QLabel("Excel Processing Status Log:", tab))
        self.excel_log = QPlainTextEdit(tab)
        self.excel_log.setReadOnly(True)
        layout.addWidget(self.excel_log, 1)

        self.tab_widget.addTab(tab, "Excel Bulk Import")

    def setup_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Supabase Cloud Credentials & Settings", tab)
        title.setFont(QFont("Outfit", 18, QFont.Bold))
        layout.addWidget(title)

        form_card = QFrame(tab)
        form_card.setObjectName("card")
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(20, 20, 20, 20)

        form_layout.addWidget(QLabel("Supabase Project REST URL:", form_card))
        self.entry_url = QLineEdit(form_card)
        self.entry_url.setText(self.config["supabase_url"])
        form_layout.addWidget(self.entry_url)

        form_layout.addWidget(QLabel("Supabase Public Anon Key (Publishable Key):", form_card))
        self.entry_key = QLineEdit(form_card)
        self.entry_key.setEchoMode(QLineEdit.Password)
        self.entry_key.setText(self.config["supabase_key"])
        form_layout.addWidget(self.entry_key)

        btn_save = QPushButton("Save & Update Cloud Connection", form_card)
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self.save_credentials)
        form_layout.addWidget(btn_save)

        self.lbl_connection_indicator = QLabel("Connection Status: Unconfigured", form_card)
        self.lbl_connection_indicator.setFont(QFont("Inter", 11, QFont.Bold))
        form_layout.addWidget(self.lbl_connection_indicator)

        form_layout.addWidget(QLabel("App Display Theme:", form_card))
        self.combo_theme = QComboBox(form_card)
        self.combo_theme.addItems(["Light Mode", "Dark Mode"])
        
        # Set selection from config
        if self.config.get("theme", "light") == "dark":
            self.combo_theme.setCurrentIndex(1)
        else:
            self.combo_theme.setCurrentIndex(0)
            
        self.combo_theme.currentIndexChanged.connect(self.on_theme_changed)
        form_layout.addWidget(self.combo_theme)

        layout.addWidget(form_card)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Cloud Credentials")

    def on_theme_changed(self):
        theme = "dark" if self.combo_theme.currentIndex() == 1 else "light"
        self.config["theme"] = theme
        self.save_config()
        
        # Apply style sheet dynamically
        if theme == "dark":
            self.setStyleSheet(DARK_THEME_QSS)
        else:
            self.setStyleSheet(LIGHT_THEME_QSS)

    # ----------------------------------------------------
    # UI Console and Settings Logic
    # ----------------------------------------------------

    def write_log(self, text: str):
        """Thread-safe method to write log events to SQLite console."""
        self.log_text.appendPlainText(text)

    def write_excel_log(self, text: str):
        """Writes log events to Excel console."""
        self.excel_log.appendPlainText(text)

    def update_sync_status(self):
        if self.sync_client and self.sync_client.is_configured:
            self.lbl_connection_indicator.setText("Status: Connected (Cloud Configured)")
            self.lbl_connection_indicator.setStyleSheet("color: #10b981;")
        else:
            self.lbl_connection_indicator.setText("Status: Offline (Configure Cloud Credentials)")
            self.lbl_connection_indicator.setStyleSheet("color: #f59e0b;")

    def save_credentials(self):
        url = self.entry_url.text().strip()
        key = self.entry_key.text().strip()

        if not url or not key:
            QMessageBox.warning(self, "Validation Error", "Please provide both Supabase URL and Key.")
            return

        self.config["supabase_url"] = url
        self.config["supabase_key"] = key
        self.save_config()

        self.sync_client.update_credentials(url, key)
        self.update_sync_status()
        self.write_log("Supabase connection credentials updated.")
        QMessageBox.information(self, "Saved", "Cloud connection details stored successfully.")

    def browse_sqlite_db(self):
        """Cross-platform native file browser."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select POS SQLite Database", "", 
            "Databases (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if filepath:
            # Normalize paths for Windows/macOS compatibility
            normalized_path = str(Path(filepath).resolve())
            self.config["db_path"] = normalized_path
            self.lbl_db_path.setText(normalized_path)
            self.save_config()
            self.write_log(f"SQLite target DB set: {normalized_path}")

    # ----------------------------------------------------
    # Real-Time SQLite Watcher Controls
    # ----------------------------------------------------

    def get_current_db_schema_config(self) -> dict:
        self.config["db_engine"] = "mssql" if self.combo_engine.currentIndex() == 1 else "sqlite"
        self.config["db_server"] = self.entry_mssql_server.text().strip()
        self.config["db_name"] = self.entry_mssql_db.text().strip()
        self.config["db_table"] = self.entry_db_table.text().strip()
        self.config["db_col_barcode"] = self.entry_col_barcode.text().strip()
        self.config["db_col_name"] = self.entry_col_name.text().strip()
        self.config["db_col_price"] = self.entry_col_price.text().strip()
        self.save_config()

        return {
            "engine": self.config["db_engine"],
            "server": self.config["db_server"],
            "database": self.config["db_name"],
            "table": self.config["db_table"],
            "barcode": self.config["db_col_barcode"],
            "product_name": self.config["db_col_name"],
            "price_iqd": self.config["db_col_price"]
        }

    def toggle_db_watcher(self):
        if self.watcher and self.watcher.is_running:
            # Stop Watcher
            self.watcher.stop()
            self.watcher = None
            self.btn_toggle_watcher.setText("Start Sync Watcher")
            self.btn_toggle_watcher.setObjectName("primaryBtn")
            self.btn_toggle_watcher.setStyleSheet("") # Clear any custom style
            self.lbl_watcher_status.setText("Watcher Status: STOPPED")
            self.lbl_watcher_status.setStyleSheet("color: #f43f5e; font-weight: bold;")
            self.write_log("Sync Database Watcher deactivated.")
        else:
            # Start Watcher
            engine = "mssql" if self.combo_engine.currentIndex() == 1 else "sqlite"
            db_path = self.config["db_path"]
            
            if engine == "sqlite" and (not db_path or not Path(db_path).exists()):
                QMessageBox.critical(self, "Error", "Selected SQLite DB file does not exist. Please select a valid file.")
                return

            schema = self.get_current_db_schema_config()
            self.write_log(f"Initializing database watcher for {engine.upper()}: SELECT {schema['barcode']}, {schema['product_name']}, {schema['price_iqd']} FROM {schema['table']}")

            self.watcher = DatabaseWatcher(
                db_path=db_path,
                query_config=schema,
                sync_callback=self.background_watcher_callback,
                log_callback=self.background_watcher_log_callback
            )
            
            try:
                self.watcher.start()
                self.btn_toggle_watcher.setText("Stop Sync Watcher")
                # Set custom danger color style directly
                self.btn_toggle_watcher.setStyleSheet("background-color: #f43f5e; color: white;")
                self.lbl_watcher_status.setText("Watcher Status: ACTIVE")
                self.lbl_watcher_status.setStyleSheet("color: #10b981; font-weight: bold;")
                self.write_log(f"Sync Watcher activated successfully. Listening for {engine.upper()} updates.")
            except Exception as e:
                self.write_log(f"Failed to start watcher: {e}")
                QMessageBox.critical(self, "Error", f"Failed to open/query database: {e}")

    def background_watcher_log_callback(self, message: str):
        """
        Triggered by background thread database watcher logs.
        Uses Qt Bridge to emit logs thread-safely to main GUI thread.
        """
        self.bridge.log_signal.emit(message)

    def background_watcher_callback(self, records: list[dict]):
        """
        Triggered by background thread database watcher.
        Uses Qt Bridge to emit logs thread-safely to main GUI thread.
        """
        self.bridge.sync_trigger_signal.emit(records)

    def process_background_sync(self, records: list[dict]):
        """Runs on the UI thread to spin up the non-blocking background thread worker."""
        if not self.sync_client.is_configured:
            self.write_log("[DRY-RUN] Cloud connection credentials missing. Sync skipped.")
            return

        # If a worker is already running, queue records by barcode so latest updates win
        if self.sync_worker is not None and self.sync_worker.isRunning():
            for r in records:
                self.pending_sync_records[r["barcode"]] = r
            self.write_log(f"Active sync in progress. Queued {len(records)} price update(s) for next batch.")
            return

        # Disable watcher control buttons briefly during active upload
        self.btn_toggle_watcher.setEnabled(False)
        
        # Instantiate background thread worker
        self.sync_worker = WatcherSyncWorker(self.sync_client, records)
        
        def on_worker_finished(success, message):
            self.write_log(message)
            self.sync_worker = None # Dereference worker thread
            
            # Check if pending updates accumulated while this sync was running
            if self.pending_sync_records:
                queued_records = list(self.pending_sync_records.values())
                self.pending_sync_records.clear()
                self.write_log(f"Processing {len(queued_records)} queued price update(s)...")
                self.process_background_sync(queued_records)
            else:
                self.btn_toggle_watcher.setEnabled(True)
            
        self.sync_worker.finished.connect(on_worker_finished)
        self.sync_worker.start() # Starts running asynchronous sync worker

    # ----------------------------------------------------
    # Excel Columns Mapping Popup & Parsing
    # ----------------------------------------------------

    def import_excel_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Excel Inventory Export", "", 
            "Excel Files (*.xlsx *.xlsm);;All Files (*)"
        )
        if not filepath:
            return

        normalized_path = str(Path(filepath).resolve())
        self.lbl_excel_path.setText(Path(normalized_path).name)
        self.write_excel_log(f"Selected Excel file: {normalized_path}")
        self.write_excel_log("Automatically parsing columns (Col 1: Barcode, Col 2: Name, Col 3: Price)")

        try:
            self.run_background_excel_import(normalized_path)
        except Exception as e:
            QMessageBox.critical(self, "Excel Error", f"Error launching import: {e}")

    def run_background_excel_import(self, file_path: str):
        class ExcelWorker(QThread):
            finished = Signal(bool, str) # success, message
            
            def __init__(self, client, path):
                super().__init__()
                self.client = client
                self.path = path

            def run(self):
                try:
                    records = ExcelParser.parse_records(self.path)
                    if not self.client.is_configured:
                        self.finished.emit(True, f"Parsed {len(records)} products. Cloud credentials missing (dry-run skipped upload).")
                        return

                    success = self.client.sync_batch(records)
                    if success:
                        self.finished.emit(True, f"Sync complete. Successfully synced {len(records)} products to Supabase.")
                    else:
                        self.finished.emit(False, "Sync failed. Error sending batch data to cloud.")
                except Exception as e:
                    self.finished.emit(False, str(e))

        self.worker = ExcelWorker(self.sync_client, file_path)
        
        def handle_finished(success, message):
            self.write_excel_log(message)
            if success:
                QMessageBox.information(self, "Success", "Excel products bulk upload complete!")
            else:
                QMessageBox.critical(self, "Import Error", f"Failed to complete import: {message}")
            self.worker = None

        self.worker.finished.connect(handle_finished)
        self.worker.start()

    def closeEvent(self, event):
        """Clean termination of background threads on close."""
        if self.watcher and self.watcher.is_running:
            self.watcher.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OneBarcodeAdminApp()
    window.show()
    sys.exit(app.exec())
