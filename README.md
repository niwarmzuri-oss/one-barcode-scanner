# One Barcode - Cross-Platform Sync & Smart Scanner System

This system connects a local Windows or macOS POS system to an in-store mobile barcode scanner web app. Customers scan a single printed QR code, point their phone's camera at a product, and view the price instantly in Iraqi Dinars (IQD).

---

## 1. Cloud Database Setup (Supabase)

To connect the applications, you will need a free project from [Supabase](https://supabase.com/).

### Database Schema SQL
Run this SQL script in your Supabase project's **SQL Editor** to initialize the `products` table and configure Row-Level Security:

```sql
-- Create shop_prices table
CREATE TABLE public.shop_prices (
    barcode TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    price_iqd INTEGER NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.shop_prices ENABLE ROW LEVEL SECURITY;

-- Policy 1: Allow public read-only access for smartphone customers
CREATE POLICY "Allow public read access" 
ON public.shop_prices 
FOR SELECT 
USING (true);

-- Policy 2: Allow the Admin Panel to write items using the Anon public key
CREATE POLICY "Allow public write access" 
ON public.shop_prices 
FOR ALL 
TO anon, authenticated
USING (true) 
WITH CHECK (true);
```

---

## 2. Desktop Admin Panel App (`desktop_app/`)

The Admin Panel is built with **PySide6 (Qt)** to support native cross-platform rendering and file interactions.

### Setup & Run
1. Verify that Python 3.10+ is installed on your computer.
2. In your terminal (macOS/Linux) or Command Prompt/PowerShell (Windows), install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the application:
   ```bash
   python app.py
   ```

### Cross-Platform Path Handling:
- The app uses Python's `pathlib` module to normalize file paths automatically. 
- Windows paths (`C:\POS\database.db`) and macOS POSIX paths (`/Users/admin/POS/database.db`) are correctly parsed, resolving forward and backward slashes without coding modifications.
- SQLite connections are established in read-only mode using native file URIs (`file:/path/to/db?mode=ro`), which prevents file write-locks, allowing the admin app to monitor POS files actively while they are in use by your POS software.

### Packaging into Standalone Installers

#### Windows (Compiling `.exe`)
Using PyInstaller in command prompt:
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "OneBarcode" app.py
```
Find the executable in `dist/OneBarcode.exe`.

#### macOS (Compiling `.app` / `.dmg`)
On macOS:
1. Compile into an app bundle:
   ```bash
   pip install pyinstaller
   pyinstaller --noconsole --onefile --windowed --name "OneBarcode" app.py
   ```
2. (Optional) Create a disk image wrapper (`.dmg`) using `create-dmg`:
   ```bash
   brew install create-dmg
   create-dmg \
     --volname "One Barcode Installer" \
     --window-pos 200 120 \
     --window-size 600 400 \
     --icon-size 100 \
     --icon "OneBarcode.app" 175 120 \
     --hide-extension "OneBarcode.app" \
     --app-drop-link 425 120 \
     "OneBarcode.dmg" \
     "dist/OneBarcode.app"
   ```

> [!NOTE]
> **macOS Security Permissions:** Under macOS Catalina and newer, the operating system may block file watchers from accessing files inside user directories (like `Desktop` or `Documents`) without approval. If the watcher fails to start, grant your compiled app or terminal **Full Disk Access** inside *System Settings > Privacy & Security*.

---

## 3. Tauri Configuration Blueprint (`tauri_blueprint/`)

If you prefer a **Tauri (Rust + React)** application structure:
- **[tauri.conf.json](file:///Users/hardos/AntiGravity%20Projects/One%20Barcode/tauri_blueprint/tauri.conf.json)** lists the build specifications, permissions allowed, and bundle targets (`msi` and `nsis` for Windows, `app` and `dmg` for macOS).
- **[Cargo.toml](file:///Users/hardos/AntiGravity%20Projects/One%20Barcode/tauri_blueprint/Cargo.toml)** outlines Cargo dependencies (such as `notify` for filesystem changes, `calamine` for Excel sheet reading, and `rusqlite` for database communication).
- To initialize a Tauri project, run:
  ```bash
  npm create tauri-app@latest
  ```

---

## 4. Customer Mobile Scanner Web App (`mobile_web/`)

A high-performance HTML/JS mobile browser page designed for customers.

### How to Run Locally for Testing
Serve the web app inside your local Wi-Fi network:
```bash
# Using Python:
python -m http.server 8000

# Or using Node.js:
npx http-server -p 8000
```

### Accessing the Web Page
1. Ensure your computer and smartphone are connected to the **same Wi-Fi network**.
2. Open your smartphone browser and navigate to your computer's local IP address (e.g. `http://192.168.1.50:8000`).
3. Tap **Connection Settings** at the bottom to configure your **Supabase URL** and **Anon Key** (read-only client key).
4. Tap **Start Scanner**, grant camera permissions, and begin scanning barcodes!

*Note: For testing without a live database, the app automatically runs in **Offline Preview Mode** if no Supabase details are supplied, demonstrating price lookups for mock items like "Local Chai" or EAN barcodes.*
