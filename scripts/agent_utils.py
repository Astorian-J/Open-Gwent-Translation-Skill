#!/usr/bin/env python3
"""Shared utilities for agent-agnostic JSON output.

This module re-exports json_output from _shared.py so that scripts have a
dedicated, discoverable location for agent-facing output helpers.
"""

from _shared import json_output

__all__ = ["json_output"]
