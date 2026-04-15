"""Stub bpy before blender_gpt modules import (they import bpy at module level)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

if "bpy" not in sys.modules:
    sys.modules["bpy"] = MagicMock()
