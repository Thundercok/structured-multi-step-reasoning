"""UI-only activation bridge: a second launch presents the existing Mini."""
import hashlib
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


def _name(state_root):
    digest = hashlib.sha256(str(state_root.resolve()).encode()).hexdigest()[:20]
    return 'rat-mini-ui-' + digest


def present_running_mini(state_root):
    socket = QLocalSocket()
    socket.connectToServer(_name(state_root))
    if not socket.waitForConnected(1500):
        return False
    written = socket.write(b'show\n')
    delivered = socket.bytesToWrite() == 0 or socket.waitForBytesWritten(1500)
    socket.disconnectFromServer()
    return written == 5 and delivered


class MiniInstanceBridge(QObject):
    showRequested = pyqtSignal()

    def __init__(self, state_root, parent=None):
        super().__init__(parent)
        self.name = _name(state_root)
        self.server = QLocalServer(self)
        # Caller owns the process lock before removing a stale endpoint.
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            raise OSError('Không tạo được kênh hiện RAT: ' + self.server.errorString())
        self.server.newConnection.connect(self._connected)

    def _connected(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.setParent(self)
            socket.readyRead.connect(lambda socket=socket: self._read(socket))
            socket.disconnected.connect(socket.deleteLater)
            self._read(socket)

    def _read(self, socket):
        if socket.bytesAvailable() > 32:
            socket.abort()
            return
        if socket.canReadLine():
            if bytes(socket.readLine(32)) == b'show\n':
                self.showRequested.emit()
            socket.disconnectFromServer()

    def close(self):
        self.server.close()
        QLocalServer.removeServer(self.name)
