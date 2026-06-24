"""Storage-Helper. Konvention: .storage/benni_media_policy_state_<entry_id>."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION


def make_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}_state_{entry_id}")


def make_matrix_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """FLEET-102 Stage B: persistenter Override der Volume-Matrix (base/scenario/
    activity-Tabellen). Getrennt vom RAM-State-Store."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}_matrix_{entry_id}")
