cat > core/http.py <<'PYEOF'
"""
core/http.py — async HTTP client for osint-srv.

Wraps aiohttp with:
- connection pooling
- automatic retries with exponential backoff
- user-agent rotation
- optional proxy
- per-request timeout
- context-manager lifecycle
"""

import asyncio
import random
from pathlib import Path
from typing import Optional, Dict, Any, Union

import aiohttp


ROOT = Path(__file__).resolve().parent.parent
UA_FILE = ROOT / "config" / "user_agents.txt"

DEFAULT_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
    "Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


def _load_user_agents() -> list:
    if UA_FILE.exists():
        lines = [l.strip() for l in UA_FILE.read_text().splitlines() if l.strip()]
        if lines:
            return lines
    return DEFAULT_UAS


class AsyncClient:
    """Async HTTP client with retries, UA rotation, proxy support."""

    def __init__(
        self,
        concurrency: int = 50,
        timeout: float = 10.0,
        retries: int = 2,
        proxy: Optional[str] = None,
        verify_ssl: bool = True,
    ):
        self.concurrency = concurrency
        self.timeout = timeout
        self.retries = retries
        self.proxy = proxy
        self.verify_ssl = verify_ssl
        self._session: Optional[aiohttp.ClientSession] = None
        self._sem = asyncio.Semaphore(concurrency)
        self._uas = _load_user_agents()

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self._uas),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=self.concurrency,
            limit_per_host=10,
            ssl=self.verify_ssl,
            ttl_dns_cache=300,
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self._headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()
            self._session = None

    async def request(
        self,
        method: str,
        url: str,
        *,
        allow_redirects: bool = True,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> Optional[aiohttp.ClientResponse]:
        """Return aiohttp response object, or None on total failure."""
        if self._session is None:
            raise RuntimeError("AsyncClient must be used inside 'async with'")

        h = self._headers()
        if headers:
            h.update(headers)

        attempt = 0
        last_exc = None
        while attempt <= self.retries:
            try:
                async with self._sem:
                    resp = await self._session.request(
                        method,
                        url,
                        headers=h,
                        data=data,
                        json=json,
                        allow_redirects=allow_redirects,
                        proxy=self.proxy,
                        timeout=aiohttp.ClientTimeout(total=timeout or self.timeout),
                    )
                    return resp
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exc = e
                attempt += 1
                if attempt > self.retries:
                    break
                await asyncio.sleep(0.5 * (2 ** attempt) + random.random() * 0.3)

        return None

    async def fetch(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch and return a normalized dict: status, text, headers, url, error."""
        out = {
            "status": 0,
            "text": "",
            "headers": {},
            "url": url,
            "error": None,
            "final_url": url,
        }
        resp = await self.request(method, url, **kwargs)
        if resp is None:
            out["error"] = "request_failed"
            return out
        try:
            out["status"] = resp.status
            out["headers"] = dict(resp.headers)
            out["final_url"] = str(resp.url)
            try:
                out["text"] = await resp.text(errors="ignore")
            except Exception:
                out["text"] = ""
        finally:
            resp.release()
        return out

    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.fetch("GET", url, **kwargs)

    async def head(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.fetch("HEAD", url, **kwargs)

    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.fetch("POST", url, **kwargs)
PYEOF
