# Design Skills

Two skills by Design On Acid for turning brand inputs into considered, usable design documents.

| Skill | Use it to | Files |
| --- | --- | --- |
| [Brand Guide](https://designonacid.com/skills/design-skills/brand-guide/) | Document an identity with practical rules and visual examples. | [Instructions](brand-guidelines/SKILL.md) · [Download](downloads/brand-guidelines.skill) |
| [Pitch Deck](https://designonacid.com/skills/design-skills/pitch-deck/) | Present a brand proposal, explain the direction, and help a client decide. | [Instructions](brand-proposal/SKILL.md) · [Download](downloads/brand-proposal.skill) |

## One adaptable system

The brand inputs and Design On Acid ACID Method findings shape the balance of structure and creative expression. The skills do not offer a menu of template styles. They preserve original logo proportions, use 48 px outer margins on a 1920 × 1080 slide canvas, and distinguish supplied material from proposed rules and interpretations.

If no ACID analysis is available, they use an explicitly provisional rationale from the brief and assets. The ACID Method skill is available separately at [designonacid/skills](https://github.com/designonacid/skills).

## Get started

1. Choose Brand Guide for a working manual, or Pitch Deck for a client direction decision.
2. Download its `.skill` archive. For assistants that load `SKILL.md` folders, extract it and put the enclosed folder in the assistant's configured skills directory. Keep its supporting scripts and references together.
3. Share the brief, original logo files, palette, fonts, imagery, and any existing ACID findings. Explain the audience and intended outcome.
4. Review the result and confirm proposed rules before treating them as approved standards.

These packages require an assistant with access to files and the ability to run their rendering tools. Installation and skill discovery depend on the host assistant.

## Outputs and requirements

**Brand Guide:** 16:9 PDF, self-contained HTML, editable brand configuration, and relevant prepared assets. Python 3 builds the HTML. Pillow supports raster assets. PDF/previews use Python Playwright and Chromium, or an available local browser renderer.

**Pitch Deck:** 16:9 PDF, self-contained HTML, and editable JSON/SVG sources. Python 3 builds the HTML. PDF/previews use Node.js, Playwright, and Chromium or Chrome. Pillow is optional for a contact sheet. The construction helper uses supported source SVG paths and fails on unsupported geometry instead of inventing it.

Licensed fonts and permitted image use remain the responsibility of the project. Missing assets or permissions should remain visible in the handoff; do not silently replace them or invent approval.

## Useful starting briefs

### Brand Guide

> Use the Brand Guide skill to create a practical manual from the identity I share. Let the brand and ACID findings shape the layout, show rules with useful examples, keep every logo intact, and identify proposed standards. Deliver PDF, self-contained HTML, and editable sources.

### Pitch Deck

> Use the Pitch Deck skill to present this brand direction. Connect the brief and ACID findings to the concept, include logo construction based on the actual vector anchors and curves, show meaningful applications, and finish with a clear decision. Deliver PDF, self-contained HTML, and editable sources.

[Explore Design Skills](https://designonacid.com/skills/design-skills/) · [The ACID Method](https://designonacid.com/method/)
