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


class MermaidGenerator(Generator):
    """Generate Mermaid diagrams from IR with auto-detection."""

    def __init__(self, diagram_type: Optional[str] = None):
        """Initialize generator.

        Args:
            diagram_type: Force specific type ('flowchart', 'c4', 'sequence')
                         or None for auto-detection
        """
        self.diagram_type = diagram_type
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
            SemanticType.PERSON.value,
            SemanticType.SYSTEM.value,
            SemanticType.CONTAINER.value,
            SemanticType.COMPONENT.value,
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

        # Filter out shapes that are in groups (will be in subgraphs)
        top_level_shapes = [
            s for s in shapes if not any(s.id in g.children for g in groups)
        ]

        # Generate top-level shapes
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
        label = shape.label or node_id

        # Determine node shape based on semantic type or geometric shape
        brackets = self._get_node_brackets(shape)

        return f"    {node_id}{brackets[0]}{label}{brackets[1]}"

    def _get_node_brackets(self, shape: Shape) -> tuple[str, str]:
        """Get Mermaid node brackets based on shape type.

        Returns tuple of (opening, closing) brackets.
        """
        # Check semantic type first
        if shape.semantic_type:
            semantic = shape.semantic_type
            if semantic == SemanticType.DECISION.value:
                return ("{", "}")  # Diamond
            elif semantic == SemanticType.DATABASE.value:
                return ("[(", ")]")  # Cylindrical
            elif semantic == SemanticType.PERSON.value:
                return ("([", "])")  # Stadium/rounded
            elif semantic == SemanticType.START_END.value:
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

        # Add label if present
        if conn.label:
            label = conn.label.replace('"', "'")  # Escape quotes
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
        label = group.label or subgraph_id

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

        # Categorize by semantic type
        people = [s for s in shapes if s.semantic_type == SemanticType.PERSON.value]
        systems = [s for s in shapes if s.semantic_type == SemanticType.SYSTEM.value]
        containers = [
            s for s in shapes if s.semantic_type == SemanticType.CONTAINER.value
        ]
        components = [
            s for s in shapes if s.semantic_type == SemanticType.COMPONENT.value
        ]

        # Generate people
        for person in people:
            label = person.label or "Person"
            node_id = self._sanitize_id(person.id)
            lines.append(f"    Person({node_id}, \"{label}\")")

        # Generate systems
        for system in systems:
            label = system.label or "System"
            node_id = self._sanitize_id(system.id)
            lines.append(f"    System({node_id}, \"{label}\")")

        # Generate containers
        for container in containers:
            label = container.label or "Container"
            node_id = self._sanitize_id(container.id)
            lines.append(f"    Container({node_id}, \"{label}\")")

        # Generate components
        for component in components:
            label = component.label or "Component"
            node_id = self._sanitize_id(component.id)
            lines.append(f"    Component({node_id}, \"{label}\")")

        # Generate boundaries (groups)
        for group in groups:
            label = group.label or "System"
            boundary_id = self._sanitize_id(group.id)
            lines.append(f"    Boundary({boundary_id}, \"{label}\") {{")

            # Add children
            for child_id in group.children:
                child = next((s for s in shapes if s.id == child_id), None)
                if child:
                    child_node_id = self._sanitize_id(child.id)
                    child_label = child.label or child_node_id
                    lines.append(f"        Container({child_node_id}, \"{child_label}\")")

            lines.append("    }")

        # Generate relationships
        for conn in connections:
            from_id = self._sanitize_id(conn.from_id)
            to_id = self._sanitize_id(conn.to_id)
            label = conn.label or "uses"
            lines.append(f"    Rel({from_id}, {to_id}, \"{label}\")")

        return "\n".join(lines)

    def _generate_sequence(self, diagram: Diagram) -> str:
        """Generate Mermaid sequence diagram."""
        lines = ["sequenceDiagram"]

        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        # Declare participants
        for shape in shapes:
            participant_id = self._sanitize_id(shape.id)
            label = shape.label or participant_id
            lines.append(f"    participant {participant_id} as {label}")

        # Generate interactions (connections in order)
        for conn in connections:
            from_id = self._sanitize_id(conn.from_id)
            to_id = self._sanitize_id(conn.to_id)

            # Determine arrow type
            if conn.connection_type == "bidirectional":
                arrow = "->>"
            elif conn.style.stroke_style == "dashed":
                arrow = "-->"
            else:
                arrow = "->>"

            # Add message
            label = conn.label or ""
            lines.append(f"    {from_id}{arrow}{to_id}: {label}")

        return "\n".join(lines)

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize ID for Mermaid (alphanumeric and underscore)."""
        return "".join(c if c.isalnum() or c == "_" else "_" for c in id_str)
