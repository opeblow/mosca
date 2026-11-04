"""Compose the original score, place the narration, duck, and mix.

Everything here is synthesised from sine partials and filtered noise, so the score is
original and free to use. Output: audio/mix.wav (48 kHz stereo).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SR = 48000
RNG = np.random.default_rng(11)

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[pitch] + 12 * (octave + 1) - 69) / 12)


CHORDS = {
    "Dm": ["D2", "A2", "D3", "F3", "A3", "E4"],
    "Bb": ["A#1", "F2", "A#2", "D3", "F3", "C4"],
    "Gm": ["G1", "D2", "G2", "A#2", "D3", "A3"],
    "A": ["A1", "E2", "A2", "C#3", "E3", "B3"],
    "C": ["C2", "G2", "C3", "E3", "G3", "D4"],
    "F": ["F1", "C2", "F2", "A2", "C3", "G3"],
    "Fmaj7": ["F1", "C2", "F2", "A2", "E3", "C4"],
    "Fadd9": ["F1", "C2", "F2", "A2", "G3", "C4"],
}
SCALE_F = ["F4", "G4", "A4", "C5", "D5", "F5", "G5", "A5"]


def env(n: int, attack: float, release: float) -> np.ndarray:
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a) ** 2
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(0, len(x), 4096):  # block-wise one-pole for speed
        blk = x[i:i + 4096]
        out = np.empty_like(blk)
        for j, v in enumerate(blk):
            acc = (1 - a) * v + a * acc
            out[j] = acc
        y[i:i + 4096] = out
    return y


def pad(chord: str, dur: float, bright: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, note in enumerate(CHORDS[chord]):
        f = hz(note)
        for det in (-0.12, 0.0, 0.11):  # gentle chorus
            ff = f * 2 ** (det / 12)
            ph = RNG.uniform(0, 2 * np.pi)
            tone = np.sin(2 * np.pi * ff * t + ph) + 0.28 * bright * np.sin(4 * np.pi * ff * t + ph) \
                + 0.1 * bright * np.sin(6 * np.pi * ff * t)
            out += tone * (0.9 if k < 2 else 0.55) / 3
    lfo = 1 + 0.06 * np.sin(2 * np.pi * 0.11 * t)
    return out * lfo * env(n, min(2.5, dur / 3), min(2.5, dur / 3)) * 0.06


def pluck(note: str, dur: float = 1.4, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(note)
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 3.99 * f * t) * np.exp(-t * 18)
         + 0.15 * np.sin(2 * np.pi * 2 * f * t))
    return x * np.exp(-t * 4.2) * env(n, 0.004, 0.05) * 0.05 * vel


def bell(note: str, dur: float = 5.0, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(note)
    ratios = [(1, 1.0, 1.6), (2.76, .45, 2.6), (5.4, .25, 4.0), (8.93, .12, 6.0), (0.5, .4, 1.0)]
    x = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d) for r, a, d in ratios)
    return x * env(n, 0.003, 0.3) * 0.07 * vel


def thump(dur: float = 0.9, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 52 + 40 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.22 * vel


def tick(vel: float = 1.0) -> np.ndarray:
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    x = RNG.standard_normal(n) * np.exp(-t * 400) + np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 300)
    return x * 0.03 * vel


def whoosh(dur: float = 0.9, vel: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    x = RNG.standard_normal(n)
    shape = np.sin(np.linspace(0, np.pi, n)) ** 2
    y = lowpass(x * shape, 900) + 0.3 * lowpass(x * shape, 3000)
    return y * 0.12 * vel


def add(buf: np.ndarray, x: np.ndarray, at: float, pan: float = 0.0) -> None:
    i = int(at * SR)
    if i < 0:
        x, i = x[-i:], 0
    if i >= len(buf):
        return
    x = x[: len(buf) - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(x), 0] += x * l * 1.41
    buf[i:i + len(x), 1] += x * r * 1.41


def main() -> None:
    tl = json.loads((ROOT / "timeline.json").read_text())
    total = tl["duration"]
    sc = {s["id"]: s for s in tl["scenes"]}
    cues = {c["id"]: c for c in tl["cues"]}
    n = int((total + 0.5) * SR)
    music = np.zeros((n, 2))
    sfx = np.zeros((n, 2))

    def chords(start: float, end: float, seq: list[str], bright: float = 1.0) -> None:
        step = (end - start) / len(seq)
        for i, c in enumerate(seq):
            add(music, pad(c, step + 2.5, bright), start + i * step - 0.6, pan=(-0.2 if i % 2 else 0.2))

    # Act one: the recording. A low minor drone, a quiet clock.
    chords(0, sc["problem"]["end"], ["Dm", "Dm", "Bb", "Dm"], bright=0.5)
    beat = 60 / 72
    t = 1.0
    while t < sc["problem"]["end"] - 0.5:
        add(sfx, tick(0.8 if int(t / beat) % 4 == 0 else 0.45), t, pan=0.3)
        t += beat
    # The inequality: tension, a slow pulse.
    chords(sc["inequality"]["start"], sc["questions"]["end"], ["Gm", "A", "Bb", "C"], bright=0.8)
    t = sc["inequality"]["start"]
    while t < sc["questions"]["end"] - 0.4:
        add(music, thump(vel=0.6), t)
        t += beat * 2
    # Reveal: the world turns to paper. A bell and an open major chord.
    rv = sc["reveal"]["start"]
    add(sfx, whoosh(1.2, 0.8), rv - 0.9)
    add(music, thump(1.4, 1.2), rv)
    for k, note in enumerate(["F4", "C5", "A5"]):
        add(music, bell(note, 6, 0.9 - k * 0.2), rv + 0.25 + k * 0.09, pan=-0.3 + 0.3 * k)
    chords(rv, sc["reveal"]["end"], ["Fmaj7"], bright=1.1)
    # The demonstration: a steady, warm loop with a plucked figure.
    demo_start, demo_end = sc["scan"]["start"], sc["review"]["end"]
    chords(demo_start, demo_end, ["F", "C", "Dm", "Bb"] * 3, bright=1.0)
    eighth = 60 / 96 / 2
    pattern = [0, 2, 4, 2, 5, 4, 2, 1]
    t, k = demo_start + 0.5, 0
    while t < demo_end - 0.5:
        prog_ = (t - demo_start) / (demo_end - demo_start)
        vel = 0.45 + 0.4 * prog_
        if k % 8 in (0, 3, 5) or prog_ > 0.35:
            add(music, pluck(SCALE_F[pattern[k % 8]], vel=vel), t, pan=0.35 * np.sin(k))
        t += eighth
        k += 1
    # Accents: a soft whoosh on wipes, a click when a scene cuts.
    for s in tl["scenes"][1:]:
        add(sfx, whoosh(0.8, 0.5) if s["id"] in ("inequality", "migrate") else tick(0.9), s["start"] - 0.1)
    add(music, bell("C6", 3, 0.5), cues["core4"]["start"] + (cues["core4"]["end"] - cues["core4"]["start"]) * .7)
    add(music, bell("A5", 3, 0.45), cues["deep2"]["start"] + 0.6)
    # The record and the close: resolve.
    chords(sc["ledger"]["start"], sc["ledger"]["end"], ["Bb", "F", "C"], bright=0.9)
    cl = sc["close"]
    chords(cl["start"], cl["end"] + 1, ["Dm", "Bb", "Fadd9"], bright=1.0)
    end_at = cues["close2"]["end"] + 1.5
    add(music, thump(1.6, 0.9), end_at)
    for k, note in enumerate(["F3", "C4", "F4", "A4", "C5"]):
        add(music, bell(note, 7, 0.8), end_at + k * 0.12, pan=-0.4 + 0.2 * k)

    # Narration, placed on its cues.
    vo = np.zeros(n)
    for c in tl["cues"]:
        x, sr = sf.read(ROOT / "audio" / "vo" / f"{c['id']}.wav")
        if x.ndim > 1:
            x = x.mean(axis=1)
        x = np.interp(np.arange(0, len(x), sr / SR), np.arange(len(x)), x)  # 24 kHz -> 48 kHz
        i = int(c["start"] * SR)
        vo[i:i + len(x)] += x[: n - i]
    # Duck the music by about 9 dB under speech, with smooth attack and release.
    def moving_average(x: np.ndarray, width: int) -> np.ndarray:
        c = np.cumsum(np.concatenate([np.zeros(width // 2 + 1), x, np.zeros(width // 2)]))
        return (c[width:] - c[:-width])[: len(x)] / width

    level = moving_average(np.abs(vo), 2400)
    speaking = (level > 0.01).astype(float)
    # Two passes of a 0.3 s box filter: a smooth, symmetric attack and release.
    smooth = moving_average(moving_average(speaking, int(0.3 * SR)), int(0.3 * SR))
    duck = 1 - 0.65 * np.clip(smooth, 0, 1)
    # Fade the whole score in and out.
    fade = np.ones(n)
    fade[: int(1.5 * SR)] = np.linspace(0, 1, int(1.5 * SR))
    tail = int(2.5 * SR)
    fade[-tail:] = np.linspace(1, 0, tail) ** 1.5
    mix = (music * duck[:, None] + sfx * (0.6 + 0.4 * duck[:, None])) * fade[:, None]
    mix += np.stack([vo, vo], axis=1) * 0.9
    peak = np.abs(mix).max()
    mix = mix / peak * 0.89
    (ROOT / "audio").mkdir(exist_ok=True)
    sf.write(ROOT / "audio" / "mix.wav", mix.astype(np.float32), SR, subtype="FLOAT")
    sf.write(ROOT / "audio" / "music.wav", (music * fade[:, None] / max(1e-9, np.abs(music).max()) * 0.8).astype(np.float32), SR)
    print(f"mix {n / SR:.1f}s, peak before normalise {peak:.2f}")


if __name__ == "__main__":
    main()
