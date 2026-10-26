# brand.json specification

All file paths are relative to the folder containing brand.json (absolute paths also work).
Only `brand_name`, one logo and one color are strictly required.

## Top level

| Key | Type | Notes |
|---|---|---|
| `brand_name` | string | Required. Used on cover, footers, file name. |
| `layout` | object | Brand-specific rationale, ACID evidence, and optional layout controls; see below. |
| `date` | string | Shown on cover/back, e.g. `"October 2026"`. The year is parsed from it. |
| `year` | string | Optional override for the footer year. |
| `version` | string | Default `"1.0"`. |
| `tagline` | string | Used on letterhead, mockups, bento summary. Keep under ~45 characters. |
| `logo` | object | See below. |
| `colors` | array | See below. |
| `fonts` | object | See below. |
| `copy` | object | Brand copy + per-slide description overrides. |
| `logo_rules` | object | Minimum sizes, clearspace. |
| `contact` | object | Letterhead + business card details. |
| `assets` | object | Optional photos, pattern, icons, application images. |
| `sections` | object | Set a section key to `false` to drop it. |
| `generate_mockups` | bool | Default `false`. Set `true` to add proposed application mockups; review them as concepts. |

## logo

```json
"logo": {
  "full": "logo.svg",              // primary lockup (required unless mark/wordmark given)
  "mark": "symbol.svg",            // logomark / icon only
  "wordmark": "wordmark.svg",      // logotype / name only
  "full_reversed": "logo-white.svg" // optional: official version for dark/colored backgrounds
}
```
- SVG (with a `viewBox`) or transparent PNG preferred. JPG/PNG on white is auto-cleaned.
- Without a suitable supplied variant, the original is retained and a contrast-review warning is emitted. Set `logo_rules.allow_generated_mono: true` only when a generated one-color proposal is wanted. Supply `full_reversed` for the actual reversed identity.
- A logo that is itself white/light is detected and shown correctly (original on dark, single-color on light).

## colors

```json
"colors": [
  {"name": "Forest", "hex": "#0B6E4F", "role": "primary"},
  {"name": "Amber", "hex": "#F2A541", "role": "secondary", "cmyk": "0, 32, 73, 5", "pantone": "1365 C"},
  {"name": "Midnight", "hex": "#0F1B2D", "role": "tertiary"},
  {"name": "Sand", "hex": "#EFE8DC", "role": "accent"},
  {"name": "Charcoal", "hex": "#333333", "role": "neutral"}
]
```
- `role`: `primary`, `secondary`, `tertiary`, `accent`, or `neutral`. Every configured entry is displayed; palettes paginate at six entries per page. Contrast pages cover all configured colors in blocks of up to six rows/columns, without adding undocumented colors.
- No undocumented neutral palette is added. The renderer may use neutral document surfaces; those are not claimed as brand palette entries. Add `status` to a color to identify `supplied`, `derived`, or `proposed` (default supplied, not automatically approved).
- `cmyk` and `pantone` are optional official values; otherwise CMYK is auto-converted (approximate).
- With only one brand color, secondary/tertiary are *derived* as darker shades for dividers, mockups and backgrounds (they are renderer-only derived surfaces, not approved palette entries; explicitly configure any proposed shade needed as a brand standard).

## fonts

```json
"fonts": {
  "heading": {
    "family": "Space Grotesk",
    "files": [{"path": "fonts/SpaceGrotesk_wght_.ttf", "weight": "300 700", "style": "normal"}],
    "weight": 700,                        // preferred headline weight; nearest available is used
    "fallback": "Helvetica, Arial, sans-serif"
  },
  "body": {
    "family": "Inter",
    "files": [{"path": "fonts/Inter-Regular.ttf", "weight": "400", "style": "normal"},
              {"path": "fonts/Inter-SemiBold.ttf", "weight": "600", "style": "normal"}]
  }
}
```
- `weight` in files: a single value (`"400"`) for static fonts, a range (`"100 900"`) for variable fonts. `fetch_google_font.py` outputs this format.
- One family only? Give just `heading` or just `body`; the other mirrors it.
- Fonts are embedded in the HTML/PDF as base64.

## copy

Brand content (sections are skipped when absent):
```json
"copy": {
  "intro_lead": "Big opening sentence on the intro slide.",
  "intro": "Smaller paragraph under it.",
  "positioning": {"purpose": "...", "vision": "...", "mission": "..."},   // any keys; shown as rows
  "values": [{"title": "Built to last", "text": "One sentence."}],        // 3-5 best
  "tone":   [{"title": "Grounded", "text": "One sentence."}],             // 3-4 best
  "photo_directions": [{"title": "Real conditions", "text": "...", "image": "photos/a.jpg"}],  // up to 3
  "photo_misuses": ["Overly staged stock imagery.", "..."],               // up to 3
  "hierarchy_sample": {"headline": "...", "subheading": "...", "body": "...", "caption": "..."}
}
```

Per-slide description overrides (all optional; built-in defaults are starting descriptions, not verified brand rules):
`positioning_desc, values_desc, tone_desc, logomark_desc, logotype_desc, logo_desc, logo_color_desc, min_size_desc, clearspace_desc, clearspace_rule, logo_bg_desc, misuse_desc, palette_desc, access_desc, typeface_desc, hierarchy_desc, pattern_desc, icons_desc, letterhead_desc, card_desc, photo_desc, photo_misuse_desc, app_digital_desc, app_social_desc, summary_desc`

Keep descriptions to 1–3 sentences (≈ 40 words max): they sit in a narrow column.

## logo_rules

```json
"logo_rules": {
  "clearspace_ratio": 0.5,
  "clearspace_status": "proposed",   // x = ratio × logo height; no clearspace page unless explicitly supplied
  "min_size": {
    "mark":     {"print": "10mm", "digital": "32px", "axis": "width", "status": "proposed"},
    "wordmark": {"print": "30mm", "digital": "120px", "axis": "width", "status": "proposed"},
    "full":     {"print": "35mm", "digital": "140px", "axis": "width", "status": "proposed"}
  }
}
```
The numerical examples above illustrate syntax, not recommended limits. Omit unsupported limits. Minimum-size pages require explicit values and an axis. Override `copy.clearspace_rule` to describe the brand's real rule (e.g. "x = height of the symbol").

## contact

`name, position, address, phone, email, website`. Missing details remain empty; contact-based stationery pages are omitted when no contact object is supplied. Do not fabricate domains, addresses, names, or phone numbers.

## assets

```json
"assets": {
  "pattern": "pattern.png",                         // optional; generated patterns require explicit generate_pattern
  "icons": [{"path": "icons/home.svg", "name": "Home"}],  // up to 15, recolored to the primary color
  "photos": ["photos/1.jpg", "photos/2.jpg", "photos/3.jpg"],  // fills photo directions if no per-direction image
  "bad_photos": ["photos/bad1.jpg"],                // optional examples for Photo Misuse
  "applications": [{"image": "mockups/bag.jpg", "title": "Packaging", "text": "One sentence."}]
}
```

## sections

Keys: `overview, logo, color, typography, visual_elements, corporate_assets, photography, applications`.
`"sections": {"corporate_assets": false}` drops that section and renumbers everything.

## layout

One adaptable design system. Do not select or present named preset styles. A legacy `style` field is ignored.

```json
"layout": {
  "rationale": "Explain why this brand needs this balance of construction and creative expression.",
  "acid_evidence": {
    "source": "Path or supplied document containing the actual ACID Method output, or explicitly state unavailable.",
    "abstraction": "Relevant finding and its layout implication.",
    "creativity": "Relevant finding and its layout implication.",
    "intention": "Relevant finding and its layout implication.",
    "depth": "Relevant finding and its layout implication."
  },
  "content_x": 480,
  "headline_scale": 1.0,
  "corner_radius": 0,
  "row_spacing": 34
}
```

Numeric controls are optional rendering adjustments, not analysis scores. Supported ranges: content_x 420–600 px, headline_scale 0.8–1.2, corner_radius 0–24 px, row_spacing 20–48 px. Choose values from the rationale, not a formula assigning ACID scores to styles. More substantial composition changes require adapting the generator. Visually verify the resulting layout with the actual brand assets.

## Extended coverage and decision records

The following metadata supports authoring and review; it does not automatically produce pages. Use `modules` or adapt a page method to visualize it.

- `coverage`: array of `{subject, included, reason}` describing scope and omissions.
- `decisions`: array of `{topic, value, status, approval, evidence}`. `status` is `supplied`, `derived`, or `proposed`; approval is a separate recorded state. Evidence refers to actual brand inputs and observations. Keep internal evidence out of client pages unless useful.
- `color_usage`: optional roles, allowed pairs, restrictions, and `weights: [{name, percent}]`; percentages must total 100 and remain labeled with their scope/status. This is authoring metadata, not an automatic weighting chart.
- `typography`: optional role specifications, print/screen scales, tracking units, fallbacks, and font-access notes. The builder's two text families remain `fonts.heading/body`; use a custom specimen for wordmark-only or additional roles.
- `asset_manifest`: array of `{path, purpose, format, status, license_note}`. Paths identify delivered local files. Use a handoff module for a readable inventory; include only real locations/contacts.
- `generate_pattern`: default `false`. Explicitly enables a proposed logo-derived pattern. An existing `assets.pattern` is shown without this switch.

## modules: additional pages within existing sections

The builder appends each module to its named section before numbering. This supports personality, messaging, placement, color behavior, detailed type specifications, photography direction, illustration, motion, social/email, production annotations, and handoff without a fixed page count. Choose content and composition from brand evidence. These are content blocks within one visual system, not selectable brand-guide styles.

```json
"modules": [
  {
    "section": "overview",
    "title": "Voice in practice",
    "description": "Keep service messages clear and helpful.",
    "status": "Proposed wording — review required",
    "columns": ["Situation", "Use", "Reason"],
    "rows": [["A delayed delivery", "Your order arrives on Friday. We will send tracking today.", "State the outcome and next step."]]
  },
  {
    "section": "typography",
    "title": "Reading hierarchy",
    "description": "Specifications and their application in long copy.",
    "images": [{"path": "artwork/editorial-specimen.svg", "alt": "Annotated editorial layout", "caption": "Sizes shown in the artwork refer to final print output."}],
    "note": "Use a production-sized proof to validate readability."
  },
  {
    "section": "handoff",
    "title": "Choosing the right asset",
    "items": [{"title": "Vector master", "text": "Use the supplied SVG for scalable artwork."}]
  }
]
```

Supported fields: `section`, `title`, `description`, `status`, `lead`, `columns` with `rows`, `items` as title/text rows, `images` as path/alt/caption objects, and `note`. All text is escaped; HTML is not executed. Images retain their proportions using `contain`. Keep modules focused: roughly 3–6 short table rows, up to 4 short text rows, or 1–3 images. Combining several dense blocks requires splitting pages. Exact-fit limits depend on real text and fonts; render and inspect.

Recognized section keys include `handoff` in addition to the existing keys. Modules can populate a section even without built-in content; `sections.<key>: false` disables both built-in and added pages. Ordering follows the core section sequence, with handoff last before the ending. For a complex measured diagram, annotated application or typographic specimen, prepare original SVG artwork from actual assets and include it as an image, or extend the generator. A descriptive metadata field alone does not render a visual proof.
