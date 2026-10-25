"""
tests/test_single_instance.py — Tests for Single Instance Enforcement & IPC Guard.
"""

import os
import unittest
from unittest.mock import patch
from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtGui import QGuiApplication

from rat.os.single_instance import (
    SingleInstanceServer,
    try_activate_existing_instance,
    kill_stale_orphan_instances,
    SINGLE_INSTANCE_SERVER_NAME,
)


class TestSingleInstance(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_no_instance_running(self) -> None:
        """When no instance is listening, try_activate_existing_instance returns False."""
        # Ensure server is stopped
        server = SingleInstanceServer()
        server.stop()
        result = try_activate_existing_instance(command="spotlight", timeout_ms=100)
        self.assertFalse(result)

    def test_single_instance_ipc_delegation(self) -> None:
        """When SingleInstanceServer is active, try_activate delegates and emits signal."""
        from PyQt6.QtNetwork import QLocalSocket
        server = SingleInstanceServer()
        self.assertTrue(server.start())

        received_commands = []
        server.command_received.connect(lambda cmd: received_commands.append(cmd))

        # Client attempt to activate
        delegated = try_activate_existing_instance(command="finder", timeout_ms=500)
        if not delegated:
            test_sock = QLocalSocket()
            test_sock.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
            test_sock.waitForConnected(100)
            if "Socket access error" in test_sock.errorString() or "Permission" in test_sock.errorString():
                server.stop()
                self.skipTest("Unix domain socket connection blocked by sandbox environment")
        self.assertTrue(delegated)

        # Process Qt events to allow server to read and emit
        for _ in range(10):
            self.app.processEvents()

        self.assertIn("finder", received_commands)

        server.stop()

    def test_kill_stale_orphan_instances_safety(self) -> None:
        """kill_stale_orphan_instances executes safely without terminating current process."""
        curr_pid = os.getpid()
        try:
            import psutil
            with patch('psutil.process_iter', return_value=[]):
                killed = kill_stale_orphan_instances(current_pid=curr_pid)
        except ImportError:
            killed = kill_stale_orphan_instances(current_pid=curr_pid)
        self.assertIsInstance(killed, int)
        self.assertGreaterEqual(killed, 0)


if __name__ == "__main__":
    unittest.main()
