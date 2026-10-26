#!/usr/bin/env python3
"""
Build a brand guidelines deck (1920x1080 slides) from a brand.json spec.

    python build_guidelines.py brand.json --out out_dir [--pdf] [--previews]

Outputs in out_dir:
    <Brand>_Brand_Guidelines.html   self-contained (fonts + images inlined)
    <Brand>_Brand_Guidelines.pdf    with --pdf (Playwright / Chromium)
    previews/slide-NN.png + contact_sheet.jpg   with --previews (for QA)

See references/brand-json.md for the full spec. Paths in brand.json are
resolved relative to the JSON file's folder.
"""
import argparse, base64, colorsys, html, io, json, math, mimetypes, os, re, sys

try:
    from PIL import Image
except ImportError:  # raster logos need Pillow; SVG works without it
    Image = None

WARNINGS = []


def warn(msg):
    if msg in WARNINGS:
        return
    WARNINGS.append(msg)
    print("WARNING:", msg, file=sys.stderr)


E = lambda s: html.escape(str(s or ""))

# ------------------------------------------------------------------ colors


def hex_norm(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"Bad hex color: {h}")
    return "#" + h.upper()


def rgb(h):
    h = hex_norm(h)
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def to_hex(r, g, b):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in (r, g, b))


def cmyk(h):
    """Naive device-independent conversion. Real print values need an ICC
    profile (e.g. FOGRA39 / GRACoL) - the deck labels these as approximate."""
    r, g, b = [v / 255 for v in rgb(h)]
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0, 0, 0, 100)
    c, m, y = [(1 - v - k) / (1 - k) for v in (r, g, b)]
    return tuple(round(v * 100) for v in (c, m, y, k))


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


INK = "#111111"
PAPER = "#FFFFFF"


def on(bg):
    """Best text color (near-black or white) on a background."""
    return PAPER if contrast(bg, PAPER) >= contrast(bg, INK) else INK


def shade(h, f):
    """f<0 darkens, f>0 lightens (towards white)."""
    r, g, b = rgb(h)
    if f < 0:
        return to_hex(r * (1 + f), g * (1 + f), b * (1 + f))
    return to_hex(r + (255 - r) * f, g + (255 - g) * f, b + (255 - b) * f)


def grade(ratio):
    if ratio >= 7: return "AAA"
    if ratio >= 4.5: return "AA"
    if ratio >= 3: return "AA Large"
    return "Fail"

# ------------------------------------------------------------------ files


def data_uri(path, mime=None):
    mime = mime or mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def png_uri(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def svg_aspect(text):
    vb = re.search(r'viewBox\s*=\s*["\']\s*([-\d.e]+)[\s,]+([-\d.e]+)[\s,]+([-\d.e]+)[\s,]+([-\d.e]+)', text)
    if vb:
        w, h = float(vb.group(3)), float(vb.group(4))
        if w > 0 and h > 0:
            return w / h
    w = re.search(r'<svg[^>]*\swidth\s*=\s*["\']([\d.]+)', text)
    h = re.search(r'<svg[^>]*\sheight\s*=\s*["\']([\d.]+)', text)
    if w and h:
        return float(w.group(1)) / float(h.group(1))
    warn("SVG logo has no viewBox/size; assuming 3:1. Add a viewBox for accurate sizing.")
    return 3.0


class Logo:
    """A logo asset: data URI + aspect ratio + whether it is light-colored."""

    def __init__(self, path, label):
        self.path, self.label, self.light = path, label, False
        ext = os.path.splitext(path)[1].lower()
        if ext == ".svg":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            self.aspect = svg_aspect(text)
            self.uri = "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()
            self.mask_uri = self.uri
            fills = re.findall(r'(?:fill|stop-color)\s*[:=]\s*["\']?\s*(#[0-9a-fA-F]{3,6})\b', text)
            if fills:
                try:
                    ls = [lum(c) for c in fills]
                    self.light = sum(ls) / len(ls) > 0.8
                except ValueError:
                    pass
            return
        if Image is None:
            raise SystemExit("Pillow is required for raster logos: pip install pillow --break-system-packages")
        im = Image.open(path).convert("RGBA")
        knock = None  # version with ALL near-white removed, used only for single-color masks
        if im.getchannel("A").getextrema()[0] == 255:  # fully opaque: try to remove a flat light background
            W, H = im.size
            px = im.load()
            corners = [px[0, 0], px[W - 1, 0], px[0, H - 1], px[W - 1, H - 1]]
            if all(min(c[:3]) > 235 for c in corners):
                # 1) flood-fill from the edges so white *inside* the logo survives in the color version
                from PIL import ImageDraw
                rgbim = im.convert("RGB")
                sentinel = (255, 0, 254)
                for xy in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
                    if rgbim.getpixel(xy) != sentinel:
                        ImageDraw.floodfill(rgbim, xy, sentinel, thresh=40)
                import numpy as np
                arr = np.array(im)
                bgmask = np.all(np.array(rgbim) == sentinel, axis=-1)
                arr[..., 3] = np.where(bgmask, 0, 255)
                im = Image.fromarray(arr, "RGBA")
                # 2) knockout version: every near-white pixel transparent
                k = arr.copy()
                k[..., 3] = np.where(arr[..., :3].min(axis=-1) > 235, 0, k[..., 3])
                knock = Image.fromarray(k, "RGBA")
                warn(f"{label}: removed the white background from {os.path.basename(path)}. "
                     "A transparent PNG or SVG gives cleaner edges.")
            else:
                warn(f"{label}: {os.path.basename(path)} has a solid non-white background. "
                     "Recolored versions will show as a block; ask for a transparent PNG or SVG.")
        bbox = im.getchannel("A").getbbox()
        if bbox:
            im = im.crop(bbox)
            if knock is not None:
                knock = knock.crop(bbox)
        if max(im.size) > 1600:
            im.thumbnail((1600, 1600))
            if knock is not None:
                knock.thumbnail((1600, 1600))
        self.aspect = im.size[0] / im.size[1]
        small = im.copy()
        small.thumbnail((200, 200))
        opaque = [p[:3] for p in small.getdata() if p[3] > 128] if not hasattr(small, "get_flattened_data") \
            else [p[:3] for p in small.get_flattened_data() if p[3] > 128]
        if opaque:
            self.light = sum(lum(to_hex(*p)) for p in opaque) / len(opaque) > 0.8
        self.uri = png_uri(im)
        self.mask_uri = png_uri(knock) if knock is not None else self.uri

    def fit(self, bw, bh):
        if bw / bh > self.aspect:
            return bh * self.aspect, bh
        return bw, bw / self.aspect

# ------------------------------------------------------------------ fonts


class Font:
    def __init__(self, spec, css_name, base):
        spec = spec or {}
        self.family = spec.get("family", "Inter")
        self.css = css_name
        self.fallback = spec.get("fallback", "Helvetica, Arial, sans-serif")
        self.faces, self.weights, self.variable = [], set(), None
        for f in spec.get("files", []):
            p = f["path"] if os.path.isabs(f["path"]) else os.path.join(base, f["path"])
            if not os.path.exists(p):
                warn(f"Font file not found: {p}")
                continue
            w = str(f.get("weight", "400"))
            st = f.get("style", "normal")
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            fmt = {"ttf": "truetype", "otf": "opentype", "woff": "woff", "woff2": "woff2"}.get(ext, "truetype")
            mime = {"ttf": "font/ttf", "otf": "font/otf", "woff": "font/woff", "woff2": "font/woff2"}.get(ext)
            self.faces.append(f"@font-face{{font-family:'{css_name}';src:url({data_uri(p, mime)}) format('{fmt}');"
                              f"font-weight:{w};font-style:{st};font-display:block}}")
            if st == "normal":
                if " " in w:
                    lo, hi = map(int, w.split())
                    self.variable = (lo, hi)
                else:
                    self.weights.add(int(w))
        if not self.faces:
            warn(f"No font files for '{self.family}'. Using it by name with fallback "
                 f"({self.fallback}); the PDF may not show the real typeface.")

    def near(self, want):
        if self.variable:
            return max(self.variable[0], min(self.variable[1], want))
        if self.weights:
            return min(self.weights, key=lambda w: (abs(w - want), -w))
        return want

    def available(self):
        names = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}
        if self.variable:
            ws = [w for w in names if self.variable[0] <= w <= self.variable[1]]
        elif self.weights:
            ws = sorted(self.weights)
        else:
            ws = [400, 700]
        return [(w, names.get(w, str(w))) for w in ws]

    def stack(self):
        return f"'{self.css}', '{self.family}', {self.fallback}"


WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}

# ------------------------------------------------------------------ builder


class Deck:
    def __init__(self, cfg, base):
        (self.cfg, self.base) = (cfg, base)
        self.name = cfg.get('brand_name', 'Brand')
        self.style = 'adaptable'
        self.layout = cfg.get('layout') or {}
        if not isinstance(self.layout, dict):
            raise ValueError('layout must be an object')
        yrs = re.findall('\\d{4}', str(cfg.get('date', '')))
        import datetime
        self.year = str(cfg.get('year') or (yrs[-1] if yrs else datetime.date.today().year))
        self.date = cfg.get('date', self.year)
        self.version = cfg.get('version', '1.0')
        self.copy = cfg.get('copy', {})
        self.sections_cfg = cfg.get('sections', {})
        cols = []
        for c in cfg.get('colors', []):
            cols.append({'name': c.get('name') or c.get('role', 'Color').title(), 'hex': hex_norm(c['hex']), 'role': c.get('role', 'brand').lower(), 'cmyk': c.get('cmyk'), 'pantone': c.get('pantone'), 'status': c.get('status', 'supplied')})
        if not cols:
            raise SystemExit('brand.json needs at least one color')
        self.brand_cols = [c for c in cols if c['role'] != 'neutral'] or cols[:1]
        self.neutral_cols = [c for c in cols if c['role'] == 'neutral']
        role = {c['role']: c for c in self.brand_cols}
        self.primary = (role.get('primary') or self.brand_cols[0])['hex']
        rest = [c['hex'] for c in self.brand_cols if c['hex'] != self.primary]
        self.secondary = (role.get('secondary') or {}).get('hex') or (rest[0] if rest else shade(self.primary, -0.35))
        self.tertiary = (role.get('tertiary') or {}).get('hex') or (rest[1] if len(rest) > 1 else shade(self.primary, -0.65))
        self.panel_bg = '#F1F3F6'
        self.cover_bg = self.primary
        self.divider_bg = self.secondary if True and contrast(self.secondary, PAPER) > 3 else self.primary
        self.ring = shade(self.primary, -0.25) if lum(self.primary) > 0.04 else shade(self.primary, 0.3)
        fonts = cfg.get('fonts', {})
        self.fh = Font(fonts.get('heading') or fonts.get('body'), 'BrandHeading', base)
        self.fb = Font(fonts.get('body') or fonts.get('heading'), 'BrandBody', base)
        self.same_font = self.fh.family == self.fb.family
        hw = (fonts.get('heading') or {}).get('weight', 700)
        self.h_w = self.fh.near(hw)
        self.sub_w = self.fb.near(600)
        self.body_w = self.fb.near(400)
        L = cfg.get('logo', {})

        def lg(key, label):
            p = L.get(key)
            if not p:
                return None
            p = p if os.path.isabs(p) else os.path.join(base, p)
            if not os.path.exists(p):
                warn(f'Logo file not found: {p}')
                return None
            return Logo(p, label)
        self.full = lg('full', 'Full logo')
        self.mark = lg('mark', 'Logomark')
        self.wordmark = lg('wordmark', 'Logotype')
        self.reversed = lg('full_reversed', 'Reversed logo')
        if not self.full:
            self.full = self.wordmark or self.mark
        if not self.full:
            raise SystemExit('brand.json needs at least logo.full (or logo.mark / logo.wordmark)')
        self.icon = self.mark or self.full
        self.slides = []

    # ---------------------------------------------------------------- logo helpers
    def logo(self, bg, box_w, box_h, which=None, force_mono=None):
        """Logo sized to fit box, choosing a legible variant for the background."""
        lg = which or self.full
        w, h = lg.fit(box_w, box_h)
        bg_light = lum(bg) > 0.45
        use_original = (bg_light and not lg.light) or (not bg_light and lg.light)
        if force_mono:
            return self.mono(lg, force_mono, w, h)
        if use_original:
            return f'<img src="{lg.uri}" style="width:{w:.3f}px;height:{h:.3f}px;display:block" alt="">'
        if not bg_light and lg is self.full and self.reversed:
            w, h = self.reversed.fit(box_w, box_h)
            return f'<img src="{self.reversed.uri}" style="width:{w:.3f}px;height:{h:.3f}px;display:block" alt="">'
        if self.cfg.get("logo_rules", {}).get("allow_generated_mono", False):
            warn("Generated monochrome logo used: verify its geometry and approval status.")
            return self.mono(lg, on(bg), w, h)
        warn("Original logo retained on backgrounds without a supplied suitable variant; review contrast.")
        return f'<img src="{lg.uri}" style="width:{w:.3f}px;height:{h:.3f}px;display:block;object-fit:contain" alt="">'

    def mono(self, lg, color, w, h, extra=""):
        m = f"url({lg.mask_uri}) center/contain no-repeat"
        return (f'<div style="width:{w:.3f}px;height:{h:.3f}px;background:{color};'
                f'-webkit-mask:{m};mask:{m};{extra}"></div>')

    # ---------------------------------------------------------------- copy helper
    def txt(self, key, default):
        v = self.copy.get(key)
        return v if v else default

    # ---------------------------------------------------------------- slide frames
    def footer(self, n, dark=False):
        col = on(self.cover_bg) if dark else INK
        return f'<div class="foot" style="color:{col}"><span>{E(self.name)} Brand Guidelines</span><span style="left:480px">{E(self.year)} · v{E(self.version)}</span><span class="pn">{n:02d}</span></div>'

    def content(self, n, sec_name, num, title, desc, body):
        s = self.style
        return f'<section class="slide">\n  <h2 class="ct">{E(title)}</h2><div class="csec">{E(sec_name)}</div>\n  <div class="cdesc">{desc}</div>\n  <div class="cbody">{body}</div>{self.footer(n)}</section>'

    def divider(self, n, idx, title, subs):
        (bg, fg) = (self.divider_bg, on(self.divider_bg))
        s = self.style
        return f'<section class="slide" style="background:{bg};color:{fg}">\n  <h1 class="dv-c">{E(title)}</h1></section>'

    def rings(self, x, y, scale=1.0, color=None):
        c = color or self.ring
        r = 560 * scale
        sw = 22 * scale
        return (f'<svg class="rings" width="1920" height="1080" viewBox="0 0 1920 1080">'
                f'<circle cx="{x}" cy="{y + 420*scale}" r="{r}" fill="none" stroke="{c}" stroke-width="{sw}"/>'
                f'<circle cx="{x + 520*scale}" cy="{y + 300*scale}" r="{r}" fill="none" stroke="{c}" stroke-width="{sw}"/></svg>')

    # ---------------------------------------------------------------- body blocks
    def rows(self, items):
        return '<div class="rows">' + "".join(
            f'<div class="row"><div class="rt">{E(i.get("title"))}</div><div class="rx">{E(i.get("text"))}</div></div>'
            for i in items) + "</div>"

    def panel(self, inner, bg=None, h=None):
        bg = bg or self.panel_bg
        hh = f'height:{h}px;' if h else 'height:100%;'
        return f'<div class="panel" style="background:{bg};{hh}">{inner}</div>'

    def strike(self):
        return ('<svg class="strike" viewBox="0 0 100 100" preserveAspectRatio="none">'
                '<line x1="0" y1="0" x2="100" y2="100" stroke="#E5322D" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>')

    # ---------------------------------------------------------------- slides
    def build(self):
        S = []  # list of (section_title or None, callable(n)->html, subsection title)
        cp = self.copy

        def add(section, title, fn):
            S.append((section, title, fn))

        # --- front matter
        add(None, "cover", self.s_cover)
        add(None, "intro", self.s_intro)
        add(None, "toc", None)  # filled later

        sections = []

        def section(key, title, items):
            items = [i for i in items if i]
            for module in self.cfg.get("modules", []):
                if module.get("section") == key:
                    items.append((module["title"], lambda n, s, num, m=module: self.s_module(n, s, num, m)))
            if not items or self.sections_cfg.get(key) is False:
                return
            sections.append((title, items))

        ov = []
        pos = cp.get("positioning")
        if pos:
            ov.append(("Brand Positioning", lambda n, s, num: self.content(n, s, num, "Brand Positioning",
                       E(self.txt("positioning_desc", "Why we exist, where we are going, and how we will get there.")),
                       self.rows([{"title": k.title(), "text": v} for k, v in pos.items() if v]))))
        if cp.get("values"):
            ov.append(("Core Values", lambda n, s, num: self.content(n, s, num, "Core Values",
                       E(self.txt("values_desc", "The principles behind every decision we make and everything we put into the world.")),
                       self.rows(cp["values"]))))
        if cp.get("tone"):
            ov.append(("Tone of Voice", lambda n, s, num: self.content(n, s, num, "Tone of Voice",
                       E(self.txt("tone_desc", "How we sound. Our voice stays consistent while our tone adapts to the moment.")),
                       self.rows(cp["tone"]))))
        section("overview", "Brand Overview", ov)

        lg = []
        if self.mark:
            lg.append(("Logomark", lambda n, s, num: self.content(n, s, num, "Logomark",
                       E(self.txt("logomark_desc", "The logomark is the brand’s symbol. Use it as a compact identifier where space is tight or the brand is already established: avatars, favicons, app icons.")),
                       self.panel(f'<div class="center">{self.logo(self.panel_bg, 420, 420, self.mark)}</div>'))))
        if self.wordmark:
            lg.append(("Logotype", lambda n, s, num: self.content(n, s, num, "Logotype",
                       E(self.txt("logotype_desc", "The logotype is our name in its own typographic form, built for clarity wherever the name needs to lead.")),
                       self.panel(f'<div class="center">{self.logo(self.panel_bg, 900, 300, self.wordmark)}</div>'))))
        lg.append(("Primary Logo", lambda n, s, num: self.content(n, s, num, "Primary Logo",
                   E(self.txt("logo_desc", "Our primary logo is the default version and the one to reach for first. It delivers immediate recognition across every touchpoint.")),
                   self.panel(f'<div class="center">{self.logo(self.panel_bg, 1000, 360)}</div>'))))
        lg.append(("Logo on Color", self.s_logo_on_color))
        if self.cfg.get("logo_rules", {}).get("min_size"):
            lg.append(("Minimum Size", self.s_min_size))
        if "clearspace_ratio" in self.cfg.get("logo_rules", {}):
            lg.append(("Clearspace", self.s_clearspace))
        lg.append(("Logo Backgrounds", self.s_logo_bgs))
        lg.append(("Logo Misuse", self.s_misuse))
        section("logo", "Logo", lg)

        palette = self.brand_cols + [c for c in self.neutral_cols if c not in self.brand_cols]
        colors = []
        for start in range(0, len(palette), 6):
            part = palette[start:start+6]
            colors.append(("Color Palette", lambda n, s, num, part=part: self.s_palette(n, s, num, part)))
        pairs = list(dict.fromkeys((c["name"], c["hex"]) for c in palette))
        unique = []; seen = set()
        for pair in pairs:
            if pair[1] not in seen:
                unique.append(pair); seen.add(pair[1])
        for r in range(0, len(unique), 6):
            for c in range(0, len(unique), 6):
                rows, cols = unique[r:r+6], unique[c:c+6]
                colors.append(("Color Accessibility", lambda n, s, num, rows=rows, cols=cols: self.s_access(n, s, num, rows, cols)))
        section("color", "Color", colors)
        section("typography", "Typography", [("Typeface", self.s_typeface), ("Type Hierarchy", self.s_hierarchy)])

        ve = []
        if self.cfg.get("assets", {}).get("pattern") or self.cfg.get("generate_pattern", False):
            ve.append(("Brand Pattern", self.s_pattern))
        if self.cfg.get("assets", {}).get("icons"):
            ve.append(("Icons", self.s_icons))
        section("visual_elements", "Visual Elements", ve)

        stationery = [("Letterhead & Cover", self.s_letterhead), ("Business Card", self.s_card)] if self.cfg.get("contact") else []
        section("corporate_assets", "Corporate Assets", stationery)

        ph = []
        if cp.get("photo_directions") or self.cfg.get("assets", {}).get("photos"):
            ph.append(("Photo Directions", self.s_photo_dir))
            ph.append(("Photo Misuse", self.s_photo_misuse))
        section("photography", "Photography", ph)

        apps = []
        user_apps = self.cfg.get("assets", {}).get("applications") or []
        for i, a in enumerate(user_apps):
            apps.append((a.get("title") or f"Application {i+1}", (lambda a: lambda n, s, num: self.s_user_app(n, s, num, a))(a)))
        if self.cfg.get("generate_mockups", False):
            apps.append(("Digital", self.s_app_digital))
            apps.append(("Social & Print", self.s_app_social))
        apps.append(("Brand Summary", self.s_bento))
        section("applications", "Applications", apps)
        section("handoff", "Asset Handoff", [])

        # assemble with numbering
        order = []  # (html_fn, args)
        n = 3
        toc = []
        for si, (title, items) in enumerate(sections, start=1):
            n += 1
            toc.append((si, title, n))
            subs = [t for t, _ in items]
            order.append((lambda n, si=si, title=title, subs=subs: self.divider(n, si, title, subs)))
            for ii, (t, fn) in enumerate(items, start=1):
                n += 1
                order.append((lambda n, fn=fn, title=title, num=f"{si}.{ii}": fn(n, title, num)))
        n += 1
        order.append(lambda n: self.s_thanks(n))
        out = [self.s_cover(1), self.s_intro(2), self.s_toc(3, toc)]
        for i, fn in enumerate(order, start=4):
            out.append(fn(i))
        return out

    def s_module(self, n, s, num, module):
        parts = []
        if module.get("lead"):
            parts.append(f'<p class="module-lead">{E(module["lead"])}</p>')
        if module.get("columns"):
            head = "".join(f"<th>{E(x)}</th>" for x in module["columns"])
            rows = "".join("<tr>" + "".join(f"<td>{E(x)}</td>" for x in row) + "</tr>" for row in module.get("rows", []))
            parts.append(f'<table class="spec-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>')
        if module.get("items"):
            parts.append(self.rows(module["items"]))
        if module.get("images"):
            figures = []
            for img in module["images"]:
                path = img["path"] if os.path.isabs(img["path"]) else os.path.join(self.base, img["path"])
                figures.append(f'<figure><img src="{data_uri(path)}" alt="{E(img.get("alt", ""))}"><figcaption>{E(img.get("caption", ""))}</figcaption></figure>')
            parts.append('<div class="module-images">' + "".join(figures) + '</div>')
        if module.get("note"):
            parts.append(f'<p class="module-note">{E(module["note"])}</p>')
        desc = E(module.get("description", ""))
        if module.get("status"):
            desc += f'<p class="module-status">{E(module["status"])}</p>'
        return self.content(n, s, num, module["title"], desc, '<div class="module">' + "".join(parts) + '</div>')

    # ---------------------------------------------------------------- front/back
    def s_cover(self, n):
        (bg, fg) = (self.cover_bg, on(self.cover_bg))
        s = self.style
        foot = f'<div class="cv-foot" style="color:{fg}"><span>{E(self.name)}<br>Version {E(self.version)}</span><span>{E(self.date)}</span></div>'
        return f'<section class="slide" style="background:{bg};color:{fg}">\n  <div style="position:absolute;left:48px;top:48px">{self.logo(bg, 260, 70)}</div>\n  <h1 class="cv-c">Brand<br>Guidelines</h1>{foot}</section>'

    def s_intro(self, n):
        bg = self.secondary if False and contrast(self.secondary, PAPER) > 3 else '#0A0A0A'
        fg = on(bg)
        lead = self.txt('intro_lead', f'Welcome to the {self.name} brand guidelines: the essential reference for understanding and applying our visual identity.')
        body = self.txt('intro', 'Inside you’ll find the core elements of our identity, from logo and color to typography, imagery and applications. Applying them consistently is how we build a brand people recognize and trust.')
        return f'<section class="slide" style="background:{bg};color:{fg}">\n  <div class="i-lab">Introduction</div><div class="i-lead">{E(lead)}</div><div class="i-body">{E(body)}</div>{self.footer(n, True).replace(INK, fg)}</section>'

    def s_toc(self, n, toc):
        lis = ''.join((f'<li><a href="#page-{p}"><span>{i:02d}.</span> {E(t)} <small>{p:02d}</small></a></li>' for (i, t, p) in toc))
        return f'<section class="slide"><h2 class="ct">Table of Contents</h2>\n  <ul class="toc-c">{lis}</ul>{self.footer(n)}</section>'

    def s_thanks(self, n):
        (bg, fg) = (self.divider_bg, None)
        fg = on(bg)
        foot = f'<div class="cv-foot" style="color:{fg}"><span>{E(self.name)} Brand Guidelines</span><span>{E(self.date)}</span></div>'
        cls = 'dv-c'
        return f'<section class="slide" style="background:{bg};color:{fg}">\n  <div style="position:absolute;left:48px;top:48px">{self.logo(bg, 300, 80)}</div>\n  <h1 class="{cls}">Thank You</h1>{foot}</section>'

    # ---------------------------------------------------------------- logo slides
    def s_logo_on_color(self, n, s, num):
        a = self.panel(f'<div class="center">{self.logo(self.primary, 640, 240)}</div>', self.primary)
        dark = "#0A0A0A"
        b = self.panel(f'<div class="center">{self.logo(dark, 640, 240)}</div>', dark)
        return self.content(n, s, num, "Logo on Color",
                            E(self.txt("logo_color_desc", "Compare the supplied logo variants on these backgrounds. Use only permitted colorways with sufficient contrast; generated variants require review.")),
                            f'<div class="g2" style="height:100%">{a}{b}</div>')

    def s_min_size(self, n, s, num):
        ms = self.cfg.get("logo_rules", {}).get("min_size", {})
        cells = []
        for key, lgo, label, h in [("mark", self.mark, "Logomark", 90), ("wordmark", self.wordmark, "Logotype", 70),
                                   ("full", self.full, "Primary Logo", 80)]:
            if not lgo:
                continue
            if key not in ms:
                continue
            v = ms[key]
            cells.append(f'''<div class="ms"><div class="ms-l">{self.logo(self.panel_bg, 360, h, lgo)}</div>
  <div class="cap"><b>{label}</b><br>{E(v.get("axis", "Axis unspecified"))} · {E(v.get("status", "supplied"))}<br>Print: {E(v.get("print", "Not specified"))}<br>Digital: {E(v.get("digital", "Not specified"))}</div></div>''')
        return self.content(n, s, num, "Minimum Size",
                            E(self.txt("min_size_desc", "Sizes below identify the measurement axis and decision status. Validate proposed limits at actual size in the intended production medium.")),
                            self.panel(f'<div class="msrow">{"".join(cells)}</div>'))

    def s_clearspace(self, n, s, num):
        ratio = float(self.cfg.get("logo_rules", {}).get("clearspace_ratio", 0.5))
        lw, lh = self.full.fit(820, 300)
        x = lh * ratio
        box = f'''<div class="cs" style="width:{lw + 2*x:.0f}px;height:{lh + 2*x:.0f}px">
  <div class="cs-in" style="left:{x:.0f}px;top:{x:.0f}px;width:{lw:.3f}px;height:{lh:.3f}px">{self.logo(self.panel_bg, lw, lh)}</div>
  <div class="xq" style="left:0;top:{x:.0f}px;width:{x:.0f}px;height:{x:.0f}px">x</div>
  <div class="xq" style="right:0;top:{x:.0f}px;width:{x:.0f}px;height:{x:.0f}px">x</div>
  <div class="xq" style="left:{x:.0f}px;top:0;width:{x:.0f}px;height:{x:.0f}px">x</div>
  <div class="xq" style="left:{x:.0f}px;bottom:0;width:{x:.0f}px;height:{x:.0f}px">x</div></div>'''
        rule = self.txt("clearspace_rule", f"x = {ratio*100:g}% of the logo’s height") + " · " + self.cfg.get("logo_rules", {}).get("clearspace_status", "supplied")
        return self.content(n, s, num, "Clearspace",
                            E(self.txt("clearspace_desc", "Clearspace is the protected area around the logo. Keep it free of text, imagery and other graphics so the logo always has room to breathe.")),
                            self.panel(f'<div class="center col">{box}<div class="cap" style="margin-top:36px">{E(rule)}</div></div>'))

    def s_logo_bgs(self, n, s, num):
        bgs = [self.primary, self.secondary, "#0A0A0A", PAPER, self.panel_bg, self.tertiary]
        seen, uniq = set(), []
        for b in bgs:
            if b not in seen:
                uniq.append(b); seen.add(b)
        while len(uniq) < 6:
            uniq.append(shade(self.primary, 0.85 if len(uniq) % 2 else -0.5))
        tiles = "".join(f'<div class="tile" style="background:{b}{";outline:1px solid #E3E5E8" if lum(b)>0.9 else ""}">'
                        f'<div class="center">{self.logo(b, 300, 110)}</div></div>' for b in uniq[:6])
        return self.content(n, s, num, "Logo Backgrounds",
                            E(self.txt("logo_bg_desc", "Pick a background that gives the logo clear contrast. On light backgrounds use the full-color logo; on brand colors and dark tones use the reversed version.")),
                            f'<div class="g3x2">{tiles}</div>')

    def off_brand(self):
        """A clearly wrong color for the 'recolor' misuse example."""
        r, g, b = [v / 255 for v in rgb(self.primary)]
        h, l, sat = colorsys.rgb_to_hls(r, g, b)
        r, g, b = colorsys.hls_to_rgb((h + 0.42) % 1, 0.5, max(sat, 0.6))
        return to_hex(r * 255, g * 255, b * 255)

    def s_misuse(self, n, s, num):
        lw, lh = self.full.fit(260, 96)
        img = lambda st: f'<img src="{self.full.uri}" style="width:{lw:.3f}px;height:{lh:.3f}px;{st}" alt="">'
        off = shade(self.secondary if self.secondary != self.primary else self.primary, 0.55)
        cases = [
            (img("transform:scaleX(1.35)"), "Don’t stretch, squash or skew the logo."),
            (self.mono(self.full, self.off_brand(), lw, lh), "Don’t change the logo’s colors."),
            (img("transform:rotate(-18deg)"), "Don’t rotate the logo."),
            (img("filter:drop-shadow(10px 10px 6px rgba(0,0,0,.55))"), "Don’t add shadows, glows or other effects."),
            (img("filter:drop-shadow(2px 0 0 #E5322D) drop-shadow(-2px 0 0 #E5322D) drop-shadow(0 2px 0 #E5322D) drop-shadow(0 -2px 0 #E5322D)"),
             "Don’t add outlines or strokes."),
            (f'<div style="background:{off};padding:26px 34px">{self.mono(self.full, shade(off, 0.25), lw*0.9, lh*0.9)}</div>',
             "Don’t place the logo on low-contrast backgrounds."),
        ]
        tbg = "#1A1D24" if self.full.light else "#F1F3F6"
        tiles = "".join(f'<div><div class="tile mis" style="background:{tbg}">{self.strike()}<div class="center">{h}</div></div><div class="cap">{E(t)}</div></div>'
                        for h, t in cases)
        return self.content(n, s, num, "Logo Misuse",
                            E(self.txt("misuse_desc", "The logo is never altered. These examples show what to avoid; consistent, correct use protects the brand.")),
                            f'<div class="g3x2 cap-under">{tiles}</div>')

    # ---------------------------------------------------------------- color slides
    def swatch_text(self, c):
        r, g, b = rgb(c["hex"])
        k = c.get("cmyk") if c.get("cmyk") is not None else cmyk(c["hex"])
        if isinstance(k, (list, tuple)):
            k = ", ".join(str(v) for v in k)
        p = f'<br>Pantone {E(c["pantone"])}' if c.get("pantone") else ""
        approximation = ' (approx.)' if c.get('cmyk') is None else ''
        return f'HEX {c["hex"]}<br>RGB {r}, {g}, {b}<br>CMYK {E(k)}{approximation}{p}'

    def s_palette(self, n, s, num, colors=None):
        colors = colors if colors is not None else self.brand_cols + self.neutral_cols
        rows = "".join(f'<tr><td><div style="background:{c["hex"]};width:120px;height:74px;border:1px solid #ddd"></div></td>'
                       f'<td><b>{E(c["name"])}</b><br>{E(c["role"])} · {E(c.get("status", "supplied"))}</td>'
                       f'<td>{self.swatch_text(c)}</td></tr>' for c in colors)
        return self.content(n, s, num, "Color Palette",
                            E(self.txt("palette_desc", "Use each color according to its documented role. RGB is calculated from HEX. Approximate CMYK conversions require production proofing; supplied print values are retained.")),
                            f'<table class="spec-table palette-table">{rows}</table>')

    def s_access(self, n, s, num, row_colors=None, col_colors=None):
        cols = col_colors or [(c["name"], c["hex"]) for c in self.brand_cols + self.neutral_cols]
        row_colors = row_colors or cols
        k = len(cols)
        head = '<div></div>' + "".join(f'<div class="am-h">{E(nm)} text</div>' for nm, _ in cols)
        cells = ""
        for bn, bg in row_colors:
            cells += f'<div class="am-r">on {E(bn)}</div>'
            for fn, fg in cols:
                if fg == bg:
                    cells += '<div class="am-c am-x"></div>'
                    continue
                r = contrast(bg, fg)
                g = grade(r)
                edge = ";box-shadow:inset 0 0 0 1px #E3E5E8" if lum(bg) > 0.9 else ""
                badge = f'<span class="am-g" style="background:{on(bg)};color:{bg}">{g}</span>' if g != "Fail" else '<span class="am-g am-f">Fail</span>'
                cells += (f'<div class="am-c{" am-fail" if g == "Fail" else ""}" style="background:{bg};color:{fg}{edge}">'
                          f'<b class="am-aa">Aa</b><span class="am-n" style="color:{on(bg)}">{r:.1f}:1</span>{badge}</div>')
        grid = f'<div class="am" style="grid-template-columns:150px repeat({k},1fr);grid-template-rows:40px repeat({len(row_colors)},1fr)">{head}{cells}</div>'
        return self.content(n, s, num, "Color Accessibility",
                            E(self.txt("access_desc", "Text must be readable for everyone. Body text needs a contrast ratio of at least 4.5:1 (WCAG AA); large headlines need 3:1 (AA Large). Failing text pairs are not suitable for essential content. A contrast pass alone does not establish brand permission.")),
                            grid)

    # ---------------------------------------------------------------- type slides
    def s_typeface(self, n, s, num):
        def spec(f, role):
            ws = " ".join(f'<span style="font-weight:{w}">{nm}</span>' for w, nm in f.available())
            return f'''<div class="tf" style="font-family:{f.stack()}">
  <div class="cap" style="font-family:{self.fb.stack()}">{role}</div>
  <div class="tf-n" style="font-weight:{f.near(700) if f is self.fh else f.near(600)}">{E(f.family)}</div>
  <div class="tf-g">ABCDEFGHIJKLMNOPQRSTUVWXYZ<br>abcdefghijklmnopqrstuvwxyz<br>0123456789 !@#$%&amp;*()?</div>
  <div class="tf-w">{ws}</div></div>'''
        if self.same_font:
            body = self.panel(spec(self.fh, "Brand typeface"))
            desc = self.txt("typeface_desc", f"{self.fh.family} is our brand typeface. One versatile family across every touchpoint keeps our typographic voice clear and consistent.")
        else:
            body = f'<div class="g2" style="height:100%">{self.panel(spec(self.fh, "Headings"))}{self.panel(spec(self.fb, "Body text"))}</div>'
            desc = self.txt("typeface_desc", f"We pair {self.fh.family} for headlines with {self.fb.family} for body text. The contrast gives headlines character while keeping long text easy to read.")
        return self.content(n, s, num, "Typeface", E(desc), body)

    def s_hierarchy(self, n, s, num):
        up = ''
        h = self.copy.get('hierarchy_sample', {})
        sub_font = self.fb
        rows = [(f'Headline · {self.fh.family} {WEIGHT_NAMES.get(self.h_w, self.h_w)}', self.fh.stack(), self.h_w, 96, 1.0, h.get('headline', 'Keep it short and bold'), up + 'letter-spacing:-0.01em;'), (f'Subheading · {sub_font.family} {WEIGHT_NAMES.get(self.sub_w, self.sub_w)}', sub_font.stack(), self.sub_w, 40, 1.2, h.get('subheading', 'Subheadings add context and lead the reader into the detail below.'), ''), (f'Body · {self.fb.family} {WEIGHT_NAMES.get(self.body_w, self.body_w)}', self.fb.stack(), self.body_w, 24, 1.5, h.get('body', f'Body text carries the message. Set it in comfortable line lengths with generous leading so it reads easily on screen and in print. {self.name} writes the way it designs: clear, confident and to the point.'), 'max-width:1000px;'), (f'Caption · {self.fb.family} {WEIGHT_NAMES.get(self.body_w, self.body_w)}', self.fb.stack(), self.body_w, 16, 1.4, h.get('caption', 'Captions, labels and legal text.'), 'opacity:.7;')]
        inner = ''.join((f'<div class="hr"><div class="cap">{E(l)} · {sz}px</div><div style="font-family:{fam};font-weight:{w};font-size:{sz}px;line-height:{lh};{ex}">{E(t)}</div></div>' for (l, fam, w, sz, lh, t, ex) in rows))
        return self.content(n, s, num, 'Type Hierarchy', E(self.txt('hierarchy_desc', 'Distinct sizes and weights make content easy to scan. Follow this structure for headlines, subheadings, body text and captions.')), self.panel(f'<div class="hier">{inner}</div>'))

    # ---------------------------------------------------------------- visual elements
    def pattern_tile(self, fg, bg, size=150, rotate=0, w=None, h=None):
        """Complete marks inside bounded cells; no edge-cropped repeats."""
        mw, mh = self.icon.fit(size * .42, size * .42)
        motif = self.mono(self.icon, fg, mw, mh)
        cell = f'<div style="display:flex;align-items:center;justify-content:center;min-width:0;min-height:0"><div style="transform:rotate({rotate}deg)">{motif}</div></div>'
        return '<div style="position:absolute;inset:20px;display:grid;grid-template-columns:repeat(6,1fr);grid-template-rows:repeat(5,1fr)">' + cell * 30 + '</div>' if self.cfg.get("generate_pattern", False) else ""

    def pattern_block(self, bg, fg, rotate=-12, size=170):
        return (f'<div class="pat" style="background:{bg}">{self.pattern_tile(fg, bg, size, rotate)}</div>')

    def s_pattern(self, n, s, num):
        pat = self.cfg.get("assets", {}).get("pattern")
        if pat:
            p = pat if os.path.isabs(pat) else os.path.join(self.base, pat)
            body = f'<div class="g2" style="height:100%"><div class="img" style="background-image:url({data_uri(p)})"></div>' \
                   f'<div class="img" style="background-image:url({data_uri(p)});background-size:40%"></div></div>'
            desc = self.txt("pattern_desc", "The brand pattern adds texture and recognition. Use it as a background or accent, never behind dense text.")
        else:
            a = self.pattern_block(self.primary, shade(self.primary, -0.18) if lum(self.primary) > 0.08 else shade(self.primary, 0.15))
            b = self.pattern_block(PAPER, shade(self.primary, 0.82), rotate=0, size=130)
            body = f'<div class="g2" style="height:100%">{a}{b}</div>'
            desc = self.txt("pattern_desc", "Our pattern is built from the logomark. Use it tone-on-tone as a background or accent to add texture and recognition, and keep it subtle behind content.")
        return self.content(n, s, num, "Brand Pattern", E(desc), body)

    def s_icons(self, n, s, num):
        icons = self.cfg["assets"]["icons"][:15]
        cells = ""
        for ic in icons:
            p = ic["path"] if os.path.isabs(ic["path"]) else os.path.join(self.base, ic["path"])
            m = f"url({data_uri(p)}) center/contain no-repeat"
            cells += (f'<div><div class="ic"><div style="width:84px;height:84px;background:{self.primary if lum(self.primary)<0.6 else INK};'
                      f'-webkit-mask:{m};mask:{m}"></div></div><div class="cap" style="text-align:center">{E(ic.get("name",""))}</div></div>')
        return self.content(n, s, num, "Icons",
                            E(self.txt("icons_desc", "Our icons communicate simply and clearly. A consistent stroke, corner and grid keeps them cohesive across every platform.")),
                            f'<div class="icg">{cells}</div>')

    # ---------------------------------------------------------------- corporate assets
    def contact(self):
        c = self.cfg.get("contact", {})
        return {key: c.get(key, "") for key in ("name", "position", "address", "phone", "email", "website")}

    def s_letterhead(self, n, s, num):
        c = self.contact()
        tag = self.cfg.get('tagline', '')
        lines = '<br>'.join((E(c[k]) for k in ('address', 'phone', 'email', 'website')))
        lh = f"""<div class="a4" style="background:#fff">\n  <div style="position:absolute;left:40px;top:40px">{self.logo(PAPER, 170, 48)}</div>\n  <div class="a4-tag">{E(tag)}</div>\n  <div class="a4-lines">{''.join(('<i></i>' for _ in range(9)))}</div>\n  <div class="a4-foot"><span style="background:{self.primary}"></span>{lines}</div></div>"""
        cv_bg = self.primary
        cover = f"""<div class="a4" style="background:{cv_bg};color:{on(cv_bg)}">\n  {self.pattern_tile(shade(cv_bg, -0.15) if lum(cv_bg) > 0.08 else shade(cv_bg, 0.12), cv_bg, 120, -12)}\n  <div style="position:absolute;left:40px;bottom:40px">{self.logo(cv_bg, 200, 56)}</div>\n  <div class="a4-title">{E(self.name)}<br><span>{E(tag or 'Document title')}</span></div></div>"""
        return self.content(n, s, num, 'Letterhead & Cover', E(self.txt('letterhead_desc', 'Use the official letterhead and document cover for all formal communication so every page we send is consistent and recognizably ours.')), self.panel(f'<div class="center" style="gap:80px">{lh}{cover}</div>'))

    def s_card(self, n, s, num):
        c = self.contact()
        front = f'<div class="bc" style="background:{self.primary}"><div class="center">{self.logo(self.primary, 340, 110)}</div></div>'
        back = f'''<div class="bc" style="background:#fff;box-shadow:0 0 0 1px #E3E5E8">
  <div style="position:absolute;left:44px;top:44px">{self.logo(PAPER, 110, 80, self.icon)}</div>
  <div class="bc-t"><b style="font-family:{self.fh.stack()};font-weight:{self.h_w}">{E(c["name"])}</b><br><span>{E(c["position"])}</span>
  <div style="margin-top:18px">{E(c["address"])}<br>{E(c["phone"])}<br>{E(c["email"])}<br>{E(c["website"])}</div></div></div>'''
        return self.content(n, s, num, "Business Card",
                            E(self.txt("card_desc", "The business card is often a first impression. A clean layout and our core brand elements make it professional and memorable.")),
                            self.panel(f'<div class="center" style="gap:70px">{front}{back}</div>'))

    # ---------------------------------------------------------------- photography
    def photo_box(self, path, i, crossed=False):
        if path:
            p = path if os.path.isabs(path) else os.path.join(self.base, path)
            inner = f'<div class="img" style="background-image:url({data_uri(p)})"></div>'
        else:
            g = [self.primary, self.secondary, self.tertiary][i % 3]
            inner = (f'<div class="img ph" style="background:linear-gradient(135deg,{shade(g,0.75)},{shade(g,0.35)})">'
                     f'<span>Image placeholder</span></div>')
        return f'<div class="phw">{self.strike() if crossed else ""}{inner}</div>'

    def s_photo_dir(self, n, s, num):
        dirs = self.copy.get("photo_directions") or []
        photos = self.cfg.get("assets", {}).get("photos") or []
        k = max(len(dirs), min(len(photos), 3), 1)
        cells = ""
        for i in range(min(k, 3)):
            d = dirs[i] if i < len(dirs) else {}
            img = d.get("image") or (photos[i] if i < len(photos) else None)
            cells += (f'<div class="pd">{self.photo_box(img, i)}<div class="pd-t">{E(d.get("title", f"Direction {i+1}"))}</div>'
                      f'<div class="cap">{E(d.get("text", ""))}</div></div>')
        return self.content(n, s, num, "Photo Directions",
                            E(self.txt("photo_desc", "Our photography should feel authentic, bright and human. Capture real moments that tell a relatable story.")),
                            f'<div class="pdg">{cells}</div>')

    def s_photo_misuse(self, n, s, num):
        mis = self.copy.get("photo_misuses") or ["Overly staged or posed stock imagery.",
                                                 "Dark, poorly lit or low-resolution photos.",
                                                 "Heavy filters or color casts that fight the palette."]
        bad = self.cfg.get("assets", {}).get("bad_photos") or []
        cells = "".join(f'<div class="pd">{self.photo_box(bad[i] if i < len(bad) else None, i, True)}'
                        f'<div class="cap" style="margin-top:16px">{E(t)}</div></div>' for i, t in enumerate(mis[:3]))
        return self.content(n, s, num, "Photo Misuse",
                            E(self.txt("photo_misuse_desc", "Avoid imagery that feels generic, staged or off-brand. Every photo should feel genuine and match our personality.")),
                            f'<div class="pdg">{cells}</div>')

    # ---------------------------------------------------------------- applications
    def s_user_app(self, n, s, num, a):
        p = a["image"] if os.path.isabs(a["image"]) else os.path.join(self.base, a["image"])
        return self.content(n, s, num, a.get("title", "Application"),
                            E(a.get("text", "Our identity in action. Use these examples as a guide for on-brand materials.")),
                            f'<div class="img" style="background-image:url({data_uri(p)});height:100%;border-radius:4px"></div>')

    def s_app_digital(self, n, s, num):
        (P, fgP) = (self.primary, on(self.primary))
        tag = self.cfg.get('tagline') or f'Welcome to {self.name}'
        hf = f"font-family:{self.fh.stack()};font-weight:{self.h_w};{''}"
        web = f'''<div class="browser"><div class="bb"><i></i><i></i><i></i><span>{E(self.contact()['website'])}</span></div>\n  <div class="site"><div class="nav">{self.logo(PAPER, 150, 36)}<span>About</span><span>Work</span><span>Contact</span>\n  <b style="background:{P};color:{fgP}">Get started</b></div>\n  <div class="hero" style="background:{P};color:{fgP}">{self.pattern_tile(shade(P, -0.12) if lum(P) > 0.08 else shade(P, 0.1), P, 140, -12)}\n  <div class="hero-t" style="{hf}">{E(tag)}</div><div class="hero-s">{E(self.copy.get('positioning', {}).get('purpose', '')[:110])}</div>\n  <b class="btn" style="background:{on(P)};color:{P}">Learn more</b></div></div></div>'''
        phone = f'<div class="phone"><div class="scr" style="background:{self.secondary};color:{on(self.secondary)}">\n  <div style="margin:70px auto 0;width:fit-content">{self.logo(self.secondary, 120, 120, self.icon)}</div>\n  <div class="ph-t" style="{hf}">{E(tag)}</div>\n  <div class="ph-b" style="background:{on(self.secondary)};color:{self.secondary}">Continue</div></div></div>'
        return self.content(n, s, num, 'Digital', E(self.txt('app_digital_desc', 'Our identity on screen. Generated mockups show color, type and logo working together on the website and in the app.')), self.panel(f'<div class="center" style="gap:60px">{web}{phone}</div>'))

    def s_app_social(self, n, s, num):
        (P, S2) = (self.primary, self.secondary)
        hf = f"font-family:{self.fh.stack()};font-weight:{self.h_w};{''}"
        vals = self.copy.get('values') or [{'title': self.cfg.get('tagline') or self.name}]
        q = (self.copy.get('tone') or [{}])[0].get('text') or self.cfg.get('tagline') or self.name
        post1 = f'''<div class="post" style="background:{P};color:{on(P)}"><div class="post-t" style="{hf}">{E(vals[0]['title'])}</div>\n  <div style="position:absolute;left:36px;bottom:36px">{self.logo(P, 140, 40)}</div></div>'''
        post2 = f'<div class="post" style="background:#fff;color:{INK};box-shadow:0 0 0 1px #E3E5E8">\n  <div style="position:absolute;left:36px;top:36px">{self.logo(PAPER, 70, 70, self.icon)}</div>\n  <div class="post-q" style="font-family:{self.fb.stack()}">“{E(q)}”</div><div class="post-bar" style="background:{P}"></div></div>'
        poster = f'''<div class="poster" style="background:{S2};color:{on(S2)}">{self.pattern_tile(shade(S2, -0.15) if lum(S2) > 0.08 else shade(S2, 0.12), S2, 110, -12)}\n  <div class="pos-t" style="{hf}">{E(self.cfg.get('tagline') or self.name)}</div>\n  <div style="position:absolute;left:34px;bottom:34px">{self.logo(S2, 170, 48)}</div></div>'''
        return self.content(n, s, num, 'Social & Print', E(self.txt('app_social_desc', 'Social posts and print pieces lead with bold color and confident type. Keep layouts simple, with one message per piece.')), self.panel(f'<div class="center" style="gap:44px">{post1}{post2}{poster}</div>'))

    def s_bento(self, n, s, num):
        (P, S2, T) = (self.primary, self.secondary, self.tertiary)
        sw = ''.join((f"""<i style="background:{c['hex']}{(';box-shadow:inset 0 0 0 1px #ddd' if lum(c['hex']) > 0.9 else '')}"></i>""" for c in (self.brand_cols + self.neutral_cols)[:7]))
        b = f"""<div class="bento">\n  <div class="bx" style="grid-area:a;background:{P}"><div class="center">{self.logo(P, 520, 200)}</div></div>\n  <div class="bx" style="grid-area:b;background:#0A0A0A"><div class="center">{self.logo('#0A0A0A', 150, 150, self.icon)}</div></div>\n  <div class="bx" style="grid-area:c;background:#fff;box-shadow:inset 0 0 0 1px #E3E5E8"><div class="sw">{sw}</div></div>\n  <div class="bx" style="grid-area:d;background:{shade(P, 0.88)};color:{INK}"><div class="bx-aa" style="font-family:{self.fh.stack()};font-weight:{self.h_w}">Aa</div><div class="cap" style="position:absolute;left:28px;bottom:24px">{E(self.fh.family)}{('' if self.same_font else ' + ' + E(self.fb.family))}</div></div>\n  <div class="bx" style="grid-area:e;background:{S2}">{self.pattern_tile(shade(S2, -0.15) if lum(S2) > 0.08 else shade(S2, 0.12), S2, 120, -12)}</div>\n  <div class="bx" style="grid-area:f;background:{T};color:{on(T)}"><div class="bx-tag" style="font-family:{self.fh.stack()};font-weight:{self.h_w};{''}">{E(self.cfg.get('tagline') or self.name)}</div></div>\n</div>"""
        return self.content(n, s, num, 'Brand Summary', E(self.txt('summary_desc', 'Every element working together: flexible enough for any touchpoint, consistent enough to always feel like us.')), b)

    # ---------------------------------------------------------------- CSS / document
    def css(self):
        (hf, bf) = (self.fh.stack(), self.fb.stack())
        up = ''
        hw = self.h_w
        P = self.primary
        return f"""
{''.join(self.fh.faces)}{''.join(self.fb.faces)}
@page{{size:1920px 1080px;margin:0}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:#2a2a2a}}
body{{font-family:{bf};font-weight:{self.body_w};color:{INK};-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.wrap{{width:calc(1920px*var(--s,1));height:calc(1080px*var(--s,1));margin:0 auto 24px;overflow:hidden}}
.slide{{width:1920px;height:1080px;position:relative;overflow:hidden;background:#fff;transform:scale(var(--s,1));transform-origin:0 0;break-after:page;page-break-after:always}}
@media print{{html,body{{background:#fff}}.wrap{{width:1920px;height:1080px;margin:0;--s:1}}}}
h1,h2,.hf{{font-family:{hf};font-weight:{hw}}}
.up{{text-transform:uppercase}}
.center{{width:100%;height:100%;display:flex;align-items:center;justify-content:center}}
.center.col{{flex-direction:column}}
.cap{{font-size:17px;line-height:1.45;color:inherit;opacity:.85}}
.rings{{position:absolute;left:0;top:0;pointer-events:none}}
.panel{{position:relative;width:100%;overflow:hidden;border-radius:{'6px'}}}
.img{{width:100%;height:100%;background-size:cover;background-position:center}}
/* shared layout */
.ct{{position:absolute;left:48px;top:48px;font-size:40px;line-height:1.1;letter-spacing:-.01em;{up}}}
.csec{{position:absolute;left:480px;top:48px;font-size:18px}}
.cdesc{{position:absolute;left:48px;top:150px;width:350px;font-size:22px;line-height:1.4}}
.cbody{{position:absolute;left:480px;top:140px;right:48px;bottom:120px}}
.foot{{position:absolute;left:48px;right:48px;bottom:48px;height:20px;font-size:16px}}
.foot span{{position:absolute;left:0}} .foot .pn{{left:auto;right:0}}
.cv-c{{position:absolute;left:48px;top:300px;font-size:170px;line-height:.98;letter-spacing:-.03em}}
.cv-foot{{position:absolute;left:48px;right:48px;bottom:48px;display:flex;justify-content:space-between;align-items:flex-end;font-size:18px;line-height:1.4}}
.dv-c{{position:absolute;left:48px;bottom:48px;font-size:150px;line-height:1;letter-spacing:-.02em;{up}}}
.i-lab{{position:absolute;left:48px;top:48px;font-size:22px;font-weight:600}}
.i-lead{{position:absolute;left:640px;top:48px;width:1100px;font-size:54px;line-height:1.15;letter-spacing:-.01em;font-family:{hf};font-weight:{self.fh.near(500)}}}
.i-body{{position:absolute;left:640px;top:520px;width:560px;font-size:22px;line-height:1.45;opacity:.85}}
.toc-c{{position:absolute;left:640px;top:48px;list-style:none;font-size:46px;line-height:1.38;font-family:{hf};font-weight:{self.fh.near(400)};{up}}}
.toc-c span{{opacity:.5}}
/* rows */
.rows{{border-top:1px solid #D9DCE1}}
.row{{display:grid;grid-template-columns:360px 1fr;padding:34px 0;border-bottom:1px solid #D9DCE1;gap:40px}}
.rt{{font-family:{hf};font-weight:{hw};font-size:30px;line-height:1.15;{up}}}
.rx{{font-size:24px;line-height:1.45;max-width:760px}}
/* grids */
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
.g3x2{{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);gap:24px;height:100%}}
.g3x2.cap-under{{gap:20px 24px}}
.g3x2.cap-under>div{{display:flex;flex-direction:column}}
.g3x2.cap-under .tile{{flex:1}}
.g3x2.cap-under .cap{{margin-top:12px;min-height:50px}}
.tile{{position:relative;border-radius:{'4px'};overflow:hidden}}
.tile.mis{{background:#F1F3F6}}
.strike{{position:absolute;inset:0;width:100%;height:100%;z-index:2}}
.msrow{{display:flex;height:100%;align-items:center;justify-content:space-around;padding:0 40px}}
.ms{{display:flex;flex-direction:column;align-items:center;gap:30px}}
.ms-l{{height:110px;display:flex;align-items:center}}
.ms .cap{{text-align:center}}
.cs{{position:relative;outline:2px dashed {P};outline-offset:0}}
.cs-in{{position:absolute;outline:1px solid rgba(0,0,0,.25)}}
.xq{{position:absolute;background:{shade(P, 0.7)};color:{INK};display:flex;align-items:center;justify-content:center;font-style:italic;font-size:22px;opacity:.9}}
/* palette */
.pal{{display:flex;height:100%;gap:0}}
.pal-b{{flex:4.2;display:flex}}
.pc{{position:relative;padding:28px}}
.pn-t{{font-weight:700;font-size:20px}}
.pn-t span{{display:block;font-weight:400;font-size:15px;opacity:.75;margin-top:2px}}
.pc .pv{{position:absolute;left:28px;bottom:28px;font-size:16px;line-height:1.5}}
.pal-n{{flex:1;display:flex;flex-direction:column}}
.nc{{flex:1;padding:16px 22px;display:flex;flex-direction:column;justify-content:space-between}}
.nc .pv{{font-size:14px;line-height:1.4}}
.am{{display:grid;gap:10px;height:100%}}
.am-h{{font-size:15px;font-weight:600;align-self:end;padding-bottom:6px}}
.am-r{{font-size:15px;font-weight:600;align-self:center}}
.am-c{{position:relative;border-radius:4px;padding:12px 14px}}
.am-x{{background:repeating-linear-gradient(45deg,#F1F3F6 0 8px,#fff 8px 16px)}}
.am-fail .am-aa{{opacity:.9}}
.am-aa{{font-family:{hf};font-weight:{hw};font-size:40px;line-height:1}}
.am-n{{position:absolute;left:14px;bottom:10px;font-size:14px;opacity:.85}}
.am-g{{position:absolute;right:10px;bottom:9px;font-size:12px;font-weight:700;padding:3px 8px;border-radius:20px}}
.am-f{{background:#E5322D;color:#fff}}
.acg{{display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:1fr;gap:18px;height:100%}}
.ac{{position:relative;padding:22px;border-radius:4px}}
.ac-aa{{font-family:{hf};font-weight:{hw};font-size:64px;line-height:1}}
.ac-m{{position:absolute;left:22px;bottom:18px;font-size:16px;line-height:1.4}}
/* type */
.tf{{padding:56px 64px;height:100%;display:flex;flex-direction:column}}
.tf-n{{font-size:{(140 if self.same_font else 110)}px;line-height:1.05;margin:18px 0 30px;letter-spacing:-.01em}}
.tf-g{{font-size:{(36 if self.same_font else 30)}px;line-height:1.35;word-break:break-all}}
.tf-w{{margin-top:auto;display:flex;flex-wrap:wrap;gap:8px 26px;font-size:24px}}
.hier{{padding:56px 64px;height:100%;display:flex;flex-direction:column;justify-content:space-evenly}}
.hr .cap{{font-size:15px;opacity:.6;margin-bottom:8px;font-family:{bf}}}
/* pattern */
.pat{{position:relative;height:100%;overflow:hidden;border-radius:{'6px'}}}
.icg{{display:grid;grid-template-columns:repeat(5,1fr);gap:24px}}
.ic{{background:#F1F3F6;aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:6px;margin-bottom:8px}}
/* assets */
.a4{{position:relative;width:500px;height:707px;overflow:hidden;box-shadow:0 18px 40px rgba(0,0,0,.12)}}
.a4-tag{{position:absolute;right:40px;top:52px;font-size:13px;opacity:.6;max-width:200px;text-align:right}}
.a4-lines{{position:absolute;left:40px;right:40px;top:180px;display:flex;flex-direction:column;gap:18px}}
.a4-lines i{{display:block;height:7px;background:#ECEEF1;border-radius:4px}}
.a4-lines i:nth-child(4n){{width:60%}}
.a4-foot{{position:absolute;left:40px;right:40px;bottom:36px;font-size:11px;line-height:1.5;color:#555}}
.a4-foot span{{display:block;width:40px;height:4px;margin-bottom:12px}}
.a4-title{{position:absolute;left:40px;top:48px;font-family:{hf};font-weight:{hw};font-size:46px;line-height:1.05;{up}}}
.a4-title span{{font-family:{bf};font-weight:400;font-size:18px;text-transform:none;opacity:.85}}
.bc{{position:relative;width:595px;height:385px;border-radius:8px;overflow:hidden;box-shadow:0 18px 40px rgba(0,0,0,.12)}}
.bc-t{{position:absolute;left:44px;bottom:40px;font-size:16px;line-height:1.5;color:#333}}
.bc-t b{{font-size:26px;color:{INK}}}
/* photo */
.pdg{{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;height:100%}}
.pd{{display:flex;flex-direction:column}}
.phw{{position:relative;flex:1;min-height:0;border-radius:4px;overflow:hidden}}
.ph{{display:flex;align-items:center;justify-content:center}}
.ph span{{font-size:16px;opacity:.55;color:{INK}}}
.pd-t{{font-family:{hf};font-weight:{hw};font-size:26px;margin:18px 0 6px;{up}}}
/* applications */
.browser{{width:980px;height:640px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.15);display:flex;flex-direction:column}}
.bb{{height:38px;background:#E9EBEE;display:flex;align-items:center;gap:8px;padding:0 16px}}
.bb i{{width:12px;height:12px;border-radius:50%;background:#C9CDD3}}
.bb span{{margin-left:20px;background:#fff;border-radius:6px;padding:3px 16px;font-size:13px;color:#666}}
.site{{flex:1;display:flex;flex-direction:column}}
.nav{{height:74px;display:flex;align-items:center;gap:34px;padding:0 36px;font-size:15px}}
.nav>div:first-child{{margin-right:auto}}
.nav b{{padding:10px 20px;border-radius:30px;font-size:14px}}
.hero{{position:relative;flex:1;overflow:hidden;padding:70px 56px}}
.hero-t{{position:relative;font-size:64px;line-height:1.02;max-width:640px;letter-spacing:-.02em}}
.hero-s{{position:relative;font-size:18px;line-height:1.45;max-width:520px;margin-top:20px;opacity:.9}}
.btn{{position:relative;display:inline-block;margin-top:28px;padding:14px 26px;border-radius:30px;font-size:15px}}
.phone{{width:320px;height:650px;background:#111;border-radius:46px;padding:12px;box-shadow:0 24px 60px rgba(0,0,0,.2)}}
.scr{{height:100%;border-radius:36px;overflow:hidden;position:relative;text-align:center}}
.ph-t{{font-size:34px;line-height:1.05;margin:40px 28px 0}}
.ph-b{{position:absolute;left:28px;right:28px;bottom:40px;padding:16px;border-radius:30px;font-weight:600}}
.post{{position:relative;width:470px;height:470px;overflow:hidden;box-shadow:0 18px 40px rgba(0,0,0,.12)}}
.post-t{{position:absolute;left:36px;top:36px;right:36px;font-size:62px;line-height:1;letter-spacing:-.02em}}
.post-q{{position:absolute;left:36px;right:36px;top:140px;font-size:30px;line-height:1.3}}
.post-bar{{position:absolute;left:36px;bottom:40px;width:80px;height:8px}}
.poster{{position:relative;width:420px;height:594px;overflow:hidden;box-shadow:0 18px 40px rgba(0,0,0,.12)}}
.pos-t{{position:relative;margin:40px 34px 0;font-size:58px;line-height:1;letter-spacing:-.02em}}
.bento{{display:grid;height:100%;gap:18px;grid-template-columns:1.3fr 1fr 1fr 1fr;grid-template-rows:1fr 1fr;
  grid-template-areas:"a a b c" "d e e f"}}
.bx{{position:relative;overflow:hidden;border-radius:{'10px'}}}
.sw{{display:flex;height:100%;padding:24px;gap:8px;align-items:stretch}}
.sw i{{flex:1;border-radius:4px}}
.bx-aa{{position:absolute;left:28px;top:10px;font-size:180px;line-height:1.1}}
.bx-tag{{position:absolute;left:28px;right:28px;bottom:26px;font-size:40px;line-height:1.05}}
"""

    def layout_css(self):
        def number(key, default, lo, hi):
            value = float(self.layout.get(key, default))
            if not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"layout.{key} must be between {lo} and {hi}")
            return value
        x = number("content_x", 480, 420, 600)
        scale = number("headline_scale", 1, 0.8, 1.2)
        radius = number("corner_radius", 6, 0, 24)
        spacing = number("row_spacing", 34, 20, 48)
        return (f".dv-c{{line-height:1.3}}.ct{{left:48px;top:48px;line-height:1.3}}.foot{{left:48px;right:48px;bottom:48px}}"
                f".cbody{{left:{x}px;top:180px}}.csec{{left:auto;right:48px;top:58px}}"
                f".ct{{max-width:1580px}}.cdesc{{top:180px}}"
                f".cdesc{{width:{x-130}px}}"
                f".cv-c{{font-size:{170*scale}px}}"
                f".dv-c{{font-size:{150*scale}px}}"
                f".panel,.tile,.bx{{border-radius:{radius}px}}"
                f".row{{padding:{spacing}px 0}}"
                ".toc-c{right:48px;font-size:38px}.toc-c a{display:flex;gap:20px;color:inherit;text-decoration:none}.toc-c small{margin-left:auto;font:inherit}"
                ".spec-table{border-collapse:collapse;width:100%;font-size:22px;line-height:1.35}.spec-table td,.spec-table th{border-bottom:1px solid #ddd;padding:14px;text-align:left;vertical-align:top}.palette-table{font-size:19px}.palette-table td{padding:10px 14px}"
                ".module{display:flex;flex-direction:column;gap:24px;height:100%;font-size:24px;line-height:1.4}.module-lead{font-size:36px}.module-note,.module-status{font-size:19px}.module-status{margin-top:24px}"
                ".module-images{display:flex;gap:24px;flex:1;min-height:0}.module-images figure{flex:1;min-width:0;display:flex;flex-direction:column;gap:12px}.module-images img{width:100%;flex:1;min-height:0;object-fit:contain}.module-images figcaption{font-size:19px}")

    def html(self):
        slides = self.build()
        body = "\n".join(f'<div class="wrap" id="page-{i}">{s}</div>' for i, s in enumerate(slides, 1))
        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(self.name)} Brand Guidelines</title><style>{self.css()}{self.layout_css()}</style></head>
<body>{body}
<script>
function fit(){{if(matchMedia('print').matches)return;var s=Math.min(1,(innerWidth-32)/1920);document.documentElement.style.setProperty('--s',s);}}
addEventListener('resize',fit);fit();
</script></body></html>""", len(slides)


# ------------------------------------------------------------------ render


def render(html_path, out_dir, base_name, pdf, previews):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto("file://" + os.path.abspath(html_path))
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(400)
        if pdf:
            pg.emulate_media(media="print")
            out = os.path.join(out_dir, base_name + ".pdf")
            pg.pdf(path=out, width="1920px", height="1080px", print_background=True,
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            print("PDF:", out)
        if previews:
            pg.emulate_media(media="print")
            pv = os.path.join(out_dir, "previews")
            os.makedirs(pv, exist_ok=True)
            els = pg.query_selector_all(".slide")
            paths = []
            for i, el in enumerate(els, 1):
                fp = os.path.join(pv, f"slide-{i:02d}.png")
                el.screenshot(path=fp)
                paths.append(fp)
            if Image:
                th = [Image.open(f).convert("RGB").resize((384, 216)) for f in paths]
                cols = 6
                rows = math.ceil(len(th) / cols)
                sheet = Image.new("RGB", (cols * 392, rows * 224), "white")
                for i, t in enumerate(th):
                    sheet.paste(t, ((i % cols) * 392, (i // cols) * 224))
                sheet.save(os.path.join(pv, "contact_sheet.jpg"), quality=85)
            print("Previews:", pv)
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--out", default="out")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--previews", action="store_true")
    a = ap.parse_args()
    with open(a.config) as f:
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(a.config))
    from validate_brand import validate
    errors, checks = validate(cfg, __import__("pathlib").Path(base))
    for message in checks:
        warn(message)
    if errors:
        raise SystemExit("Invalid brand configuration:\n" + "\n".join(errors))
    deck = Deck(cfg, base)
    doc, count = deck.html()
    os.makedirs(a.out, exist_ok=True)
    base_name = re.sub(r"[^A-Za-z0-9]+", "_", deck.name).strip("_") + "_Brand_Guidelines"
    hp = os.path.join(a.out, base_name + ".html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"HTML: {hp} ({count} slides, layout=adaptable)")
    if a.pdf or a.previews:
        render(hp, a.out, base_name, a.pdf, a.previews)
    if WARNINGS:
        print("\n%d warning(s) - mention relevant ones to the user." % len(WARNINGS))


if __name__ == "__main__":
    main()
