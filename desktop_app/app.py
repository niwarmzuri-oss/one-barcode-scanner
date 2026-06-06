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

CONFIG_FILE = "config.json"

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

class GUIThreadBridge(QObject):
    """
    Bridge object to emit thread-safe signals from background file watchers
    to update the GUI widgets safely on the main Qt thread.
    """
    log_signal = Signal(str)
    sync_trigger_signal = Signal(list)


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
            "db_path": "",
            "db_table": "shop_prices",
            "db_col_barcode": "barcode",
            "db_col_name": "product_name",
            "db_col_price": "price_iqd"
        }
        
        self.watcher = None
        self.sync_client = None
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
        self.setStyleSheet(DARK_THEME_QSS)

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
        title = QLabel("SQLite Real-Time Monitoring", tab)
        title.setFont(QFont("Outfit", 18, QFont.Bold))
        layout.addWidget(title)

        # SQLite Database File Selection Card
        db_card = QFrame(tab)
        db_card.setObjectName("card")
        db_layout = QHBoxLayout(db_card)
        db_layout.setContentsMargins(15, 15, 15, 15)

        self.btn_select_db = QPushButton("Select SQLite DB", db_card)
        self.btn_select_db.setObjectName("primaryBtn")
        self.btn_select_db.clicked.connect(self.browse_sqlite_db)
        db_layout.addWidget(self.btn_select_db)

        # Path label (pathlib-resolved string)
        self.lbl_db_path = QLabel(self.config["db_path"] or "No POS SQLite database file selected.", db_card)
        self.lbl_db_path.setWordWrap(True)
        db_layout.addWidget(self.lbl_db_path, 1)

        layout.addWidget(db_card)

        # SQLite Schema Mapping Card
        schema_card = QFrame(tab)
        schema_card.setObjectName("card")
        schema_layout = QVBoxLayout(schema_card)
        schema_layout.setContentsMargins(15, 15, 15, 15)

        schema_title = QLabel("Database Table & Columns Settings:", schema_card)
        schema_title.setFont(QFont("Inter", 12, QFont.Bold))
        schema_layout.addWidget(schema_title)

        grid = QGridLayout()
        grid.setSpacing(10)

        # Fields inputs
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

        self.tab_widget.addTab(tab, "SQLite POS Sync")

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

        title = QLabel("Supabase Cloud Credentials", tab)
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

        layout.addWidget(form_card)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Cloud Credentials")

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
        self.config["db_table"] = self.entry_db_table.text().strip()
        self.config["db_col_barcode"] = self.entry_col_barcode.text().strip()
        self.config["db_col_name"] = self.entry_col_name.text().strip()
        self.config["db_col_price"] = self.entry_col_price.text().strip()
        self.save_config()

        return {
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
            db_path = self.config["db_path"]
            if not db_path or not Path(db_path).exists():
                QMessageBox.critical(self, "Error", "Selected SQLite DB file does not exist. Please select a valid file.")
                return

            schema = self.get_current_db_schema_config()
            self.write_log(f"Initializing database watcher for SQL: SELECT {schema['barcode']}, {schema['product_name']}, {schema['price_iqd']} FROM {schema['table']}")

            self.watcher = DatabaseWatcher(
                db_path=db_path,
                query_config=schema,
                sync_callback=self.background_watcher_callback
            )
            
            try:
                self.watcher.start()
                self.btn_toggle_watcher.setText("Stop Sync Watcher")
                # Set custom danger color style directly
                self.btn_toggle_watcher.setStyleSheet("background-color: #f43f5e; color: white;")
                self.lbl_watcher_status.setText("Watcher Status: ACTIVE")
                self.lbl_watcher_status.setStyleSheet("color: #10b981; font-weight: bold;")
                self.write_log("Sync Watcher activated successfully. Listening for SQLite modifications.")
            except Exception as e:
                self.write_log(f"Failed to start watcher: {e}")
                QMessageBox.critical(self, "Error", f"Failed to open/query database: {e}")

    def background_watcher_callback(self, records: list[dict]):
        """
        Triggered by background thread file watcher.
        Uses Qt Bridge to emit logs/synchronization values thread-safely to main GUI thread.
        """
        self.bridge.log_signal.emit(f"SQLite file modification detected. Preparing sync of {len(records)} records...")
        self.bridge.sync_trigger_signal.emit(records)

    def process_background_sync(self, records: list[dict]):
        """Runs safely on the UI thread."""
        if not self.sync_client.is_configured:
            self.write_log("[DRY-RUN] Cloud connection credentials missing. Sync skipped.")
            return

        # Perform bulk upload
        success = self.sync_client.sync_batch(records)
        if success:
            self.write_log(f"Sync complete. Successfully synced {len(records)} products to Supabase.")
        else:
            self.write_log("Sync error: Failed to upload data batch. Check connection.")

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

        try:
            headers = ExcelParser.get_headers(normalized_path)
            if not headers:
                QMessageBox.warning(self, "Excel Warning", "No valid headers found in first row.")
                return
            
            # Show Dialog
            self.open_excel_mapping_popup(normalized_path, headers)
        except Exception as e:
            QMessageBox.critical(self, "Excel Error", f"Error opening workbook: {e}")

    def open_excel_mapping_popup(self, file_path: str, headers: list[str]):
        dialog = QDialog(self)
        dialog.setWindowTitle("Column Mapper")
        dialog.resize(400, 300)
        dialog.setModal(True)
        dialog.setStyleSheet(DARK_THEME_QSS)

        d_layout = QVBoxLayout(dialog)
        d_layout.setSpacing(12)
        d_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Map Excel Column Headers", dialog)
        title.setFont(QFont("Inter", 14, QFont.Bold))
        d_layout.addWidget(title)

        # Heuristics for default headers selection
        def find_closest_header(targets, candidates):
            for t in targets:
                for c in candidates:
                    if t.lower() in c.lower():
                        return c
            return candidates[0] if candidates else ""

        default_barcode = find_closest_header(["barcode", "code", "upc", "ean", "sku"], headers)
        default_name = find_closest_header(["name", "title", "product", "item"], headers)
        default_price = find_closest_header(["price", "cost", "dinar", "iqd"], headers)

        # Barcode combobox
        d_layout.addWidget(QLabel("Barcode Column:", dialog))
        combo_barcode = QComboBox(dialog)
        combo_barcode.addItems(headers)
        combo_barcode.setCurrentText(default_barcode)
        d_layout.addWidget(combo_barcode)

        # Product Name combobox
        d_layout.addWidget(QLabel("Product Name Column:", dialog))
        combo_name = QComboBox(dialog)
        combo_name.addItems(headers)
        combo_name.setCurrentText(default_name)
        d_layout.addWidget(combo_name)

        # Price combobox
        d_layout.addWidget(QLabel("Price Column (IQD):", dialog))
        combo_price = QComboBox(dialog)
        combo_price.addItems(headers)
        combo_price.setCurrentText(default_price)
        d_layout.addWidget(combo_price)

        # Button box
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancel", dialog)
        btn_cancel.clicked.connect(dialog.reject)
        btn_box.addWidget(btn_cancel)

        btn_import = QPushButton("Start Bulk Upload", dialog)
        btn_import.setObjectName("primaryBtn")
        
        def on_import_click():
            mapping = {
                "barcode": combo_barcode.currentText(),
                "product_name": combo_name.currentText(),
                "price_iqd": combo_price.currentText()
            }
            dialog.accept()
            self.write_excel_log("Parsing Excel items with mappings:")
            self.write_excel_log(f"  Barcode -> {mapping['barcode']}")
            self.write_excel_log(f"  Name    -> {mapping['product_name']}")
            self.write_excel_log(f"  Price   -> {mapping['price_iqd']}")
            
            # Run parser in background thread to keep UI alive
            self.run_background_excel_import(file_path, mapping)

        btn_import.clicked.connect(on_import_click)
        btn_box.addWidget(btn_import)
        
        d_layout.addLayout(btn_box)
        dialog.exec()

    def run_background_excel_import(self, file_path: str, mapping: dict):
        class ExcelWorker(QThread):
            finished = Signal(bool, str) # success, message
            
            def __init__(self, client, path, map_data):
                super().__init__()
                self.client = client
                self.path = path
                self.map_data = map_data

            def run(self):
                try:
                    records = ExcelParser.parse_records(self.path, self.map_data)
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

        self.worker = ExcelWorker(self.sync_client, file_path, mapping)
        
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
