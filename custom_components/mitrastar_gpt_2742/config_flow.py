import logging
from typing import Any, Optional

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_USERNAME
from .router import RouterClient


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    client = RouterClient(
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )
    try:
        if not await client.async_login():
            raise InvalidAuth
    finally:
        await client.close()


class MitraStarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST]}
            )
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"MitraStar GPT-2742 ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(
                    CONF_USERNAME, default=DEFAULT_USERNAME
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_import(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        return await self.async_step_user(user_input)


class CannotConnect(Exception):
    pass


class InvalidAuth(Exception):
    pass
