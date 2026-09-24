"""
web/app.py — Flask web UI for osint-srv.

Routes:
  GET  /              search form
  GET  /settings      behaviour settings
  POST /settings      save settings
  POST /api/scan      run a module, return JSON
  GET  /history       recent scans
  GET  /api/history   JSON history
  GET  /health        health check
"""

import asyncio
import json
import sys
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SETTINGS_FILE = ROOT / "config" / "settings.json"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        # create fresh loop for thread
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return loop.run_until_complete(coro)


async def _scan_username(target, opts):
    from modules import username as mod
    return await mod.scan(
        target,
        concurrency=opts.get("concurrent", 50),
        timeout=opts.get("timeout", 10.0),
        proxy=opts.get("proxy") or None,
        use_content=opts.get("use_content", False),
        show_progress=False,
    )


async def _scan_phone(target, opts):
    from modules import phone as mod
    return await mod.scan(
        target,
        region=opts.get("region", "IN"),
        timeout=opts.get("timeout", 10.0),
        proxy=opts.get("proxy") or None,
    )


async def _scan_email(target, opts):
    from modules import email as mod
    return await mod.scan(
        target,
        aggressive=opts.get("aggressive", False),
        timeout=opts.get("timeout", 10.0),
        proxy=opts.get("proxy") or None,
    )


async def _scan_domain(target, opts):
    from modules import domain as mod
    return await mod.scan(
        target,
        timeout=opts.get("timeout", 10.0),
        proxy=opts.get("proxy") or None,
    )


SCANNERS = {
    "username": _scan_username,
    "phone": _scan_phone,
    "email": _scan_email,
    "domain": _scan_domain,
}


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    @app.route("/")
    def index():
        settings = _load_settings()
        return render_template("index.html", settings=settings)

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            data = {
                "proxy": request.form.get("proxy", "").strip(),
                "timeout": float(request.form.get("timeout") or 10.0),
                "concurrent": int(request.form.get("concurrent") or 50),
                "cache_ttl": int(request.form.get("cache_ttl") or 24),
                "region": request.form.get("region", "IN").strip(),
            }
            _save_settings(data)
            return redirect(url_for("settings", saved="1"))
        return render_template(
            "settings.html",
            settings=_load_settings(),
            saved=request.args.get("saved"),
        )

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        payload = request.get_json(silent=True) or {}
        module = payload.get("module", "").strip().lower()
        target = (payload.get("target") or "").strip()

        if module not in SCANNERS:
            return jsonify({"error": f"unknown module: {module}"}), 400
        if not target:
            return jsonify({"error": "target required"}), 400

        settings = _load_settings()
        opts = {
            "proxy": payload.get("proxy") or settings.get("proxy") or None,
            "timeout": float(payload.get("timeout") or settings.get("timeout") or 10.0),
            "concurrent": int(payload.get("concurrent") or settings.get("concurrent") or 50),
            "region": payload.get("region") or settings.get("region") or "IN",
            "aggressive": bool(payload.get("aggressive", False)),
            "use_content": bool(payload.get("use_content", False)),
        }

        try:
            result = _run_async(SCANNERS[module](target, opts))
        except Exception as e:
            return jsonify({"error": f"{type(e).__name__}: {e}"}), 500

        # log to history (best effort)
        try:
            from core.cache import Cache
            async def _log():
                async with Cache() as c:
                    summary = {}
                    if module == "username":
                        summary = {"found": len(result.get("found", [])),
                                   "total": result.get("total", 0)}
                    elif module == "phone":
                        summary = {"valid": result.get("valid", False)}
                    elif module == "email":
                        summary = {"valid": result.get("valid", False)}
                    elif module == "domain":
                        summary = {"subdomains": len(result.get("subdomains", []))}
                    await c.log(module, target, summary)
            _run_async(_log())
        except Exception:
            pass

        return jsonify(result)

    @app.route("/history")
    def history_page():
        try:
            from core.cache import Cache
            async def _get():
                async with Cache() as c:
                    return await c.history(limit=100)
            hist = _run_async(_get())
        except Exception:
            hist = []
        return render_template("history.html", history=hist)

    @app.route("/api/history")
    def api_history():
        try:
            from core.cache import Cache
            async def _get():
                async with Cache() as c:
                    return await c.history(limit=100)
            hist = _run_async(_get())
        except Exception:
            hist = []
        return jsonify({"history": hist})

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "service": "osint-srv"})

    return app
