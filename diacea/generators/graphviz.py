"""GraphViz DOT generator - converts IR to GraphViz DOT format.

Supports directed/undirected graphs with clusters and auto-layout.

Design decisions (from Phase 3 open questions):
1. Color mapping: Use hex values for accuracy
2. Nested clusters: Support 2 levels, extendable
3. Position preservation: Let GraphViz optimize (no position constraints)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape


@dataclass
class GraphVizConfig:
    """Configuration for GraphViz generator."""

    direction: Optional[str] = None  # LR, TB, RL, BT (None = auto-detect)
    graph_type: str = "digraph"  # digraph or graph
    use_clusters: bool = True
    cluster_prefix: str = "cluster_"
    node_shape_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default node shape mappings."""
        if not self.node_shape_map:
            self.node_shape_map = {
                SemanticType.COMPONENT.value: "box",
                SemanticType.SYSTEM.value: "box3d",
                SemanticType.DATABASE.value: "cylinder",
                SemanticType.PERSON.value: "ellipse",
                SemanticType.QUEUE.value: "folder",
                SemanticType.CONTAINER.value: "component",
                SemanticType.SERVICE.value: "box",
                SemanticType.DECISION.value: "diamond",
                SemanticType.EXTERNAL.value: "octagon",
                SemanticType.STORAGE.value: "cylinder",
                SemanticType.CLOUD.value: "cloud",
            }


class GraphVizGenerator(Generator):
    """Generate GraphViz DOT from IR."""

    def __init__(self, config: Optional[GraphVizConfig] = None):
        """Initialize generator.

        Args:
            config: GraphViz configuration or None for defaults
        """
        self.config = config or GraphVizConfig()

    def generate(self, diagram: Diagram) -> str:
        """Generate DOT file from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            GraphViz DOT string
        """
        lines = []

        # Determine direction
        direction = self.config.direction or self._detect_direction(diagram)

        # Header
        graph_type = self.config.graph_type
        lines.append(f'{graph_type} "{diagram.name or "diagram"}" {{')

        # Graph attributes
        if direction:
            lines.append(f'    rankdir="{direction}";')

        lines.append('    node [fontname="Helvetica"];')
        lines.append('    edge [fontname="Helvetica"];')
        lines.append("")

        # Process groups as clusters
        groups = diagram.get_groups()
        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        if self.config.use_clusters and groups:
            self._write_clusters(groups, shapes, lines, depth=1)
            lines.append("")

        # Process standalone nodes (not in clusters)
        standalone_shapes = self._get_standalone_shapes(shapes, groups)
        for shape in standalone_shapes:
            lines.append(self._format_node(shape))

        if standalone_shapes:
            lines.append("")

        # Process connections
        for conn in connections:
            lines.append(self._format_edge(conn))

        # Footer
        lines.append("}")

        return "\n".join(lines)

    def _detect_direction(self, diagram: Diagram) -> str:
        """Auto-detect optimal rankdir based on diagram layout.

        Returns LR (horizontal) or TB (vertical) based on aspect ratio.
        """
        shapes = diagram.get_shapes()
        if not shapes:
            return "LR"  # Default

        # Calculate bounding box
        min_x = min(s.position.x for s in shapes)
        max_x = max(s.position.x + s.size.width for s in shapes)
        min_y = min(s.position.y for s in shapes)
        max_y = max(s.position.y + s.size.height for s in shapes)

        width = max_x - min_x
        height = max_y - min_y

        # If significantly wider than tall, use LR
        if width > height * 1.5:
            return "LR"
        # If significantly taller than wide, use TB
        elif height > width * 1.5:
            return "TB"

        return "LR"  # Default horizontal

    def _get_standalone_shapes(
        self, shapes: list[Shape], groups: list[Group]
    ) -> list[Shape]:
        """Get shapes that are not in any group and haven't become groups."""
        grouped_ids = set()
        for group in groups:
            grouped_ids.update(group.children)

        group_source_ids = {g.id.removeprefix("group-") for g in groups}
        return [s for s in shapes if s.id not in grouped_ids and s.id not in group_source_ids]

    def _write_clusters(
        self, groups: list[Group], all_shapes: list[Shape], lines: list[str], depth: int
    ) -> None:
        """Write clusters (subgraphs) for groups."""
        if depth > 2:  # Max 2 levels of nesting
            return

        indent = "    " * depth

        for group in groups:
            cluster_id = self._sanitize_id(group.id)
            label = self._escape_label(group.label or cluster_id)

            lines.append(
                f'{indent}subgraph {self.config.cluster_prefix}{cluster_id} {{'
            )
            lines.append(f'{indent}    label="{label}";')

            # Add child nodes
            for child_id in group.children:
                child = next((s for s in all_shapes if s.id == child_id), None)
                if child:
                    node_line = self._format_node(child, indent=indent + "    ")
                    lines.append(node_line)

            lines.append(f"{indent}}}")

    def _format_node(self, shape: Shape, indent: str = "    ") -> str:
        """Format a GraphViz node."""
        node_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or node_id)

        # Determine node shape
        node_shape = self._get_node_shape(shape)

        # Build attribute list
        attrs = [f'label="{label}"']

        if node_shape != "box":  # box is default
            attrs.append(f'shape="{node_shape}"')

        # Add styling
        if shape.style.fill_color:
            attrs.append(f'fillcolor="{shape.style.fill_color}"')
            attrs.append('style="filled"')

        if shape.style.stroke_color:
            attrs.append(f'color="{shape.style.stroke_color}"')

        if shape.style.stroke_width:
            attrs.append(f'penwidth="{shape.style.stroke_width}"')

        # Join attributes
        attr_str = ", ".join(attrs)
        return f"{indent}{node_id} [{attr_str}];"

    def _get_node_shape(self, shape: Shape) -> str:
        """Get GraphViz node shape based on semantic or geometric type."""
        # Check semantic type first
        if shape.semantic_type and shape.semantic_type in self.config.node_shape_map:
            return self.config.node_shape_map[shape.semantic_type]

        # Fallback to geometric shape
        shape_map = {
            "rectangle": "box",
            "ellipse": "ellipse",
            "diamond": "diamond",
            "circle": "circle",
        }

        return shape_map.get(shape.shape_type, "box")

    def _format_edge(self, conn: Connection) -> str:
        """Format a GraphViz edge."""
        from_id = self._sanitize_id(conn.from_id)
        to_id = self._sanitize_id(conn.to_id)

        # Determine arrow type
        dir_attr = None
        if self.config.graph_type == "graph":  # Undirected
            arrow = "--"
        elif conn.connection_type == "bidirectional":
            arrow = "->"
            dir_attr = 'dir="both"'
        else:
            arrow = "->"

        # Build attribute list
        attrs = []

        if conn.label:
            label = self._escape_label(conn.label)
            attrs.append(f'label="{label}"')

        if conn.style.stroke_style == "dashed":
            attrs.append('style="dashed"')

        if conn.style.stroke_color:
            attrs.append(f'color="{conn.style.stroke_color}"')

        if conn.style.stroke_width:
            attrs.append(f'penwidth="{conn.style.stroke_width}"')

        if dir_attr:
            attrs.append(dir_attr)

        # Format edge
        if attrs:
            attr_str = ", ".join(attrs)
            return f"    {from_id} {arrow} {to_id} [{attr_str}];"

        return f"    {from_id} {arrow} {to_id};"

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize ID for DOT format."""
        # Replace invalid characters
        sanitized = id_str.replace("-", "_").replace(":", "_").replace(" ", "_")

        # Ensure starts with letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == "_"):
            sanitized = "n_" + sanitized

        return sanitized or "node"

    def _escape_label(self, label: str) -> str:
        """Escape label for DOT format."""
        # Escape backslashes and quotes
        return label.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
