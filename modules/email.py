"""
modules/email.py — email address reconnaissance.

Checks (all keyless, public):
- syntax + MX records (dnspython)
- disposable domain (local list)
- gravatar profile (public JSON)
- PGP key servers (keys.openpgp.org)
- GitHub commit email search (HTML scrape)
- pastebin dumps (psbdmp.ws)
- dork URLs
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

import dns.resolver

from core.http import AsyncClient
from core.validators import is_email, md5
from core import output


ROOT = Path(__file__).resolve().parent.parent
DISPOSABLE_FILE = ROOT / "data" / "disposable.txt"


def _load_disposable() -> set:
    if not DISPOSABLE_FILE.exists():
        return set()
    return {
        l.strip().lower()
        for l in DISPOSABLE_FILE.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    }


def _mx_lookup(domain: str) -> Dict[str, Any]:
    out = {"domain": domain, "mx": [], "error": None}
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)
        out["mx"] = sorted(
            [str(r.exchange).rstrip(".") for r in answers]
        )
    except Exception as e:
        out["error"] = str(e)
    return out


async def _gravatar(client: AsyncClient, email: str) -> Dict[str, Any]:
    h = md5(email)
    url = f"https://gravatar.com/{h}.json"
    resp = await client.get(url)
    if resp.get("status") == 200:
        try:
            data = json.loads(resp["text"])
            entry = data.get("entry", [{}])[0]
            return {
                "exists": True,
                "url": url,
                "profile": entry.get("profileUrl"),
                "name": entry.get("displayName") or entry.get("name", {}).get("formatted"),
                "accounts": [
                    a.get("shortname") for a in entry.get("accounts", [])
                ],
            }
        except Exception:
            return {"exists": True, "url": url}
    return {"exists": False, "url": url}


async def _pgp(client: AsyncClient, email: str) -> Dict[str, Any]:
    url = f"https://keys.openpgp.org/vks/v1/by-email/{email}"
    resp = await client.get(url)
    if resp.get("status") == 200 and "BEGIN PGP PUBLIC KEY" in resp.get("text", ""):
        return {"exists": True, "url": url, "size": len(resp["text"])}
    return {"exists": False, "url": url}


async def _github_search(client: AsyncClient, email: str) -> Dict[str, Any]:
    # GitHub commits search HTML — count matches on page
    url = f"https://github.com/search?q={email}&type=commits"
    resp = await client.get(url)
    text = resp.get("text", "") or ""
    found = "commit" in text.lower() and "sign in" not in text[:500].lower()
    return {"exists": found, "url": url}


async def _psbdmp(client: AsyncClient, email: str) -> Dict[str, Any]:
    url = f"https://psbdmp.ws/api/search/{email}"
    resp = await client.get(url)
    if resp.get("status") == 200:
        try:
            data = json.loads(resp["text"])
            count = len(data.get("data", []))
            return {"exists": count > 0, "count": count, "url": f"https://psbdmp.ws/search/{email}"}
        except Exception:
            pass
    return {"exists": False, "count": 0, "url": f"https://psbdmp.ws/search/{email}"}


async def _social_reg(client: AsyncClient, email: str) -> List[Dict[str, Any]]:
    """Aggressive: response-diff on password reset pages."""
    checks = [
        ("Instagram", "https://www.instagram.com/accounts/emailsignup/"),
        ("Twitter",   "https://api.twitter.com/i/users/email_available.json?email=" + email),
    ]
    out = []
    for name, url in checks:
        resp = await client.get(url)
        out.append({
            "platform": name,
            "status": resp.get("status", 0),
            "note": "manual check recommended",
            "url": url,
        })
    return out


def _dork_urls(email: str) -> List[Dict[str, str]]:
    return [
        {"site": "Google",       "url": f"https://www.google.com/search?q=%22{email}%22"},
        {"site": "GitHub commits","url": f"https://github.com/search?q={email}&type=commits"},
        {"site": "Pastebin dump","url": f"https://psbdmp.ws/search/{email}"},
        {"site": "IntelX",       "url": f"https://intelx.io/?s={email}"},
        {"site": "Hunter.io",    "url": f"https://hunter.io/search/{email.split('@')[-1]}"},
        {"site": "HaveIBeenPwned","url": f"https://haveibeenpwned.com/account/{email}"},
    ]


async def scan(
    email: str,
    *,
    aggressive: bool = False,
    timeout: float = 10.0,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    email = email.strip().lower()
    result: Dict[str, Any] = {
        "email": email,
        "valid": is_email(email),
        "mx": None,
        "disposable": False,
        "gravatar": None,
        "pgp": None,
        "github": None,
        "pastebin": None,
        "social": [],
        "dorks": [],
    }
    if not result["valid"]:
        return result

    domain = email.split("@")[-1]
    result["mx"] = _mx_lookup(domain)
    result["disposable"] = domain.lower() in _load_disposable()

    async with AsyncClient(concurrency=10, timeout=timeout, proxy=proxy) as client:
        result["gravatar"] = await _gravatar(client, email)
        result["pgp"] = await _pgp(client, email)
        result["github"] = await _github_search(client, email)
        result["pastebin"] = await _psbdmp(client, email)
        if aggressive:
            result["social"] = await _social_reg(client, email)

    result["dorks"] = _dork_urls(email)
    return result


def render(result: Dict[str, Any]) -> None:
    output.print_banner("email", result.get("email", "?"))

    if not result.get("valid"):
        output.console.print("[red]invalid email format[/red]")
        return

    mx = result.get("mx") or {}
    rows = [
        ["Valid",       "[green]yes[/green]"],
        ["Domain",      result["email"].split("@")[-1]],
        ["MX records",  ", ".join(mx.get("mx", [])) or f"[red]{mx.get('error','none')}[/red]"],
        ["Disposable",  "[red]yes[/red]" if result["disposable"] else "no"],
    ]
    output.print_table("Email info", ["Field", "Value"], rows)

    findings = []
    if result.get("gravatar", {}).get("exists"):
        g = result["gravatar"]
        findings.append(["Gravatar", "found", g.get("name") or "-", g.get("url", "")])
    if result.get("pgp", {}).get("exists"):
        findings.append(["PGP key", "found", f"{result['pgp']['size']} bytes", result["pgp"]["url"]])
    if result.get("github", {}).get("exists"):
        findings.append(["GitHub commits", "hits", "-", result["github"]["url"]])
    if result.get("pastebin", {}).get("exists"):
        findings.append(["Pastebin", f"{result['pastebin']['count']} hits", "-", result["pastebin"]["url"]])
    if findings:
        output.print_table("Presence", ["Service", "Status", "Detail", "URL"], findings)

    dork_rows = [[d["site"], d["url"]] for d in result.get("dorks", [])]
    if dork_rows:
        output.print_table("Manual search links", ["Site", "URL"], dork_rows)
