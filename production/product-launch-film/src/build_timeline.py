"""Build timeline.json from the scene plan and the measured narration durations."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = 174.0  # seconds; the brief asks for 165 to 180

# scene id, lead-in pause, [(section, pause after)], tail pause, transition into next
PLAN = [
    ("hook", 1.4, [("hook1", 0.9), ("hook2", 1.1), ("hook3", 0.0)], 1.6, "cut"),
    ("problem", 0.5, [("prob1", 0.7), ("prob2", 0.0)], 0.9, "wipe"),
    ("inequality", 0.4, [("prob3", 0.0)], 1.4, "cut"),
    ("questions", 0.3, [("prob4", 0.0)], 1.0, "fade"),
    ("reveal", 1.2, [("reveal", 0.0)], 2.0, "rise"),
    ("scan", 0.5, [("core1", 0.7), ("core2", 0.0)], 0.8, "cut"),
    ("question", 0.4, [("core3", 0.9), ("core4", 0.0)], 1.2, "wipe"),
    ("migrate", 0.5, [("deep1", 0.8), ("deep2", 0.0)], 0.9, "cut"),
    ("review", 0.4, [("deep3", 0.8), ("deep4", 0.0)], 1.2, "fade"),
    ("ledger", 0.5, [("pay1", 0.8), ("pay2", 0.0)], 1.2, "cut"),
    ("close", 1.0, [("close1", 1.4), ("close2", 0.0)], 6.0, "end"),
]


def main() -> None:
    dur = json.loads((ROOT / "audio" / "vo" / "durations.json").read_text())
    texts = {s["id"]: s["text"] for s in json.loads((ROOT / "narration.json").read_text(encoding="utf-8"))["sections"]}
    speech = sum(dur[s] for _, _, secs, _, _ in PLAN for s, _ in secs)
    pauses = sum(lead + tail + sum(p for _, p in secs) for _, lead, secs, tail, _ in PLAN)
    scale = max(0.6, (TARGET - speech) / pauses)
    t = 0.0
    scenes, cues = [], []
    for sid, lead, secs, tail, trans in PLAN:
        start = t
        t += lead * scale
        for sec, gap in secs:
            cues.append({"id": sec, "start": round(t, 3), "end": round(t + dur[sec], 3), "text": texts[sec]})
            t += dur[sec] + gap * scale
        t += tail * scale
        scenes.append({"id": sid, "start": round(start, 3), "end": round(t, 3), "transition": trans})
    out = {"fps": 30, "width": 1920, "height": 1080, "duration": round(t, 3),
           "pause_scale": round(scale, 3), "scenes": scenes, "cues": cues}
    (ROOT / "timeline.json").write_text(json.dumps(out, indent=2))
    print(f"speech {speech:.1f}s, pauses x{scale:.2f}, total {t:.1f}s")
    for s in scenes:
        print(f"  {s['id']:11s} {s['start']:6.1f} - {s['end']:6.1f}")


if __name__ == "__main__":
    main()
