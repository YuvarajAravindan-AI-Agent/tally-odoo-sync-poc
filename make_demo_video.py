"""
Renders demo videos of the Tally -> Odoo live sync using the REAL Odoo results
in odoo_results.json. Produces BOTH:
  - portrait  1080x1920  (WhatsApp / mobile)
  - landscape 1920x1080  (laptop / projector / YouTube)

Branding + per-step captions included. Frames stream straight into ffmpeg
(no intermediate PNGs). Output: H.264 / yuv420p mp4.

Run in the project venv:  .venv/bin/python make_demo_video.py
"""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FPS = 30
BRAND = "AI-Agentic-Accounting"          # <- change to your company/consultancy name
BRAND_TAGLINE = "Tally × Odoo Integration"
SCRATCH = "/tmp/claude-1000/-home-yuvaraj-Documents-Google-Drive-Backup-Documents-company-website/a020b5a6-2b2b-46c5-aa7d-4c83522e150b/scratchpad"
OUT_DIR = Path.home() / "Projects/tally-odoo-sync-poc/demo"

# palette
BG = (15, 20, 32)
CARD = (26, 33, 51)
CARD2 = (32, 41, 64)
WHITE = (238, 242, 248)
MUTE = (148, 160, 184)
TEAL = (38, 198, 166)
ORANGE = (240, 158, 60)
GREEN = (80, 210, 120)
BLUE = (110, 150, 255)
LINE = (52, 64, 92)

F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FMB = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

_FONT_CACHE = {}


def font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease(t):
    return t * t * (3 - 2 * t)


def clampf(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def center_text(d, cx, y, text, fnt, fill):
    w = d.textlength(text, font=fnt)
    d.text((cx - w / 2, y), text, font=fnt, fill=fill)
    return w


def rtext(d, xr, y, text, fnt, fill):
    """right-aligned at xr"""
    w = d.textlength(text, font=fnt)
    d.text((xr - w, y), text, font=fnt, fill=fill)


def rounded(d, box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(d, x, y, text, fnt, fg, bg, padx=22, pady=10):
    w = d.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    h = asc + desc
    rounded(d, [x, y, x + w + padx * 2, y + h + pady * 2], (h + pady * 2) // 2, bg)
    d.text((x + padx, y + pady), text, font=fnt, fill=fg)
    return w + padx * 2


def wrap(d, text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=fnt) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def new_frame(W, H):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(0, 220):
        t = 1 - y / 220
        d.line([(0, y), (W, y)], fill=lerp(BG, (24, 32, 52), t * 0.7))
    return img, d


def brand_strip(d, W):
    # small logo mark + brand name, top-left
    x, y = 60, 46
    rounded(d, [x, y, x + 54, y + 54], 12, TEAL)
    d.text((x + 12, y + 6), "T", font=font(FB, 40), fill=(12, 16, 26))
    d.text((x + 74, y + 2), BRAND, font=font(FB, 34), fill=WHITE)
    d.text((x + 76, y + 42), BRAND_TAGLINE, font=font(F, 22), fill=MUTE)


def header(d, W, title, subtitle, y0):
    center_text(d, W // 2, y0, title, font(FB, 46), WHITE)
    center_text(d, W // 2, y0 + 62, subtitle, font(F, 32), TEAL)


def caption_bar(d, W, H, text, appear=1.0):
    a = ease(clampf(appear))
    if a <= 0:
        return
    fnt = font(F, 34)
    maxw = W - 240
    lines = wrap(d, text, fnt, maxw)
    lh = 46
    bh = 40 + lh * len(lines)
    by = H - bh - 60
    rounded(d, [90, by, W - 90, by + bh], 22, lerp(BG, CARD, a * 0.9),
            outline=lerp(BG, LINE, a), width=2)
    yy = by + 22
    for ln in lines:
        center_text(d, W // 2, yy, ln, fnt, lerp(BG, WHITE, a))
        yy += lh


CAPTIONS = {
    "title": "Real-time accounting sync between TallyPrime and Odoo",
    "voucher": "Data is entered once in Tally — the single source of entry.",
    "terminal": "The connector detects the voucher and pushes it to Odoo automatically.",
    "results": "It appears instantly as an invoice / bill in Odoo — no re-keying, no duplicates.",
    "outro": "One entry in Tally. Instantly live in Odoo.",
}


# ---------------- scenes (orientation-aware) ----------------

def draw_title(d, t, W, H, land):
    brand_strip(d, W)
    a = ease(clampf(t * 2))
    cy = H // 2 - 120
    center_text(d, W // 2, cy, "TallyPrime  →  Odoo", font(FB, 76 if land else 72),
                lerp(BG, WHITE, a))
    center_text(d, W // 2, cy + 96, "Live Accounting Sync", font(FB, 60),
                lerp(BG, TEAL, a))
    a2 = ease(clampf((t - 0.35) * 2))
    center_text(d, W // 2, cy + 200, "Voucher entered in Tally  →  created in Odoo",
                font(F, 38), lerp(BG, MUTE, a2))
    caption_bar(d, W, H, CAPTIONS["title"], appear=(t - 0.2) * 2)


def draw_voucher_scene(d, t, W, H, land):
    brand_strip(d, W)
    header(d, W, "TallyPrime  →  Odoo", "Step 1 — New voucher in TallyPrime", 150)
    a = ease(clampf(t * 1.6))
    rows = [("Sales Account", "40,000.00"),
            ("Output CGST 9%", "3,600.00"),
            ("Output SGST 9%", "3,600.00")]

    if land:
        bx0, by0, bx1, by1 = 220, 300, W - 220, 760
    else:
        bx0, by0 = 90, 340
        bx1, by1 = W - 90, 340 + 620
    by0 = int(by0 + (1 - a) * 30)
    by1 = int(by1 + (1 - a) * 30)
    rounded(d, [bx0, by0, bx1, by1], 30, CARD, outline=ORANGE, width=3)
    x = bx0 + 46
    pill(d, x, by0 + 34, "SALES VOUCHER", font(FMB, 28), (20, 20, 20), ORANGE)
    d.text((x, by0 + 106), "S/002", font=font(FMB, 38), fill=WHITE)
    rtext(d, bx1 - 46, by0 + 112, "15-Jul-2026", font(F, 32), MUTE)
    d.line([(x, by0 + 170), (bx1 - 46, by0 + 170)], fill=LINE, width=2)
    d.text((x, by0 + 192), "Party", font=font(F, 30), fill=MUTE)
    d.text((x, by0 + 230), "Global Enterprises Pvt Ltd", font=font(FB, 40), fill=WHITE)

    ry = by0 + 312
    for i, (name, amt) in enumerate(rows):
        ta = ease(clampf((t - 0.22 - i * 0.12) * 3))
        if ta <= 0:
            continue
        d.text((x, ry), name, font=font(F, 32), fill=lerp(BG, MUTE, ta))
        rtext(d, bx1 - 46, ry, amt, font(FM, 32), lerp(BG, WHITE, ta))
        ry += 52

    ta = ease(clampf((t - 0.6) * 3))
    if ta > 0:
        d.line([(x, ry + 6), (bx1 - 46, ry + 6)], fill=LINE, width=2)
        d.text((x, ry + 22), "Total", font=font(FB, 38), fill=lerp(BG, MUTE, ta))
        rtext(d, bx1 - 46, ry + 14, "₹ 47,200.00", font(FMB, 50), lerp(BG, ORANGE, ta))
    caption_bar(d, W, H, CAPTIONS["voucher"], appear=(t - 0.15) * 2)


TERM_LINES = [
    ("$ python3 connector/sync.py --once", WHITE),
    ("[tally] GET vouchers  127.0.0.1:9000", MUTE),
    ("[tally] parsed 5 vouchers", MUTE),
    ("  - S/001  already synced (id 1)", MUTE),
    ("  - P/001  already synced (id 2)", MUTE),
    ("  + S/002  Global Enterprises  -> Odoo", GREEN),
    ("  + P/002  Sunrise Distributors -> Odoo", GREEN),
    ("[sync] 2 created, 2 skipped, 1 deferred", TEAL),
]


def draw_terminal_scene(d, t, W, H, land):
    brand_strip(d, W)
    header(d, W, "TallyPrime  →  Odoo", "Step 2 — Connector syncs in real time", 150)
    if land:
        bx0, by0, bx1, by1 = 220, 300, W - 220, 780
        fsz, lh, y_first = 34, 52, 430
    else:
        bx0, by0, bx1, by1 = 80, 340, W - 80, 340 + 780
        fsz, lh, y_first = 33, 60, 450
    rounded(d, [bx0, by0, bx1, by1], 26, (10, 14, 24), outline=LINE, width=2)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([bx0 + 40 + i * 46, by0 + 32, bx0 + 68 + i * 46, by0 + 60], fill=c)
    center_text(d, (bx0 + bx1) // 2, by0 + 32, "tally-odoo-sync", font(FM, 30), MUTE)

    fm = font(FM, fsz)
    shown = clampf(t * 1.15) * len(TERM_LINES)
    y = y_first
    for i, (text, col) in enumerate(TERM_LINES):
        if i + 1 <= shown:
            d.text((bx0 + 50, y), text, font=fm, fill=col)
        elif i < shown:
            n = int(len(text) * ease(shown - i))
            d.text((bx0 + 50, y), text[:n], font=fm, fill=col)
            if int(t * FPS) % 2 == 0:
                cw = d.textlength(text[:n], font=fm)
                d.text((bx0 + 50 + cw, y), "▌", font=fm, fill=col)
        y += lh

    p = clampf(t * 1.15)
    pby = by1 - 70
    rounded(d, [bx0 + 50, pby, bx1 - 50, pby + 34], 17, CARD2)
    rounded(d, [bx0 + 50, pby, bx0 + 50 + int((bx1 - bx0 - 100) * p), pby + 34], 17, TEAL)
    caption_bar(d, W, H, CAPTIONS["terminal"], appear=(t - 0.15) * 2)


def result_card(d, x, y, w, h, kind, title, party, amount, ref, appear):
    a = ease(clampf(appear))
    if a <= 0:
        return
    yy = int(y + (1 - a) * 30)
    rounded(d, [x, yy, x + w, yy + h], 26, lerp(BG, CARD, a),
            outline=lerp(BG, TEAL, a), width=3)
    tag_bg = TEAL if kind == "inv" else BLUE
    pill(d, x + 30, yy + 26, "CUSTOMER INVOICE" if kind == "inv" else "VENDOR BILL",
         font(FMB, 26), (12, 16, 26), lerp(BG, tag_bg, a))
    d.text((x + w - 70, yy + 22), "✓", font=font(FB, 52), fill=lerp(BG, GREEN, a))
    d.text((x + 30, yy + 92), title, font=font(FMB, 30), fill=lerp(BG, WHITE, a))
    d.text((x + 30, yy + 140), party, font=font(FB, 38), fill=lerp(BG, WHITE, a))
    rtext(d, x + w - 30, yy + 196, amount, font(FMB, 46), lerp(BG, TEAL, a))
    d.text((x + 30, yy + 208), "state: draft", font=font(F, 30), fill=lerp(BG, MUTE, a))
    d.text((x + 30, yy + 260), ref, font=font(FM, 22), fill=lerp(BG, MUTE, a))


def draw_results_scene(d, t, W, H, land, results):
    brand_strip(d, W)
    header(d, W, "TallyPrime  →  Odoo", "Step 3 — Live in Odoo Accounting", 150)
    news = [r for r in results if r["ref"][-4:] in ("0004", "0005")] or results[-2:]

    def card_for(i, x, y, w):
        r = news[i]
        kind = "inv" if r["move_type"] == "out_invoice" else "bill"
        result_card(d, x, y, w, 314,
                     kind, f"Odoo move  #{r['id']}   {r['invoice_date']}",
                     r["partner"], f"₹ {r['amount_total']:,.2f}", r["ref"],
                     appear=(t - i * 0.28) * 1.8)

    if land:
        cw = (W - 180 - 60) // 2
        card_for(0, 90, 320, cw)
        card_for(1, 90 + cw + 60, 320, cw)
        note_y = 320 + 340
    else:
        card_for(0, 90, 340, W - 180)
        card_for(1, 90, 340 + 350, W - 180)
        note_y = 340 + 350 * 2 + 8

    a = ease(clampf((t - 0.6) * 2.2))
    if a > 0:
        center_text(d, W // 2, note_y, "Re-run the sync  →  0 duplicates",
                    font(FB, 40), lerp(BG, GREEN, a))
        center_text(d, W // 2, note_y + 56, "(deduped on Tally voucher GUID)",
                    font(F, 30), lerp(BG, MUTE, a))
    caption_bar(d, W, H, CAPTIONS["results"], appear=(t - 0.15) * 2)


def draw_outro(d, t, W, H, land):
    brand_strip(d, W)
    a = ease(clampf(t * 1.6))
    cx, cy = W // 2, H // 2 - 140
    r = int(110 * a)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=lerp(BG, GREEN, a), width=10)
    if t > 0.35:
        a2 = ease(clampf((t - 0.35) * 2.5))
        d.line([(cx - 48, cy + 4), (cx - 10, cy + 42)], fill=lerp(BG, GREEN, a2), width=13)
        d.line([(cx - 10, cy + 42), (cx + 52, cy - 36)], fill=lerp(BG, GREEN, a2), width=13)
    a3 = ease(clampf((t - 0.45) * 2))
    center_text(d, cx, cy + 170, "Synced in real time", font(FB, 60), lerp(BG, WHITE, a3))
    center_text(d, cx, cy + 250, BRAND, font(F, 40), lerp(BG, TEAL, a3))
    caption_bar(d, W, H, CAPTIONS["outro"], appear=(t - 0.3) * 2)


def build_timeline(results):
    return [
        (draw_title, 3.0, ()),
        (draw_voucher_scene, 6.0, ()),
        (draw_terminal_scene, 6.5, ()),
        (draw_results_scene, 7.0, (results,)),
        (draw_outro, 3.5, ()),
    ]


def render(mode, results):
    W, H = (1080, 1920) if mode == "portrait" else (1920, 1080)
    out = str(OUT_DIR / f"tally_odoo_sync_demo_{mode}.mp4")
    timeline = build_timeline(results)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fade = int(0.35 * FPS)
    written = 0
    for fn, secs, extra in timeline:
        n = int(secs * FPS)
        for i in range(n):
            t = i / max(1, n - 1)
            img, d = new_frame(W, H)
            fn(d, t, W, H, mode == "landscape", *extra)
            k = 1.0
            if i < fade:
                k = i / fade
            elif i > n - fade:
                k = (n - i) / fade
            if k < 1.0:
                img = Image.blend(Image.new("RGB", (W, H), BG), img, ease(clampf(k)))
            proc.stdin.write(img.tobytes())
            written += 1
    proc.stdin.close()
    proc.wait()
    print(f"[{mode}] {W}x{H}  frames={written} (~{written/FPS:.1f}s) -> {out}")
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = json.load(open(f"{SCRATCH}/odoo_results.json"))
    render("portrait", results)
    render("landscape", results)


if __name__ == "__main__":
    main()
