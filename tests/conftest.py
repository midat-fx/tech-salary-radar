"""Shared fixtures. Auto-skip llm_eval tests when GEMINI_API_KEY is not set."""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("GEMINI_API_KEY"):
        return
    skip = pytest.mark.skip(reason="GEMINI_API_KEY not set")
    for item in items:
        if "llm_eval" in item.keywords:
            item.add_marker(skip)
