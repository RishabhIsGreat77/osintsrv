cat > core/output.py <<'PYEOF'
"""
core/output.py — output formatters for osint-srv.

- print_table: pretty terminal output via rich
- to_json: machine-readable
- to_csv: spreadsheet-friendly
- print_banner: tool header
"""

import csv
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


console = Console()


def print_banner(module: str, target: str) -> None:
    text = Text()
    text.append("osint-srv", style="bold cyan")
    text.append("  ::  ")
    text.append(module, style="bold yellow")
    text.append("  ::  ")
    text.append(target, style="bold white")
    console.print(Panel(text, border_style="cyan"))


def print_table(
    title: str,
    columns: List[str],
    rows: List[List[str]],
    footer: Optional[str] = None,
) -> None:
    table = Table(title=title, show_lines=False, header_style="bold magenta")
    for col in columns:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print(table)
    if footer:
        console.print(f"[dim]{footer}[/dim]")


def print_found_list(items: List[Dict[str, Any]]) -> None:
    """Print a compact list of found items."""
    for it in items:
        site = it.get("site", "?")
        url = it.get("url", "")
        console.print(f"  [green]✓[/green] [bold]{site}[/bold]  [dim]{url}[/dim]")


def to_json(
    data: Dict[str, Any],
    path: Optional[str] = None,
) -> str:
    payload = json.dumps(data, indent=2, default=str, ensure_ascii=False)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(payload, encoding="utf-8")
        console.print(f"[green]saved:[/green] {path}")
    else:
        print(payload)
    return payload


def to_csv(
    rows: List[Dict[str, Any]],
    path: str,
    fieldnames: Optional[List[str]] = None,
) -> None:
    if not rows:
        console.print("[yellow]no rows to write[/yellow]")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    console.print(f"[green]saved:[/green] {path}")


def status_icon(status: int) -> str:
    if status == 200:
        return "[green]✓[/green]"
    if status in (301, 302):
        return "[cyan]→[/cyan]"
    if status == 404:
        return "[red]✗[/red]"
    if status in (403, 429):
        return "[yellow]⚠[/yellow]"
    if status == 0:
        return "[red]·[/red]"
    return f"[dim]{status}[/dim]"
PYEOF
