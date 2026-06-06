import sys

try:
    import qrcode
    from PIL import Image
except ImportError:
    print("\n" + "="*70)
    print("WARNING: Required libraries are missing!")
    print("Please install them by running the following command in your terminal:")
    print("    pip3 install qrcode pillow")
    print("="*70 + "\n")
    sys.exit(1)

def main():
    print("--- QR Code Generator ---")
    url = input("Enter your deployed HTTPS website URL: ").strip()
    if not url:
        print("Error: URL cannot be empty.")
        return

    try:
        # Create a QR code instance with high error correction (perfect for physical prints)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=15, # High resolution box size
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Generate image using PIL (Pillow) back-end
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save automatically as qrcode.png in the current directory
        output_filename = "qrcode.png"
        img.save(output_filename)
        
        print(f"\nSuccess! High-resolution QR code saved as '{output_filename}' in the root directory.")
    except Exception as e:
        print(f"Failed to generate QR code: {e}")

if __name__ == "__main__":
    main()
