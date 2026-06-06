// Global Application State
let html5QrcodeScanner = null;
let isScanning = false;
let isTorchOn = false;
let cameraTrack = null;

// Supabase Credentials
let config = {
    supabaseUrl: "https://hthrzecjdnopsfcaowpm.supabase.co",
    supabaseKey: "sb_publishable_p6TTTnE9TKs3uWEPaycx5w_da92W15l"
};

// Mock product inventory for testing and local/preview mode
const MOCK_PRODUCTS = {
    "9780201633610": { name: "Design Patterns Book", price: 45000 },
    "123456789": { name: "Local Chai (500g)", price: 4250 },
    "6281006803212": { name: "Alokozay Green Tea", price: 2500 },
    "01234567": { name: "Sparkling Water 330ml", price: 750 },
    "00000000": { name: "Fresh Iraqi Samoon (5 pcs)", price: 1000 }
};

// UI Elements
const btnScanTrigger = document.getElementById("btn-scan-trigger");
const btnTorchToggle = document.getElementById("btn-torch-toggle");
const btnScanNext = document.getElementById("btn-scan-next");
const btnSaveConfig = document.getElementById("btn-save-config");
const btnResetConfig = document.getElementById("btn-reset-config");
const inputSbUrl = document.getElementById("input-sb-url");
const inputSbKey = document.getElementById("input-sb-key");

const scannerSplash = document.getElementById("scanner-splash");
const viewfinder = document.getElementById("viewfinder");
const setupBanner = document.getElementById("setup-banner");
const configDrawer = document.getElementById("config-drawer");

const priceModal = document.getElementById("price-modal");
const modalStatusIcon = document.getElementById("modal-status-icon");
const resultProductName = document.getElementById("result-product-name");
const resultProductBarcode = document.getElementById("result-product-barcode");
const resultProductPrice = document.getElementById("result-product-price");
const toast = document.getElementById("toast");

// Initialize App
window.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    setupEventListeners();
});

// Load config settings from browser storage
function loadSettings() {
    const savedUrl = localStorage.getItem("ob_supabase_url");
    const savedKey = localStorage.getItem("ob_supabase_key");
    
    if (savedUrl && savedKey) {
        config.supabaseUrl = savedUrl;
        config.supabaseKey = savedKey;
    }
    
    // Prefill values
    inputSbUrl.value = config.supabaseUrl;
    inputSbKey.value = config.supabaseKey;
    
    // If we have credentials (either default or saved), hide the setup alert banner
    if (config.supabaseUrl && config.supabaseKey) {
        setupBanner.classList.add("hidden");
    } else {
        setupBanner.classList.remove("hidden");
        configDrawer.setAttribute("open", "");
    }
}

// Save config settings to browser storage
function saveSettings() {
    const url = inputSbUrl.value.trim().replace(/\/$/, "");
    const key = inputSbKey.value.trim();
    
    if (!url || !key) {
        showToast("Please fill in both Supabase URL and Anon Key.");
        return;
    }
    
    localStorage.setItem("ob_supabase_url", url);
    localStorage.setItem("ob_supabase_key", key);
    
    config.supabaseUrl = url;
    config.supabaseKey = key;
    
    setupBanner.classList.add("hidden");
    configDrawer.removeAttribute("open");
    showToast("Connection settings saved successfully!", 2000);
}

// Clear saved config and restore defaults
function resetSettings() {
    localStorage.removeItem("ob_supabase_url");
    localStorage.removeItem("ob_supabase_key");
    
    // Default credentials
    config.supabaseUrl = "https://hthrzecjdnopsfcaowpm.supabase.co";
    config.supabaseKey = "sb_publishable_p6TTTnE9TKs3uWEPaycx5w_da92W15l";
    
    inputSbUrl.value = config.supabaseUrl;
    inputSbKey.value = config.supabaseKey;
    
    setupBanner.classList.add("hidden");
    configDrawer.removeAttribute("open");
    showToast("Settings reset to default credentials!", 2000);
}

// Setup click and action event listeners
function setupEventListeners() {
    btnScanTrigger.addEventListener("click", toggleScanner);
    btnTorchToggle.addEventListener("click", toggleTorch);
    btnScanNext.addEventListener("click", scanNextItem);
    btnSaveConfig.addEventListener("click", saveSettings);
    btnResetConfig.addEventListener("click", resetSettings);
    
    // Close modal if user clicks outside of modal content (on the handle or overlay)
    priceModal.addEventListener("click", (e) => {
        if (e.target === priceModal || e.target.classList.contains("modal-handle")) {
            scanNextItem();
        }
    });
}

// Show clean top toast alert
function showToast(message, duration = 3000) {
    toast.textContent = message;
    toast.classList.remove("hidden");
    toast.style.opacity = "1";
    
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.classList.add("hidden"), 300);
    }, duration);
}

// Toggle camera scanner execution state
async function toggleScanner() {
    if (isScanning) {
        stopScanner();
    } else {
        startScanner();
    }
}

// Start Camera Stream & Decoding loop
async function startScanner() {
    if (html5QrcodeScanner) return;
    
    // Reset States
    scannerSplash.classList.add("hidden");
    viewfinder.classList.remove("hidden");
    btnScanTrigger.innerHTML = '<span class="btn-icon">⏹</span> Stop Scanner';
    
    html5QrcodeScanner = new Html5Qrcode("scanner-view");
    isScanning = true;
    
    const qrCodeSuccessCallback = (decodedText, decodedResult) => {
        // Trigger haptic vibration on mobile devices
        if (navigator.vibrate) {
            navigator.vibrate(100);
        }
        
        // Success feedback audio (soft synth beep)
        playBeep();
        
        // Stop scanning after successful barcode read
        stopScanner();
        
        // Query product details from database
        fetchProductDetails(decodedText);
    };
    
    try {
        // Query available camera devices (asks for permissions if not granted)
        const devices = await Html5Qrcode.getCameras();
        if (!devices || devices.length === 0) {
            throw new Error("No camera devices found on this device.");
        }
        
        // Find best camera (prefer rear/back camera on phones)
        let cameraId = devices[0].id;
        for (const device of devices) {
            const label = device.label.toLowerCase();
            if (label.includes("back") || label.includes("rear") || label.includes("environment")) {
                cameraId = device.id;
                break;
            }
        }
        
        // On iOS devices, if multiple cameras exist but labels are empty or don't match,
        // the last camera in the list is typically the main rear camera.
        if (devices.length > 1 && cameraId === devices[0].id) {
            cameraId = devices[devices.length - 1].id;
        }

        // Start scanning using the specific resolved cameraId
        await html5QrcodeScanner.start(
            cameraId,
            {
                fps: 15,
                qrbox: 250 // Static box width for scanner view
            },
            qrCodeSuccessCallback,
            (errorMessage) => {}
        );
        
        // Detect camera stream and check torch capabilities
        setTimeout(() => {
            detectTorchSupport();
        }, 1000);
        
    } catch (err) {
        console.error("Camera access failed", err);
        showToast("Error: Could not access camera. Make sure permissions are granted.");
        stopScanner();
    }
}

// Terminate camera stream safely
async function stopScanner() {
    isScanning = false;
    isTorchOn = false;
    cameraTrack = null;
    btnTorchToggle.classList.add("hidden");
    
    viewfinder.classList.add("hidden");
    scannerSplash.classList.remove("hidden");
    btnScanTrigger.innerHTML = '<span class="btn-icon">📷</span> Start Scanner';
    
    if (html5QrcodeScanner) {
        try {
            await html5QrcodeScanner.stop();
        } catch (e) {
            console.warn("Error while stopping scanner camera:", e);
        }
        html5QrcodeScanner = null;
    }
}

// Check if the current video stream track supports a torch / flashlight
function detectTorchSupport() {
    if (!html5QrcodeScanner) return;
    
    try {
        const scannerElement = document.querySelector("#scanner-view video");
        if (!scannerElement) return;
        
        const stream = scannerElement.srcObject;
        if (!stream) return;
        
        cameraTrack = stream.getVideoTracks()[0];
        if (!cameraTrack) return;
        
        const capabilities = cameraTrack.getCapabilities();
        
        // If device camera supports torch capability, show the button
        if (capabilities.torch) {
            btnTorchToggle.classList.remove("hidden");
        }
    } catch (e) {
        console.warn("Flashlight capability checking not supported by browser:", e);
    }
}

// Toggle device camera flashlight
async function toggleTorch() {
    if (!cameraTrack) return;
    
    try {
        isTorchOn = !isTorchOn;
        await cameraTrack.applyConstraints({
            advanced: [{ torch: isTorchOn }]
        });
        
        if (isTorchOn) {
            btnTorchToggle.classList.add("btn-primary");
            btnTorchToggle.classList.remove("btn-secondary");
        } else {
            btnTorchToggle.classList.remove("btn-primary");
            btnTorchToggle.classList.add("btn-secondary");
        }
    } catch (e) {
        console.error("Failed to toggle flashlight", e);
        showToast("Flashlight controls not accessible.");
    }
}

// Play a friendly synth success beep
function playBeep() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(880, audioCtx.currentTime); // High pitch note A5
        gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.12);
    } catch (e) {
        // AudioContext browser restrictions or lack of support, ignore
    }
}

// Fetch price and metadata from Supabase
async function fetchProductDetails(barcode) {
    // Show Loading inside Modal sheet immediately
    resultProductName.textContent = "Checking prices...";
    resultProductBarcode.textContent = `Barcode: ${barcode}`;
    resultProductPrice.textContent = "--";
    
    // Reset status icon style
    modalStatusIcon.textContent = "✓";
    modalStatusIcon.classList.remove("error");
    modalStatusIcon.classList.add("success");
    
    priceModal.classList.add("active");
    
    // Check if cloud backend is set up
    const hasCloud = config.supabaseUrl && config.supabaseKey;
    
    if (!hasCloud) {
        // Fallback to local MOCK database preview
        setTimeout(() => {
            const product = MOCK_PRODUCTS[barcode];
            if (product) {
                displayProduct(product.name, barcode, product.price);
            } else {
                displayProductNotFound(barcode);
            }
            showToast("Showing mock demo data. Configure Supabase in drawer for live database.", 4000);
        }, 800);
        return;
    }
    
    const url = `${config.supabaseUrl}/rest/v1/shop_prices?barcode=eq.${encodeURIComponent(barcode)}&select=*`;
    try {
        const response = await fetch(url, {
            method: "GET",
            headers: {
                "apikey": config.supabaseKey,
                "Authorization": `Bearer ${config.supabaseKey}`,
                "Content-Type": "application/json"
            }
        });
        
        if (!response.ok) {
            throw new Error(`API returned status ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data && data.length > 0) {
            const item = data[0];
            displayProduct(item.product_name, item.barcode, item.price_iqd);
        } else {
            displayProductNotFound(barcode);
        }
    } catch (err) {
        console.error("Error fetching product data", err);
        showToast("Network error. Checking mock data instead...");
        
        // Network fallback to mock data so scanner is testable
        const product = MOCK_PRODUCTS[barcode];
        if (product) {
            displayProduct(product.name + " (Offline Preview)", barcode, product.price);
        } else {
            resultProductName.textContent = "Connection Error";
            resultProductPrice.textContent = "Error";
            showToast("Failed to connect to Supabase database. Verify configuration settings.");
        }
    }
}

// Formats number into readable standard IQD (e.g. 5250 -> "5,250")
function formatIQD(price) {
    return Number(price).toLocaleString("en-US");
}

// Update modal sheet details with product info
function displayProduct(name, barcode, price) {
    modalStatusIcon.textContent = "✓";
    modalStatusIcon.classList.remove("error");
    modalStatusIcon.classList.add("success");
    resultProductName.textContent = name;
    resultProductBarcode.textContent = `Barcode: ${barcode}`;
    resultProductPrice.textContent = formatIQD(price);
}

// Display product not found details
function displayProductNotFound(barcode) {
    modalStatusIcon.textContent = "✗";
    modalStatusIcon.classList.remove("success");
    modalStatusIcon.classList.add("error");
    resultProductName.textContent = "Product Not Found";
    resultProductBarcode.textContent = `Barcode: ${barcode}`;
    resultProductPrice.textContent = "N/A";
    showToast(`Barcode "${barcode}" is not registered in the database.`, 5000);
}

// Close bottom sheet modal and restart scanner automatically
function scanNextItem() {
    priceModal.classList.remove("active");
    // Restart scanning loop
    setTimeout(() => {
        if (!isScanning) {
            startScanner();
        }
    }, 300);
}
