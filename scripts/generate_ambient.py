"""Generate simple ambient background tones for reels using FFmpeg.

Creates soft sine-wave based ambient tracks suitable for background music.
Run: python scripts/generate_ambient.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

AUDIO_DIR = Path(__file__).parent.parent / "audio"


def generate_track(name: str, freq: float, duration: int = 30) -> None:
    """Generate a soft ambient tone using FFmpeg's sine wave generator."""
    output = AUDIO_DIR / f"{name}.mp3"
    if output.exists():
        print(f"  Skipping {name} (already exists)")
        return

    # Layer multiple sine waves for a richer ambient sound
    # Main tone + fifth + octave, all at low volume with fade in/out
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        (
            f"sine=frequency={freq}:duration={duration},"
            f"volume=0.15"
        ),
        "-f", "lavfi", "-i",
        (
            f"sine=frequency={freq * 1.5}:duration={duration},"
            f"volume=0.08"
        ),
        "-f", "lavfi", "-i",
        (
            f"sine=frequency={freq * 2}:duration={duration},"
            f"volume=0.05"
        ),
        "-filter_complex",
        (
            "[0:a][1:a][2:a]amix=inputs=3:duration=longest,"
            f"afade=t=in:st=0:d=3,"
            f"afade=t=out:st={duration - 3}:d=3,"
            "lowpass=f=2000,"
            "volume=0.6"
        ),
        "-c:a", "libmp3lame", "-q:a", "4",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Created {name}.mp3")
    else:
        print(f"  Failed to create {name}: {result.stderr[-200:]}")


def main() -> None:
    if not shutil.which("ffmpeg"):
        print("Error: FFmpeg not found. Install it first.")
        sys.exit(1)

    AUDIO_DIR.mkdir(exist_ok=True)
    print("Generating ambient tracks...")

    # Soft, warm tones in different keys
    tracks = [
        ("ambient_warm", 220.0),       # A3 — warm, meditative
        ("ambient_peaceful", 261.63),   # C4 — neutral, calm
        ("ambient_deep", 164.81),       # E3 — deep, grounding
        ("ambient_hopeful", 293.66),    # D4 — bright, uplifting
        ("ambient_reflective", 196.0),  # G3 — contemplative
    ]

    for name, freq in tracks:
        generate_track(name, freq)

    print(f"\nDone! Tracks saved to {AUDIO_DIR}")
    print("Replace these with real royalty-free music from Pixabay or Mixkit for better quality.")


if __name__ == "__main__":
    main()
