import logging
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known_macs: set[str] = set()

    @callback
    def _update_entities() -> None:
        macs = coordinator.data.get("macs", [])
        hostnames = coordinator.data.get("hostnames", {})
        new_macs = [m for m in macs if m not in known_macs]
        if not new_macs:
            return
        known_macs.update(new_macs)
        entities = [
            MitraStarDeviceEntity(coordinator, mac, hostnames.get(mac))
            for mac in new_macs
        ]
        async_add_entities(entities)

    coordinator.async_add_listener(_update_entities)
    _update_entities()


class MitraStarDeviceEntity(ScannerEntity):
    _attr_has_entity_name = False

    def __init__(
        self, coordinator, mac: str, hostname: str | None
    ) -> None:
        self.coordinator = coordinator
        self._mac = mac
        self._hostname = hostname
        self._attr_unique_id = f"{DOMAIN}_{mac}"
        self._attr_name = hostname or mac
        self._coordinator_listener = (
            coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def is_connected(self) -> bool:
        return self._mac in self.coordinator.data.get("macs", [])

    @property
    def source_type(self) -> SourceType | str:
        return SourceType.ROUTER

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        hostnames = self.coordinator.data.get("hostnames", {})
        hostname = hostnames.get(self._mac)
        attrs = {}
        if hostname:
            attrs["hostname"] = hostname
        return attrs

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
