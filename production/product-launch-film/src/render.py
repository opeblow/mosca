"""Render film.html frame by frame with Chromium and encode with FFmpeg.

    python render.py --stills 3,20,60           # preview frames as PNG
    python render.py --video                    # silent H.264 master, out/video.mp4
    python render.py --video --start 40 --end 60   # a section, for review
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def open_film(p):
    tl = json.loads((ROOT / "timeline.json").read_text())
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": tl["width"], "height": tl["height"]}, device_scale_factor=1)
    page.add_init_script(f"window.TIMELINE = {json.dumps(tl)};")
    page.goto((ROOT / "src" / "film.html").as_uri())
    page.evaluate("window.ready")
    page.wait_for_timeout(500)
    return browser, page, tl


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser, page, tl = open_film(p)
        if args.stills:
            (OUT / "stills").mkdir(exist_ok=True)
            for s in args.stills.split(","):
                t = float(s)
                page.evaluate(f"window.seek({t})")
                page.screenshot(path=str(OUT / "stills" / f"t{t:07.2f}.png"))
            print("stills written")
        if args.video:
            fps = tl["fps"]
            end = args.end if args.end is not None else tl["duration"]
            first, last = int(args.start * fps), int(end * fps)
            name = "video.mp4" if args.start == 0 and args.end is None else f"section_{args.start:g}_{end:g}.mp4"
            ff = subprocess.Popen([
                "ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
                "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(OUT / name)],
                stdin=subprocess.PIPE)
            t0 = time.time()
            for f in range(first, last):
                page.evaluate(f"window.seek({f / fps})")
                ff.stdin.write(page.screenshot(type="jpeg", quality=95))
                if f % 300 == 0:
                    print(f"frame {f}/{last}  {time.time() - t0:.0f}s", flush=True)
            ff.stdin.close()
            ff.wait()
            print("wrote", OUT / name)
        browser.close()


if __name__ == "__main__":
    main()
