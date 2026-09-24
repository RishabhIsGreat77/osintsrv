"""
main.py — osint-srv CLI entry point.

Usage:
    python main.py username <handle> [options]
    python main.py phone <number> [options]
    python main.py email <address> [options]
    python main.py domain <domain> [options]
    python main.py web [--host H] [--port P]
    python main.py cache [--clear|--history]
"""

import argparse
import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="osint-srv",
        description="Self-hosted OSINT reconnaissance tool.",
    )
    sub = p.add_subparsers(dest="module", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output", choices=["table", "json", "csv"],
                        default="table", help="output format")
    common.add_argument("-f", "--file", help="output file path")
    common.add_argument("--proxy", help="http:// or socks5:// proxy")
    common.add_argument("--timeout", type=float, default=10.0)
    common.add_argument("--concurrent", type=int, default=50)
    common.add_argument("--no-cache", action="store_true")
    common.add_argument("--verbose", action="store_true")

    # username
    u = sub.add_parser("username", parents=[common], help="username recon")
    u.add_argument("username", help="username to check")
    u.add_argument("--content", action="store_true",
                   help="use GET + content checks (slower, more accurate)")

    # phone
    ph = sub.add_parser("phone", parents=[common], help="phone recon")
    ph.add_argument("phone", help="phone number (any format)")
    ph.add_argument("--region", default="IN", help="default region code")

    # email
    e = sub.add_parser("email", parents=[common], help="email recon")
    e.add_argument("email", help="email address")
    e.add_argument("--aggressive", action="store_true",
                   help="enable social-registration checks")

    # domain
    d = sub.add_parser("domain", parents=[common], help="domain recon")
    d.add_argument("domain", help="domain name")

    # web
    w = sub.add_parser("web", help="start local web UI")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=5000)
    w.add_argument("--debug", action="store_true")

    # cache
    c = sub.add_parser("cache", help="manage local cache")
    c.add_argument("--clear", action="store_true", help="clear cache")
    c.add_argument("--history", action="store_true", help="show history")

    return p


async def _run_username(args) -> int:
    try:
        from modules import username as mod
    except ImportError as e:
        print(f"[!] username module not available: {e}")
        return 2

    result = await mod.scan(
        args.username,
        concurrency=args.concurrent,
        timeout=args.timeout,
        proxy=args.proxy,
        use_content=args.content,
    )

    if args.output == "json":
        from core import output
        output.to_json(result, args.file)
    elif args.output == "csv":
        from core import output
        rows = result.get("found", [])
        if args.file:
            output.to_csv(rows, args.file)
        else:
            output.to_csv(rows, "username_result.csv")
    else:
        mod.render(result)

    return 0


async def _run_phone(args) -> int:
    try:
        from modules import phone as mod
    except ImportError:
        print("[!] phone module not built yet. coming in next drop.")
        return 2
    result = await mod.scan(
        args.phone,
        region=args.region,
        timeout=args.timeout,
        proxy=args.proxy,
    )
    if args.output == "json":
        from core import output
        output.to_json(result, args.file)
    else:
        mod.render(result)
    return 0


async def _run_email(args) -> int:
    try:
        from modules import email as mod
    except ImportError:
        print("[!] email module not built yet. coming in next drop.")
        return 2
    result = await mod.scan(
        args.email,
        aggressive=args.aggressive,
        timeout=args.timeout,
        proxy=args.proxy,
    )
    if args.output == "json":
        from core import output
        output.to_json(result, args.file)
    else:
        mod.render(result)
    return 0


async def _run_domain(args) -> int:
    try:
        from modules import domain as mod
    except ImportError:
        print("[!] domain module not built yet. coming in next drop.")
        return 2
    result = await mod.scan(args.domain, timeout=args.timeout)
    if args.output == "json":
        from core import output
        output.to_json(result, args.file)
    else:
        mod.render(result)
    return 0


async def _run_cache(args) -> int:
    from core.cache import Cache
    async with Cache() as c:
        if args.clear:
            await c.clear()
            print("[✓] cache cleared")
        elif args.history:
            hist = await c.history(limit=50)
            if not hist:
                print("(no history)")
            for h in hist:
                print(f"{h['module']:10s} {h['target']:30s} {h['summary']}")
        else:
            print("use --clear or --history")
    return 0


def _run_web(args) -> int:
    try:
        from web.app import create_app
    except ImportError as e:
        print(f"[!] web module not built yet. coming in next drop. ({e})")
        return 2
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.module == "web":
        return _run_web(args)

    if args.module == "cache":
        return asyncio.run(_run_cache(args))

    runners = {
        "username": _run_username,
        "phone": _run_phone,
        "email": _run_email,
        "domain": _run_domain,
    }
    runner = runners.get(args.module)
    if not runner:
        parser.print_help()
        return 2
    return asyncio.run(runner(args))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] interrupted")
        sys.exit(130)
