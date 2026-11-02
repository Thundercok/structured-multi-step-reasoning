"""
rat.os.single_instance — Single Instance Enforcement and IPC Guard.
Prevents duplicate resident app instances from running concurrently,
delegating summon/toggle commands to the running primary instance.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger("rat.os.single_instance")

SINGLE_INSTANCE_SERVER_NAME = f"rat_instance_{os.getuid()}"


def try_activate_existing_instance(command: str = "spotlight", timeout_ms: int = 600) -> bool:
    """
    Attempts to connect to an existing running RAT resident instance.
    If an instance is already running, transmits the activation command and returns True.
    If no instance is running, returns False.
    """
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
    if socket.waitForConnected(timeout_ms):
        try:
            payload = command.strip().encode("utf-8")
            socket.write(payload)
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            logger.info(f"Delegated '{command}' command to running RAT instance.")
            return True
        except Exception as e:
            logger.warning(f"Failed to communicate with running RAT instance: {e}")
            return False
        finally:
            socket.close()
    return False


def kill_stale_orphan_instances(current_pid: Optional[int] = None) -> int:
    """
    Safely terminates any stale/zombie rat resident processes if no instance is actively listening.
    Excludes the current process PID and test runners.
    """
    try:
        import psutil
    except ImportError:
        return 0

    curr = current_pid or os.getpid()
    killed = 0

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == curr:
                continue
            cmdline = proc.info.get("cmdline") or []
            cmd_str = " ".join(cmdline)
            # Match python running rat.main with resident modes
            if "rat.main" in cmd_str and any(m in cmd_str for m in ("spotlight", "--daemon", "finder", "resident")):
                # Double check this is not a pytest process
                if "pytest" in cmd_str:
                    continue
                logger.warning(f"Terminating stale orphan rat instance PID {proc.info['pid']}")
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except psutil.TimeoutExpired:
                    proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            logger.debug(f"Error checking orphan process: {e}")

    return killed


class SingleInstanceServer(QObject):
    """
    Resident QLocalServer that listens for commands from subsequent rat invocations.
    """

    command_received = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)

    def start(self) -> bool:
        """Binds the local server, unlinking any stale Unix domain socket."""
        # Unlink any stale socket left over from hard kills or system crashes
        QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)
        success = self._server.listen(SINGLE_INSTANCE_SERVER_NAME)
        if success:
            logger.info(f"SingleInstanceServer listening on '{SINGLE_INSTANCE_SERVER_NAME}'")
        else:
            logger.warning(
                f"SingleInstanceServer failed to listen on '{SINGLE_INSTANCE_SERVER_NAME}': "
                f"{self._server.errorString()}"
            )
        return success

    def stop(self) -> None:
        """Closes the server and removes the socket name."""
        if self._server.isListening():
            self._server.close()
        QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)
        logger.info(f"SingleInstanceServer stopped and unlinked '{SINGLE_INSTANCE_SERVER_NAME}'")

    def _on_new_connection(self) -> None:
        """Handles incoming socket connection from a subsequent rat process."""
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            if not client:
                continue

            def _read_and_process() -> None:
                try:
                    data = bytes(client.readAll()).decode("utf-8", errors="ignore").strip()
                    if data:
                        logger.info(f"SingleInstanceServer received remote command: '{data}'")
                        self.command_received.emit(data)
                except Exception as e:
                    logger.warning(f"Error reading from single instance client: {e}")
                finally:
                    client.disconnectFromServer()
                    client.deleteLater()

            client.readyRead.connect(_read_and_process)
            # In case data arrived already before signal was bound:
            if client.bytesAvailable() > 0:
                _read_and_process()
