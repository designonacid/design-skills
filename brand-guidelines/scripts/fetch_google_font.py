#!/usr/bin/env python3
"""
Download a Google Font family (upright + italic files) from the google/fonts
GitHub repo, which is reachable even when fonts.googleapis.com is not.

Usage:
    python fetch_google_font.py "Inter" --out ./fonts
    python fetch_google_font.py "Playfair Display" --out ./fonts

Prints a JSON list of downloaded files with weight/style, which you can paste
into the "files" list of a font entry in brand.json.
Exit code 1 if the family can't be found (then ask the user for the font files,
or pick a close Google Fonts alternative and say so).
"""
import argparse, json, os, re, sys, urllib.parse, urllib.request

BASE = "https://raw.githubusercontent.com/google/fonts/main"
LICENSE_DIRS = ["ofl", "apache", "ufl"]


def slug(family):
    return re.sub(r"[^a-z0-9]", "", family.lower())


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def find_metadata(family):
    s = slug(family)
    for d in LICENSE_DIRS:
        try:
            return d, s, get(f"{BASE}/{d}/{s}/METADATA.pb").decode("utf-8")
        except Exception:
            continue
    return None, None, None


def parse_fonts(meta):
    out = []
    for block in re.findall(r"fonts \{(.*?)\n\}", meta, re.S):
        fn = re.search(r'filename: "([^"]+)"', block)
        st = re.search(r'style: "([^"]+)"', block)
        wt = re.search(r"weight: (\d+)", block)
        if fn:
            out.append({"filename": fn.group(1),
                        "style": st.group(1) if st else "normal",
                        "weight": int(wt.group(1)) if wt else 400})
    axes = {}
    for a in re.findall(r"axes \{(.*?)\}", meta, re.S):
        tag = re.search(r'tag: "([^"]+)"', a)
        lo = re.search(r"min_value: ([\d.]+)", a)
        hi = re.search(r"max_value: ([\d.]+)", a)
        if tag and lo and hi:
            axes[tag.group(1)] = (float(lo.group(1)), float(hi.group(1)))
    return out, axes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("family")
    ap.add_argument("--out", default="fonts")
    args = ap.parse_args()

    d, s, meta = find_metadata(args.family)
    if not meta:
        print(f"Font family '{args.family}' not found in google/fonts.", file=sys.stderr)
        sys.exit(1)
    fonts, axes = parse_fonts(meta)
    os.makedirs(args.out, exist_ok=True)
    result = []
    for f in fonts:
        url = f"{BASE}/{d}/{s}/" + urllib.parse.quote(f["filename"])
        dest = os.path.join(args.out, f["filename"].replace("[", "_").replace("]", "_").replace(",", "_"))
        if not os.path.exists(dest):
            with open(dest, "wb") as fh:
                fh.write(get(url))
        entry = {"path": os.path.abspath(dest), "style": f["style"]}
        if "wght" in axes:  # variable font: covers a weight range
            lo, hi = axes["wght"]
            entry["weight"] = f"{int(lo)} {int(hi)}"
        else:
            entry["weight"] = str(f["weight"])
        result.append(entry)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
