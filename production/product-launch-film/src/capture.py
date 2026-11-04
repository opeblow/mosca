"""Capture real product footage: the q-day room in Mattermost, the website and the ledger.

    python capture.py --mm http://localhost:18065 --web http://localhost:3100

Reads the Mattermost login from ../../../.private/switch.env (never printed).
Writes PNGs to ../capture/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "capture"
ENV = HERE.parents[2] / ".private" / "switch.env"

# (file name, text that identifies the post, which match to take)
POSTS = [
    ("p01_scan_cmd", "@Mosca scan", 0),
    ("p02_cbom_doc", "created room document “CBOM acme-payments main”", 0),
    ("p03_report", "Scanned main at 3f68c6e", 0),
    ("p04_question", "Question for dev, owner of auth", 0),
    ("p05_answer_cmd", "@Mosca 10 years", 0, "Question"),
    ("p06_recorded", "Recorded in the ledger", 0),
    ("p07_mig_cmd", "Fix the edge TLS config", 0),
    ("p08_mig_reply", "I updated the edge TLS config", 0),
    ("p09_rescan_cmd", "@Mosca rescan pq/edge-hybrid-tls", 0),
    ("p10_rescan", "Rescanned pq/edge-hybrid-tls", 0),
    ("p11_rev_cmd", "Review branch pq/edge-hybrid-tls", 0),
    ("p12_rev_reply", "Reviewed git diff main pq/edge-hybrid-tls", 0),
    ("p13_approve", "Approved. pq/edge-hybrid-tls is good to merge", 0),
    ("p14_decline", "I haven't merged", 0),
    ("p15_final", "Scanned main at 393235b", 0),
]


def creds() -> tuple[str, str]:
    env = dict(line.strip().split("=", 1) for line in ENV.read_text().splitlines() if "=" in line)
    return env["MATTERMOST_USER"], env["MATTERMOST_USER_PASSWORD"]


def login(ctx, mm: str) -> None:
    """Sign in through the API and give the browser the session cookies."""
    user, password = creds()
    r = ctx.request.post(f"{mm}/api/v4/users/login", data={"login_id": user, "password": password})
    assert r.ok, f"login failed: {r.status}"
    host = mm.split("://", 1)[1].split(":")[0]
    token = r.headers["token"]
    ctx.add_cookies([
        {"name": "MMAUTHTOKEN", "value": token, "domain": host, "path": "/"},
        {"name": "MMUSERID", "value": r.json()["id"], "domain": host, "path": "/"},
    ])
    ctx.add_init_script("try { localStorage.setItem('__landingPageSeen__', 'true') } catch (e) {}")


def capture_room(p, mm: str, only: set[str] | None = None) -> None:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1200, "height": 1000}, device_scale_factor=2)
    login(ctx, mm)
    page = ctx.new_page()
    page.goto(f"{mm}/switch/channels/q-day")
    page.wait_for_selector("div.post", timeout=60000)
    page.wait_for_timeout(2500)
    # Load the whole channel history by scrolling to the top a few times.
    for _ in range(6):
        page.evaluate("document.querySelector('.post-list__dynamic')?.scrollTo(0, 0)")
        page.wait_for_timeout(700)
    page.add_style_tag(content="""
      .post__header .post-menu, .post-menu, .post-pre-header, [class*="hover"] .post-menu { display:none !important; }
      .post:hover { background: transparent !important; }
    """)
    for name, text, nth, *skip in POSTS:
        if only and name not in only:
            continue
        loc = page.locator("div.post").filter(has_text=text)
        if skip:
            loc = loc.filter(has_not_text=skip[0])
        loc = loc.nth(nth)
        try:
            loc.scroll_into_view_if_needed(timeout=15000)
            page.mouse.move(5, 5)
            page.wait_for_timeout(400)
            loc.screenshot(path=str(OUT / f"{name}.png"))
            print("ok", name)
        except Exception as exc:  # keep going; report what is missing
            print("MISSING", name, type(exc).__name__)
    if only:
        browser.close()
        return
    # An establishing shot of the whole room.
    big = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    login(big, mm)
    bp = big.new_page()
    bp.goto(f"{mm}/switch/channels/q-day")
    bp.wait_for_selector("div.post", timeout=60000)
    bp.wait_for_timeout(3000)
    bp.screenshot(path=str(OUT / "room_wide.png"))
    browser.close()


def capture_web(p, web: str) -> None:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(web, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "web_hero.png"))
    page.screenshot(path=str(OUT / "web_full.png"), full_page=True)
    page.goto(f"{web}/ledger", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "ledger_view.png"))
    page.screenshot(path=str(OUT / "ledger_full.png"), full_page=True)
    browser.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mm")
    ap.add_argument("--web")
    ap.add_argument("--only", help="comma-separated post names to recapture")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        if args.web:
            capture_web(p, args.web)
        if args.mm:
            capture_room(p, args.mm, set(args.only.split(",")) if args.only else None)


if __name__ == "__main__":
    main()
