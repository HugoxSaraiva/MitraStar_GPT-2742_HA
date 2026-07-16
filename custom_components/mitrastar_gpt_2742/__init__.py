import logging
from datetime import timedelta
from typing import Any

from .const import DEFAULT_POLL_INTERVAL, DOMAIN, PLATFORMS
from .router import RouterClient

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class MitraStarCoordinator:
    def __init__(self, hass, entry):
        from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
        from homeassistant.helpers.storage import Store
        from homeassistant.helpers.update_coordinator import (
            DataUpdateCoordinator,
        )

        self.client = RouterClient(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        self.entry = entry
        self.hass = hass
        self._store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.known_devices_{entry.entry_id}"
        )
        self._known_macs: set[str] = set()

        self._coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
            update_method=self._async_update_data,
        )

    @property
    def data(self) -> dict[str, Any]:
        return self._coordinator.data or {}

    @property
    def last_update_success(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def known_macs(self) -> set[str]:
        return self._known_macs

    def async_add_listener(self, callback):
        return self._coordinator.async_add_listener(callback)

    async def async_config_entry_first_refresh(self):
        return await self._coordinator.async_config_entry_first_refresh()

    async def async_load_known_macs(self) -> set[str]:
        stored = await self._store.async_load()
        self._known_macs = set(stored.get("macs", [])) if stored else set()
        return self._known_macs

    async def async_save_known_macs(self, macs: set[str]) -> None:
        self._known_macs = macs
        await self._store.async_save({"macs": list(macs)})

    async def _async_update_data(self) -> dict[str, Any]:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        if not await self.client.async_is_session_valid():
            if not await self.client.async_login():
                raise UpdateFailed("Failed to log in to router")

        macs, hostnames = await self.client.async_get_connected_devices()

        hostname_map: dict[str, str] = {}
        for hostname, mac, _ip in hostnames:
            hostname_map[mac.lower()] = hostname

        return {
            "macs": macs,
            "hostnames": hostname_map,
        }


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    coordinator = MitraStarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_load_known_macs()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    coordinator: MitraStarCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.client.close()
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    return unload_ok
