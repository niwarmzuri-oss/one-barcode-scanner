import openpyxl
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ExcelParser:
    """
    Utility class to read Excel spreadsheets and map columns cross-platform.
    """
    @staticmethod
    def get_headers(file_path: str) -> list[str]:
        """
        Loads the Excel workbook and retrieves headers from the first active row.
        Resolves path using pathlib for cross-platform safety.
        """
        try:
            resolved_path = Path(file_path).resolve()
            wb = openpyxl.load_workbook(resolved_path, read_only=True, data_only=True)
            sheet = wb.active
            if not sheet:
                return []
            
            # Read first row for headers
            for row in sheet.iter_rows(max_row=1, values_only=True):
                if row:
                    # Clean up header values (convert to string, strip whitespace, remove None)
                    headers = [str(cell).strip() for cell in row if cell is not None]
                    return headers
            return []
        except Exception as e:
            logging.error(f"Error reading headers from {file_path}: {e}")
            raise e

    @staticmethod
    def parse_records(file_path: str, mapping: dict[str, str]) -> list[dict]:
        """
        Parses rows from Excel file using the mapping dict.
        Mapping dict structure: {
            "barcode": "User Selected Barcode Header",
            "product_name": "User Selected Name Header",
            "price_iqd": "User Selected Price Header"
        }
        Returns a list of dicts: [{"barcode": "...", "product_name": "...", "price_iqd": 0.0}]
        """
        try:
            resolved_path = Path(file_path).resolve()
            wb = openpyxl.load_workbook(resolved_path, read_only=True, data_only=True)
            sheet = wb.active
            if not sheet:
                return []

            # Find columns indexes corresponding to headers
            headers = []
            
            # Read first row to locate column indices (1-based index)
            for row in sheet.iter_rows(max_row=1, values_only=True):
                headers = [str(cell).strip() if cell is not None else "" for cell in row]
                break
            
            barcode_col = mapping.get("barcode")
            name_col = mapping.get("product_name")
            price_col = mapping.get("price_iqd")

            barcode_idx = headers.index(barcode_col) if barcode_col in headers else -1
            name_idx = headers.index(name_col) if name_col in headers else -1
            price_idx = headers.index(price_col) if price_col in headers else -1

            if barcode_idx == -1 or name_idx == -1 or price_idx == -1:
                raise ValueError("Missing mapped columns in Excel file. Please recheck mappings.")

            records = []
            row_count = 0
            
            # Start iterating from row 2 (data rows)
            for row in sheet.iter_rows(min_row=2, values_only=True):
                # Ensure row is not entirely empty
                if not any(cell is not None for cell in row):
                    continue
                
                # Safe bounds check
                barcode_val = row[barcode_idx] if barcode_idx < len(row) else None
                name_val = row[name_idx] if name_idx < len(row) else None
                price_val = row[price_idx] if price_idx < len(row) else None

                # Clean barcode
                if barcode_val is None:
                    continue
                
                # Check if it is a numeric float or int, convert to clean integer string to avoid scientific notation
                if isinstance(barcode_val, (int, float)):
                    try:
                        barcode_str = str(int(round(float(barcode_val))))
                    except (ValueError, TypeError):
                        barcode_str = str(barcode_val).strip().split('.')[0]
                else:
                    barcode_str = str(barcode_val).strip().split('.')[0]
                    
                if not barcode_str or barcode_str == "None":
                    continue

                # Clean product name
                name_str = str(name_val).strip() if name_val is not None else "Unnamed Product"

                # Clean price
                price_num = 0
                if price_val is not None:
                    try:
                        # Strip currency symbols and commas if it was read as string
                        val_str = str(price_val).replace(',', '').replace('IQD', '').replace('ID', '').strip()
                        price_num = int(round(float(val_str)))
                    except ValueError:
                        logging.warning(f"Row {row_count+2}: Invalid price value '{price_val}'. Setting to 0.")

                records.append({
                    "barcode": barcode_str,
                    "product_name": name_str,
                    "price_iqd": price_num
                })
                row_count += 1

            logging.info(f"ExcelParser parsed {len(records)} records from {file_path}.")
            return records
            
        except Exception as e:
            logging.error(f"Error parsing records from {file_path}: {e}")
            raise e
