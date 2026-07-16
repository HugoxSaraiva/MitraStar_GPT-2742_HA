import hashlib
import logging
import re
from typing import Optional
from urllib.parse import quote

from aiohttp import CookieJar
import aiohttp

_LOGGER = logging.getLogger(__name__)

SID_RE = re.compile(r"var sid = '([a-f0-9]+)'")

DHCP_SELECT_RE = re.compile(
    r'<option value="([^"]*?) '
    r'((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}) '
    r'(\d+\.\d+\.\d+\.\d+)">'
)

WIFI_STATION_RE = re.compile(
    r'<td class="cinza">([^<]*)</td>\s*'
    r'<td class="center">((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})</td>'
)


def compute_password_hash(password: str, sid: str) -> str:
    encoded = quote(password, safe='')
    passwd_val = re.sub(
        r'%[0-9A-F]{2}', lambda m: m.group(0).lower(), encoded
    )
    return hashlib.md5(f"{passwd_val}:{sid}".encode()).hexdigest()


def parse_dhcp_select_index(html: str) -> list[tuple[str, str, str]]:
    return sorted(set(
        (hostname, mac.lower(), ip)
        for hostname, mac, ip in DHCP_SELECT_RE.findall(html)
    ))


def parse_wifi_stations(html: str) -> list[str]:
    return sorted(set(
        mac.lower() for _, mac in WIFI_STATION_RE.findall(html)
    ))


class RouterClient:
    LOGIN_PATH = "/cgi-bin/login.cgi"
    DHCP_SELECT_INDEX_PATH = "/cgi-bin/sophia_dhcp_SelectIndex.cgi"
    STATISTICS_PATH = "/cgi-bin/device-management-statistics.cgi"

    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self.base_url = f"http://{host}"
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                cookie_jar=CookieJar(unsafe=True),
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _extract_sid(self, html: str) -> Optional[str]:
        m = SID_RE.search(html)
        return m.group(1) if m else None

    async def async_login(self) -> bool:
        login_url = self._url(self.LOGIN_PATH)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": login_url,
        }
        try:
            get_resp = await self.session.get(login_url, headers=headers)
            body = await get_resp.text()
            sid = self._extract_sid(body)
            if not sid:
                return False

            pw_hash = compute_password_hash(self.password, sid)

            data = {
                "Loginuser": self.username,
                "LoginPasswordValue": pw_hash,
                "acceptLoginIndex": "1",
            }
            post_resp = await self.session.post(
                login_url, data=data, headers=headers, allow_redirects=False
            )
            post_body = await post_resp.text()
            return "sophia_index.cgi" in post_body
        except Exception as exc:
            _LOGGER.warning("Login failed: %s: %s", type(exc).__name__, exc)
            return False

    async def _read_path(self, path: str) -> Optional[str]:
        url = self._url(path)
        try:
            resp = await self.session.get(url, allow_redirects=False)
            if resp.status == 200:
                return await resp.text()
        except Exception:
            pass
        return None

    async def async_is_session_valid(self) -> bool:
        html = await self._read_path(self.STATISTICS_PATH)
        return html is not None

    async def async_get_connected_devices(
        self,
    ) -> tuple[list[str], list[tuple[str, str, str]]]:
        macs: set[str] = set()
        hostnames: list[tuple[str, str, str]] = []

        dhcp_html = await self._read_path(self.DHCP_SELECT_INDEX_PATH)
        if dhcp_html:
            for hostname, mac, ip in parse_dhcp_select_index(dhcp_html):
                macs.add(mac)
                hostnames.append((hostname, mac, ip))

        stats_html = await self._read_path(self.STATISTICS_PATH)
        if stats_html:
            macs.update(parse_wifi_stations(stats_html))

        return sorted(macs), hostnames
