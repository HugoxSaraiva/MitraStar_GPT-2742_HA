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
    known_macs = coordinator.known_macs.copy()
    hostnames = coordinator.data.get("hostnames", {})
    current_macs = coordinator.data.get("macs", [])

    all_macs = known_macs | set(current_macs)
    entities = [
        MitraStarDeviceEntity(coordinator, mac, hostnames.get(mac))
        for mac in all_macs
    ]
    async_add_entities(entities)

    await coordinator.async_save_known_macs(all_macs)

    @callback
    def _update_entities() -> None:
        macs = coordinator.data.get("macs", [])
        hostnames_new = coordinator.data.get("hostnames", {})
        known = coordinator.known_macs
        new_macs = [m for m in macs if m not in known]
        if not new_macs:
            return
        known.update(new_macs)
        new_entities = [
            MitraStarDeviceEntity(coordinator, mac, hostnames_new.get(mac))
            for mac in new_macs
        ]
        async_add_entities(new_entities)
        coordinator.hass.async_create_task(
            coordinator.async_save_known_macs(known)
        )

    coordinator.async_add_listener(_update_entities)


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

    async def async_will_remove_from_hass(self) -> None:
        if hasattr(self, "_coordinator_listener"):
            self._coordinator_listener()
