"""Join the rendered parts, add the mix normalised to -16 LUFS, write the final MP4.

    python finish.py out/section_0_58.mp4 out/section_58_116.mp4 out/section_116_174.mp4
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parts = [Path(p).resolve() for p in sys.argv[1:]] or [ROOT / "out" / "video.mp4"]
    listing = ROOT / "out" / "parts.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    joined = ROOT / "out" / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(joined)], check=True)
    final = ROOT / "mosca-launch-film.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-i", str(ROOT / "audio" / "mix.wav"),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(final)], check=True)
    print("wrote", final)


if __name__ == "__main__":
    main()
