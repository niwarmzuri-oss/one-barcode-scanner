import urllib.request
import urllib.parse
from pathlib import Path

def generate_qr(url: str, output_name: str = "main_store_qr.png"):
    """
    Downloads a high-definition, printable QR code for the given URL
    using a free secure API with zero Python dependencies.
    """
    encoded_url = urllib.parse.quote_plus(url)
    # 500x500 high-resolution QR code
    api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=500x500&data={encoded_url}"
    
    output_path = Path(__file__).parent / output_name
    try:
        print(f"Fetching QR Code from API for: {url}")
        urllib.request.urlretrieve(api_url, output_path)
        print(f"Success! High-resolution QR Code image saved to:")
        print(f"  {output_path.resolve()}")
    except Exception as e:
        print(f"Failed to download QR code: {e}")

if __name__ == "__main__":
    url_input = input("Enter your deployed HTTPS website URL: ").strip()
    if url_input:
        generate_qr(url_input)
    else:
        print("Error: URL cannot be empty.")
