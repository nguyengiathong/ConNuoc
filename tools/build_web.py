#!/usr/bin/env python3
"""Turn the single-file Con_nuoc.html into the WebView assets of the Android app.

The source page embeds its model data as base64 <script type="application/octet-stream"
id="emb:..."> blocks (~20 MB). Inside the app those blocks become separate binary files
under assets/www/emb/ that the page fetches on demand, so the WebView only has to parse
a small index.html at start-up. Google Fonts and pako are bundled so the app runs offline.

Usage: python3 tools/build_web.py path/to/Con_nuoc.html
"""
import base64
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "app" / "src" / "main" / "assets" / "www"
FONTS_CSS = ("https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700"
             "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")
PAKO_URL = "https://registry.npmjs.org/pako/-/pako-2.1.0.tgz"
# a Chrome user agent makes Google Fonts answer with woff2 files
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"

EMB_RE = re.compile(r'<script type="application/octet-stream" id="emb:([^"]+)">([^<]*)</script>\n?')

LOADER_OLD = """loader: async (p) => {
    const el = document.getElementById('emb:' + p);
    if (!el) throw new Error('HTTP 404 ' + p);
    const bin = atob(el.textContent.replace(/\\s+/g, ''));
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8;
  } });"""
LOADER_NEW = """loader: async (p) => {
    const r = await fetch('emb/' + p.replace(/\\.txt$/, '.bin'));
    if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + p);
    return new Uint8Array(await r.arrayBuffer());
  } });"""

FONT_LINKS_OLD = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="%s">""" % FONTS_CSS
FONT_LINKS_NEW = '<link rel="stylesheet" href="fonts/fonts.css">'

PAKO_OLD = "https://cdnjs.cloudflare.com/ajax/libs/pako/2.1.0/pako.min.js"
PAKO_NEW = "vendor/pako.min.js"

SHIM = '<script src="android.js"></script>\n'

# The water-level chart only reacted to mouse hover. On a touch screen a tap shows the reading,
# a sideways drag scrubs along the curve (vertical swipes still scroll the page), and the
# reading stays after the finger lifts until the next tap outside the chart.
TOUCH_FIXES = [
    (".chart svg { display: block; width: 100%; height: auto; overflow: visible; }",
     ".chart svg { display: block; width: 100%; height: auto; overflow: visible; }\n"
     ".chart svg { touch-action: pan-y; -webkit-user-select: none; user-select: none; -webkit-tap-highlight-color: transparent; }",
     "chart CSS"),
    ("hit.addEventListener('pointermove', onHover); hit.addEventListener('pointerleave', () => { el.querySelector('#tip').hidden = true; for (const id of ['#xh', '#xd', '#xd2']) el.querySelector(id).setAttribute('visibility', 'hidden'); });",
     "hit.addEventListener('pointerdown', onHover); hit.addEventListener('pointermove', onHover); hit.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') hideChartTip(); });",
     "chart hover listeners"),
    ("  function onHover(e) {",
     """  // a mouse reading goes when the pointer leaves the chart; a touch reading stays until a tap elsewhere
  function hideChartTip() {
    const el = $('#chart'); const tip = el.querySelector('#tip'); if (!tip) return;
    tip.hidden = true; for (const id of ['#xh', '#xd', '#xd2']) el.querySelector(id).setAttribute('visibility', 'hidden');
  }
  function onHover(e) {""",
     "chart hover handler"),
    ("}).observe($('#chart'));",
     "}).observe($('#chart'));\n"
     "    document.addEventListener('pointerdown', (e) => { if (e.pointerType !== 'mouse' && !e.target.closest('#chart')) hideChartTip(); });",
     "chart resize observer"),
]

# For each day: the time of the lowest low water and the window from 3 hours before to 3 hours
# after it, as a table under the chart and as shaded bands on the chart.
LOW_WINDOW = [
    (".chart-legend i.now {",
     ".chart-legend i.win { width: 14px; height: 10px; border: 0; border-radius: 2px; background: var(--overprint-soft); outline: 1px solid var(--overprint); outline-offset: -1px; vertical-align: -1px; }\n"
     ".oday { display: block; color: var(--ink-3); font-family: var(--f-mono); font-size: 12px; }\n"
     ".chart-legend i.now {",
     "chart legend CSS"),
    ("""    <div class="card">
      <div class="card-h"><h3>Nước lớn, nước ròng theo ngày</h3>""",
     """    <div class="card">
      <div class="card-h"><h3>Ròng thấp nhất trong ngày ± 3 giờ</h3><span class="meta" id="lowMeta"></span></div>
      <div class="tbl-wrap"><table id="lowWin"></table></div>
      <p class="small">Giờ nước ròng thấp nhất của mỗi ngày và khoảng từ 3 giờ trước đến 3 giờ sau mốc đó (vùng tô trên biểu đồ).</p>
    </div>
    <div class="card">
      <div class="card-h"><h3>Nước lớn, nước ròng theo ngày</h3>""",
     "daily table card"),
    ("    renderChart(S, D);\n    renderDaily(S, D);",
     "    renderChart(S, D);\n    renderLowWindows(S, D);\n    renderDaily(S, D);",
     "render() calls"),
    ("    // area + lines\n",
     """    // windows 3 hours either side of each day's lowest low water
    for (const { low } of dailyLows(S)) {
      if (!low) continue; const x0 = Math.max(m.l, X(low.t - LOW_WIN)), x1 = Math.min(W - m.r, X(low.t + LOW_WIN));
      if (x1 > x0) g += `<rect x="${x0.toFixed(1)}" y="${m.t}" width="${(x1 - x0).toFixed(1)}" height="${ph}" fill="var(--overprint-soft)"/>`;
    }
    // area + lines
""",
     "chart area"),
    ("""lg.push('<span><i class="hw"></i>Nước lớn</span><span><i class="lw"></i>Nước ròng</span>');""",
     """lg.push('<span><i class="hw"></i>Nước lớn</span><span><i class="lw"></i>Nước ròng</span><span><i class="win"></i>Ròng thấp nhất ± 3 giờ</span>');""",
     "chart legend"),
    ("  // ---------------- daily table\n",
     """  // ---------------- lowest low water of each day, with the window 3 hours either side
  const LOW_WIN = 3 * HOUR;
  function dailyLows(S) {
    const out = [];
    for (let d = 0; d < state.days; d++) {
      const a = S.t0 + d * DAY, b = a + DAY; let low = null;
      for (const e of S.ex) if (!e.high && e.t >= a && e.t < b && (!low || e.h < low.h)) low = e;
      out.push({ a, low });
    }
    return out;
  }
  function renderLowWindows(S, D) {
    const now = Date.now(), todayKey = fmtDate(now);
    // window ends on another date than the low itself get that date underneath
    const at = (t, ref) => `<span class="num">${fmtHM(t)}</span>${fmtDate(t) !== fmtDate(ref) ? `<span class="oday">${fmtDay(t)}</span>` : ''}`;
    const body = dailyLows(S).map(({ a, low }) => {
      const p = parts(a);
      const cells = low
        ? `<td><span class="ex">${fmtHM(low.t)}<span class="h">${fmtM(low.h + D.off, false)}</span></span>${now >= low.t - LOW_WIN && now <= low.t + LOW_WIN ? '<span class="chip spring">đang trong khung</span>' : ''}</td><td>${at(low.t - LOW_WIN, low.t)}</td><td>${at(low.t + LOW_WIN, low.t)}</td>`
        : '<td colspan="3"><span class="small">Không có nước ròng trong ngày</span></td>';
      return `<tr${fmtDate(a) === todayKey ? ' class="today"' : ''}><td class="day">${WD[p.wd]} ${p.d}/${p.mo}</td>${cells}</tr>`;
    }).join('');
    $('#lowWin').innerHTML = `<thead><tr><th>Ngày</th><th>Thấp nhất · m</th><th>Từ</th><th>Đến</th></tr></thead><tbody>${body}</tbody>`;
    $('#lowMeta').textContent = `giờ ${tzLabel(state.tz)} · mốc ${D.label}`;
  }

  // ---------------- daily table
""",
     "daily table section"),
]


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def replace_once(html, old, new, what):
    n = html.count(old)
    if n != 1:
        sys.exit(f"build_web: expected exactly one {what} in the page, found {n}")
    return html.replace(old, new)


def bundle_fonts():
    out = WWW / "fonts"
    if (out / "fonts.css").exists():
        return
    out.mkdir(parents=True, exist_ok=True)
    css = fetch(FONTS_CSS, {"User-Agent": UA}).decode()
    # keep the subsets the page can use: Vietnamese, Latin and Latin Extended
    blocks = re.findall(r"/\* ([\w-]+) \*/\s*(@font-face \{.*?\})", css, re.S)
    kept = []
    for subset, block in blocks:
        if subset not in ("vietnamese", "latin", "latin-ext"):
            continue
        url = re.search(r"url\((https://[^)]+)\)", block).group(1)
        family = re.search(r"font-family: '([^']+)'", block).group(1).replace(" ", "")
        weight = re.search(r"font-weight: (\d+)", block).group(1)
        name = f"{family}-{weight}-{subset}.woff2"
        (out / name).write_bytes(fetch(url))
        kept.append(f"/* {subset} */\n" + block.replace(url, name))
    (out / "fonts.css").write_text("\n".join(kept) + "\n")


def bundle_pako():
    dst = WWW / "vendor" / "pako.min.js"
    if dst.exists():
        return
    import io
    import tarfile
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(fetch(PAKO_URL)), mode="r:gz") as tf:
        dst.write_bytes(tf.extractfile("package/dist/pako.min.js").read())


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    html = Path(sys.argv[1]).read_text(encoding="utf-8")

    emb = WWW / "emb"
    names = []
    for name, b64 in EMB_RE.findall(html):
        dst = emb / re.sub(r"\.txt$", ".bin", name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(base64.b64decode("".join(b64.split())))
        names.append(name)
    if not names:
        sys.exit("build_web: no embedded data blocks found")
    html = EMB_RE.sub("", html)

    cfg = re.search(r"window\.TIDE_CONFIG = (\{.*?\});", html)
    missing = [k for k in json.loads(cfg.group(1))["available"] if f"data/b{k}.txt" not in names]
    if missing:
        sys.exit(f"build_web: blocks listed as available but not embedded: {missing}")

    html = replace_once(html, LOADER_OLD, LOADER_NEW, "embedded-data loader")
    html = replace_once(html, FONT_LINKS_OLD, FONT_LINKS_NEW, "Google Fonts link")
    html = replace_once(html, PAKO_OLD, PAKO_NEW, "pako CDN URL")
    for old, new, what in TOUCH_FIXES + LOW_WINDOW:
        html = replace_once(html, old, new, what)
    html = html.rstrip("\n") + "\n" + SHIM

    WWW.mkdir(parents=True, exist_ok=True)
    (WWW / "index.html").write_text(html, encoding="utf-8")
    bundle_fonts()
    bundle_pako()
    print(f"index.html {len(html.encode()) // 1024} KB, {len(names)} data files in {emb.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
