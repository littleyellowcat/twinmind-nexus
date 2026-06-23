"""Unit tests for dashboard internationalization helpers."""

from __future__ import annotations

from src.observability.dashboard.i18n import (
    DEFAULT_LANGUAGE,
    normalize_language,
    t,
)


def test_normalize_language_falls_back_to_default() -> None:
    assert normalize_language("missing") == DEFAULT_LANGUAGE


def test_translate_returns_requested_language() -> None:
    assert t("nav.twinmind_archive", "zh") == "TwinMind 档案馆"
    assert t("nav.twinmind_archive", "en") == "TwinMind Archive"


def test_translate_falls_back_to_key_for_unknown_text() -> None:
    assert t("missing.translation.key", "zh") == "missing.translation.key"
