#!/usr/bin/env python3
"""Render tools/og-image.html into og-image.png (1200x630 social preview)."""
import pathlib, sys
from playwright.sync_api import sync_playwright

root = pathlib.Path(__file__).resolve().parent.parent
src, out = root / "tools" / "og-image.html", root / "og-image.png"
with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
    p.goto(src.as_uri())
    p.wait_for_timeout(300)
    p.screenshot(path=str(out))
    b.close()
print(f"{out} {out.stat().st_size // 1024} KiB", file=sys.stderr)
