import sys
from supabase import create_client, Client
from pathlib import Path

# Load config settings to reuse credentials
CONFIG_FILE = Path(__file__).parent / "desktop_app" / "config.json"
if not CONFIG_FILE.exists():
    # Fallback to current directory config
    CONFIG_FILE = Path(__file__).parent / "config.json"

def get_credentials():
    if CONFIG_FILE.exists():
        import json
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config.get("supabase_url"), config.get("supabase_key")
        except Exception:
            pass
    return None, None

def register_item(barcode: str, name: str, price: int):
    url, key = get_credentials()
    if not url or not key:
        print("Error: Could not load Supabase URL/Key from config.json. Please run the desktop app first to configure it.")
        return

    try:
        supabase: Client = create_client(url, key)
        payload = {
            "barcode": str(barcode).strip(),
            "product_name": str(name).strip(),
            "price_iqd": int(price)
        }
        
        print(f"Registering item in Supabase table 'shop_prices':")
        print(f"  Barcode: {payload['barcode']}")
        print(f"  Name:    {payload['product_name']}")
        print(f"  Price:   {payload['price_iqd']} IQD")
        
        # Upsert the product
        supabase.table("shop_prices").upsert(payload).execute()
        print("\nSuccess! Product has been registered in your live database.")
        print("Try scanning the barcode again with your phone!")
    except Exception as e:
        print(f"Error registering product: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python3 register_product.py <barcode> <product_name> <price_iqd>")
        print("\nExample:")
        print("  python3 register_product.py 8690632025732 \"Chocolate Wafer\" 750")
        sys.exit(1)
        
    barcode_val = sys.argv[1]
    name_val = sys.argv[2]
    try:
        price_val = int(sys.argv[3])
    except ValueError:
        print("Error: Price must be a whole number.")
        sys.exit(1)
        
    register_item(barcode_val, name_val, price_val)
