"""
macOS Native Vision Framework OCR Engine (NPU/Neural Engine Accelerated)
"""

import os
import json
import subprocess
from typing import List, Dict, Any


class MacOSVisionEngine:
    def __init__(self):
        self.swift_script_path = os.path.join(os.path.dirname(__file__), "vision_native.swift")
        self.swift_bin_path = os.path.join(os.path.dirname(__file__), "vision_native_bin")
        self._compiled = False

    def _compile_binary(self) -> bool:
        """
        Attempts to pre-compile the Swift script into a native macOS binary.
        Returns True if successful, False otherwise.
        """
        if not os.path.exists(self.swift_script_path):
            return False
        
        # If binary already exists and is newer than the script, we are good
        if os.path.exists(self.swift_bin_path):
            if os.path.getmtime(self.swift_bin_path) >= os.path.getmtime(self.swift_script_path):
                self._compiled = True
                return True

        try:
            # Compile with optimizations
            cmd = ["swiftc", "-O", self.swift_script_path, "-o", self.swift_bin_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and os.path.exists(self.swift_bin_path):
                self._compiled = True
                return True
        except Exception:
            pass
        return False

    def run_ocr(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Invokes native Swift binary (or script fallback) running VNRecognizeTextRequest on macOS.
        Returns list of recognized text tokens with pixel bounding boxes.
        """
        if not os.path.exists(image_path):
            return []

        # Try compiled binary first
        if self._compiled or self._compile_binary():
            try:
                cmd = [self.swift_bin_path, image_path]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0 and res.stdout.strip():
                    return json.loads(res.stdout.strip())
            except Exception:
                pass

        # Fallback to JIT Swift execution
        if os.path.exists(self.swift_script_path):
            try:
                cmd = ["swift", self.swift_script_path, image_path]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0 and res.stdout.strip():
                    return json.loads(res.stdout.strip())
            except Exception:
                pass

        return []

