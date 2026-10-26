---
name: brand-proposal
description: Create client-facing brand proposal pitch decks that present a brand concept, explain design decisions, demonstrate applications, and ask for a direction decision. Includes a source-based logo construction page with vector anchors, curve handles, and a few guides. Use for presenting or pitching a proposed identity to a client, rather than documenting an approved identity in a brand manual.
---

# Brand Proposal

Create a 16:9 client presentation as PDF and self-contained HTML, with editable JSON and SVG sources. Use one adaptable visual system. Brand inputs and the Design On Acid ACID Method output determine how constructive or creative the layout becomes. Do not offer template styles.

## Slide margins

Use exactly 48 px on the top, left, right, and bottom of every 1920 × 1080 slide. Align primary headings and the cover logo to the 48 px left edge. Place top-aligned headings at y = 48 px and footer boxes 48 px above the bottom. Keep other content inside this safe area. Full-bleed backgrounds may extend to the canvas edge. Application mockup interiors have their own padding.

## Establish the proposal

Use the accessible brief, brand assets, and existing ACID output. Ask together for missing essentials: the brand/concept, logo artwork, and the client decision the deck should support. Discover available inputs before asking. Draft nonessential copy without blocking, and label proposals or assumptions accurately.

A proposal explains why a direction fits and helps a client decide. It should connect the brief to a concept, reveal the identity, explain important design choices, and demonstrate relevant applications. Finish with specific feedback or a direction decision. Do not turn it into an exhaustive usage manual. Do not invent research, client approval, designer intent, commercial terms, or delivery dates.

For an existing-brand sample, state that it demonstrates a proposal presentation using the existing identity. Separate observed assets, interpretive rationale, and proposed extensions.

## Derive the layout

Read the supplied ACID output and record relevant evidence in the proposal JSON. Let Abstraction, Creativity, Intention, and Depth jointly inform hierarchy, pacing, typography, imagery, and composition. Structure and creative expression can coexist within one deck. Avoid assigning an automatic template or invented numerical style score to a lens.

If performing a new analysis, use the available acid-method skill and include its required source-framework heat map. Keep evidence and qualitative interpretation distinct. If no analysis exists and none is performed, record the limitation and use a provisional rationale from the assets and brief.

Start around 12–18 slides, adapting to the actual decision and evidence. A useful arc is brief, insight, concept, logo reveal, construction, visual system, applications, and decision. Combine or reorder when it improves the story. A proposal can be expressive without reducing the precision of the construction page.

## Logo construction page

Read [references/logo-construction.md](references/logo-construction.md) before authoring this page. It is required when source geometry is available.

Show the complete logo in pale grey, sparse cyan guides, clearly visible square anchors, and relevant curve handles. Base the drawing on actual vector geometry. Do not invent perfect ratios, optical corrections, golden circles, or the designer's historical process.

Use `scripts/svg_construction.py` for supported SVG sources. It extracts path nodes and control handles, and converts circle/ellipse primitives to a clearly disclosed conventional cubic representation. It fails on unsupported transforms, references, or primitives instead of silently inventing geometry. Flatten or convert those in a vector editor with the original retained. For raster-only inputs, ask for the vector or label a separately approved reconstruction as an interpretation.

Keep all logos intact and at the original aspect ratio. Align the cover logo with its title unless the user requests another placement. Avoid repeating background masks that cut logos at the edges. Inspect construction at full size; anchors and handles must remain readable.

## Author and render

Read [references/proposal-json.md](references/proposal-json.md) for the schema and available composition primitives. The builder is a starting point; adapt compositions to the brand evidence rather than merely replacing text in a fixed template.

```bash
python scripts/build_proposal.py proposal.json --out output
```

To also render PDF and page PNGs, supply available runtime paths when they are not on the standard search path:

```bash
python scripts/build_proposal.py proposal.json --out output --pdf --previews   --node /path/to/node --playwright-module /path/to/playwright --browser /path/to/chrome
```

The Python renderer needs no extra package for HTML. PDF/previews need Node.js, Playwright, and Chromium or Chrome. Pillow is optional for the contact sheet. Use the host's artifact-operation marker before PDF authoring when required. Use the presentation workflow if the user requests PPTX or Google Slides rather than the PDF/HTML format.

## Review and deliver

Inspect the contact sheet and every slide at readable size. Check the cover alignment, original logo proportions and edges, construction source correspondence, diagram labels, font loading, text fit, and application credits. The renderer checks image containment but visual inspection is still required. Keep diagnosis and QA records out of the client slides.

Deliver the PDF and HTML with a concise note about draft assumptions that affect the decision. Retain JSON, SVG, and script sources for revisions. Install this skill in the user's skills folder when requested, and package a `.skill` archive when useful for handoff. Do not publish or contact the client unless explicitly instructed.
