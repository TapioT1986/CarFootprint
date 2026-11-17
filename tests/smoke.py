"""Smoke test for the built page, run on GitHub after every push (.github/workflows/test.yml).

Opens index.html in headless Chromium at phone width (390 px) and desktop width,
in Finnish and English, and runs tests/smoke_checks.js: cards and results show the
same cars (also after the maximum price changes and after picking a model), the
page fits the screen, the model search list is visible, and the page throws no
JavaScript errors.

Needs Playwright (pip install playwright; python -m playwright install chromium).
It does not run on the owner's Windows PC, where Smart App Control blocks it.
    python tests/smoke.py
"""
import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
_js = (ROOT / "tests" / "smoke_checks.js").read_text(encoding="utf-8")
CHECKS = _js[_js.index("async () =>"):]  # drop the leading comment so Playwright sees a function
SIZES = {"phone": {"width": 390, "height": 844}, "desktop": {"width": 1280, "height": 900}}


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    server = serve()
    url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size_name, size in SIZES.items():
            for lang in ("fi", "en"):
                # a fresh context = empty localStorage, like a first visit
                ctx = browser.new_context(viewport=size, is_mobile=size_name == "phone",
                                          has_touch=size_name == "phone")
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url)
                page.wait_for_selector("#sums .big")
                if lang == "en":
                    page.click(".lang[data-lang='en']")
                    page.wait_for_function("document.documentElement.lang === 'en'")
                problems = page.evaluate(CHECKS)
                problems += [f"{lang}: JavaScript error: {e}" for e in errors]
                for pr in problems:
                    failures.append(f"[{size_name}] {pr}")
                print(f"{size_name:7} {lang}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
                ctx.close()
        browser.close()
    server.shutdown()
    if failures:
        print("\nProblems found:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
