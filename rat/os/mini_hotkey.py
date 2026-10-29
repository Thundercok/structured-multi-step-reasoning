"""Native hotkey transport; emits intent only, never executes business tools."""
import logging
import re
from pathlib import Path
import sys
import time

from PyQt6.QtCore import QCoreApplication, QProcess

from rat.os.hotkey_chords import chord, DEFAULT_CHORD

logger = logging.getLogger(__name__)
_keepalive = []


class HotkeyRegistration:
    def __init__(self, callback, on_error=None, on_minimal=None, on_event=None, on_state=None, chord_name=DEFAULT_CHORD):
        self.callback = callback
        self.on_minimal = on_minimal
        self.on_event = on_event
        self.on_error = on_error
        self.on_state = on_state
        self.helper_pid = 0
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
        key, modifiers, _ = chord(chord_name)
        self.ready_line = f"READY SELECT2 {key} {modifiers}".encode()
        self.process.setProgram(str(helper))
        self.process.setArguments([str(key), str(modifiers)])
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self._event('starting', state='starting')
        self.process.start()
        try:
            if not self.process.waitForStarted(3000):
                raise OSError(self.process.errorString())
            self.helper_pid = int(self.process.processId())
            self._event('started', state='starting')
            if not self.ready:
                self.process.waitForReadyRead(3000)
                self._read()
            if not self.ready:
                details = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
                raise OSError(self.protocol_error or details or 'Native hotkey helper không báo READY.')
            if self.process.state() == QProcess.ProcessState.NotRunning:
                raise OSError('Helper đã dừng ngay sau khi đăng ký phím tắt.')
        except Exception:
            if not self.close('startup_failed') and self not in _keepalive:
                _keepalive.append(self)
            raise

    def _event(self, stage, **metadata):
        if self.on_event:
            self.on_event(stage)
        if self.on_state:
            self.on_state(stage, helper_pid=self.helper_pid or int(self.process.processId()), **metadata)

    def _read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            if line in (b'READY', b'READY MODES1', b'READY HOLD1', b'READY HOLD2'):
                # Older helpers have different keys or reversed tap/hold outcomes.
                self.protocol_error = 'Helper phím tắt cũ; cần build lại helper cho Quick Look selection.'
                continue
            if line == b'READY SELECT1':
                self.protocol_error = 'Helper cũ; cần build lại để hỗ trợ đổi phím tắt.'
                continue
            if line == self.ready_line:
                self.ready = True
                self._event('ready', state='registered')
                logger.info('hotkey_registered target=native_helper intent=selection pid=%s', self.process.processId())
            elif line == b'DOWN' and self.ready and not self.closed:
                self._event('pressed')
            elif line == b'SELECTION' and self.ready and not self.closed:
                now = time.monotonic()
                if now-self.last_fire >= 0.25:
                    self.last_fire = now
                    self._event('selection', state='registered')
                    logger.info('hotkey_received origin=carbon_helper')
                    callback = self.callback
                    if callback:
                        try:
                            callback()
                        except Exception as exc:
                            self._event('callback_error', reason=type(exc).__name__)
                            if self.on_error:
                                self.on_error('Chưa xử lý được yêu cầu Quick Look. Mã QL_CALLBACK_FAILED.')

    def _finished(self, code, status):
        if self.closed:
            return
        self.ready = False
        details = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
        native_status = re.search(r'OSStatus=(-?\d+)', details)
        self._event('stopped', state='stopped', exit_code=code, exit_status=status.name,
            reason='native_osstatus:' + native_status.group(1) if native_status else 'process_exit')
        message = f'Bộ nhận phím tắt đã dừng ({code}): {details}'
        logger.error('hotkey_helper_stopped %s', message)
        if self.on_error:
            self.on_error(message)

    def _process_error(self, error):
        if self.closed:
            return
        self.ready = False
        self._event('process_error', state='failed', reason=error.name)
        if self.on_error:
            self.on_error('Bộ nhận phím tắt gặp lỗi. Chọn Đăng ký lại phím tắt trong menu RAT.')

    def close(self, reason='shutdown'):
        if self.closed and self.process.state() == QProcess.ProcessState.NotRunning:
            if self in _keepalive:
                _keepalive.remove(self)
            return True
        self.closed = True
        self.ready = False
        self._event('closing', state='closing', reason=reason)
        # The helper watches parent PID, not stdin. SIGTERM releases its Carbon
        # registration; unexpected parent death is handled by the PID watcher.
        self.process.closeWriteChannel()
        self.process.terminate()
        if not self.process.waitForFinished(1000):
            self.process.kill()
            self.process.waitForFinished(1000)
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self._event('close_failed', state='failed', reason=reason)
            return False
        if self in _keepalive:
            _keepalive.remove(self)
        self._event('closed', state='closed', reason=reason)
        return True


def register_hotkey(callback, on_error=None, on_minimal=None, on_event=None, on_state=None, chord_name=DEFAULT_CHORD):
    if any(item.process.state() != QProcess.ProcessState.NotRunning for item in _keepalive):
        raise OSError('Bộ nhận phím cũ chưa đóng; chưa tạo đăng ký cạnh tranh.')
    registration = HotkeyRegistration(callback, on_error, on_minimal, on_event, on_state, chord_name)
    _keepalive.append(registration)
    return registration


def close_hotkey_registrations(reason='shutdown'):
    outcomes = [item.close(reason) for item in tuple(_keepalive)]
    return all(outcomes)
