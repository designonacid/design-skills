# Source-based logo construction

The diagram explains the supplied geometry. It does not establish how the original designer created it.

Use a complete pale-grey logo, cyan alignment guides and square anchor nodes, and thin dark lines to round handle endpoints. Keep guides sparse: major top/baseline and only useful vertical extrema or shared alignments. Guides may be chosen from observed geometry or supplied coordinates. Arbitrary guides must not masquerade as measured proportions.

Extract anchors and control points from the visible SVG paths. The helper supports M/L/H/V/C/S/Q/T/Z path commands, circles, ellipses, polygons, polylines, and simple unrounded rectangles. It respects display:none on groups and CSS classes. Unsupported paths, transforms, references, and shapes stop generation with an actionable error. Convert/flatten those explicitly using an appropriate vector tool, retaining the source. Never infer anchors from a PNG edge and label them original.

A circle/ellipse element has no Bezier nodes in the source. When its conventional four-node cubic representation is shown, disclose that conversion. The visible outline remains the source circle. Use kappa = 4(sqrt(2)-1)/3 for explanatory handles, and do not call those handles original source anchors. Straight path segments need no decorative handles. Close-path endpoints should not create duplicate squares.

Verify guide positions against the viewBox, overlay endpoints against the outline, and show only meaningful handles. Use non-scaling strokes and fixed-size markers at the final viewing scale. Keep the source artwork intact in reveal/application slides. No golden-ratio or exact-grid claims without evidence.

For export, retain the construction as SVG alongside the deck so the geometry remains editable. If a client requests the original editable design file, explain that the SVG explanation does not replace that file.
