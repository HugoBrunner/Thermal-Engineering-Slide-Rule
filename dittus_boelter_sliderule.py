#!/usr/bin/env python3
"""
Dittus-Boelter Slide Rule Generator — v5 FINAL
================================================
Nu = 0.023 * Re^0.8 * Pr^n   (n=0.4 heating, n=0.3 cooling)

v5 changes:
  - Latin Modern Roman (Computer Modern) font
  - Better Nu scale: labeled at every 1-2-3-5-7 per decade
  - Pr(n=0.4) / Pr(n=0.3) labels moved to left margin
  - Priority-based anti-collision for all labels
"""
import xml.etree.ElementTree as ET
import math, os, sys, base64

SIMULATOR = os.path.dirname(os.path.abspath(__file__))

LOG_C = math.log10(0.023)
RE_MIN, RE_MAX = 2500, 1_000_000
PR_MIN, PR_MAX = 0.6, 160

RL_MIN = 0.8 * math.log10(RE_MIN)
RL_MAX = 0.8 * math.log10(RE_MAX)
R_SPAN = RL_MAX - RL_MIN

SCALE_W = 900
PPL = SCALE_W / R_SPAN

LM = 200  # wider left margin for Pr labels
RM = 150
RULE_W = LM + SCALE_W + RM

def pr_width(n):
    return n * (math.log10(PR_MAX) - math.log10(PR_MIN)) * PPL

PR04_W = pr_width(0.4)
PR03_W = pr_width(0.3)

BODY_H = 130
SLIDER_H = 120
BG_BODY = "#FFFFFF"
BG_SLIDER = "#E3F0FF"

# Font: embed Latin Modern Roman via @font-face in SVG
FONT_REG = SIMULATOR + "/fonts/lmroman10-regular.otf"
FONT_BOLD = SIMULATOR + "/fonts/lmroman10-bold.otf"
FONT_FAMILY = "Latin Modern Roman"

def b64font(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def font_style_block():
    reg_b64 = b64font(FONT_REG)
    bold_b64 = b64font(FONT_BOLD)
    return f"""
@font-face {{
  font-family: '{FONT_FAMILY}';
  src: url('data:font/otf;base64,{reg_b64}') format('opentype');
  font-weight: 400;
  font-style: normal;
}}
@font-face {{
  font-family: '{FONT_FAMILY}';
  src: url('data:font/otf;base64,{bold_b64}') format('opentype');
  font-weight: 700;
  font-style: normal;
}}
text {{ font-family: '{FONT_FAMILY}', 'Computer Modern', serif; }}
"""

# ─── Position helpers ────────────────────────────────────────────────────────
def re_x(v):  return LM + (0.8 * math.log10(v) - RL_MIN) * PPL
def nu_x(v):  return LM + (math.log10(v) - LOG_C - RL_MIN) * PPL
def pr_lx(v, n): return (n * math.log10(v) - n * math.log10(PR_MIN)) * PPL

# ─── Anti-collision ──────────────────────────────────────────────────────────
def place_labels(candidates, min_gap=28, char_w=7.5):
    candidates = sorted(candidates, key=lambda c: (c[2], c[0]))
    placed = []
    for x, label, _ in candidates:
        lw = len(label) * char_w
        left, right = x - lw/2, x + lw/2
        if any(not (right + min_gap < pl or left - min_gap > pr) for pl, pr, _, _ in placed):
            continue
        placed.append((left, right, label, x))
    placed.sort(key=lambda p: p[3])
    return [(x, lab) for _, _, lab, x in placed]

# ─── SVG helpers ─────────────────────────────────────────────────────────────
def mksvg(w, h, embed_font=True):
    s = ET.Element('svg', {'width': str(w), 'height': str(h),
        'version': '1.1', 'xmlns': 'http://www.w3.org/2000/svg'})
    st = ET.SubElement(s, 'style')
    if embed_font:
        st.text = font_style_block()
    else:
        st.text = f"text{{font-family:'{FONT_FAMILY}','Computer Modern',serif}}"
    return s

def ln(p, x1, y1, x2, y2, c="#333", w=0.8):
    ET.SubElement(p, 'line', {'x1': f'{x1:.1f}', 'y1': f'{y1:.1f}',
        'x2': f'{x2:.1f}', 'y2': f'{y2:.1f}',
        'style': f'stroke:{c};stroke-width:{w}'})

# def tx(p, s, x, y, sz=13, c="#333", anchor="middle", wt="400"):
#     t = ET.SubElement(p, 'text', {'x': f'{x:.1f}', 'y': f'{y:.1f}', 'fill': c,
#         'font-size': str(sz), 'text-anchor': anchor, 'font-weight': wt})
#     t.text = str(s)

import re

def tx(p, s, x, y, sz=13, c="#333", anchor="middle", wt="400", italic=False):
    t = ET.SubElement(p, 'text', {
        'x': f'{x:.1f}',
        'y': f'{y:.1f}',
        'fill': c,
        'font-size': str(sz),
        'text-anchor': anchor,
        'font-weight': wt,
        'font-style': 'italic' if italic else 'normal'
    })

    s = str(s)
    parts = re.split(r'(\^.*?\^)', s)

    first = True
    for part in parts:
        if not part:
            continue

        is_super = part.startswith('^') and part.endswith('^')

        if is_super:
            txt = part[1:-1]
            node = ET.SubElement(t, 'tspan', {
                'baseline-shift': 'super',
                'font-size': f'{sz * 0.7:.1f}'
            })
            node.text = txt
        else:
            txt = part
            if first:
                t.text = txt
            else:
                node = ET.SubElement(t, 'tspan')
                node.text = txt

        first = False

    return t

def rc(p, x, y, w, h, fill, stroke="#333", sw=1.2):
    ET.SubElement(p, 'rect', {'x': str(x), 'y': str(y),
        'width': str(w), 'height': str(h),
        'style': f'fill:{fill};stroke:{stroke};stroke-width:{sw}'})

def fmt(v):
    if v >= 1000:
        k = v / 1000
        return f"{int(k)}k" if k == int(k) else f"{k:g}k"
    if v == int(v): return str(int(v))
    return f"{v:g}"

# ─── Scale drawing ───────────────────────────────────────────────────────────
def draw_re(svg, yb, d, ox=0):
    
    """Draw Re scale. d=+1 ticks down, d=-1 ticks up."""
    
    candidates = [
        (re_x(2500),"2.5k",1),(re_x(10000),"10k",1),(re_x(100000),"100k",1),(re_x(1000000),"1M",1),
        (re_x(5000),"5k",2),(re_x(50000),"50k",2),(re_x(500000),"500k",2),
        (re_x(20000),"20k",3),(re_x(200000),"200k",3),
        (re_x(3000),"3k",4),(re_x(4000),"4k",4),(re_x(7000),"7k",4),
        (re_x(15000),"15k",4),(re_x(30000),"30k",4),(re_x(70000),"70k",4),
        (re_x(150000),"150k",4),(re_x(300000),"300k",4),(re_x(700000),"700k",4),
    ]
    labeled = place_labels(candidates)

    # Dense systematic ticks — like a real slide rule
    # Each decade: 1,2,3...9 are tier-2 (medium), 5 is tier-1 (long)
    # Sub-ticks at 0.5 intervals (tier-3, short) where space allows
    major_set = {2500,5000,10000,20000,50000,100000,200000,500000,1000000}
    mid_set = {3000,4000,6000,7000,8000,9000,
               15000,25000,30000,40000,60000,70000,80000,90000,
               150000,250000,300000,400000,600000,700000,800000,900000}
    # Generate all ticks
    for decade_start in [1000, 10000, 100000]:
        step_major = decade_start  # e.g. 1000,10000,100000
        step_half = step_major // 2  # 500, 5000, 50000
        for v in range(decade_start, decade_start * 10 + 1, step_half):
            if v < RE_MIN or v > RE_MAX: continue
            x = re_x(v) + ox
            if v in major_set:
                ln(svg, x, yb, x, yb + d*30, "#333", 1.0)
            elif v in mid_set:
                ln(svg, x, yb, x, yb + d*22, "#333", 0.6)
            elif v % step_major == 0:
                ln(svg, x, yb, x, yb + d*16, "#333", 0.5)
            else:
                ln(svg, x, yb, x, yb + d*10, "#333", 0.3)

    for x, label in labeled:
        ty = yb + d*34 + d*15 if d > 0 else yb - 34 - 5
        tx(svg, label, x + ox, ty, 14, "#333", wt="700")

    tx(svg, "Re", ox + 100, yb + d*22 if d > 0 else yb - 16, 20, "#333", "start", "700")


def draw_nu(svg, yb, d, ox=0):
    
    """Draw Nu scale with 1-2-3-5-7 per decade labeling."""
    
    col = "#333"

    # Generate 1-2-3-5-7 labels per decade + extra useful ones
    candidates = []
    for dec in range(1, 4):
        base = 10**dec
        for mult, pri in [(1,1),(1.5,3),(2,1),(3,2),(5,1),(7,2)]:
            v = base * mult
            x = nu_x(v)
            if LM - 2 <= x <= LM + SCALE_W + 2:
                candidates.append((x, fmt(v), pri))
    # Add 15 explicitly
    x15 = nu_x(15)
    if LM - 2 <= x15 <= LM + SCALE_W + 2:
        candidates.append((x15, "15", 2))

    labeled = place_labels(candidates, min_gap=24)

    # Dense systematic ticks for Nu — every 1 in [10,100], every 10 in [100,1000], every 100 in [1000,10000]
    major_nu = {10,20,30,50,70,100,150,200,300,500,700,1000,1500,2000}
    mid_nu = {15,25,40,60,80,90,120,140,160,180,250,350,400,450,600,800,900,1200}

    # Decade 10-100: tick every 1, subtick every 0.5 where space > 5px
    for v in range(10, 101):
        x = nu_x(v) + ox
        if x < ox + LM - 2 or x > ox + LM + SCALE_W + 2: continue
        if v in major_nu:
            ln(svg, x, yb, x, yb + d*30, col, 1.0)
        elif v in mid_nu or v % 10 == 0:
            ln(svg, x, yb, x, yb + d*22, col, 0.6)
        elif v % 5 == 0:
            ln(svg, x, yb, x, yb + d*16, col, 0.5)
        elif v % 2 == 0:
            ln(svg, x, yb, x, yb + d*10, col, 0.3)
        else:
            # Only draw unit ticks where there's enough space (early in decade)
            if v < 40:
                ln(svg, x, yb, x, yb + d*6, col, 0.2)

    # Decade 100-1000: tick every 10, subtick every 5 early on
    for v in range(100, 1001, 5):
        x = nu_x(v) + ox
        if x < ox + LM - 2 or x > ox + LM + SCALE_W + 2: continue
        if v in major_nu:
            ln(svg, x, yb, x, yb + d*30, col, 1.0)
        elif v in mid_nu or v % 100 == 0:
            ln(svg, x, yb, x, yb + d*22, col, 0.6)
        elif v % 50 == 0:
            ln(svg, x, yb, x, yb + d*16, col, 0.5)
        elif v % 10 == 0:
            ln(svg, x, yb, x, yb + d*10, col, 0.3)
        elif v < 400:  # sub-ticks only where space allows
            ln(svg, x, yb, x, yb + d*6, col, 0.2)

    # Decade 1000-2000+: tick every 100, subtick every 50
    for v in range(1000, 2100, 50):
        x = nu_x(v) + ox
        if x < ox + LM - 2 or x > ox + LM + SCALE_W + 2: continue
        if v in major_nu:
            ln(svg, x, yb, x, yb + d*30, col, 1.0)
        elif v in mid_nu or v % 100 == 0:
            ln(svg, x, yb, x, yb + d*16, col, 0.5)
        else:
            ln(svg, x, yb, x, yb + d*8, col, 0.3)

    for x, label in labeled:
        ty = yb + d*34 + d*15 if d > 0 else yb - 34 - 5
        tx(svg, label, x + ox, ty, 14, col, wt="700")

    tx(svg, "Nu", ox + 100, yb + d*22 if d > 0 else yb - 16, 20, col, "start", "700")


def draw_pr(svg, yb, d, n, ox=0, label_in_margin=False, margin_x=0):
    
    """Draw Pr scale. ox = absolute x of Pr=PR_MIN."""
    
    col = "#C62828" if n == 0.4 else "#1565C0"
    pw = pr_width(n)

    candidates = [
        (pr_lx(1,n),"1",1),(pr_lx(10,n),"10",1),(pr_lx(100,n),"100",1),
        (pr_lx(2,n),"2",2),(pr_lx(5,n),"5",2),(pr_lx(20,n),"20",2),(pr_lx(50,n),"50",2),
        (pr_lx(3,n),"3",3),(pr_lx(7,n),"7",3),(pr_lx(30,n),"30",3),(pr_lx(0.7,n),"0.7",3),
        (pr_lx(4,n),"4",4),(pr_lx(6,n),"6",4),(pr_lx(15,n),"15",4),
        (pr_lx(40,n),"40",4),(pr_lx(1.5,n),"1.5",4),(pr_lx(160,n),"160",4),
    ]
    valid = [(x,l,p) for x,l,p in candidates if 0 <= x <= pw]
    labeled = place_labels(valid, min_gap=20)

    # Dense systematic Pr ticks
    mj_set = {2,5,10,20,50,100}
    md_set = {0.7,3,7,0.6,1.5,4,6,15,30,40,160}

    # Sub-decade 0.6-1: every 0.1
    for vi in range(6, 11):
        v = vi / 10
        if v < PR_MIN or v > PR_MAX: continue
        lx = pr_lx(v, n)
        if lx < 0 or lx > pw: continue
        x = ox + lx
        if v in mj_set:
            ln(svg, x, yb, x, yb + d*24, col, 1.0)
        elif v in md_set:
            ln(svg, x, yb, x, yb + d*16, col, 0.6)
        else:
            ln(svg, x, yb, x, yb + d*10, col, 0.3)

    # Decade 1-10: every 0.5 (where space), every 1 always
    for vi in range(10, 101):
        v = vi / 10
        if v < PR_MIN or v > PR_MAX: continue
        lx = pr_lx(v, n)
        if lx < 0 or lx > pw: continue
        x = ox + lx
        iv = round(v, 1)
        if iv in mj_set:
            ln(svg, x, yb, x, yb + d*24, col, 1.0)
        elif iv in md_set or iv == int(iv):
            ln(svg, x, yb, x, yb + d*16, col, 0.6)
        elif vi % 5 == 0:
            ln(svg, x, yb, x, yb + d*10, col, 0.4)
        elif v < 4:
            ln(svg, x, yb, x, yb + d*6, col, 0.2)

    # Decade 10-100: every 5 (subtick), every 10 (medium)
    for v in range(10, 101):
        if v < PR_MIN or v > PR_MAX: continue
        lx = pr_lx(v, n)
        if lx < 0 or lx > pw: continue
        x = ox + lx
        if v in mj_set:
            ln(svg, x, yb, x, yb + d*24, col, 1.0)
        elif v in md_set or v % 10 == 0:
            ln(svg, x, yb, x, yb + d*16, col, 0.6)
        elif v % 5 == 0:
            ln(svg, x, yb, x, yb + d*10, col, 0.4)
        elif v < 40:
            ln(svg, x, yb, x, yb + d*6, col, 0.2)

    # 100-160: every 10
    for v in range(100, 170, 10):
        if v < PR_MIN or v > PR_MAX: continue
        lx = pr_lx(v, n)
        if lx < 0 or lx > pw: continue
        x = ox + lx
        if v in mj_set:
            ln(svg, x, yb, x, yb + d*24, col, 1.0)
        elif v in md_set:
            ln(svg, x, yb, x, yb + d*16, col, 0.6)
        else:
            ln(svg, x, yb, x, yb + d*10, col, 0.4)

    for lx, label in labeled:
        x = ox + lx
        ty = yb + d*28 + d*14 if d > 0 else yb - 28 - 4
        tx(svg, label, x, ty, 13, col, wt="700")

    # INDEX at Pr=1
    ix = ox + pr_lx(1, n)
    ln(svg, ix, yb, ix, yb + d*30, "#FFA500", 2.0)
    # ity = yb + d*30 + d*12 if d > 0 else yb - 30 - 4
    # tx(svg, "INDEX", ix, ity, 10, "#C62828", wt="700")

    # Label in left margin
    if n == 0.3:
        label_text = "Pr (cooling)"
    elif n == 0.4:
        label_text = "Pr (heating)"
    
    if label_in_margin:
        ly = yb + d*14 if d > 0 else yb - 8
        tx(svg, label_text, margin_x+90, ly, 14, col, "start", "700")
    else:
        tx(svg, label_text, ox - 5, yb + d*14 if d > 0 else yb - 8, 14, col, "end", "700")


# ─── Build SVGs ──────────────────────────────────────────────────────────────
def build_combined():
    gap = 6
    h = BODY_H + gap + SLIDER_H + gap + BODY_H + 20
    svg = mksvg(RULE_W + 20, h)
    ox, oy = 10, 10

    # Top body
    rc(svg, ox, oy, RULE_W, BODY_H, BG_BODY)
    draw_nu(svg, oy + 4, 1, ox)
    draw_re(svg, oy + BODY_H - 4, -1, ox)

    # Slider
    sy = oy + BODY_H + gap
    rc(svg, ox, sy, RULE_W, SLIDER_H, BG_SLIDER)
    prox = ox + LM
    draw_pr(svg, sy + 4, 1, 0.4, prox, label_in_margin=True, margin_x=ox + 10)
    draw_pr(svg, sy + SLIDER_H - 4, -1, 0.3, prox, label_in_margin=True, margin_x=ox + 10)
    tx(svg, "Dittus-Boelter  -  Nu = 0.023·Re^0.8^·Pr^n^",
       ox + RULE_W/2, sy + SLIDER_H/2 + 5, 13, "#555", italic=True)
    
    tx(svg, "Thermal Engineer Slide Rule",
       ox + RULE_W*3.8/5, sy + SLIDER_H/2 + 5, 17, "#000", wt="700")

    # Bottom body
    by = sy + SLIDER_H + gap
    rc(svg, ox, by, RULE_W, BODY_H, BG_BODY)
    draw_re(svg, by + 4, 1, ox)
    draw_nu(svg, by + BODY_H - 4, -1, ox)

    return svg

def build_body():
    gap = 8
    h = BODY_H * 2 + gap + 20
    svg = mksvg(RULE_W + 20, h)
    ox, oy = 10, 10
    rc(svg, ox, oy, RULE_W, BODY_H, BG_BODY)
    draw_nu(svg, oy + 4, 1, ox)
    draw_re(svg, oy + BODY_H - 4, -1, ox)
    by = oy + BODY_H + gap
    rc(svg, ox, by, RULE_W, BODY_H, BG_BODY)
    draw_re(svg, by + 4, 1, ox)
    draw_nu(svg, by + BODY_H - 4, -1, ox)
    return svg

def build_slider():
    sw = LM + max(PR04_W, PR03_W) + RM
    h = SLIDER_H + 20
    svg = mksvg(sw + 20, h)
    ox, oy = 10, 10
    rc(svg, ox, oy, sw, SLIDER_H, BG_SLIDER)
    prox = ox + LM
    draw_pr(svg, oy + 4, 1, 0.4, prox, label_in_margin=True, margin_x=ox + 10)
    draw_pr(svg, oy + SLIDER_H - 4, -1, 0.3, prox, label_in_margin=True, margin_x=ox + 10)
    tx(svg, "Dittus-Boelter", ox + sw/2, oy + SLIDER_H/2 + 5, 12, "#555")
    return svg


# ─── Verify ──────────────────────────────────────────────────────────────────
def verify():
    print("VERIFICATION")
    for Re, Pr, n in [(50000,7,0.4),(100000,0.7,0.4),(10000,10,0.3),
                       (2500,0.6,0.3),(500000,100,0.4),(1000000,160,0.4)]:
        Nu = 0.023 * Re**0.8 * Pr**n
        idx = pr_lx(1, n)
        re_pos = re_x(Re) - LM
        off = re_pos - idx
        hp = off + pr_lx(Pr, n)
        bl = RL_MIN + hp / SCALE_W * R_SPAN
        nr = 10**(bl + LOG_C)
        ok = "✓" if abs(Nu - nr)/Nu < 1e-6 else "✗"
        print(f"  Re={Re:>7} Pr={Pr:>5} n={n} → Nu={Nu:>8.1f} rule={nr:>8.1f} {ok}")


if __name__ == "__main__":
    verify()
    out = SIMULATOR + "/hugo/"
    os.makedirs(out, exist_ok=True)
    for name, fn in [("combined", build_combined), ("body", build_body), ("slider", build_slider)]:
        tree = ET.ElementTree(fn())
        p = f"{out}/dittus_boelter_{name}.svg"
        tree.write(p, xml_declaration=True)
        print(f"Written: {p}")
