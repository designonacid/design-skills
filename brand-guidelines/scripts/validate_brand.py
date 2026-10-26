#!/usr/bin/env python3
"""Check a brand-guide configuration before rendering. Uses only the standard library."""
import argparse
import json
import math
import re
from pathlib import Path

SECTIONS = {'overview', 'logo', 'color', 'typography', 'visual_elements', 'corporate_assets', 'photography', 'applications', 'handoff'}
STATUSES = {'supplied', 'derived', 'proposed'}

def validate(cfg, base):
    errors, warnings = [], []
    def asset(value, label):
        if not isinstance(value, str) or not value.strip():
            errors.append(f'{label}: expected a non-empty file path'); return
        if not (base / value).is_file():
            errors.append(f'{label}: file does not exist: {value}')
    if not isinstance(cfg, dict):
        return ['Configuration must be an object'], []
    if not cfg.get('brand_name'):
        errors.append('brand_name is required')
    logos = cfg.get('logo', {})
    if not any(logos.get(k) for k in ('full', 'mark', 'wordmark')):
        errors.append('Supply at least one primary logo asset')
    for k, value in logos.items():
        if value: asset(value, f'logo.{k}')
    colors = cfg.get('colors', [])
    if not colors: errors.append('Supply at least one palette color')
    for i, c in enumerate(colors):
        if not re.fullmatch(r'#?(?:[\da-fA-F]{3}|[\da-fA-F]{6})', str(c.get('hex', ''))):
            errors.append(f'colors[{i}].hex: expected 3 or 6 hexadecimal digits')
        if c.get('status', 'supplied') not in STATUSES:
            errors.append(f'colors[{i}].status: use supplied, derived, or proposed')
        if not c.get('role'): warnings.append(f'colors[{i}]: color role is unspecified')
        if c.get('cmyk') is not None:
            vals = c['cmyk'] if isinstance(c['cmyk'], list) else str(c['cmyk']).split(',')
            try:
                if len(vals) != 4 or not all(0 <= float(v) <= 100 for v in vals): raise ValueError()
            except (TypeError, ValueError): errors.append(f'colors[{i}].cmyk: expected four percentages from 0 to 100')
    fonts = cfg.get('fonts', {})
    for role in ('heading', 'body'):
        font = fonts.get(role) or fonts.get('body' if role == 'heading' else 'heading') or {}
        if not font.get('files'): warnings.append(f'fonts.{role}: no embedded font files; verify actual font and disclose any substitute')
        for i, f in enumerate(font.get('files', [])): asset(f.get('path'), f'fonts.{role}.files[{i}]')
    assets = cfg.get('assets', {})
    if assets.get('pattern'): asset(assets['pattern'], 'assets.pattern')
    for key in ('photos', 'bad_photos'):
        for value in assets.get(key, []): asset(value, f'assets.{key}')
    for item in assets.get('icons', []): asset(item.get('path'), 'assets.icons.path')
    for item in assets.get('applications', []): asset(item.get('image'), 'assets.applications.image')
    for item in cfg.get('copy', {}).get('photo_directions', []):
        if item.get('image'): asset(item['image'], 'copy.photo_directions.image')
    rules = cfg.get('logo_rules', {})
    if 'clearspace_ratio' in rules:
        ratio = rules['clearspace_ratio']
        if not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or not 0 < ratio <= 2:
            errors.append('logo_rules.clearspace_ratio: expected a finite ratio above 0 and at most 2')
        if not rules.get('clearspace_status'): warnings.append('Clearspace approval/status is unspecified')
    for key, value in rules.get('min_size', {}).items():
        if value.get('axis') not in ('width', 'height'): errors.append(f'logo_rules.min_size.{key}: specify width or height axis')
        if not value.get('status'): warnings.append(f'Minimum size for {key}: approval/status is unspecified')
        for medium, unit in (('print', 'mm'), ('digital', 'px')):
            if medium in value and not re.fullmatch(r'\d+(?:\.\d+)?\s*' + unit, str(value[medium])):
                errors.append(f'Minimum {medium} size for {key}: use a positive numeric value in {unit}')
            elif medium in value and float(re.match(r'\d+(?:\.\d+)?', str(value[medium]))[0]) <= 0:
                errors.append(f'Minimum {medium} size for {key} must be above zero')
    for i, m in enumerate(cfg.get('modules', [])):
        label = f'modules[{i}]'
        if m.get('section') not in SECTIONS: errors.append(f'{label}: unknown section')
        if not m.get('title'): errors.append(f'{label}: title required')
        if not any(m.get(k) for k in ('lead', 'items', 'columns', 'images')): errors.append(f'{label}: needs content')
        if m.get('rows') and not m.get('columns'): errors.append(f'{label}: table rows need columns')
        for row in m.get('rows', []):
            if len(row) != len(m.get('columns', [])): errors.append(f'{label}: table row length differs from column count')
        if len(m.get('rows', [])) > 7 or len(m.get('items', [])) > 4 or len(m.get('images', [])) > 3:
            warnings.append(f'{label}: dense content; split and visually check overflow')
        for im in m.get('images', []): asset(im.get('path'), label + '.images.path')
    weights = cfg.get('color_usage', {}).get('weights', [])
    if weights:
        try:
            if not math.isclose(sum(float(v['percent']) for v in weights), 100, abs_tol=.01):
                errors.append('color_usage.weights: percentages must total 100')
            if any(float(v['percent']) < 0 for v in weights): errors.append('color_usage.weights: percentages cannot be negative')
        except (KeyError, TypeError, ValueError): errors.append('color_usage.weights: each entry needs numeric percent')
    years = re.findall(r'\b\d{4}\b', str(cfg.get('date', '')))
    if years and cfg.get('year') and str(cfg['year']) != years[-1]: errors.append('date and year disagree')
    for asset_entry in cfg.get('asset_manifest', []):
        if asset_entry.get('path'): asset(asset_entry['path'], 'asset_manifest.path')
    if not cfg.get('layout', {}).get('rationale'): warnings.append('Record a brand-specific layout rationale')
    return errors, warnings

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    try:
        cfg = json.loads(args.config.read_text())
        errors, warnings = validate(cfg, args.config.resolve().parent)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors, warnings = [f'Invalid configuration: {exc}'], []
    for message in warnings: print('WARNING:', message)
    for message in errors: print('ERROR:', message)
    print(f'{len(errors)} error(s), {len(warnings)} warning(s)')
    raise SystemExit(bool(errors))

if __name__ == '__main__': main()
