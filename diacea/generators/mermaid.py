"""Mermaid generator - converts IR to Mermaid diagram formats.

Supports flowchart, C4, and sequence diagrams with auto-detection.

Design decisions (from Phase 2 open questions):
1. Default diagram type: Auto-detect from structure, fallback to flowchart
2. Style preservation: Basic colors only (fill, stroke)
3. Subgraph depth: Max 3 levels to avoid visual complexity
"""

from __future__ import annotations

from typing import Optional

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape
from ._text import sanitize_alnum_id

_C4_BOUNDARY_KEYWORDS = {
    SemanticType.COMPONENT: "Component",
    SemanticType.CONTAINER: "Container",
    SemanticType.DATABASE: "ContainerDb",
    SemanticType.PERSON: "Person",
    SemanticType.QUEUE: "ContainerQueue",
    SemanticType.STORAGE: "ContainerDb",
    SemanticType.SYSTEM: "System",
}

_C4_TOP_LEVEL_KEYWORDS = {
    SemanticType.COMPONENT: "Component",
    SemanticType.CONTAINER: "Container",
    SemanticType.DATABASE: "SystemDb",
    SemanticType.PERSON: "Person",
    SemanticType.QUEUE: "SystemQueue",
    SemanticType.STORAGE: "SystemDb",
    SemanticType.SYSTEM: "System",
}

_LABEL_CHARS_REQUIRING_QUOTES = frozenset('"()[]{}|')


class MermaidGenerator(Generator):
    """Generate Mermaid diagrams from IR with auto-detection."""

    def __init__(self, diagram_type: Optional[str] = None):
        """Initialize generator.

        Args:
            diagram_type: Force specific type ('flowchart', 'c4', 'sequence')
                         or None for auto-detection
        """
        self.diagram_type = diagram_type
        self.detected_type: Optional[str] = None
        self.max_subgraph_depth = 3

    def generate(self, diagram: Diagram) -> str:
        """Generate Mermaid diagram from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            Mermaid diagram string
        """
        # Auto-detect diagram type if not specified
        diagram_type = self.diagram_type or self._detect_diagram_type(diagram)
        self.detected_type = diagram_type

        if diagram_type == "c4":
            return self._generate_c4(diagram)
        elif diagram_type == "sequence":
            return self._generate_sequence(diagram)
        else:  # flowchart (default)
            return self._generate_flowchart(diagram)

    def _detect_diagram_type(self, diagram: Diagram) -> str:
        """Auto-detect best Mermaid diagram type.

        Detection logic:
        - If has Person/System/Container semantic types → C4
        - If connections form sequential flow → Sequence
        - Default → Flowchart
        """
        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        # Check for C4 semantic types
        c4_types = {
            SemanticType.PERSON,
            SemanticType.SYSTEM,
            SemanticType.CONTAINER,
            SemanticType.COMPONENT,
        }

        semantic_types = {s.semantic_type for s in shapes if s.semantic_type}

        if semantic_types & c4_types:  # Intersection
            return "c4"

        # Check for sequential pattern (each shape has at most one out connection)
        # This is a simple heuristic - could be improved
        out_counts = {}
        for conn in connections:
            out_counts[conn.from_id] = out_counts.get(conn.from_id, 0) + 1

        if connections and all(count <= 1 for count in out_counts.values()):
            return "sequence"

        # Default to flowchart
        return "flowchart"

    def _generate_flowchart(self, diagram: Diagram) -> str:
        """Generate Mermaid flowchart."""
        lines = ["flowchart LR"]  # Left-to-right by default

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        group_source_ids = {g.source_shape_id for g in groups}
        top_level_shapes = [
            s for s in shapes
            if not any(s.id in g.children for g in groups)
            and s.id not in group_source_ids
        ]

        for shape in top_level_shapes:
            lines.append(self._format_flowchart_node(shape))

        # Generate subgraphs (groups)
        for group in groups:
            subgraph_lines = self._generate_subgraph(group, shapes, depth=1)
            lines.extend(subgraph_lines)

        # Generate connections
        for conn in connections:
            lines.append(self._format_flowchart_connection(conn))

        # Add styling (basic colors)
        style_lines = self._generate_flowchart_styles(shapes)
        if style_lines:
            lines.append("")
            lines.extend(style_lines)

        return "\n".join(lines)

    def _format_flowchart_node(self, shape: Shape) -> str:
        """Format a Mermaid flowchart node."""
        node_id = self._sanitize_id(shape.id)
        label = self._format_bracket_label(shape.label or node_id)
        brackets = self._get_node_brackets(shape)
        return f"    {node_id}{brackets[0]}{label}{brackets[1]}"

    def _format_bracket_label(self, label: str) -> str:
        escaped = self._escape_label(label)
        if _LABEL_CHARS_REQUIRING_QUOTES & set(label):
            return f'"{escaped}"'
        return escaped

    def _get_node_brackets(self, shape: Shape) -> tuple[str, str]:
        """Get Mermaid node brackets based on shape type.

        Returns tuple of (opening, closing) brackets.
        """
        # Check semantic type first
        if shape.semantic_type:
            semantic = shape.semantic_type
            if semantic == SemanticType.DECISION:
                return ("{", "}")  # Diamond
            elif semantic == SemanticType.DATABASE:
                return ("[(", ")]")  # Cylindrical
            elif semantic == SemanticType.PERSON:
                return ("([", "])")  # Stadium/rounded
            elif semantic == SemanticType.START_END:
                return ("([", "])")  # Stadium

        # Fall back to geometric shape
        shape_map = {
            "rectangle": ("[", "]"),
            "ellipse": ("([", "])"),
            "diamond": ("{", "}"),
            "circle": ("((", "))"),
        }

        return shape_map.get(shape.shape_type, ("[", "]"))  # Default rectangle

    def _format_flowchart_connection(self, conn: Connection) -> str:
        """Format a Mermaid flowchart connection."""
        from_id = self._sanitize_id(conn.from_id)
        to_id = self._sanitize_id(conn.to_id)

        # Determine arrow style
        if conn.connection_type == "bidirectional":
            arrow = "<-->"
        elif conn.style.stroke_style == "dashed":
            arrow = "-.."
        else:
            arrow = "-->"

        if conn.label:
            label = self._escape_pipe_label(conn.label)
            return f"    {from_id} {arrow}|{label}| {to_id}"
        return f"    {from_id} {arrow} {to_id}"

    def _generate_subgraph(
        self, group: Group, all_shapes: list[Shape], depth: int
    ) -> list[str]:
        """Generate Mermaid subgraph for a group."""
        if depth > self.max_subgraph_depth:
            return []  # Skip too deeply nested groups

        lines = []
        indent = "    " * depth
        subgraph_id = self._sanitize_id(group.id)
        label = self._format_bracket_label(group.label or subgraph_id)
        lines.append(f"{indent}subgraph {subgraph_id}[{label}]")

        # Add child shapes
        for child_id in group.children:
            child_shape = next((s for s in all_shapes if s.id == child_id), None)
            if child_shape:
                node_line = self._format_flowchart_node(child_shape)
                lines.append(indent + node_line)

        lines.append(f"{indent}end")
        return lines

    def _generate_flowchart_styles(self, shapes: list[Shape]) -> list[str]:
        """Generate Mermaid style definitions for shapes."""
        lines = []

        for shape in shapes:
            if not shape.style.fill_color and not shape.style.stroke_color:
                continue  # No custom styling

            node_id = self._sanitize_id(shape.id)
            style_parts = []

            if shape.style.fill_color:
                style_parts.append(f"fill:{shape.style.fill_color}")

            if shape.style.stroke_color:
                style_parts.append(f"stroke:{shape.style.stroke_color}")

            if style_parts:
                style_str = ",".join(style_parts)
                lines.append(f"    style {node_id} {style_str}")

        return lines

    def _generate_c4(self, diagram: Diagram) -> str:
        """Generate Mermaid C4 diagram."""
        lines = ["C4Context"]  # Start with Context level
        lines.append("    title " + (diagram.name or "Architecture Diagram"))

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        group_source_ids = {g.source_shape_id for g in groups}
        child_ids = {cid for g in groups for cid in g.children}
        declared_ids: set[str] = set()

        for shape in shapes:
            if shape.id in child_ids or shape.id in group_source_ids:
                continue
            if shape.id in declared_ids:
                continue
            lines.append(self._format_c4_element(shape, in_boundary=False))
            declared_ids.add(shape.id)

        for group in groups:
            label = self._escape_quoted_label(group.label or "System")
            boundary_id = self._sanitize_id(group.id)
            lines.append(f'    Boundary({boundary_id}, "{label}") {{')

            for child_id in group.children:
                child = next((s for s in shapes if s.id == child_id), None)
                if child and child.id not in declared_ids:
                    lines.append(self._format_c4_element(child, in_boundary=True))
                    declared_ids.add(child.id)

            lines.append("    }")

        for shape in shapes:
            if shape.id in declared_ids or shape.id in group_source_ids:
                continue
            lines.append(self._format_c4_element(shape, in_boundary=False))
            declared_ids.add(shape.id)

        for conn in connections:
            from_id = self._sanitize_id(conn.from_id)
            to_id = self._sanitize_id(conn.to_id)
            label = self._escape_quoted_label(conn.label or "uses")
            lines.append(f'    Rel({from_id}, {to_id}, "{label}")')

        return "\n".join(lines)

    def _format_c4_element(self, shape: Shape, in_boundary: bool) -> str:
        keywords = _C4_BOUNDARY_KEYWORDS if in_boundary else _C4_TOP_LEVEL_KEYWORDS
        default = "Container" if in_boundary else "System"
        keyword = keywords.get(shape.semantic_type, default)
        node_id = self._sanitize_id(shape.id)
        label = self._escape_quoted_label(shape.label or node_id)
        indent = "        " if in_boundary else "    "
        return f'{indent}{keyword}({node_id}, "{label}")'

    def _generate_sequence(self, diagram: Diagram) -> str:
        """Generate Mermaid sequence diagram."""
        lines = ["sequenceDiagram"]

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        for shape in shapes:
            participant_id = self._sanitize_id(shape.id)
            label = self._escape_label(shape.label or participant_id)
            lines.append(f"    participant {participant_id} as {label}")

        for conn in connections:
            from_id = self._sanitize_id(conn.from_id)
            to_id = self._sanitize_id(conn.to_id)

            if conn.connection_type == "bidirectional":
                arrow = "->>"
            elif conn.style.stroke_style == "dashed":
                arrow = "-->"
            else:
                arrow = "->>"

            label = self._escape_label(conn.label or "")
            lines.append(f"    {from_id}{arrow}{to_id}: {label}")

        return "\n".join(lines)

    _sanitize_id = staticmethod(sanitize_alnum_id)

    def _escape_label(self, label: str) -> str:
        """Escape label for Mermaid flowchart node syntax."""
        escaped = label.replace("&", "&amp;")
        escaped = escaped.replace('"', "#quot;")
        escaped = escaped.replace("<", "&lt;")
        escaped = escaped.replace(">", "&gt;")
        escaped = escaped.replace("\n", "<br/>")
        return escaped

    def _escape_quoted_label(self, label: str) -> str:
        """Escape label for Mermaid quoted string contexts (C4, sequence)."""
        escaped = label.replace("\\", "\\\\")
        escaped = escaped.replace('"', '\\"')
        escaped = escaped.replace("&", "&amp;")
        escaped = escaped.replace("<", "&lt;")
        escaped = escaped.replace(">", "&gt;")
        escaped = escaped.replace("\n", "<br/>")
        return escaped

    def _escape_pipe_label(self, label: str) -> str:
        """Escape label for Mermaid pipe-delimited connection labels."""
        escaped = label.replace("&", "&amp;")
        escaped = escaped.replace("|", "&#124;")
        escaped = escaped.replace("<", "&lt;")
        escaped = escaped.replace(">", "&gt;")
        escaped = escaped.replace("\n", "<br/>")
        return escaped
