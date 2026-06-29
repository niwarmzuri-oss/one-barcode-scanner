// Global Application State
let isScanning = false;
let isTorchOn = false;
let cameraTrack = null;
let basket = [];
let lastDecodedCode = null;
let consecutiveMatches = 0;
let currentProduct = null;

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

// Basket UI Elements
const btnAddToBasket = document.getElementById("btn-add-to-basket");
const basketBar = document.getElementById("basket-bar");
const basketBarCount = document.getElementById("basket-bar-count");
const basketBarTotal = document.getElementById("basket-bar-total");
const btnOpenBasket = document.getElementById("btn-open-basket");

const btnHeaderCart = document.getElementById("btn-header-cart");
const headerCartBadge = document.getElementById("header-cart-badge");

const basketModal = document.getElementById("basket-modal");
const basketItems = document.getElementById("basket-items");
const basketGrandTotal = document.getElementById("basket-grand-total");
const btnCloseBasket = document.getElementById("btn-close-basket");
const btnClearBasket = document.getElementById("btn-clear-basket");

// Manual Entry UI Elements
const inputManualBarcode = document.getElementById("input-manual-barcode");
const btnManualSubmit = document.getElementById("btn-manual-submit");

// Initialize App
window.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    loadBasket();
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
    
    // Add to Basket button listener
    btnAddToBasket.addEventListener("click", addCurrentToBasket);
    
    // Floating bar / View Basket toggle and header cart button
    btnOpenBasket.addEventListener("click", openBasket);
    btnHeaderCart.addEventListener("click", openBasket);
    
    // Close basket modal actions
    btnCloseBasket.addEventListener("click", closeBasket);
    btnClearBasket.addEventListener("click", clearBasket);
    
    // Manual Barcode Entry event listeners
    btnManualSubmit.addEventListener("click", handleManualBarcodeSubmit);
    inputManualBarcode.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            handleManualBarcodeSubmit();
        }
    });
    
    // Close modal if user clicks outside of modal content (on the handle or overlay)
    priceModal.addEventListener("click", (e) => {
        if (e.target === priceModal || e.target.classList.contains("modal-handle")) {
            scanNextItem();
        }
    });

    // Close basket modal if user clicks outside of modal content
    basketModal.addEventListener("click", (e) => {
        if (e.target === basketModal || e.target.classList.contains("modal-handle")) {
            closeBasket();
        }
    });

    // Event delegation for item adjustments and deletes inside the basket modal
    basketItems.addEventListener("click", handleBasketItemClick);

    // Register Quagga barcode detected callback once
    if (typeof Quagga !== 'undefined') {
        Quagga.onDetected(handleBarcodeDetected);
    }
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

// Start Camera Stream & Decoding loop using Quagga2
async function startScanner() {
    if (isScanning) return;
    
    // Reset States
    scannerSplash.classList.add("hidden");
    viewfinder.classList.remove("hidden");
    btnScanTrigger.innerHTML = '<span class="btn-icon">⏹</span> Stop Scanner';
    
    isScanning = true;
    
    // Clear consecutive match trackers
    lastDecodedCode = null;
    consecutiveMatches = 0;
    
    Quagga.init({
        inputStream: {
            name: "LiveStream",
            type: "LiveStream",
            target: document.querySelector("#scanner-view"),
            constraints: {
                facingMode: "environment",
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        },
        locator: {
            patchSize: "medium",
            halfSample: true
        },
        numOfWorkers: 2,
        decoder: {
            readers: [
                "ean_reader",
                "ean_8_reader",
                "upc_reader",
                "upc_e_reader",
                "code_128_reader"
            ]
        },
        locate: true
    }, function(err) {
        if (err) {
            console.error("Quagga initialization failed:", err);
            showToast("Error: Could not access camera. Make sure permissions are granted.");
            stopScanner();
            return;
        }
        
        Quagga.start();
        
        // Detect camera stream and check torch capabilities
        setTimeout(() => {
            detectTorchSupport();
        }, 1000);
    });
}

// Terminate camera stream safely using Quagga2
async function stopScanner() {
    isScanning = false;
    isTorchOn = false;
    cameraTrack = null;
    btnTorchToggle.classList.add("hidden");
    
    viewfinder.classList.add("hidden");
    scannerSplash.classList.remove("hidden");
    btnScanTrigger.innerHTML = '<span class="btn-icon">📷</span> Start Scanner';
    
    try {
        Quagga.stop();
    } catch (e) {
        // scanner might not be running, safe to catch
    }
}

// Check if the current video stream track supports a torch / flashlight
function detectTorchSupport() {
    try {
        cameraTrack = Quagga.CameraAccess.getActiveTrack();
        if (!cameraTrack) return;
        
        const capabilities = cameraTrack.getCapabilities();
        
        // If device camera supports torch capability, show the button
        if (capabilities.torch) {
            btnTorchToggle.classList.remove("hidden");
        }

        // Apply auto-zoom if supported to ensure focus from a distance
        if (capabilities.zoom) {
            const minZoom = capabilities.zoom.min || 1.0;
            const maxZoom = capabilities.zoom.max || 1.0;
            // A target zoom of 2.0x is ideal for barcode scanners to read EANs instantly
            const targetZoom = Math.min(2.0, maxZoom);
            
            if (targetZoom > minZoom) {
                cameraTrack.applyConstraints({
                    advanced: [{ zoom: targetZoom }]
                }).then(() => {
                    console.log(`Auto-zoom applied: ${targetZoom}x`);
                }).catch(err => {
                    console.warn("Failed to apply auto-zoom constraint:", err);
                });
            }
        }
    } catch (e) {
        console.warn("Camera track capability checking not supported by browser:", e);
    }
}

// Filter detected barcodes over consecutive frames to avoid errors, then show results
function handleBarcodeDetected(data) {
    if (!isScanning) return;
    const decodedText = data.codeResult.code;
    if (!decodedText) return;
    
    // We require the barcode to match in 2 consecutive frames to prevent false decodes
    if (decodedText === lastDecodedCode) {
        consecutiveMatches++;
    } else {
        lastDecodedCode = decodedText;
        consecutiveMatches = 1;
        return; // wait for next frame
    }
    
    if (consecutiveMatches < 2) {
        return; // wait for consecutive match
    }
    
    // Successful match! Reset filter variables
    lastDecodedCode = null;
    consecutiveMatches = 0;
    isScanning = false;
    
    if (navigator.vibrate) {
        navigator.vibrate(100);
    }
    playBeep();
    fetchProductDetails(decodedText);
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
    // Reset currently selected product and hide basket action during loading
    currentProduct = null;
    btnAddToBasket.style.display = "none";
    
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
        }, 400); // short background delay for mock
        return;
    }
    
    const cleanBarcode = barcode.trim();
    const variations = [cleanBarcode];
    if (cleanBarcode.startsWith('0')) {
        variations.push(cleanBarcode.replace(/^0+/, ''));
    } else {
        variations.push('0' + cleanBarcode);
    }
    
    let foundItem = null;
    try {
        for (const code of variations) {
            const timestamp = Date.now();
            const url = `${config.supabaseUrl}/rest/v1/shop_prices?barcode=eq.${encodeURIComponent(code)}&select=*&_t=${timestamp}`;
            const response = await fetch(url, {
                method: "GET",
                cache: "no-store",
                headers: {
                    "apikey": config.supabaseKey,
                    "Authorization": `Bearer ${config.supabaseKey}`,
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache"
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data && data.length > 0) {
                    foundItem = data[0];
                    break;
                }
            }
        }
        
        if (foundItem) {
            displayProduct(foundItem.product_name, foundItem.barcode, foundItem.price_iqd);
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
            currentProduct = null;
            btnAddToBasket.style.display = "none";
            
            // Stop camera and show connection error modal sheet
            stopScanner();
            
            modalStatusIcon.textContent = "✗";
            modalStatusIcon.classList.remove("success");
            modalStatusIcon.classList.add("error");
            resultProductName.textContent = "Connection Error";
            resultProductBarcode.textContent = `Barcode: ${barcode}`;
            resultProductPrice.textContent = "Error";
            
            priceModal.classList.add("active");
            
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
    currentProduct = { name, barcode, price };
    btnAddToBasket.style.display = ""; // Show the Add to Basket button
    
    modalStatusIcon.textContent = "✓";
    modalStatusIcon.classList.remove("error");
    modalStatusIcon.classList.add("success");
    resultProductName.textContent = name;
    resultProductBarcode.textContent = `Barcode: ${barcode}`;
    resultProductPrice.textContent = formatIQD(price);
    
    // Stop camera feed now that the result is ready to display
    stopScanner();
    
    // Slide up modal ONLY after the content is fully loaded
    priceModal.classList.add("active");
}

// Display product not found details
function displayProductNotFound(barcode) {
    currentProduct = null;
    btnAddToBasket.style.display = "none"; // Hide the Add to Basket button
    
    modalStatusIcon.textContent = "✗";
    modalStatusIcon.classList.remove("success");
    modalStatusIcon.classList.add("error");
    resultProductName.textContent = "Product Not Found";
    resultProductBarcode.textContent = `Barcode: ${barcode}`;
    resultProductPrice.textContent = "N/A";
    
    // Stop camera feed
    stopScanner();
    
    // Slide up modal sheet
    priceModal.classList.add("active");
    
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

// ==========================================
// SHOPPING BASKET STATE & ACTIONS
// ==========================================

// Load basket state from localStorage
function loadBasket() {
    try {
        const savedBasket = localStorage.getItem("ob_shopping_basket");
        if (savedBasket) {
            basket = JSON.parse(savedBasket);
        } else {
            basket = [];
        }
    } catch (e) {
        console.error("Failed to load basket:", e);
        basket = [];
    }
    renderBasket();
}

// Save basket state to localStorage
function saveBasket() {
    try {
        localStorage.setItem("ob_shopping_basket", JSON.stringify(basket));
    } catch (e) {
        console.error("Failed to save basket:", e);
    }
}

// Add currently scanned product to the shopping basket
function addCurrentToBasket() {
    if (!currentProduct) {
        showToast("No product selected to add.");
        return;
    }
    
    const existingIndex = basket.findIndex(item => item.barcode === currentProduct.barcode);
    if (existingIndex > -1) {
        basket[existingIndex].quantity += 1;
    } else {
        basket.push({
            barcode: currentProduct.barcode,
            name: currentProduct.name,
            price: currentProduct.price,
            quantity: 1
        });
    }
    
    saveBasket();
    renderBasket();
    
    // Auto close product modal and restart camera
    priceModal.classList.remove("active");
    showToast(`Added "${currentProduct.name}" to basket!`, 2000);
    
    currentProduct = null;
    
    setTimeout(() => {
        if (!isScanning) {
            startScanner();
        }
    }, 300);
}

// Render dynamic basket interface
function renderBasket() {
    // Clear dynamic list
    basketItems.innerHTML = "";
    
    let totalCount = 0;
    let grandTotal = 0;
    
    if (basket.length === 0) {
        basketItems.innerHTML = '<div class="basket-empty-msg">Your basket is empty</div>';
        basketBar.classList.add("hidden");
    } else {
        basket.forEach(item => {
            totalCount += item.quantity;
            const itemTotal = item.price * item.quantity;
            grandTotal += itemTotal;
            
            const row = document.createElement("div");
            row.className = "basket-item";
            row.innerHTML = `
                <div class="basket-item-info">
                    <div class="basket-item-name">${escapeHTML(item.name)}</div>
                    <div class="basket-item-meta">${formatIQD(item.price)} IQD | Barcode: ${item.barcode}</div>
                </div>
                <div class="basket-item-actions">
                    <div class="basket-qty-control">
                        <button class="btn-qty btn-qty-minus" data-barcode="${item.barcode}">-</button>
                        <span class="basket-qty-val">${item.quantity}</span>
                        <button class="btn-qty btn-qty-plus" data-barcode="${item.barcode}">+</button>
                    </div>
                    <div class="basket-item-price">${formatIQD(itemTotal)}</div>
                    <button class="btn-delete-item" data-barcode="${item.barcode}" aria-label="Remove item">✕</button>
                </div>
            `;
            basketItems.appendChild(row);
        });
        
        // Render floating indicator
        basketBar.classList.remove("hidden");
    }
    
    // Update total count labels & totals
    basketBarCount.textContent = totalCount;
    basketBarTotal.textContent = `${formatIQD(grandTotal)} IQD`;
    basketGrandTotal.textContent = `${formatIQD(grandTotal)} IQD`;

    // Update header cart badge
    if (totalCount > 0) {
        headerCartBadge.textContent = totalCount;
        headerCartBadge.classList.remove("hidden");
    } else {
        headerCartBadge.classList.add("hidden");
    }
}

// Simple HTML escaping helper for display safety
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

// Handle basket action buttons click delegation
function handleBasketItemClick(e) {
    const target = e.target;
    const barcode = target.getAttribute("data-barcode");
    if (!barcode) return;
    
    if (target.classList.contains("btn-qty-plus")) {
        updateQuantity(barcode, 1);
    } else if (target.classList.contains("btn-qty-minus")) {
        updateQuantity(barcode, -1);
    } else if (target.classList.contains("btn-delete-item")) {
        removeBasketItem(barcode);
    }
}

// Update item quantity inside the basket
function updateQuantity(barcode, delta) {
    const index = basket.findIndex(item => item.barcode === barcode);
    if (index === -1) return;
    
    basket[index].quantity += delta;
    if (basket[index].quantity <= 0) {
        basket.splice(index, 1);
    }
    
    saveBasket();
    renderBasket();
}

// Remove item entirely from the basket
function removeBasketItem(barcode) {
    const index = basket.findIndex(item => item.barcode === barcode);
    if (index === -1) return;
    
    const name = basket[index].name;
    basket.splice(index, 1);
    
    saveBasket();
    renderBasket();
    showToast(`Removed "${name}" from basket.`, 2000);
}

// Clear all basket contents after confirmation
function clearBasket() {
    if (basket.length === 0) return;
    
    if (confirm("Are you sure you want to clear your shopping basket?")) {
        basket = [];
        saveBasket();
        renderBasket();
        closeBasket();
        showToast("Basket cleared.", 2000);
    }
}

// Open basket modal sheet and pause camera
function openBasket() {
    if (isScanning) {
        stopScanner();
    }
    basketModal.classList.add("active");
}

// Close basket modal sheet and resume scanning
function closeBasket() {
    basketModal.classList.remove("active");
    setTimeout(() => {
        if (!isScanning && !priceModal.classList.contains("active")) {
            startScanner();
        }
    }, 300);
}

// Handle manual barcode input submission
function handleManualBarcodeSubmit() {
    const barcode = inputManualBarcode.value.trim();
    if (!barcode) {
        showToast("Please enter a barcode number first.");
        return;
    }
    
    // Stop scanner camera if currently running to focus on results modal
    if (isScanning) {
        stopScanner();
    }
    
    // Clear input field for next search
    inputManualBarcode.value = "";
    
    // Fetch product details for manual barcode (this will display it in priceModal)
    fetchProductDetails(barcode);
}
