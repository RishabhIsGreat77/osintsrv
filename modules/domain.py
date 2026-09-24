"""
modules/domain.py — domain reconnaissance.

Keyless sources:
- whois (system binary)
- dnspython: A, AAAA, MX, NS, TXT, CNAME
- crt.sh: certificate transparency for subdomains
"""

import json
import subprocess
import shutil
from typing import Dict, Any, Optional, List

import dns.resolver

from core.http import AsyncClient
from core.validators import is_domain
from core import output


RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]


def _whois(domain: str) -> Dict[str, Any]:
    if not shutil.which("whois"):
        return {"available": False, "error": "whois binary not installed"}
    try:
        p = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=15
        )
        return {"available": True, "raw": p.stdout.strip()}
    except Exception as e:
        return {"available": True, "error": str(e)}


def _parse_whois(raw: str) -> Dict[str, str]:
    fields = {}
    keys = {
        "registrar": "Registrar",
        "creation date": "Created",
        "created": "Created",
        "updated date": "Updated",
        "expiry date": "Expires",
        "expiration": "Expires",
        "name server": "NS",
        "registrant organization": "Org",
        "registrant country": "Country",
    }
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        kl = k.strip().lower()
        for match, out_key in keys.items():
            if kl.startswith(match):
                fields.setdefault(out_key, v.strip())
    return fields


def _dns(domain: str) -> Dict[str, List[str]]:
    out = {}
    for rtype in RECORD_TYPES:
        try:
            answers = dns.resolver.resolve(domain, rtype, lifetime=5.0)
            out[rtype] = sorted([str(r).strip() for r in answers])
        except Exception:
            out[rtype] = []
    return out


async def _crtsh(client: AsyncClient, domain: str) -> List[str]:
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    resp = await client.get(url, timeout=20.0)
    if resp.get("status") != 200:
        return []
    try:
        data = json.loads(resp["text"])
    except Exception:
        return []
    subs = set()
    for entry in data:
        for name in (entry.get("name_value") or "").splitlines():
            name = name.strip().lower()
            if name.endswith("." + domain) or name == domain:
                subs.add(name.lstrip("*."))
    return sorted(subs)


async def scan(
    domain: str,
    *,
    timeout: float = 10.0,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    domain = domain.strip().lower()
    if domain.startswith("http"):
        domain = domain.split("://", 1)[-1].split("/", 1)[0]
    if not is_domain(domain):
        return {"domain": domain, "valid": False}

    result: Dict[str, Any] = {
        "domain": domain,
        "valid": True,
        "whois": {},
        "whois_raw": "",
        "dns": {},
        "subdomains": [],
    }

    w = _whois(domain)
    if w.get("available"):
        result["whois_raw"] = w.get("raw", "")
        result["whois"] = _parse_whois(w.get("raw", ""))
    else:
        result["whois"] = {"error": w.get("error")}

    result["dns"] = _dns(domain)

    async with AsyncClient(concurrency=5, timeout=timeout, proxy=proxy) as client:
        result["subdomains"] = await _crtsh(client, domain)

    return result


def render(result: Dict[str, Any]) -> None:
    output.print_banner("domain", result.get("domain", "?"))

    if not result.get("valid"):
        output.console.print("[red]invalid domain[/red]")
        return

    whois = result.get("whois", {})
    if whois and "error" not in whois:
        rows = [[k, str(v)] for k, v in whois.items()]
        output.print_table("Whois", ["Field", "Value"], rows)
    elif "error" in whois:
        output.console.print(f"[yellow]whois:[/yellow] {whois['error']}")

    dns = result.get("dns", {})
    dns_rows = []
    for rtype, values in dns.items():
        if values:
            dns_rows.append([rtype, "\n".join(values[:10])])
    if dns_rows:
        output.print_table("DNS records", ["Type", "Value"], dns_rows)

    subs = result.get("subdomains", [])
    if subs:
        rows = [[str(i + 1), s] for i, s in enumerate(subs[:100])]
        output.print_table(
            f"Subdomains ({len(subs)} found via crt.sh)",
            ["#", "Host"],
            rows,
        )
