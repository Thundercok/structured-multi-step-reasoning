"""
tests/test_memory_sentinel.py — Comprehensive tests for Darwin Memory Pressure & Idle Sentinel.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from rat.engine.embedder import LocalEmbedder
from rat.os.memory_sentinel import (
    PRESSURE_CRITICAL,
    PRESSURE_NAMES,
    PRESSURE_NORMAL,
    PRESSURE_WARN,
    MemorySentinel,
    get_darwin_memory_pressure_level,
)


class TestMemorySentinel(unittest.TestCase):

    def setUp(self) -> None:
        self.sentinel = MemorySentinel(
            idle_timeout_seconds=2700.0,
            poll_interval_seconds=0.1,
        )

    def tearDown(self) -> None:
        if self.sentinel.is_running:
            self.sentinel.stop()

    def test_darwin_pressure_query(self) -> None:
        """Verify query returns an expected Darwin pressure level."""
        level = get_darwin_memory_pressure_level()
        self.assertIn(level, [PRESSURE_NORMAL, PRESSURE_WARN, PRESSURE_CRITICAL])
        self.assertIn(level, PRESSURE_NAMES)

    def test_callback_registration_and_trigger(self) -> None:
        """Verify callbacks are properly executed upon eviction trigger."""
        calls = []

        def my_callback(reason: str) -> None:
            calls.append(reason)

        self.sentinel.register_eviction_callback(my_callback)
        count = self.sentinel.trigger_eviction("test_simulated_pressure")

        self.assertEqual(count, 1)
        self.assertEqual(calls, ["test_simulated_pressure"])
        self.assertEqual(self.sentinel.eviction_count, 1)
        self.assertEqual(self.sentinel.last_eviction_reason, "test_simulated_pressure")
        self.assertGreater(self.sentinel.last_eviction_time, 0.0)

        # Test unregister
        self.sentinel.unregister_eviction_callback(my_callback)
        count = self.sentinel.trigger_eviction("second_test")
        self.assertEqual(count, 0)
        self.assertEqual(len(calls), 1)  # not called again

    def test_zero_arg_callback_compatibility(self) -> None:
        """Verify callbacks that take 0 arguments (like embedder.evict) work seamlessly."""
        calls = []

        def zero_arg_callback() -> None:
            calls.append("evicted")

        self.sentinel.register_eviction_callback(zero_arg_callback)
        self.sentinel.trigger_eviction("test_zero_arg")
        self.assertEqual(calls, ["evicted"])

    def test_memory_pressure_check_triggers_eviction(self) -> None:
        """Simulate high memory pressure and verify check_memory_pressure_and_evict triggers."""
        calls = []
        self.sentinel.register_eviction_callback(lambda r: calls.append(r))

        with patch("rat.os.memory_sentinel.get_darwin_memory_pressure_level", return_value=PRESSURE_WARN):
            evicted = self.sentinel.check_memory_pressure_and_evict()
            self.assertTrue(evicted)
            self.assertEqual(calls, ["memory_pressure_WARN"])

        calls.clear()
        with patch("rat.os.memory_sentinel.get_darwin_memory_pressure_level", return_value=PRESSURE_CRITICAL):
            evicted = self.sentinel.check_memory_pressure_and_evict()
            self.assertTrue(evicted)
            self.assertEqual(calls, ["memory_pressure_CRITICAL"])

        calls.clear()
        with patch("rat.os.memory_sentinel.get_darwin_memory_pressure_level", return_value=PRESSURE_NORMAL):
            evicted = self.sentinel.check_memory_pressure_and_evict()
            self.assertFalse(evicted)
            self.assertEqual(len(calls), 0)

    def test_idle_eviction_when_loaded_and_inactive(self) -> None:
        """Verify idle eviction triggers only when model is loaded and inactive > timeout."""
        calls = []
        self.sentinel.register_eviction_callback(lambda r: calls.append(r))
        self.sentinel.idle_timeout_seconds = 100.0

        mock_embedder = MagicMock()
        mock_embedder.is_loaded = True
        mock_embedder.last_accessed = time.time() - 200.0  # Inactive for 200s (> 100s)

        with patch("rat.engine.embedder.embedder", mock_embedder):
            evicted = self.sentinel.check_idle_and_evict()
            self.assertTrue(evicted)
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0].startswith("deep_idle_"))

        # Model active recently (< timeout)
        calls.clear()
        mock_embedder.last_accessed = time.time() - 10.0
        with patch("rat.engine.embedder.embedder", mock_embedder):
            evicted = self.sentinel.check_idle_and_evict()
            self.assertFalse(evicted)
            self.assertEqual(len(calls), 0)

        # Model not loaded (cold)
        mock_embedder.is_loaded = False
        mock_embedder.last_accessed = time.time() - 5000.0
        with patch("rat.engine.embedder.embedder", mock_embedder):
            evicted = self.sentinel.check_idle_and_evict()
            self.assertFalse(evicted)
            self.assertEqual(len(calls), 0)

    def test_lifecycle_start_and_stop(self) -> None:
        """Verify background worker thread starts and stops gracefully."""
        self.assertFalse(self.sentinel.is_running)
        self.sentinel.start()
        self.assertTrue(self.sentinel.is_running)

        # Double start should be idempotent
        self.sentinel.start()
        self.assertTrue(self.sentinel.is_running)

        self.sentinel.stop()
        self.assertFalse(self.sentinel.is_running)

    def test_get_status_diagnostics(self) -> None:
        """Verify telemetry dictionary contains all expected health and state keys."""
        status = self.sentinel.get_status()
        self.assertIn("is_running", status)
        self.assertIn("pressure_level", status)
        self.assertIn("pressure_name", status)
        self.assertIn("idle_timeout_seconds", status)
        self.assertIn("eviction_count", status)
        self.assertIn("last_eviction_time", status)
        self.assertIn("last_eviction_reason", status)
        self.assertIn("is_embedder_loaded", status)
        self.assertIn("embedder_last_accessed", status)

    def test_embedder_evict_integration(self) -> None:
        """Verify embedder.evict interacts correctly with MemorySentinel dispatch."""
        test_embedder = LocalEmbedder()
        self.assertFalse(test_embedder.is_loaded)
        # Cold eviction returns False
        self.assertFalse(test_embedder.evict())

        # Register eviction
        self.sentinel.register_eviction_callback(test_embedder.evict)
        # Trigger eviction while cold
        self.sentinel.trigger_eviction("cold_test")
        self.assertFalse(test_embedder.is_loaded)


if __name__ == "__main__":
    unittest.main()
