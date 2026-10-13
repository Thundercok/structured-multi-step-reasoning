// signalr-client.js

const KioskSignalR = (() => {
    const signalRScriptPath = '/lib/microsoft/signalr/dist/browser/signalr.min.js';
    let connection = null;
    let loadingScript = null;

    function loadSignalR() {
        if (window.signalR) return Promise.resolve(window.signalR);
        if (loadingScript) return loadingScript;

        loadingScript = new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = signalRScriptPath;
            script.onload = () => resolve(window.signalR);
            script.onerror = () => reject(new Error('SignalR client failed to load.'));
            document.head.appendChild(script);
        });

        return loadingScript;
    }

    async function connect() {
        const signalR = await loadSignalR();

        if (connection && connection.state === signalR.HubConnectionState.Connected) {
            return connection;
        }

        connection = new signalR.HubConnectionBuilder()
            .withUrl('/hubs/rental')
            .withAutomaticReconnect()
            .build();

        await connection.start();
        connection.onreconnected(async () => {
            if (KioskState.currentRentalId) {
                try { await connection.invoke('JoinRentalGroup', KioskState.currentRentalId); }
                catch { /* polling fallback handles it */ }
            }
        });
        return connection;
    }

    async function joinRental(rentalId) {
        if (!connection) await connect();
        await connection.invoke('JoinRentalGroup', rentalId);
    }

    async function leaveRental(rentalId) {
        if (!connection || !rentalId) return;
        await connection.invoke('LeaveRentalGroup', rentalId);
    }

    function onStatusChanged(callback) {
        if (!connection) return;
        connection.off('RentalStatusChanged');
        connection.on('RentalStatusChanged', callback);
    }

    async function disconnect() {
        if (!connection) return;
        await connection.stop();
        connection = null;
    }

    return {
        connect,
        joinRental,
        leaveRental,
        onStatusChanged,
        disconnect
    };
})();

window.KioskSignalR = KioskSignalR;
