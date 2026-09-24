# osintsrv

# osint-srv

A self-hosted OSINT reconnaissance tool for Termux.

## What it does

- **Username recon** — checks a handle across 400+ platforms in parallel
- **Phone recon** — carrier, region, line type, social footprint
- **Email recon** — MX, gravatar, PGP, disposable check, pastebin dumps
- **Domain recon** — whois, DNS, subdomains, cert transparency logs

No API keys required. Everything runs on public endpoints and scraping.

## Requirements

- Termux (Android) or any Linux
- Python 3.10+
- ~50 MB disk

## Install

```bash
git clone https://github.com/<your-username>/osint-srv.git
cd osint-srv
bash setup.sh
