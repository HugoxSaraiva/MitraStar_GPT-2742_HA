"""Integration tests — hit a real MitraStar GPT-2742 router.

Requires environment variables:
    ROUTER_HOST=<router_ip>
    ROUTER_USERNAME=<username>
    ROUTER_PASSWORD=<password>
"""

import re

import pytest

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
