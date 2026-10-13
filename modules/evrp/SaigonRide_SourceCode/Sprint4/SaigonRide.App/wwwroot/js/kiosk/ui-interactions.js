// ui-interactions.js

const KioskState = {
    kioskToken:        null,
    userToken:         null,
    currentRentalId:   null,
    currentDepositAmt: 0,
    otpEmail:          null,
    currentState:      null,
    selectedVehicleId: null,
    signalRConnection: null,
    pendingToken:      null,
};

const $   = id => document.getElementById(id);
const fmt = n  => n != null ? n.toLocaleString('vi-VN') + ' VNĐ' : 'N/A';

let timerInterval   = null;
let pollingInterval = null;

function startCountdown(seconds) {
    clearInterval(timerInterval);
    let timer = seconds;
    timerInterval = setInterval(() => {
        const el = $('countdownTimer');
        if (el) el.textContent = `${String(Math.floor(timer / 60)).padStart(2,'0')}:${String(timer % 60).padStart(2,'0')}`;
        if (--timer < 0) {
            stopAll();
            goToState('Error', { message: 'Phiên giao dịch đã hết hạn. Vui lòng thử lại.' });
        }
    }, 1000);
}

function startPolling(rentalId) {
    (async () => {
        try {
            KioskState.signalRConnection = await KioskSignalR.connect();
            await KioskSignalR.joinRental(rentalId);
            KioskSignalR.onStatusChanged(data => {
                if (data.status === 'Active') {
                    stopAll();
                    goToState('Success', { vehicleId: data.vehicleCode, dockId: data.dockId });
                } else if (data.status === 'Cancelled') {
                    stopAll();
                    goToState('Error', { message: 'Giao dịch đã bị hủy.' });
                }
            });
        } catch {
            KioskState.signalRConnection = null;
        }
    })();

    pollingInterval = setInterval(async () => {
        try {
            const data = await ApiClient.getRentalStatus(rentalId, KioskState.userToken);
            if (!data) return;
            if (data.status === 'Active') {
                stopAll();
                goToState('Success', { vehicleId: data.vehicleCode, dockId: data.dockId });
            } else if (data.status === 'Cancelled') {
                stopAll();
                goToState('Error', { message: 'Giao dịch đã bị hủy.' });
            }
        } catch { /* silent */ }
    }, 3000);
}

function pollReturnStatus(rentalId) {
    let attempts = 0;
    const interval = setInterval(async () => {
        attempts++;
        try {
            const data = await ApiClient.getReturnStatus(rentalId, KioskState.kioskToken);           
            if (!data) return;
            if (data.status === 'Completed') {
                clearInterval(interval);
                goToState('ReturnReceipt', { summary: data.summary });
            }
        } catch { /* silent */ }
        if (attempts > 20) {
            clearInterval(interval);
            goToState('Error', { message: 'Trả xe quá thời gian. Liên hệ kỹ thuật viên.' });
        }
    }, 3000);
}

function stopAll() {
    const rentalId = KioskState.currentRentalId;
    if (KioskState.signalRConnection && window.KioskSignalR) {
        KioskSignalR.leaveRental(rentalId)
            .catch(() => {})
            .finally(() => {
                KioskSignalR.disconnect().catch(() => {});
            });
        KioskState.signalRConnection = null;
    }

    clearInterval(timerInterval);
    clearInterval(pollingInterval);
    timerInterval = pollingInterval = null;
}

// ── Payment handlers ──────────────────────────────────────────────────────────

async function handleStartRental() {
    const btn = $('btnVietQR') ?? $('btnStartRental');
    if (btn) { btn.disabled = true; btn.textContent = 'ĐANG TẠO MÃ...'; }

    try {
        const { ok, data } = await ApiClient.startRental(KioskState.selectedVehicleId, KioskState.userToken);
        console.log('[START] response:', JSON.stringify(data));
        if (ok) {
            // Defensive: handle both camelCase and PascalCase (Codex may have changed serialisation)
            KioskState.currentRentalId = data.rentalId ?? data.RentalId ?? data.id ?? data.Id;
            const qrUrl = data.qrUrl ?? data.QrUrl ?? data.qr_url ?? '';
            goToState('Active', { qrUrl, rentalId: KioskState.currentRentalId });
        } else {
            if ($('systemMessage')) $('systemMessage').textContent = data.message ?? data.Message ?? 'Lỗi hệ thống.';
            goToState('Idle');
        }
    } catch (err) {
        console.error('[START] error:', err);
        goToState('Error', { message: 'Không thể kết nối máy chủ.' });
    }
}

async function handleStripeCheckout() {
    const btn = $('btnStripe');
    if (btn) { btn.disabled = true; btn.textContent = 'ĐANG XỬ LÝ...'; }

    let rentalStarted = false;
    try {
        const { ok: startOk, data: startData } = await ApiClient.startRental(KioskState.selectedVehicleId, KioskState.userToken, 'Stripe');
        if (!startOk) {
            goToState('Error', { message: startData.message ?? startData.Message ?? 'Không thể tạo thuê xe.' });
            return;
        }
        KioskState.currentRentalId = startData.rentalId ?? startData.RentalId;
        rentalStarted = true;

        const { ok: checkoutOk, data: checkoutData } = await ApiClient.createStripeCheckout(
            KioskState.currentRentalId,
            KioskState.currentDepositAmt,
            window.location.origin,
            KioskState.userToken
        );
        if (!checkoutOk) {
            await cancelCurrentPendingRental();
            goToState('Error', { message: checkoutData.error ?? 'Không thể tạo phiên thanh toán.' });
            return;
        }

        // Persist rentalId across the page reload that Stripe causes
        sessionStorage.setItem('sgr_stripe_rental', String(KioskState.currentRentalId));
        window.location.href = checkoutData.url;
    } catch (err) {
        console.error('[STRIPE] error:', err);
        if (rentalStarted) await cancelCurrentPendingRental();
        goToState('Error', { message: 'Không thể kết nối Stripe.' });
    }
}

async function cancelCurrentPendingRental() {
    if (!KioskState.currentRentalId) return;
    try {
        await ApiClient.cancelRental(KioskState.currentRentalId, KioskState.userToken);
    } catch { /* timeout worker will clean up */ }
    finally { KioskState.currentRentalId = null; }
}

// ── Numpad ────────────────────────────────────────────────────────────────────
document.addEventListener('click', e => {
    const key = e.target.closest('.numpad-key');
    if (!key) return;
    const input = document.getElementById(key.dataset.target);
    if (!input) return;
    const val = key.dataset.val;
    if (val === 'clear') input.value = '';
    else if (val === 'back') input.value = input.value.slice(0, -1);
    else if (input.value.length < parseInt(input.maxLength)) input.value += val;
    input.dispatchEvent(new Event('input', { bubbles: true }));
});

// ── Back / Cancel buttons ─────────────────────────────────────────────────────
document.addEventListener('click', e => {
    const backBtn = e.target.closest('[data-back-to]');
    if (!backBtn) return;
    const targetState = backBtn.getAttribute('data-back-to');
    if (targetState === 'Splash') {
        KioskState.userToken = null;
        KioskState.selectedVehicleId = null;
        stopAll();
    }
    goToState(targetState);
});

// ── Idle timer ────────────────────────────────────────────────────────────────
let idleTimeout = null;
const IDLE_LIMIT_MS = 60000;

function resetIdleTimer() {
    clearTimeout(idleTimeout);
    if (['Splash', 'Active', 'ReturnProcessing'].includes(KioskState.currentState)) return;
    idleTimeout = setTimeout(() => {
        stopAll();
        KioskState.userToken = null;
        goToState('Splash');
    }, IDLE_LIMIT_MS);
}
document.addEventListener('click', resetIdleTimer);
document.addEventListener('touchstart', resetIdleTimer);

// ── RFID wedge ────────────────────────────────────────────────────────────────
let rfidBuffer  = '';
let rfidTimeout = null;

document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && rfidBuffer.length >= 8) {
        const cardId = rfidBuffer;
        rfidBuffer = '';
        handleRfidLogin(cardId);
    } else if (/^\d$/.test(e.key)) {
        rfidBuffer += e.key;
        clearTimeout(rfidTimeout);
        rfidTimeout = setTimeout(() => { rfidBuffer = ''; }, 100);
    }
});

async function handleRfidLogin(cardId) {
    if (!['Splash', 'EmailInput', 'OtpInput'].includes(KioskState.currentState)) return;
    try {
        const { ok, data } = await ApiClient.rfidLogin(cardId);
        if (ok) {
            KioskState.userToken = data.token;
            goToState('AuthSuccess', { userName: data.userName });
        } else {
            goToState('Error', { message: data.message || 'Thẻ không hợp lệ hoặc chưa đăng ký.' });
        }
    } catch {
        goToState('Error', { message: 'Lỗi đọc thẻ. Vui lòng thử lại.' });
    }
}
