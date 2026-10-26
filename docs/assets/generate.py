"""Generate the README images as SVGs, one light and one dark file each.

The README picks the variant matching the reader's GitHub theme with
<picture>. Run from anywhere: python3 docs/assets/generate.py
"""
from pathlib import Path

OUT = Path(__file__).parent

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
MONO_W = 0.602  # advance width of one monospace glyph, in em

PALETTE = {
    "light": "--ink:#1B1F3B; --muted:#5D6480; --line:#CDD2E1; --card:#FFFFFF; --surface:#F4F5FA; "
             "--accent:#E8772E; --accent-soft:#FDEBDD; --ok:#2E9E6B; --bad:#D64545; --idle:#8A90A6; "
             "--solid:#1B1F3B; --on-solid:#FFFFFF;",
    "dark": "--ink:#E7E9F3; --muted:#9AA1BC; --line:#3A4160; --card:#161B2E; --surface:#12172A; "
            "--accent:#F28C3C; --accent-soft:#3B2A1E; --ok:#3DBA82; --bad:#EF6B6B; --idle:#8A90A6; "
            "--solid:#E7E9F3; --on-solid:#0D1117;",
}


def style(theme):
    """Palette for one theme, or both behind a media query for theme "auto"."""
    if theme == "auto":
        colors = (f"svg {{ {PALETTE['light']} }}\n"
                  f"@media (prefers-color-scheme: dark) {{ svg {{ {PALETTE['dark']} }} }}")
    else:
        colors = f"svg {{ {PALETTE[theme]} }}"
    return f"""<style>
{colors}
text {{ font-family:{SANS}; }}
.mono {{ font-family:{MONO}; }}
.ink {{ fill:var(--ink); }} .muted {{ fill:var(--muted); }} .accent {{ fill:var(--accent); }}
.on-solid {{ fill:var(--on-solid); }}
.card {{ fill:var(--card); stroke:var(--line); stroke-width:1.5; }}
.solid {{ fill:var(--solid); }}
.surface {{ fill:var(--surface); stroke:var(--line); stroke-width:1.5; }}
.chip {{ fill:var(--accent-soft); stroke:var(--accent); stroke-width:1.2; }}
.wire {{ fill:none; stroke:var(--muted); stroke-width:1.8; }}
.loop {{ fill:none; stroke:var(--accent); stroke-width:1.8; stroke-dasharray:6 5; }}
.head {{ fill:var(--muted); }} .head-accent {{ fill:var(--accent); }}
</style>"""


THEME = "auto"


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{title}">\n<title>{title}</title>\n{style(THEME)}\n{body}\n</svg>\n')


def mark(x, y, s):
    """The lens: one line of findings singled out. Drawn in a 64-unit box."""
    return f"""<g transform="translate({x} {y}) scale({s})">
  <circle cx="26" cy="26" r="19" fill="none" stroke="var(--ink)" stroke-width="5"/>
  <line x1="40.5" y1="40.5" x2="56" y2="56" stroke="var(--ink)" stroke-width="7" stroke-linecap="round"/>
  <line x1="17" y1="18" x2="31" y2="18" stroke="var(--muted)" stroke-width="3.4" stroke-linecap="round"/>
  <line x1="17" y1="26" x2="36" y2="26" stroke="var(--accent)" stroke-width="3.4" stroke-linecap="round"/>
  <line x1="17" y1="34" x2="28" y2="34" stroke="var(--muted)" stroke-width="3.4" stroke-linecap="round"/>
</g>"""


def chip(x, y, label, size=12, pad=8, h=26):
    w = round(len(label) * size * MONO_W + 2 * pad)
    return w, (f'<rect class="chip" x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}"/>'
               f'<text class="mono ink" x="{x + w/2}" y="{y + h/2 + size*0.36:.1f}" font-size="{size}" '
               f'text-anchor="middle">{label}</text>')


def arrow(x1, y1, x2, y2, cls="wire", head="head"):
    """Straight or one-elbow wire with an arrowhead at (x2, y2)."""
    if x1 == x2 or y1 == y2:
        d = f"M{x1} {y1} L{x2} {y2}"
    else:
        d = f"M{x1} {y1} L{x1} {y2} L{x2} {y2}"
    if x1 == x2:
        sign = 1 if y2 > y1 else -1
        tip = f"{x2},{y2} {x2-5},{y2-9*sign} {x2+5},{y2-9*sign}"
        end = (x2, y2 - 8 * sign)
    else:
        sign = 1 if x2 > x1 else -1
        tip = f"{x2},{y2} {x2-9*sign},{y2-5} {x2-9*sign},{y2+5}"
        end = (x2 - 8 * sign, y2)
    d = d.rsplit(" L", 1)[0] + f" L{end[0]} {end[1]}"
    return f'<path class="{cls}" d="{d}"/><polygon class="{head}" points="{tip}"/>'


def node(x, y, w, h, name, sub, user=False):
    if user:
        return (f'<rect class="solid" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/>'
                f'<text class="mono on-solid" x="{x+18}" y="{y+30}" font-size="15" font-weight="700">{name}</text>'
                f'<text class="on-solid" x="{x+18}" y="{y+52}" font-size="12.5" opacity="0.78">{sub}</text>')
    return (f'<rect class="card" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/>'
            f'<text class="mono ink" x="{x+18}" y="{y+30}" font-size="15" font-weight="700">{name}</text>'
            f'<text class="muted" x="{x+18}" y="{y+52}" font-size="12.5">{sub}</text>')


AXES = ["app-security", "infra-security", "privacy", "code-quality",
        "architecture", "accessibility", "seo", "performance"]


def banner():
    body = [f'<g transform="translate(110 0)">', mark(70, 46, 2.1)]
    body.append('<text x="232" y="102" font-size="54" font-weight="700" letter-spacing="-1">'
                '<tspan class="muted">birdiz/</tspan><tspan class="ink">skills</tspan></text>')
    body.append('<text class="ink" x="234" y="138" font-size="21">Agent skills for technical audits.</text>')
    body.append('<text class="muted" x="234" y="164" font-size="15">'
                'Evidenced findings, refuted from a separate context, turned into fixes.</text>')
    body.append('</g>')
    widths = [round(len(a) * 12 * MONO_W + 16) for a in AXES]
    gap = 9
    total = sum(widths) + gap * (len(AXES) - 1)
    x = (960 - total) / 2
    for a in AXES:
        w, c = chip(round(x), 206, a)
        body.append(c)
        x += w + gap
    return svg(960, 256, "\n".join(body), "birdiz/skills: agent skills for technical audits")


def workflow():
    b = []
    L = 150  # content left edge
    # band labels
    for y, n, label in [(68, "01", "FRAME"), (230, "02", "AUDIT"), (418, "03", "DELIVER")]:
        b.append(f'<text class="mono accent" x="28" y="{y}" font-size="13" font-weight="700">{n}</text>'
                 f'<text class="mono muted" x="28" y="{y+18}" font-size="12" letter-spacing="1.5">{label}</text>')
    W, H, G = 236, 68, 40
    xs = [L, L + W + G, L + 2 * (W + G)]
    # frame
    yA = 34
    b.append(node(xs[0], yA, W, H, "/audit-setup", "auditor profile · once per machine", user=True))
    b.append(node(xs[1], yA, W, H, "/audit-kickoff", "engagement · once per audit", user=True))
    b.append(node(xs[2], yA, W, H, "recon", "one shared codebase map"))
    b.append(arrow(xs[0] + W, yA + H/2, xs[1], yA + H/2))
    b.append(arrow(xs[1] + W, yA + H/2, xs[2], yA + H/2))
    # audit: axes cluster on the right, verify on the left
    cx, cy, cw, ch = 440, 150, xs[2] + W - 440, 150
    b.append(f'<rect class="surface" x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="14"/>')
    b.append(f'<text class="ink" x="{cx+18}" y="{cy+28}" font-size="14" font-weight="600">8 axes</text>'
             f'<text class="muted" x="{cx+76}" y="{cy+28}" font-size="12.5">one findings file each, in a common format</text>')
    colw = (cw - 36 - 3 * 8) / 4
    for i, a in enumerate(AXES):
        r, c = divmod(i, 4)
        x = cx + 18 + c * (colw + 8)
        y = cy + 44 + r * 36
        b.append(f'<rect class="chip" x="{x:.1f}" y="{y}" width="{colw:.1f}" height="27" rx="13.5"/>'
                 f'<text class="mono ink" x="{x + colw/2:.1f}" y="{y + 18}" font-size="12" text-anchor="middle">{a}</text>')
    b.append(f'<text class="muted" x="{cx+18}" y="{cy+134}" font-size="12.5">'
             'findings · leads · questions only the owner can answer</text>')
    b.append(arrow(xs[2] + W/2, yA + H, xs[2] + W/2, cy))
    vx, vy, vw, vh = L, 172, 254, 106
    b.append(f'<rect class="card" x="{vx}" y="{vy}" width="{vw}" height="{vh}" rx="12"/>'
             f'<text class="mono ink" x="{vx+18}" y="{vy+30}" font-size="15" font-weight="700">verify-findings</text>'
             f'<text class="muted" x="{vx+18}" y="{vy+52}" font-size="12.5">try to refute, from another context</text>')
    sx = vx + 18
    for color, label in [("--ok", "confirmed"), ("--bad", "refuted"), ("--idle", "unverified")]:
        b.append(f'<circle cx="{sx+5}" cy="{vy+79}" r="5" fill="var({color})"/>'
                 f'<text class="muted" x="{sx+15}" y="{vy+83.5}" font-size="11.5">{label}</text>')
        sx += 15 + len(label) * 6.0 + 12
    b.append(arrow(cx, vy + 40, vx + vw, vy + 40))
    # the lead-pass loop
    ly = 330
    lx1, lx2 = vx + vw - 50, cx + cw / 2
    b.append(f'<path class="loop" d="M{lx1} {vy+vh} L{lx1} {ly} L{lx2} {ly} L{lx2} {cy+ch+9}"/>'
             f'<polygon class="head-accent" points="{lx2},{cy+ch} {lx2-5},{cy+ch+9} {lx2+5},{cy+ch+9}"/>')
    pw = 312
    px = (lx1 + lx2) / 2 - pw / 2
    b.append(f'<rect x="{px}" y="{ly-14}" width="{pw}" height="28" rx="14" fill="var(--card)" stroke="var(--accent)" stroke-width="1.5"/>'
             f'<text class="ink" x="{px + pw/2}" y="{ly+4.5}" font-size="12.5" text-anchor="middle">'
             f'owner’s answers → lead pass → verified again</text>')
    # deliver
    yC = 384
    b.append(arrow(vx + 60, vy + vh, vx + 60, yC))
    b.append(node(xs[0], yC, W, H, "remediation-plan", "findings grouped into ordered fixes"))
    b.append(node(xs[1], yC, W, H, "audit-report", "peer report · summary · prompts"))
    b.append(node(xs[2], yC, W, H, "tickets", "one per fix · tracker or local files"))
    b.append(arrow(xs[0] + W, yC + H/2, xs[1], yC + H/2))
    b.append(arrow(xs[1] + W, yC + H/2, xs[2], yC + H/2))
    # foundation
    fy = 482
    fw = xs[2] + W - L
    b.append(f'<rect x="{L}" y="{fy}" width="{fw}" height="36" rx="10" fill="none" stroke="var(--line)" stroke-width="1.5" stroke-dasharray="2 4"/>'
             f'<text x="{L+18}" y="{fy+23}" font-size="12.5"><tspan class="mono ink" font-weight="700">finding-format</tspan>'
             f'<tspan class="muted" dx="10">the schema, rules of engagement and validator every step writes to</tspan></text>')
    # legend
    gy = 548
    b.append(f'<rect class="solid" x="{L}" y="{gy-10}" width="18" height="14" rx="4"/>'
             f'<text class="muted" x="{L+26}" y="{gy+2}" font-size="12">you run it</text>'
             f'<rect class="card" x="{L+110}" y="{gy-10}" width="18" height="14" rx="4"/>'
             f'<text class="muted" x="{L+136}" y="{gy+2}" font-size="12">the agent runs it</text>'
             f'<line x1="{L+262}" y1="{gy-3}" x2="{L+292}" y2="{gy-3}" class="loop"/>'
             f'<text class="muted" x="{L+300}" y="{gy+2}" font-size="12">only touches what the answers concern</text>')
    return svg(960, 572, "\n".join(b), "Audit workflow: frame, audit, deliver")


def projections():
    b = []
    # findings stack on the left
    fx, fy = 40, 70
    for i in range(3):
        o = (2 - i) * 9
        b.append(f'<rect class="card" x="{fx+o}" y="{fy-o}" width="190" height="132" rx="10"/>')
    b.append(f'<text class="mono ink" x="{fx+18}" y="{fy+34}" font-size="14" font-weight="700">findings/*.md</text>')
    for i, (w, c) in enumerate([(120, "--muted"), (150, "--accent"), (100, "--muted"), (132, "--muted")]):
        b.append(f'<line x1="{fx+18}" y1="{fy+58+i*16}" x2="{fx+18+w}" y2="{fy+58+i*16}" '
                 f'stroke="var({c})" stroke-width="4" stroke-linecap="round" opacity="{1 if c == "--accent" else 0.45}"/>')
    b.append(f'<text class="muted" x="{fx}" y="{fy+164}" font-size="12.5">one set, verified</text>')
    cards = [
        ("peer report", "technical reader · confidential", "everything, sensitive included"),
        ("summary", "decision maker · plain language", "confirmed only, quick wins first"),
        ("remediation prompts", "coding agent or developer", "the target state, never the attack"),
    ]
    rx, rw, rh = 470, 450, 70
    src = (fx + 190, fy + 66)
    for i, (t, a, c) in enumerate(cards):
        y = 24 + i * 86
        mid = y + rh / 2
        bx = 380
        b.append(f'<path class="wire" d="M{src[0]} {src[1]} C{bx-60} {src[1]} {bx-60} {mid} {rx-9} {mid}"/>'
                 f'<polygon class="head" points="{rx},{mid} {rx-9},{mid-5} {rx-9},{mid+5}"/>')
        b.append(f'<rect class="card" x="{rx}" y="{y}" width="{rw}" height="{rh}" rx="12"/>'
                 f'<rect x="{rx}" y="{y+14}" width="4" height="{rh-28}" rx="2" fill="var(--accent)"/>'
                 f'<text class="ink" x="{rx+22}" y="{y+29}" font-size="15" font-weight="700">{t}</text>'
                 f'<text class="muted" x="{rx+22}" y="{y+51}" font-size="12.5">{a}</text>'
                 f'<text class="muted" x="{rx+rw-18}" y="{y+29}" font-size="12.5" text-anchor="end">{c}</text>')
    b.append(f'<text class="muted" x="{rx}" y="300" font-size="12.5">'
             'A projection adds no analysis: regenerated, never edited, when the findings change.</text>')
    return svg(960, 316, "\n".join(b), "One set of findings, several reports")


def mark_only():
    return svg(64, 64, mark(0, 0, 1), "birdiz/skills mark")


for THEME in ("light", "dark"):
    for name, draw in [("banner", banner), ("workflow", workflow), ("projections", projections)]:
        (OUT / f"{name}-{THEME}.svg").write_text(draw())
THEME = "auto"
(OUT / "mark.svg").write_text(mark_only())
