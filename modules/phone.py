"""
modules/phone.py — phone number reconnaissance.

Uses:
- phonenumbers (offline): carrier, region, line type, timezone
- wa.me and t.me: public presence checks
- dork URLs: for manual clicking
"""

from typing import Dict, Any, Optional, List

from core.http import AsyncClient
from core.validators import phone_info, normalize_phone
from core import output


async def _check_whatsapp(client: AsyncClient, e164: str) -> Dict[str, Any]:
    url = f"https://wa.me/{e164.lstrip('+')}"
    resp = await client.get(url, allow_redirects=True)
    text = (resp.get("text") or "").lower()
    final = (resp.get("final_url") or "").lower()
    exists = None
    if resp.get("status") == 0:
        exists = None
    elif "send?phone=" in final or "api.whatsapp.com/send" in final:
        exists = True
    elif "invalid" in text or "isn't on whatsapp" in text:
        exists = False
    else:
        exists = True
    return {"platform": "WhatsApp", "url": url, "exists": exists}


async def _check_telegram(client: AsyncClient, e164: str) -> Dict[str, Any]:
    url = f"https://t.me/{e164}"
    resp = await client.get(url)
    text = (resp.get("text") or "")
    exists = "tgme_page_title" in text or "tgme_page_photo" in text
    if resp.get("status") == 0:
        exists = None
    return {"platform": "Telegram", "url": url, "exists": exists}


def _dork_urls(e164: str, national: str) -> List[Dict[str, str]]:
    q = e164.lstrip("+")
    nat = national.replace(" ", "").replace("-", "")
    return [
        {"site": "Google",     "url": f"https://www.google.com/search?q=%22{q}%22"},
        {"site": "Google (nat)","url": f"https://www.google.com/search?q=%22{nat}%22"},
        {"site": "Facebook",   "url": f"https://www.google.com/search?q=site:facebook.com+%22{nat}%22"},
        {"site": "Twitter",    "url": f"https://www.google.com/search?q=site:twitter.com+%22{nat}%22"},
        {"site": "Instagram",  "url": f"https://www.google.com/search?q=site:instagram.com+%22{nat}%22"},
        {"site": "LinkedIn",   "url": f"https://www.google.com/search?q=site:linkedin.com+%22{nat}%22"},
        {"site": "Truecaller", "url": f"https://www.truecaller.com/search/in/{q}"},
        {"site": "Sync.me",    "url": f"https://sync.me/search/?number={q}"},
    ]


async def scan(
    raw: str,
    *,
    region: str = "IN",
    timeout: float = 10.0,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    info = phone_info(raw, region)
    if not info:
        return {
            "input": raw,
            "valid": False,
            "error": "invalid phone number",
        }

    result: Dict[str, Any] = {
        "input": raw,
        "valid": True,
        "info": info,
        "checks": [],
        "dorks": [],
    }

    async with AsyncClient(concurrency=5, timeout=timeout, proxy=proxy) as client:
        result["checks"].append(await _check_whatsapp(client, info["e164"]))
        result["checks"].append(await _check_telegram(client, info["e164"]))

    result["dorks"] = _dork_urls(info["e164"], info["national"])
    return result


def render(result: Dict[str, Any]) -> None:
    output.print_banner("phone", result.get("input", "?"))

    if not result.get("valid"):
        output.console.print(f"[red]invalid:[/red] {result.get('error')}")
        return

    info = result["info"]
    rows = [
        ["E.164",     info["e164"]],
        ["National",  info["national"]],
        ["Country",   f"+{info['country_code']}"],
        ["Region",    info["region"]],
        ["Carrier",   info["carrier"]],
        ["Line type", info["line_type"]],
        ["Timezones", ", ".join(info["timezones"]) or "-"],
    ]
    output.print_table("Number info", ["Field", "Value"], rows)

    check_rows = []
    for c in result.get("checks", []):
        if c["exists"] is True:
            verdict = "[green]exists[/green]"
        elif c["exists"] is False:
            verdict = "[red]no[/red]"
        else:
            verdict = "[yellow]unknown[/yellow]"
        check_rows.append([c["platform"], verdict, c["url"]])
    if check_rows:
        output.print_table("Platform presence", ["Platform", "Status", "URL"], check_rows)

    dork_rows = [[d["site"], d["url"]] for d in result.get("dorks", [])]
    if dork_rows:
        output.print_table("Manual search links", ["Site", "URL"], dork_rows)
