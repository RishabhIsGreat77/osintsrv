"""
modules/username.py — check a username across public sites.

Strategy:
- load site list from config/sites_username.json
- fire async HEAD/GET requests in parallel
- determine FOUND / NOT FOUND / UNKNOWN via status + content rules
- return structured results
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.http import AsyncClient
from core import output


ROOT = Path(__file__).resolve().parent.parent
SITES_FILE = ROOT / "config" / "sites_username.json"


def _load_sites() -> List[Dict[str, Any]]:
    if not SITES_FILE.exists():
        return []
    data = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    return data.get("sites", [])


def _classify(site: Dict[str, Any], resp: Dict[str, Any]) -> str:
    """Return 'found', 'not_found', or 'unknown'."""
    status = resp.get("status", 0)
    text = resp.get("text", "") or ""

    if status == 0:
        return "unknown"

    status_found = site.get("status_found", [200])
    status_notfound = site.get("status_notfound", [404])

    if status in status_notfound:
        return "not_found"

    if status in status_found:
        # content-based override
        content_notfound = site.get("content_notfound")
        if content_notfound and content_notfound.lower() in text.lower():
            return "not_found"
        content_found = site.get("content_found")
        if content_found and content_found.lower() not in text.lower():
            return "not_found"
        return "found"

    return "unknown"


async def _check_one(
    client: AsyncClient,
    site: Dict[str, Any],
    username: str,
    use_content: bool,
) -> Dict[str, Any]:
    url = site["url"].format(username)
    method = site.get("method", "GET").upper()

    if use_content or site.get("content_notfound") or site.get("content_found"):
        resp = await client.get(url, allow_redirects=True)
    else:
        resp = await client.head(url, allow_redirects=True)
        # HEAD not supported by some sites — fall back to GET
        if resp.get("status") in (0, 405, 501):
            resp = await client.get(url, allow_redirects=True)

    verdict = _classify(site, resp)
    return {
        "site": site["name"],
        "url": url,
        "status": resp.get("status", 0),
        "verdict": verdict,
    }


async def scan(
    username: str,
    *,
    concurrency: int = 50,
    timeout: float = 10.0,
    proxy: Optional[str] = None,
    use_content: bool = False,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """Scan username across all sites. Returns full result dict."""
    sites = _load_sites()
    if not sites:
        return {
            "username": username,
            "total": 0,
            "found": [],
            "not_found": [],
            "unknown": [],
            "error": "no sites loaded — check config/sites_username.json",
        }

    results: List[Dict[str, Any]] = []

    async with AsyncClient(
        concurrency=concurrency, timeout=timeout, proxy=proxy
    ) as client:
        tasks = [_check_one(client, s, username, use_content) for s in sites]

        if show_progress:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
            ) as prog:
                tid = prog.add_task(f"scanning {username}", total=len(tasks))
                for coro in asyncio.as_completed(tasks):
                    r = await coro
                    results.append(r)
                    prog.advance(tid)
        else:
            for coro in asyncio.as_completed(tasks):
                results.append(await coro)

    found = [r for r in results if r["verdict"] == "found"]
    not_found = [r for r in results if r["verdict"] == "not_found"]
    unknown = [r for r in results if r["verdict"] == "unknown"]

    found.sort(key=lambda r: r["site"].lower())

    return {
        "username": username,
        "total": len(results),
        "found": found,
        "not_found": not_found,
        "unknown": unknown,
    }


def render(result: Dict[str, Any]) -> None:
    """Print a result dict to the terminal."""
    username = result.get("username", "?")
    found = result.get("found", [])
    total = result.get("total", 0)

    output.print_banner("username", username)

    if not found:
        output.console.print("[yellow]no profiles found[/yellow]")
        return

    rows = [[r["site"], output.status_icon(r["status"]), r["url"]] for r in found]
    footer = f"found: {len(found)}/{total}"
    output.print_table(
        title=f"Profiles for '{username}'",
        columns=["Site", "Status", "URL"],
        rows=rows,
        footer=footer,
    )
