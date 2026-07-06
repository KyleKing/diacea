# Real-World Diagram Fixtures

Diagram files collected from public repositories to exercise diacea's parsers against
real-world input. All files retrieved 2026-07-05. `tests/test_real_fixtures.py`
parametrizes over this directory.

The `.mmd` files from `max9159/system-design` and `mermaid-js/mermaid` are mermaid code
blocks extracted verbatim from the source markdown/HTML (fence markers removed, nothing
else changed). The tldraw files were taken from commit `6bd7f4fcc97bbecda6785968c64c2814ea25452f`
(2023-12-19), the last commit at which tldraw/tldraw was Apache-2.0 licensed.

| File | Source URL | License |
| ---- | ---------- | ------- |
| `ai_patent_check_app.mmd` | <https://github.com/max9159/system-design/blob/main/flowchart/AIPatentInfringementCheckApp.flowchart.md> | MIT |
| `azure_stream_analytics.puml` | <https://github.com/plantuml-stdlib/Azure-PlantUML/blob/master/samples/Basic%20usage%20-%20Stream%20processing%20with%20Azure%20Stream%20Analytics.puml> | MIT |
| `bigbank_c4_container.puml` | <https://github.com/plantuml-stdlib/C4-PlantUML/blob/master/samples/C4_Container%20Diagram%20Sample%20-%20bigbankplc.puml> | MIT |
| `dynamic_loading_mechanism.mmd` | <https://github.com/max9159/system-design/blob/main/flowchart/dynamicLoading/DynamicLoadindgMechanism.flowchart.md> | MIT |
| `fineract_command_architecture_c4.puml` | <https://github.com/apache/fineract/blob/develop/fineract-doc/src/docs/en/diagrams/command-architecture-level-1.puml> | Apache-2.0 |
| `fineract_release_process.puml` | <https://github.com/apache/fineract/blob/develop/fineract-doc/src/docs/en/diagrams/release-process.puml> | Apache-2.0 |
| `intertwin_c4_qa_pipeline.excalidraw` | <https://github.com/interTwin-eu/architecture-diagrams/blob/main/T6.2/C4-for-QA.excalidraw> | MIT |
| `intertwin_dte_infra_containers.excalidraw` | <https://github.com/interTwin-eu/architecture-diagrams/blob/main/WP5/dte%20infra%20containers.excalidraw> | MIT |
| `intertwin_system_context.excalidraw` | <https://github.com/interTwin-eu/architecture-diagrams/blob/main/Blueprint%20architecture/system_context_diagram/system_conetxt_diagram.excalidraw> | MIT |
| `llm_proxy_component.svg` | <https://github.com/max9159/system-design/blob/main/architecture/ai-integration/llm-proxy-cmp-diagram.svg> | MIT |
| `mcp_playwright_architecture.mmd` | <https://github.com/max9159/system-design/blob/main/flowchart/McpServerWithPlaywrightExample.flowchart.md> | MIT |
| `mermaid_infra_topology.mmd` | <https://github.com/mermaid-js/mermaid/blob/develop/demos/flowchart.html> | MIT |
| `tldraw_legacy_shapes.tldr` | <https://github.com/tldraw/tldraw/blob/6bd7f4fcc97bbecda6785968c64c2814ea25452f/apps/vscode/extension/examples/1.tldr> | Apache-2.0 (at pinned commit) |
| `tldraw_v2_selection_demo.tldr` | <https://github.com/tldraw/tldraw/blob/6bd7f4fcc97bbecda6785968c64c2814ea25452f/packages/tldraw/src/lib/tools/selection-logic/selection.tldr> | Apache-2.0 (at pinned commit) |
| `tldraw_v2_vscode_frames.tldr` | <https://github.com/tldraw/tldraw/blob/6bd7f4fcc97bbecda6785968c64c2814ea25452f/apps/vscode/VS-Code-Extension-1.tldr> | Apache-2.0 (at pinned commit) |

Sources considered but skipped: <https://plus.excalidraw.com/use-cases/software-architecture-diagram>
links no downloadable `.excalidraw` scenes; <https://libraries.excalidraw.com> hosts
`.excalidrawlib` libraries (not scenes); `swaymun/system-design-excalidraws` and
`Prakash-sa/system-design-ultimatum` have no license; `zsviczian/obsidian-excalidraw-plugin`
(only real `.excalidraw.md` source found) is AGPL-3.0.
