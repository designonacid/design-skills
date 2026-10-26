# Proposal input

Paths are relative to the JSON file. The deck is 1920 × 1080 with fixed 48 px margins on all four sides. The top-level keys are:

- `brand_name`, `title`, `subtitle`, `date`, and `status`: presentation identity.
- `logo`: original SVG path. All placements preserve its viewBox aspect.
- `fonts`: array of `{family, path, weight}`. Fonts embed in HTML/PDF; identify any substitute.
- `font_family`: the family to use across the deck.
- `layout`: `{rationale, acid_evidence, title_size}`. Use actual method evidence, not invented scores. Optional `css` permits brand-specific composition refinements; use trusted authored CSS only.
- `slides`: ordered content objects. Each has `type`, `title`, optional `body`, `note`, and `dark`. A `note` contains client-relevant source/assumption information, not QA logs.

Supported types:

- `cover`: brand logo, proposal title and subtitle.
- `statement`: large `title` and optional supporting `body`.
- `text`: `title`, `body`, and `items` with `title` and `text`.
- `logo`: complete source mark and optional explanatory `body`.
- `construction`: optional `guides` containing `x` and `y` arrays in source SVG coordinates. Generates an editable construction SVG from the top-level logo.
- `image`: `image` path, `body`, and `credit`. Use for a complete composition, reference, framework or mockup.
- `analysis`: `image` containing the actual method framework heat map, and four evidence-grounded `items`. Attribute Design On Acid and disclose qualitative inference.
- `versions`: source logo on positive and reversed backgrounds.
- `typography`: `headline`, `sample`, and `body`.
- `palette`: `colors` array of `{name, hex}` and a short `body` explaining their strategic role.
- `editorial`: `image`, `project`, `studio`, and `credit`; shows an example web editorial composition.
- `social`: `image`, `project`, `studio`, and `credit`; shows a proposed social editorial layout.
- `decision`: `title`, `body`, and `items` describing the feedback needed and proposed next steps.

Composition types are reusable building blocks inside one adaptable style, not client-selectable template styles. Most slides need 20–60 words. Let artwork-led slides carry less text. End on a decision appropriate to the brief. Keep factual source notes in JSON and visible where they affect interpretation. Do not invent prices, deadlines, survey results, or signed-off strategy.
