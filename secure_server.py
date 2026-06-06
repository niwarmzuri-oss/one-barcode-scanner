import ssl
import http.server
import socket
import os
import subprocess
import sys
from pathlib import Path

# Paths configurations
BASE_DIR = Path(__file__).parent.resolve()
MOBILE_WEB_DIR = BASE_DIR / "mobile_web"
CERT_FILE = BASE_DIR / "cert.pem"
KEY_FILE = BASE_DIR / "key.pem"

def generate_ssl_certs() -> bool:
    """
    Generates a self-signed SSL certificate using macOS native openssl.
    """
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print("Generating a self-signed SSL certificate for local HTTPS testing...")
        cmd = [
            "openssl", "req", "-new", "-x509", 
            "-keyout", str(KEY_FILE), 
            "-out", str(CERT_FILE), 
            "-days", "365", "-nodes",
            "-subj", "/C=IQ/O=RetailStore/CN=LocalBarcodeScanner"
        ]
        try:
            # Run openssl command
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("SSL Certificate generated successfully (cert.pem / key.pem created).")
        except Exception as e:
            print(f"Error generating SSL certificate: {e}")
            print("Please make sure 'openssl' is installed and available in your terminal path.")
            return False
    return True

def get_local_ip() -> str:
    """
    Gets the local IP address of this Mac on the Wi-Fi network.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to connect successfully, just used to read local socket interface
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def run_https_server():
    if not generate_ssl_certs():
        sys.exit(1)

    # Change working directory to serve the mobile_web files
    if not MOBILE_WEB_DIR.exists():
        print(f"Error: mobile_web folder not found at: {MOBILE_WEB_DIR}")
        sys.exit(1)
        
    os.chdir(str(MOBILE_WEB_DIR))
    
    port = 8443
    server_address = ('0.0.0.0', port)
    
    # Native Python HTTP request handler
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.HTTPServer(server_address, handler)
    
    # Configure SSL
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    
    # Wrap server socket with SSL context
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    local_ip = get_local_ip()
    print("\n" + "="*75)
    print("           SECURE LOCAL HTTPS TESTING SERVER ACTIVE")
    print("="*75)
    print(f"To test the camera barcode scanner on your smartphone:")
    print(f"1. Connect your phone to the same Wi-Fi network.")
    print(f"2. Open Safari (iOS) or Chrome (Android) and navigate to:")
    print(f"   👉 https://{local_ip}:{port}")
    print("\n* Safari will show a warning: 'This Connection is Not Private'")
    print("  -> Click 'Show Details' / 'Advanced'")
    print("  -> Click 'Visit This Website' / 'Proceed' to bypass and trust the link.")
    print("="*75)
    print("Press Ctrl+C in this terminal to stop the server.\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping secure HTTPS server...")
        httpd.server_close()
        print("Server stopped.")

if __name__ == "__main__":
    run_https_server()
