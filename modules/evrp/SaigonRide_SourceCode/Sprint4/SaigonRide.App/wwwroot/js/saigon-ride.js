/* wwwroot/js/saigon-ride.js */
document.addEventListener('DOMContentLoaded', () => {
    refreshWalletBalance();

    // Check if there's an active ride stored locally (for UI state recovery)
    const activeRide = localStorage.getItem('activeRentalId');
    if (activeRide) {
        showActiveRideView();
    }
});

// --- WALLET LOGIC ---
async function refreshWalletBalance() {
    try {
        const res = await fetch('/api/wallet/balance');
        if (res.ok) {
            const data = await res.json();
            document.getElementById('walletBalance').innerText =
                new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(data.balance);
        }
    } catch (err) {
        console.error("Failed to fetch balance", err);
    }
}

async function topUpWallet() {
    const amountStr = prompt("Nhập số tiền muốn nạp (VND) / Enter amount to top up:", "50000");
    if (!amountStr) return;

    const amount = parseInt(amountStr);
    if (amount < 20000) {
        alert("Minimum top-up is 20,000 VND.");
        return;
    }

    try {
        const res = await fetch('/api/wallet/topup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: amount, provider: 'Stripe' }) // Defaulting to Stripe for web
        });

        if (res.ok) {
            const data = await res.json();
            window.location.href = data.url; // Redirect to Stripe Checkout
        } else {
            alert("Error initiating top-up.");
        }
    } catch (err) {
        console.error(err);
    }
}

// --- RIDE LOGIC ---
async function startRide(stationId, vehicleId) {
    if (!confirm("Bắt đầu thuê xe? / Start ride? (Min balance: 20k VND)")) return;

    try {
        const res = await fetch('/api/ride/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stationId: stationId, vehicleId: vehicleId })
        });

        if (res.ok) {
            const rental = await res.json();
            localStorage.setItem('activeRentalId', rental.id);
            localStorage.setItem('rideStartTime', new Date().getTime());
            showActiveRideView();
            refreshWalletBalance();
        } else {
            const error = await res.text();
            alert("Cannot start ride: " + error);
        }
    } catch (err) {
        console.error(err);
    }
}

async function stopRide() {
    const rentalId = localStorage.getItem('activeRentalId');
    if (!rentalId) return;

    // For demo, we assume returning to Station 1 (Ben Thanh Hub). 
    // In production, GPS or QR code scan at the dock provides this.
    const endStationId = 1;

    try {
        const res = await fetch('/api/ride/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rentalId: parseInt(rentalId), endStationId: endStationId })
        });

        if (res.ok) {
            const result = await res.json();
            localStorage.removeItem('activeRentalId');
            localStorage.removeItem('rideStartTime');

            alert(`Ride completed! Fare deducted: ${result.fareDeducted} VND`);
            showStationView();
            refreshWalletBalance();
        } else {
            alert("Error stopping ride.");
        }
    } catch (err) {
        console.error(err);
    }
}

// --- UI STATE MANAGEMENT ---
function showActiveRideView() {
    document.getElementById('stationView').classList.add('hidden');
    document.getElementById('activeRideView').classList.remove('hidden');
    startTimer();
}

function showStationView() {
    document.getElementById('activeRideView').classList.add('hidden');
    document.getElementById('stationView').classList.remove('hidden');
    document.getElementById('rideTimer').innerText = "00:00";
}

function startTimer() {
    const startTime = localStorage.getItem('rideStartTime');
    if (!startTime) return;

    setInterval(() => {
        const now = new Date().getTime();
        const diff = Math.floor((now - startTime) / 1000);
        const mins = String(Math.floor(diff / 60)).padStart(2, '0');
        const secs = String(diff % 60).padStart(2, '0');

        const timerEl = document.getElementById('rideTimer');
        if (timerEl) timerEl.innerText = `${mins}:${secs}`;
    }, 1000);
}