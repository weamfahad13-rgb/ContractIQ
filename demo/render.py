"""Turn demo/build/storyboard.json into demo/build/ContractIQ-demo.mp4.

    python demo/render.py

Camera zooms, cursor, click ripples, captions and cross-fades are drawn with Pillow; the
sound effects and background pad are synthesized with numpy (no third-party audio), and
ffmpeg encodes the result.
"""

import json
import math
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path(__file__).parent / "build"
FPS = 30
SR = 44100
FONTS = Path("C:/Windows/Fonts")

NAVY = (7, 18, 38)
ACCENT = (34, 211, 238)
WHITE = (255, 255, 255)
MUTED = (159, 179, 200)

CAMERA_S = 0.9  # zoom move duration
CURSOR_S = 0.55  # cursor move duration
FADE_S = 0.4  # cross-fade between screenshots
MAX_ZOOM = 2.4

# Which effects are audible. Available: "whoosh", "click", "type", "pop", "rise".
SOUNDS = {"type"}
MUSIC = False  # the quiet background chord pad


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def lerp(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


# ---------------------------------------------------------------- camera

def fit(rect, W, H):
    """Grow a focus box to the video's aspect ratio, cap the zoom, keep it inside the frame."""
    if not rect:
        return [0.0, 0.0, float(W), float(H)]
    x, y, w, h = rect
    aspect = W / H
    w, h = max(w, h * aspect, W / MAX_ZOOM), max(h, w / aspect, H / MAX_ZOOM)
    w, h = max(w, h * aspect), max(h, w / aspect)
    w, h = min(w, W), min(h, H)
    cx, cy = x + rect[2] / 2, y + rect[3] / 2
    x = min(max(cx - w / 2, 0), W - w)
    y = min(max(cy - h / 2, 0), H - h)
    return [x, y, w, h]


def view(img: Image.Image, rect, W, H) -> Image.Image:
    x, y, w, h = rect
    return img.resize((W, H), Image.Resampling.BICUBIC, box=(x, y, x + w, y + h))


def to_screen(p, rect, W, H):
    x, y, w, h = rect
    return ((p[0] - x) * W / w, (p[1] - y) * H / h)


# ---------------------------------------------------------------- overlays

def make_cursor() -> Image.Image:
    s = 4  # draw big, then shrink for smooth edges
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    img = Image.new("RGBA", (40 * s, 50 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shadow = [(px * s + 3 * s, py * s + 3 * s) for px, py in pts]
    d.polygon(shadow, fill=(0, 0, 0, 90))
    img = img.filter(ImageFilter.GaussianBlur(2 * s))
    d = ImageDraw.Draw(img)
    d.polygon([(px * s + 4, py * s + 4) for px, py in pts], fill=WHITE, outline=NAVY, width=2 * s)
    return img.resize((40, 50), Image.Resampling.LANCZOS)


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if f.getlength(trial) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


CAPTION_MARGIN = 30  # transparent room around the card for its shadow


def make_caption(tag: str, title: str, body: str) -> Image.Image:
    """A light card with dark text, so it reads as a video overlay, not part of the dark app UI."""
    f_tag, f_title, f_body = font("segoeuib.ttf", 20), font("segoeuib.ttf", 40), font("segoeui.ttf", 25)
    width = 900
    body_lines = wrap(body, f_body, width - 72)
    h = 40 + 30 + 56 + 36 * len(body_lines) + 32
    m = CAPTION_MARGIN
    img = Image.new("RGBA", (width + 2 * m, h + 2 * m), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([m, m + 8, m + width, m + h + 8], radius=22, fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([m, m, m + width - 1, m + h - 1], radius=22, fill=(248, 250, 252, 255))
    d.rounded_rectangle([m, m, m + 10, m + h - 1], radius=5, fill=(*ACCENT, 255))
    d.text((m + 36, m + 36), " ".join(tag), font=f_tag, fill=(8, 145, 178))
    d.text((m + 36, m + 66), title, font=f_title, fill=NAVY)
    for i, line in enumerate(body_lines):
        d.text((m + 36, m + 126 + 36 * i), line, font=f_body, fill=(71, 85, 105))
    return img


def caption_y(cap: Image.Image, top: bool, H: int) -> int:
    m = CAPTION_MARGIN
    return 60 - m if top else H - cap.height - 60 + m


def covers(focus, cam, cap: Image.Image, W, H) -> bool:
    """True when the bottom caption would overlap the focused element on screen."""
    if not focus:
        return False
    x0, y0 = to_screen(focus[:2], cam, W, H)
    x1, y1 = to_screen((focus[0] + focus[2], focus[1] + focus[3]), cam, W, H)
    m = CAPTION_MARGIN  # the card sits inside the shadow margin
    cx0, cy0, cx1 = 60, H - (cap.height - 2 * m) - 60, 60 + cap.width - 2 * m
    return x0 < cx1 and x1 > cx0 and y1 > cy0


def with_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 1:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


def ripple(frame: Image.Image, pos, t: float):
    """Expanding ring under the cursor, t in [0, 1]."""
    if not 0 <= t <= 1:
        return
    r = 10 + 46 * ease(t)
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r],
                                  outline=(*ACCENT, int(230 * (1 - t))), width=5)
    frame.alpha_composite(layer)


# ---------------------------------------------------------------- title / outro cards

def card(W, H, title: str, subtitle: str, lines: list[str], mascot: str | None) -> Image.Image:
    img = Image.new("RGBA", (W, H), (*NAVY, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.45, -H * 0.4, W * 1.25, H * 0.7], fill=(*ACCENT, 38))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(img)
    x = 140
    d.text((x, 300), "AI FOR PROCUREMENT TEAMS", font=font("segoeuib.ttf", 26), fill=ACCENT)
    d.text((x, 345), title, font=font("segoeuib.ttf", 120), fill=WHITE)
    d.text((x, 500), subtitle, font=font("segoeui.ttf", 40), fill=(220, 230, 240))
    for i, line in enumerate(lines):
        d.text((x, 600 + 52 * i), line, font=font("segoeui.ttf", 30), fill=MUTED)
    if mascot:
        m = Image.open(ROOT / "assets" / "mascots" / mascot).convert("RGBA")
        m.thumbnail((760, 820))
        img.alpha_composite(m, (W - m.width - 90, (H - m.height) // 2 + 30))
    return img


# ---------------------------------------------------------------- sound

def env(n, attack, release):
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass_sweep(x, cutoffs):
    """One-pole low-pass whose cutoff (Hz) changes per sample."""
    y = np.zeros_like(x)
    a = 1 - np.exp(-2 * np.pi * cutoffs / SR)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def sfx_whoosh(rng):
    n = int(0.75 * SR)
    t = np.linspace(0, 1, n)
    cut = 300 + 5200 * np.sin(np.pi * t) ** 2
    s = lowpass_sweep(rng.standard_normal(n), cut) * np.sin(np.pi * t) ** 2
    s = s / (np.abs(s).max() + 1e-9) * 0.32
    pan = np.linspace(0.25, 0.75, n)
    return np.stack([s * (1 - pan) * 2, s * pan * 2], axis=1)


def sfx_click(rng):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    s = 0.35 * np.sin(2 * np.pi * 1900 * t) * np.exp(-t * 95) + 0.2 * rng.standard_normal(n) * np.exp(-t * 400)
    return np.stack([s, s], axis=1)


def sfx_type(rng):
    n = int(0.035 * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n + 1))
    s = 0.07 * noise * np.exp(-t * 300) + 0.05 * np.sin(2 * np.pi * rng.uniform(2200, 3200) * t) * np.exp(-t * 200)
    return np.stack([s, s], axis=1)


def sfx_pop(rng):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = 620 + 700 * (1 - np.exp(-t * 30))
    s = 0.26 * (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR))
    s *= np.exp(-t * 16) * env(n, 0.004, 0.05)
    return np.stack([s, s], axis=1)


def sfx_rise(rng):
    n = int(1.6 * SR)
    t = np.linspace(0, 1, n)
    f = 180 + 700 * t ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.12 + np.sin(4 * np.pi * np.cumsum(f) / SR) * 0.05
    air = lowpass_sweep(rng.standard_normal(n), 400 + 6000 * t ** 2) * 0.22
    s = (tone + air) * (t ** 1.5) * env(n, 0, 0.12)
    return np.stack([s, s], axis=1)


SFX = {"whoosh": sfx_whoosh, "click": sfx_click, "type": sfx_type, "pop": sfx_pop, "rise": sfx_rise}


def pad(seconds: float) -> np.ndarray:
    """A quiet, slowly moving chord bed (A minor, F, C, G)."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    out = np.zeros(n)
    bar = 4.0
    for i in range(int(seconds // bar) + 1):
        a, b = int(i * bar * SR), min(n, int((i + 1.25) * bar * SR))
        if a >= n:
            break
        seg = t[a:b] - i * bar
        e = np.sin(np.pi * np.clip(seg / (1.25 * bar), 0, 1)) ** 2
        for f in chords[i % 4]:
            out[a:b] += (np.sin(2 * np.pi * f * seg) + 0.25 * np.sin(4 * np.pi * f * seg)) * e
    out *= 0.018 * env(n, 2.5, 3.0)
    return np.stack([out, out * 0.96], axis=1)


def write_wav(path: Path, audio: np.ndarray):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- main

def main() -> None:
    board = json.loads((BUILD / "storyboard.json").read_text(encoding="utf-8"))
    W, H = board["width"], board["height"]
    shots = {}

    def shot(name):
        if name not in shots:
            shots[name] = Image.open(BUILD / "shots" / name).convert("RGBA")
        return shots[name]

    title = card(W, H, "ContractIQ", "Your contracts. Clear answers.",
                 ["A bilingual RAG assistant for supplier contracts", "and purchase-order data."], "mascot-landing.webp")
    outro = card(W, H, "ContractIQ", "Hybrid search · Reranking · Text-to-SQL",
                 ["Arabic & English · Clause-level citations · Evaluated on CUAD",
                  "Python · FastAPI · PostgreSQL + pgvector · BGE-M3 · Gemini"], "mascot-evaluation.webp")
    segments = ([{"card": title, "dur": 4.2, "sfx": ["rise"]}] + board["segments"]
                + [{"card": outro, "dur": 5.5, "sfx": ["whoosh"]}])

    total = sum(s["dur"] for s in segments)
    n_frames = int(round(total * FPS))
    audio = np.zeros((int((total + 1) * SR), 2))
    rng = np.random.default_rng(7)

    def place(name, at):
        clip = SFX[name](rng)
        i = int(at * SR)
        audio[i:i + len(clip)] += clip[: len(audio) - i]

    cursor_img = make_cursor()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    wav = BUILD / "audio.wav"
    out = BUILD / "ContractIQ-demo.mp4"
    proc = subprocess.Popen(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)

    # Write the audio first (ffmpeg reads it as the second input), so sound effects are placed
    # with a dry run over the same timeline the frames use.
    t0 = 0.0
    cur_pos = None
    for s in segments:
        for name in s.get("sfx", []):
            if name in SOUNDS:
                place(name, t0 + (0.0 if name != "pop" else 0.1))
        if s.get("cursor") and s.get("click") and "click" in SOUNDS:
            moved = cur_pos is not None and cur_pos != s["cursor"]
            place("click", t0 + (CURSOR_S if moved else 0.15))
        if s.get("cursor"):
            cur_pos = s["cursor"]
        t0 += s["dur"]
    if MUSIC:
        audio[: int(total * SR)] += pad(total)
    audio /= max(1.0, np.abs(audio).max() / 0.95)
    write_wav(wav, audio[: int((total + 0.5) * SR)])

    full = [0.0, 0.0, float(W), float(H)]
    cam = full
    pos = None
    caption, cap_img, cap_since, old_cap, old_since = None, None, -10.0, None, -10.0
    cap_top, old_top = False, False
    prev_frame = None
    t_start = 0.0
    written = 0
    for s in segments:
        is_card = "card" in s
        target = full if is_card else fit(s.get("zoom"), W, H)
        cam_from = cam
        pos_from = pos
        if s.get("cursor"):
            pos = s["cursor"]
        new_caption = s.get("caption") and s["caption"] != caption
        # Move the caption to the top when it would cover what the camera is showing.
        top = cap_top
        if (new_caption or caption) and not is_card:
            img = make_caption(*s["caption"]) if new_caption else cap_img
            top = s.get("caption_top") or covers(s.get("zoom") or s.get("cursor") and [*s["cursor"], 1, 1],
                                                 target, img, W, H)
        fade = (s.get("transition") == "fade" or is_card) and prev_frame is not None
        if new_caption or (cap_img is not None and top != cap_top):
            old_cap, old_since, old_top = cap_img, t_start, cap_top
            if new_caption:
                caption, cap_img = s["caption"], make_caption(*s["caption"])
            # Let the new scene finish fading in before its caption appears.
            cap_since, cap_top = t_start + (FADE_S if fade else 0.0), top
        if is_card:
            old_cap, old_since, old_top = cap_img, t_start, cap_top
            caption, cap_img = None, None
        move = 0 if is_card else min(CAMERA_S, max(s["dur"] * 0.8, 0.01))
        click_at = None
        if s.get("click") and pos:
            click_at = CURSOR_S if (pos_from and pos_from != pos) else 0.15

        n = int(round((t_start + s["dur"]) * FPS)) - written
        for i in range(n):
            lt = i / FPS
            now = t_start + lt
            cam = lerp(cam_from, target, ease(lt / move)) if move and lt < move else target
            if is_card:
                frame = s["card"].copy()
            else:
                frame = view(shot(s["img"]), cam, W, H)
            # caption: old one fades out, new one slides up and fades in
            if old_cap is not None and now - old_since < 0.25:
                a = 1 - (now - old_since) / 0.25
                frame.alpha_composite(with_alpha(old_cap, a), (60 - CAPTION_MARGIN, caption_y(old_cap, old_top, H)))
            if cap_img is not None:
                k = ease((now - cap_since - 0.15) / 0.4)
                if k > 0:
                    slide = int(26 * (1 - k)) * (-1 if cap_top else 1)
                    frame.alpha_composite(with_alpha(cap_img, k), (60 - CAPTION_MARGIN, caption_y(cap_img, cap_top, H) + slide))
            # cursor and click ripple
            if pos and not is_card:
                p = pos
                if pos_from and pos_from != pos and lt < CURSOR_S:
                    p = lerp(pos_from, pos, ease(lt / CURSOR_S))
                sp = to_screen(p, cam, W, H)
                if click_at is not None:
                    ripple(frame, sp, (lt - click_at) / 0.45)
                    press = 1 - 0.15 * math.sin(math.pi * min(max((lt - click_at) / 0.2, 0), 1))
                else:
                    press = 1
                c = cursor_img if press == 1 else cursor_img.resize(
                    (int(40 * press), int(50 * press)), Image.Resampling.LANCZOS)
                frame.alpha_composite(c, (int(sp[0] - 4), int(sp[1] - 4)))
            # cross-fade from the previous screenshot
            if fade and lt < FADE_S:
                frame = Image.blend(prev_frame, frame, ease(lt / FADE_S))
            # thin progress bar along the bottom edge
            ImageDraw.Draw(frame).rectangle([0, H - 5, int(W * now / total), H], fill=(*ACCENT, 255))
            proc.stdin.write(frame.convert("RGB").tobytes())
            written += 1
            prev_last = frame
        prev_frame = prev_last
        if is_card:
            pos = None
        t_start += s["dur"]
        print(f"\r{written}/{n_frames} frames", end="", flush=True)

    proc.stdin.close()
    proc.wait()
    print(f"\n{out}  ({total:.0f}s)")


if __name__ == "__main__":
    main()
