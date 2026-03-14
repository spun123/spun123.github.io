#!/usr/bin/env python3
"""Basic smoke checks for the static website."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "index.html",
    "product.html",
    "products/product-1.html",
    "products/product-2.html",
    "products/product-3.html",
    "products/product-4.html",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


def find_missing_local_refs() -> list[str]:
    html_files = list(ROOT.rglob("*.html"))
    missing: list[str] = []
    pattern = re.compile(r"(?:href|src)=['\"]([^'\"]+)['\"]")

    for html_file in html_files:
        text = html_file.read_text(encoding="utf-8")
        for ref in pattern.findall(text):
            if ref.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:", "data:")):
                continue
            target = (html_file.parent / ref).resolve()
            if not target.exists():
                missing.append(f"{html_file.relative_to(ROOT)} -> {ref}")
    return missing


def check_http_pages() -> list[CheckResult]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    results: list[CheckResult] = []
    try:
        for page in PAGES:
            url = urljoin("http://127.0.0.1:8765/", page)
            with urlopen(url, timeout=5) as response:
                status = response.getcode()
                body = response.read().decode("utf-8", errors="ignore")
                has_markup = "<html" in body.lower() and "</html>" in body.lower()
                results.append(
                    CheckResult(
                        name=page,
                        ok=status == 200 and has_markup,
                        message=f"status={status}, html_markup={has_markup}",
                    )
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    return results


def main() -> int:
    failures = 0

    missing_refs = find_missing_local_refs()
    if missing_refs:
        failures += len(missing_refs)
        print("[FAIL] Missing local references:")
        for item in missing_refs:
            print(f"  - {item}")
    else:
        print("[OK] All local href/src references resolve to existing files")

    page_results = check_http_pages()
    for result in page_results:
        tag = "OK" if result.ok else "FAIL"
        print(f"[{tag}] {result.name}: {result.message}")
        if not result.ok:
            failures += 1

    if failures:
        print(f"\nSmoke check completed with {failures} failure(s).")
        return 1

    print("\nSmoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
