import asyncio
import os
from pathlib import Path

import pytest

from custom_components.mitrastar_gpt_2742.router import RouterClient


def _load_dotenv():
    dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if not dotenv_path.exists():
        return
    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key not in os.environ:
                os.environ.setdefault(key, value)


def _get_credentials():
    _load_dotenv()
    host = os.environ.get("ROUTER_HOST")
    username = os.environ.get("ROUTER_USERNAME")
    password = os.environ.get("ROUTER_PASSWORD")
    if host and username and password:
        return host, username, password
    return None


@pytest.fixture
def router_client():
    creds = _get_credentials()
    if creds is None:
        pytest.skip(
            "Set ROUTER_HOST, ROUTER_USERNAME, and ROUTER_PASSWORD "
            "in .env file or environment variables"
        )
    host, username, password = creds
    client = RouterClient(host, username, password)
    yield client
    asyncio.run(client.close())
