"""Render each narration section with Kokoro (Apache 2.0, runs locally) and record durations.

    python tts.py                # all sections
    python tts.py --voice af_heart --only hook1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "assets" / "models"
OUT = ROOT / "audio" / "vo"
SR = 24000


def trim(audio: np.ndarray, thresh: float = 0.004) -> np.ndarray:
    """Cut leading and trailing silence, keeping 40 ms of air at each end."""
    idx = np.where(np.abs(audio) > thresh)[0]
    if not len(idx):
        return audio
    pad = int(0.04 * SR)
    return audio[max(0, idx[0] - pad): min(len(audio), idx[-1] + pad)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice")
    ap.add_argument("--only")
    args = ap.parse_args()
    spec = json.loads((ROOT / "narration.json").read_text(encoding="utf-8"))
    voice = args.voice or spec["voice"]
    kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    OUT.mkdir(parents=True, exist_ok=True)
    durations = {}
    dur_file = OUT / "durations.json"
    if dur_file.exists():
        durations = json.loads(dur_file.read_text())
    for sec in spec["sections"]:
        if args.only and sec["id"] != args.only:
            continue
        samples, sr = kokoro.create(sec["text"], voice=voice, speed=spec["speed"], lang="en-us")
        assert sr == SR
        audio = trim(np.asarray(samples, dtype=np.float32))
        sf.write(OUT / f"{sec['id']}.wav", audio, SR)
        durations[sec["id"]] = round(len(audio) / SR, 3)
        print(f"{sec['id']:8s} {durations[sec['id']]:6.2f}s  {sec['text'][:60]}")
    dur_file.write_text(json.dumps(durations, indent=2))
    print("total speech", round(sum(durations.values()), 1), "s")


if __name__ == "__main__":
    main()
