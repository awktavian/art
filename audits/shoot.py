#!/usr/bin/env python3
"""Visual inspection rig: screenshot every app page via headless Chromium.

Usage: python3 audits/shoot.py [--base http://localhost:8899] [--out audits/shots]
                               [--width 1440] [--height 900] [--scale 0.5]
                               [--settle 2.5] [page ...]
Pages default to every top-level dir with an index.html plus 'apps' and 'home'.
Writes <out>/<name>.png (downscaled for review) and a shoot-log.json with
per-page load errors and console errors — broken pages are part of the audit.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SKIP = {
    "audits", "fonts", "scripts", "workspace", "node_modules", "shared",
    "lib", "assets", ".git", ".github", ".vercel", "kagami-validation-matrix",
    "shiba",
}


def default_pages():
    pages = []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in SKIP:
            continue
        if (d / "index.html").exists():
            pages.append(d.name)
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8899")
    ap.add_argument("--out", default=str(ROOT / "audits" / "shots"))
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--settle", type=float, default=2.5)
    ap.add_argument("pages", nargs="*")
    args = ap.parse_args()

    pages = args.pages or default_pages()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--enable-unsafe-swiftshader"])
        ctx = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )
        for name in pages:
            url = f"{args.base}/{name}/" if name not in ("",) else args.base
            entry = {"url": url, "console_errors": [], "page_errors": []}
            page = ctx.new_page()
            page.on(
                "console",
                lambda m, e=entry: e["console_errors"].append(m.text[:200])
                if m.type == "error"
                else None,
            )
            page.on(
                "pageerror",
                lambda exc, e=entry: e["page_errors"].append(str(exc)[:200]),
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    entry["networkidle"] = "timeout"
                time.sleep(args.settle)
                shot = out / f"{name}.png"
                page.screenshot(path=str(shot))
                if args.scale != 1.0:
                    w = int(args.width * args.scale)
                    subprocess.run(
                        ["sips", "--resampleWidth", str(w), str(shot)],
                        capture_output=True,
                    )
                entry["ok"] = True
            except Exception as exc:
                entry["ok"] = False
                entry["error"] = str(exc)[:300]
            finally:
                page.close()
            log[name] = entry
            status = "ok" if entry.get("ok") else "FAIL"
            errs = len(entry["console_errors"]) + len(entry["page_errors"])
            print(f"{status:4} {name} (js_errors={errs})", flush=True)
        browser.close()

    (out / "shoot-log.json").write_text(json.dumps(log, indent=2))
    fails = [k for k, v in log.items() if not v.get("ok")]
    errpages = [
        k
        for k, v in log.items()
        if v.get("ok") and (v["console_errors"] or v["page_errors"])
    ]
    print(f"\nshots={len(log)} fails={fails} js_error_pages={errpages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
