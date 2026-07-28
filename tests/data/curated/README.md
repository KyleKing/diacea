# Curated fixtures

Hand-authored minimal sources, each pinning one behavior. `scripts/render_fixtures.py` converts and renders the full matrix; `tests/test_curated_fixtures.py` runs the conversion, render (DIACEA_RENDER=1), and golden checks. Goldens in `goldens/` regenerate with DIACEA_REGEN_GOLDENS=1 once conversion behavior is trusted.

- `aws_hatchet_sketch.excalidraw`: realistic 20+ shape architecture (AWS region > Serverless lambdas, VPC > Hatchet on ECS) drawn by hand in excalidraw.com; carries soft-deleted (isDeleted) elements from a cleared canvas, boxes accidentally dragged to straddle boundaries, a stray unbound arrow, and orbit-mode arrow bindings
- `cloudflare_edge.mmd`: realistic 25-node edge architecture; frontmatter title, 3-level subgraph nesting (Workers platform > Durable Objects), node shape variety (cylinder, double-bracket queue), labeled and dashed edges, externals outside the boundary
- `deep_nesting.mmd`: flowchart with 3-level nested subgraphs and cross-subgraph edges
- `frames.tldr`: tldraw v2 nested frames (frame inside frame) with a leaf in each and one bound arrow across them
- `human_sketch_nested.excalidraw`: small hand-drawn sketch from excalidraw.com; mixed bound and loose labels, a label straddling its container's top edge, a leaf straddling the container border
- `email_service_c4.puml`: realistic 20+ element C4 design-review doc; nested System_Boundary x2 inside the service, System_Ext actors, technology descriptions, Rel crossing from externals into nested components
- `misaligned_containment.excalidraw`: human-sloppiness case; a leaf straddles the container border (~35% outside) and a label text sits just above its shape
- `nested_boundaries.excalidraw`: outer container > inner container > two leaves, one leaf directly in the outer, geometric text labels, two bound arrows
- `nested_c4.puml`: C4 System_Boundary > Container_Boundary > components, with a Rel from an outside Person into a nested component
- `styles.excalidraw`: style pass-through; solid fill, dashed stroke, ellipse and diamond shape types, one dotted bound arrow
- `tui_cloud_sync_sketch.excalidraw`: upper-bound manual sketch (96 live elements: 40 boxes, 16 arrows) drawn by hand in excalidraw.com; offline TUI app + sync daemon + cloud services, two boxes accidentally stacked on each other, labels straddling container borders, long cross-boundary arrows
