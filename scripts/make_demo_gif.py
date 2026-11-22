"""Render docs/demo.gif — an animated terminal recording of `newsscan demo`.

Runs the real CLI with rich's recording console, then draws each command being typed and
its colored output line by line with Pillow. Fully offline; uses only the fictional demo data.

    pip install pillow
    python scripts/make_demo_gif.py
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsscan import cli, report  # noqa: E402

COLS = 104
FONT_SIZE = 15
PAD = 18
BG = (24, 26, 33)
FG = (220, 223, 228)
TITLE_BG = (40, 43, 52)
MAX_ROWS = 32  # visible terminal rows; older lines scroll off

# Standard ANSI colors mapped to a pleasant dark palette.
ANSI = {
    "black": (60, 63, 70), "red": (240, 98, 102), "green": (110, 210, 120), "yellow": (235, 200, 100),
    "blue": (100, 160, 240), "magenta": (200, 130, 230), "cyan": (90, 200, 215), "white": FG,
    "bright_black": (120, 124, 134),
}


def _font(bold=False):
    name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    for d in ("/usr/share/fonts/truetype/dejavu", "/Library/Fonts", "C:/Windows/Fonts"):
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), FONT_SIZE)
    return ImageFont.load_default()


def capture(argv: list[str]) -> list[list[tuple[str, tuple, bool]]]:
    """Run a CLI command and return its output as lines of (text, rgb, bold) spans."""
    con = Console(record=True, width=COLS, force_terminal=True, color_system="truecolor", file=io.StringIO())
    report.console = con
    cli.report.console = con
    cli.main(argv)
    lines: list[list] = [[]]
    for seg in con._record_buffer:
        style = seg.style
        rgb, bold = FG, False
        if style:
            bold = bool(style.bold)
            if style.color is not None:
                name = style.color.name
                rgb = ANSI.get(name) or (style.color.get_truecolor().red, style.color.get_truecolor().green,
                                         style.color.get_truecolor().blue)
            if style.dim:
                rgb = ANSI["bright_black"]
        parts = seg.text.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((part, rgb, bold))
    while lines and not lines[-1]:
        lines.pop()
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="docs/demo.gif")
    args = ap.parse_args()

    font, bold_font = _font(), _font(True)
    cw = font.getbbox("M")[2]
    lh = int(FONT_SIZE * 1.45)
    W = PAD * 2 + cw * COLS
    H = 34 + PAD * 2 + lh * MAX_ROWS

    scenes = [
        (["demo", "--headlines", "0"], "newsscan demo"),
    ]
    # Split the single demo run into its three sections so each gets its own "command".
    out = capture(scenes[0][0])
    assert out, "demo produced no output"
    sections, cur = [], []
    for ln in out:
        text = "".join(t for t, _, _ in ln)
        if text.startswith("─") and cur:
            sections.append(cur)
            cur = []
        cur.append(ln)
    sections.append(cur)
    # sections[0] is the banner; the rest are the four demo steps.
    commands = ["newsscan demo",
                "newsscan scan",
                "newsscan cues",
                "newsscan scan --notify        # next run, 2 hours later",
                "newsscan size --capital 100000 --entry 500 --stop 480 --target 560"]
    sections[1] = sections[0] + sections[1]
    sections = sections[1:]
    commands = commands[1:]

    frames: list[Image.Image] = []
    durations: list[int] = []
    screen: list[list] = []

    def render() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 30], fill=TITLE_BG)
        for i, c in enumerate([(240, 98, 102), (235, 200, 100), (110, 210, 120)]):
            d.ellipse([14 + i * 20, 10, 26 + i * 20, 22], fill=c)
        title = "newsscan — demo · fictional companies, made-up headlines"
        d.text((W // 2 - cw * len(title) // 2, 7), title, font=font, fill=ANSI["bright_black"])
        y = 34 + PAD
        for ln in screen[-MAX_ROWS:]:
            x = PAD
            for text, rgb, b in ln:
                d.text((x, y), text, font=bold_font if b else font, fill=rgb)
                x += cw * len(text)
            y += lh
        return img

    def snap(ms: int) -> None:
        frames.append(render())
        durations.append(ms)

    prompt = [("$ ", ANSI["green"], True)]
    for cmd, body in zip(commands, sections):
        screen.append(list(prompt))
        snap(400)
        typed = ""
        for ch in cmd:
            typed += ch
            screen[-1] = prompt + [(typed, FG, False)]
            if ch == " " or len(typed) == len(cmd):
                snap(60)
        snap(500)
        # Reveal output a few lines at a time (tables appear quickly, like a real terminal).
        for i in range(0, len(body), 3):
            screen.extend(body[i:i + 3])
            snap(90)
        snap(2600)
        screen.append([])

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    pal[0].save(args.out, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {args.out}: {len(frames)} frames, {W}x{H}, {Path(args.out).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
