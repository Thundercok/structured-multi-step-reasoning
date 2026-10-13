// state-manager.js

document.addEventListener('DOMContentLoaded', async () => {

    function goToState(name, payload = {}) {
        document.querySelectorAll('.state-container').forEach(el => el.style.display = 'none');
        const el = document.getElementById('paymentState_' + name);
        if (!el) { console.error('Missing state div: paymentState_' + name); return; }
        el.style.display = 'flex';
        KioskState.currentState = name;
        resetIdleTimer();
        onEnter[name]?.(payload);
        window.kioskReady = true;
    }

    window.goToState = goToState;

    const onEnter = {

        Splash: () => {
            $('btnTouchToStart')?.addEventListener('click', () => goToState('EmailInput'), { once: true });
            $('btnGoToReturn')?.addEventListener('click',  () => goToState('ReturnScan'),  { once: true });
        },

        EmailInput: () => {
            const input = $('emailInput');
            if ($('emailError')) $('emailError').textContent = '';
            $('emailError').textContent = '';
            $('btnSubmitEmail')?.addEventListener('click', async () => {
                const email = $('emailInput').value.trim();
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                    if ($('emailError')) $('emailError').textContent = 'Email không hợp lệ.';
                    return;
                }
                KioskState.otpEmail = email;
                try {
                    const { ok, data } = await ApiClient.sendOtp(email);
                    if ($('emailError')) $('emailError').textContent = data.message || 'Không thể gửi OTP.';
                    goToState('OtpInput');
                } catch {
                    if ($('emailError')) $('emailError').textContent = 'Không thể gửi OTP. Thử lại.';
                }
            }, { once: true });
        },

        OtpInput: () => {
            $('otpInput').value = '';
            $('otpError').textContent = '';
            $('btnSubmitOtp')?.addEventListener('click', async () => {
                const otp = $('otpInput').value.trim();
                try {
                    const { ok, data } = await ApiClient.verifyOtp(KioskState.otpEmail, otp);
                    if (ok) {
                        if (data.requiresTotp) {
                            KioskState.pendingToken = data.pendingToken;
                            goToState('TotpInput');
                        } else {
                            KioskState.userToken = data.token;
                            goToState('AuthSuccess', { userName: data.userName });
                        }
                    } else {
                        $('otpError').textContent = data.message || 'Mã OTP sai. Thử lại.';
                    }
                } catch {
                    $('otpError').textContent = 'Lỗi kết nối.';
                }
            }, { once: true });
        },
        OtpInput: () => {
            $('otpInput').value = '';
            $('otpError').textContent = '';
            $('btnSubmitOtp')?.addEventListener('click', async () => {
                const otp = $('otpInput').value.trim();
                try {
                    const { ok, data } = await ApiClient.verifyOtp(KioskState.otpEmail, otp);
                    if (ok) {
                        KioskState.userToken = data.token;
                        goToState('AuthSuccess', { userName: data.userName });
                    } else {
                        $('otpError').textContent = data.message || 'Mã OTP sai. Thử lại.';
                    }
                } catch {
                    $('otpError').textContent = 'Lỗi kết nối.';
                }
            }, { once: true });
        },
        AuthSuccess: ({ userName } = {}) => {
            if ($('authUserName')) $('authUserName').textContent = userName ?? '';
            setTimeout(() => goToState('VehicleSelect'), 2000);
        },

        VehicleSelect: async () => {
            const list = document.querySelector('.vehicle-option-list');
            list.innerHTML = '<p class="section-subtitle">Đang tải danh sách xe...</p>';
            try {
                const vehicles = await ApiClient.getVehicles();
                if (!vehicles.length) {
                    list.innerHTML = '<p class="error-msg">Không có xe khả dụng tại trạm này.</p>';
                    return;
                }
                list.innerHTML = vehicles.map(v => {
                    const depositRate = v.grade === 2 ? 0.20 : v.grade === 1 ? 0.15 : 0.10;
                    const deposit     = (v.marketValue * depositRate).toLocaleString('vi-VN');
                    const icon        = v.grade === 2 ? '🛵' : v.grade === 1 ? '⚡' : '🚲';
                    const gradeName   = ['C', 'B', 'A'][v.grade] ?? '?';
                    return `<button class="vehicle-option-btn"
                        data-vehicle-id="${v.id}" data-market-value="${v.marketValue}"
                        data-grade="${v.grade}" data-hourly-rate="${v.hourlyRate}" data-name="${v.name}">
                        <span class="vehicle-icon">${icon}</span>
                        <div class="vehicle-option-info">
                            <span class="vehicle-option-name">${v.name}</span>
                            <span class="vehicle-option-desc">Grade ${gradeName} — Phí cọc: ${deposit} VNĐ</span>
                        </div>
                        <span class="vehicle-option-arrow">&rarr;</span>
                    </button>`;
                }).join('');

                document.querySelectorAll('.vehicle-option-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        goToState('DepositInfo', {
                            vehicleId:   parseInt(btn.dataset.vehicleId),
                            marketValue: parseFloat(btn.dataset.marketValue),
                            grade:       parseInt(btn.dataset.grade),
                            hourlyRate:  parseFloat(btn.dataset.hourlyRate),
                            name:        btn.dataset.name
                        });
                    }, { once: true });
                });
            } catch (err) {
                list.innerHTML = `<p class="error-msg">Không thể tải danh sách xe: ${err.message}</p>`;
            }
        },

        DepositInfo: ({ vehicleId, marketValue, grade, hourlyRate } = {}) => {
            KioskState.selectedVehicleId = vehicleId;
            const depositRate = grade === 2 ? 0.20 : grade === 1 ? 0.15 : 0.10;
            const depositAmt  = Math.round(marketValue * depositRate);
            KioskState.currentDepositAmt = depositAmt;

            const rows = document.querySelectorAll('#paymentState_DepositInfo .deposit-row');
            if (rows[0]) rows[0].querySelector('.deposit-value').textContent = hourlyRate.toLocaleString('vi-VN') + ' VNĐ';
            if (rows[1]) rows[1].querySelector('.deposit-value').textContent = depositAmt.toLocaleString('vi-VN') + ' VNĐ';
            $('btnConfirmDeposit')?.addEventListener('click', () => goToState('Idle'), { once: true });
        },

        Idle: ({ error } = {}) => {
            if ($('systemMessage')) $('systemMessage').textContent = error ?? '';
            const actionArea = $('idleActionArea');
            if (actionArea) {
                actionArea.innerHTML = `
                    <button id="btnVietQR" class="action-btn btn-primary" style="margin-bottom:12px;">🇻🇳 VietQR (Nội địa)</button>
                    <button id="btnStripe" class="action-btn btn-secondary" style="margin-bottom:12px;">💳 Thẻ quốc tế</button>
                    <button class="action-btn btn-secondary" data-back-to="DepositInfo">⬅ QUAY LẠI</button>
                `;
                $('btnVietQR').addEventListener('click', handleStartRental,   { once: true });
                $('btnStripe').addEventListener('click', handleStripeCheckout, { once: true });
            }
        },

        Active: ({ qrUrl, rentalId } = {}) => {
            const qrImg = $('qrImage');
            if (qrImg) {
                qrImg.src = qrUrl ?? '';
                qrImg.style.display = qrUrl ? 'block' : 'none';
            }
            startCountdown(900);
            startPolling(rentalId);
            $('btnCancelRental')?.addEventListener('click', async () => {
                stopAll();
                await cancelCurrentPendingRental();
                goToState('Idle');
            }, { once: true });
        },

        Success: ({ vehicleId, dockId } = {}) => {
            if ($('assignedVehicleId')) $('assignedVehicleId').textContent = vehicleId ?? 'N/A';
            if ($('assignedDockId'))    $('assignedDockId').textContent    = dockId    ?? 'N/A';
            setTimeout(() => goToState('Splash'), 30000);
            $('btnDone')?.addEventListener('click', () => goToState('Splash'), { once: true });
        },

        ReturnScan: () => {
            $('bikeIdInput').value = '';
            $('returnError').textContent = '';
            $('btnSubmitReturn')?.addEventListener('click', async () => {
                const bikeCode = $('bikeIdInput').value.trim();
                if (!bikeCode) { $('returnError').textContent = 'Nhập mã xe.'; return; }
                try {
                    const { ok, data } = await ApiClient.returnRental(bikeCode, KioskState.kioskToken);
                    if (ok) goToState('ReturnProcessing', { rentalId: data.rentalId });
                    else $('returnError').textContent = data.message || 'Không tìm thấy xe.';
                } catch {
                    $('returnError').textContent = 'Lỗi kết nối.';
                }
            }, { once: true });
        },

        ReturnProcessing: ({ rentalId } = {}) => { pollReturnStatus(rentalId); },

        ReturnReceipt: ({ summary } = {}) => {
            if ($('receiptBaseFare'))    $('receiptBaseFare').textContent    = fmt(summary?.baseFare);
            if ($('receiptDiscount'))    $('receiptDiscount').textContent    = fmt(summary?.discount);
            if ($('receiptFinalFare'))   $('receiptFinalFare').textContent   = fmt(summary?.finalFare);
            if ($('receiptDepositNote')) $('receiptDepositNote').textContent = summary?.depositNote ?? '';
            setTimeout(() => goToState('Splash'), 30000);
            $('btnReceiptDone')?.addEventListener('click', () => goToState('Splash'), { once: true });
        },

        Error: ({ message } = {}) => {
            if ($('errorMessage')) $('errorMessage').textContent = message ?? 'Đã xảy ra lỗi.';
            setTimeout(() => goToState('Splash'), 10000);
            $('btnErrorRetry')?.addEventListener('click', () => goToState('Splash'), { once: true });
        }
    };

    // ── Boot ──────────────────────────────────────────────────────────────────
    try {
        const data = await ApiClient.kioskToken();
        KioskState.kioskToken = data.token;
    } catch {
        goToState('Error', { message: 'Lỗi kết nối hệ thống. Vui lòng liên hệ kỹ thuật viên.' });
        return;
    }

    const urlParams       = new URLSearchParams(window.location.search);
    const stripeSession   = urlParams.get('stripe_session');
    const stripeRentalId  = urlParams.get('rental_id');
    const stripeCancelled = urlParams.get('stripe_cancelled');

    if (stripeSession && stripeRentalId) {
        sessionStorage.removeItem('sgr_stripe_rental');
        history.replaceState({}, '', '/Kiosk');
        // Stripe webhook already activated rental — go straight to Success
        goToState('Success', { vehicleId: `Rental #${stripeRentalId}`, dockId: 'Vui lòng lấy xe' });
    } else if (stripeCancelled && stripeRentalId) {
        history.replaceState({}, '', '/Kiosk');
        goToState('Idle', { error: 'Thanh toán bị hủy. Vui lòng thử lại.' });
    } else {
        goToState('Splash');
    }
});