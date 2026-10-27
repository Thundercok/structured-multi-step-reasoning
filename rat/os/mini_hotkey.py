"""Native hotkey transport; emits intent only, never executes business tools."""
import logging
from pathlib import Path
import sys
import time

from PyQt6.QtCore import QCoreApplication, QProcess

logger = logging.getLogger(__name__)
_keepalive = []


class HotkeyRegistration:
    def __init__(self, callback, on_error=None, on_minimal=None, on_event=None):
        self.callback = callback
        self.on_minimal = on_minimal
        self.on_event = on_event
        self.on_error = on_error
        self.closed = False
        self.last_fire = 0.0
        self.buffer = bytearray()
        self.ready = False
        self.protocol_error = ''
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
        helper = base / 'rat/bin/rat-hotkey'
        if not helper.is_file():
            raise OSError('Thiếu rat-hotkey; cần build native helper trước khi chạy Mini.')
        self.process = QProcess(QCoreApplication.instance())
        self.process.setProgram(str(helper))
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.start()
        try:
            if not self.process.waitForStarted(3000):
                raise OSError(self.process.errorString())
            if not self.ready:
                self.process.waitForReadyRead(3000)
                self._read()
            if not self.ready:
                details = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
                raise OSError(self.protocol_error or details or 'Native hotkey helper không báo READY.')
        except Exception:
            self.close()
            raise

    def _read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            if line in (b'READY', b'READY MODES1', b'READY HOLD1'):
                # Older helpers have different keys or reversed tap/hold outcomes.
                self.protocol_error = 'Helper phím tắt cũ; cần build lại helper cho Look / Minimal.'
                continue
            if line == b'READY HOLD2':
                self.ready = True
                if self.on_event: self.on_event('ready')
                logger.info('hotkey_registered target=native_helper modes=look,minimal pid=%s', self.process.processId())
            elif line == b'DOWN' and self.ready and not self.closed:
                if self.on_event: self.on_event('pressed')
            elif line in (b'LOOK', b'MINIMAL') and self.ready and not self.closed:
                now = time.monotonic()
                if now-self.last_fire >= 0.25:
                    self.last_fire = now
                    if self.on_event: self.on_event(line.decode('ascii').lower())
                    logger.info('hotkey_received origin=carbon_helper')
                    callback = self.callback if line == b'LOOK' else self.on_minimal
                    if callback:
                        callback()

    def _finished(self, code, status):
        if self.closed:
            return
        self.ready = False
        details = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
        message = f'Bộ nhận phím tắt đã dừng ({code}): {details}'
        logger.error('hotkey_helper_stopped %s', message)
        if self.on_error:
            self.on_error(message)

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Closing stdin also releases the hotkey if the parent dies abruptly.
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(1000):
            self.process.kill()
            self.process.waitForFinished(1000)
        if self in _keepalive:
            _keepalive.remove(self)


def register_hotkey(callback, on_error=None, on_minimal=None, on_event=None):
    registration = HotkeyRegistration(callback, on_error, on_minimal, on_event)
    _keepalive.append(registration)
    return registration
