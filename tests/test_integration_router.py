"""Integration tests — hit a real MitraStar GPT-2742 router.

Requires environment variables:
    ROUTER_HOST=<router_ip>
    ROUTER_USERNAME=<username>
    ROUTER_PASSWORD=<password>
"""

import re
from http.cookies import SimpleCookie

import pytest
from yarl import URL

from custom_components.mitrastar_gpt_2742.router import RouterClient


@pytest.mark.integration
class TestRouterLogin:
    async def test_login_succeeds(self, router_client):
        result = await router_client.async_login()
        assert result is True, (
            "Login failed — check ROUTER_HOST/ROUTER_PASSWORD"
        )

    async def test_login_with_bad_password_fails(self, router_client):
        bad_client = RouterClient(
            router_client.host, router_client.username, "wrong_password"
        )
        result = await bad_client.async_login()
        await bad_client.close()
        assert result is False


@pytest.mark.integration
class TestRouterConnectedDevices:
    async def test_get_connected_devices_returns_macs(self, router_client):
        assert await router_client.async_login()
        macs, hostnames = (
            await router_client.async_get_connected_devices()
        )
        assert isinstance(macs, list)
        assert isinstance(hostnames, list)
        assert len(macs) > 0, (
            "Expected at least one device (including the router itself)"
        )

    async def test_all_macs_are_valid_format(self, router_client):
        mac_re = re.compile(
            r'^([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})$'
        )

        assert await router_client.async_login()
        macs, _ = await router_client.async_get_connected_devices()
        for mac in macs:
            assert mac_re.match(mac), f"Invalid MAC format: {mac}"

    async def test_dhcp_hostnames_match_macs(self, router_client):
        assert await router_client.async_login()
        macs, hostnames = (
            await router_client.async_get_connected_devices()
        )
        mac_set = set(macs)
        for hostname, mac, _lease in hostnames:
            assert mac.lower() in mac_set, (
                f"DHCP hostname '{hostname}' MAC {mac} "
                f"not found in connected devices"
            )


@pytest.mark.integration
class TestRouterSessionValidation:
    async def test_session_valid_after_login(self, router_client):
        assert await router_client.async_login()
        assert await router_client.async_is_session_valid() is True

    async def test_session_invalid_with_garbage_cookies(self, router_client):
        assert await router_client.async_login()
        cookie_jar = router_client._session.cookie_jar
        cookie_jar.clear()
        sc = SimpleCookie()
        sc["COOKIE_SESSION_KEY"] = "garbage"
        cookie_jar.update_cookies(sc, URL(f"http://{router_client.host}/"))
        assert await router_client.async_is_session_valid() is False

    async def test_session_invalid_before_login(self, router_client):
        assert await router_client.async_is_session_valid() is False

    async def test_old_session_invalidated_by_new_login(self, router_client):
        assert await router_client.async_login()
        assert await router_client.async_is_session_valid() is True

        new_client = RouterClient(
            router_client.host, router_client.username, router_client.password
        )
        assert await new_client.async_login()
        assert await new_client.async_is_session_valid() is True

        assert await router_client.async_is_session_valid() is False
        await new_client.close()
