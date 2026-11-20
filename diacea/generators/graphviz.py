"""GraphViz DOT generator - converts IR to GraphViz DOT format.

Supports directed/undirected graphs with clusters and auto-layout.

Design decisions (from Phase 3 open questions):
1. Color mapping: Use hex values for accuracy
2. Nested clusters: Support 2 levels, extendable
3. Position preservation: Let GraphViz optimize (no position constraints)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape
from ._text import Containers, canonical_shape, top_level_groups, visual_semantic

_DOT_SHAPES = {
    'circle': 'circle',
    'cloud': 'cloud',
    'cylinder': 'cylinder',
    'diamond': 'diamond',
    'document': 'note',
    'ellipse': 'ellipse',
    'hexagon': 'hexagon',
    'parallelogram': 'parallelogram',
    'person': 'ellipse',
    'queue': 'folder',
    'rectangle': 'box',
    'rounded_rectangle': 'box',
    'stadium': 'box',
}


@dataclass
class GraphVizConfig:
    """Configuration for GraphViz generator."""

    direction: str | None = None  # LR, TB, RL, BT (None = auto-detect)
    graph_type: str = 'digraph'  # digraph or graph
    use_clusters: bool = True
    cluster_prefix: str = 'cluster_'
    max_cluster_depth: int = 4
    node_shape_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default node shape mappings."""
        if not self.node_shape_map:
            self.node_shape_map = {
                SemanticType.COMPONENT: 'box',
                SemanticType.SYSTEM: 'box3d',
                SemanticType.DATABASE: 'cylinder',
                SemanticType.PERSON: 'ellipse',
                SemanticType.QUEUE: 'folder',
                SemanticType.CONTAINER: 'component',
                SemanticType.SERVICE: 'box',
                SemanticType.DECISION: 'diamond',
                SemanticType.EXTERNAL: 'octagon',
                SemanticType.STORAGE: 'cylinder',
                SemanticType.CLOUD: 'cloud',
            }


class GraphVizGenerator(Generator):
    """Generate GraphViz DOT from IR."""

    def __init__(self, config: GraphVizConfig | None = None) -> None:
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
        self._diagram = diagram

        # Determine direction
        direction = (
            self.config.direction
            or diagram.direction
            or ('TB' if diagram.metadata.get('synthesized_layout') else self._detect_direction(diagram))
        )

        # Header
        graph_type = self.config.graph_type
        lines.append(f'{graph_type} "{diagram.name or "diagram"}" {{')

        # Graph attributes
        if direction:
            lines.append(f'    rankdir="{direction}";')

        lines.extend(('    node [shape="box", fontname="Helvetica"];', '    edge [fontname="Helvetica"];', ''))

        # Process groups as clusters
        groups = diagram.get_groups()
        shapes = diagram.get_shapes()
        connections = diagram.get_connections()

        if self.config.use_clusters and groups:
            shapes_by_id = {s.id: s for s in shapes}
            groups_by_id = {g.id: g for g in groups}
            for group in top_level_groups(groups):
                self._write_cluster(group, shapes_by_id, groups_by_id, lines, depth=1)
            lines.append('')

        # Process standalone nodes (not in clusters)
        standalone_shapes = self._get_standalone_shapes(shapes, groups)
        lines.extend(self._format_node(shape) for shape in standalone_shapes)

        if standalone_shapes:
            lines.append('')

        # Process connections
        self._containers = Containers(diagram)
        edge_lines = [line for conn in connections if (line := self._format_edge(conn)) is not None]
        if any('lhead=' in line or 'ltail=' in line for line in edge_lines):
            lines.insert(1, '    compound=true;')
        lines.extend(edge_lines)

        # Footer
        lines.append('}')

        return '\n'.join(lines)

    def _detect_direction(self, diagram: Diagram) -> str:
        """Auto-detect optimal rankdir based on diagram layout.

        Returns LR (horizontal) or TB (vertical) based on aspect ratio.
        """
        shapes = diagram.get_shapes()
        if not shapes:
            return 'LR'  # Default

        # Calculate bounding box
        min_x = min(s.position.x for s in shapes)
        max_x = max(s.position.x + s.size.width for s in shapes)
        min_y = min(s.position.y for s in shapes)
        max_y = max(s.position.y + s.size.height for s in shapes)

        width = max_x - min_x
        height = max_y - min_y

        # If significantly wider than tall, use LR
        if width > height * 1.5:
            return 'LR'
        # If significantly taller than wide, use TB
        if height > width * 1.5:
            return 'TB'

        return 'LR'  # Default horizontal

    def _get_standalone_shapes(self, shapes: list[Shape], groups: list[Group]) -> list[Shape]:
        """Get shapes that are not in any group and haven't become groups."""
        grouped_ids = set()
        for group in groups:
            grouped_ids.update(group.children)

        group_source_ids = {g.source_shape_id for g in groups}
        return [s for s in shapes if s.id not in grouped_ids and s.id not in group_source_ids]

    def _write_cluster(
        self,
        group: Group,
        shapes_by_id: dict[str, Shape],
        groups_by_id: dict[str, Group],
        lines: list[str],
        depth: int,
    ) -> None:
        """Write a cluster (subgraph) for a group, recursing into child groups."""
        if depth > self.config.max_cluster_depth:
            warnings.warn(
                f'group {group.id!r} exceeds max cluster depth {self.config.max_cluster_depth}; truncating',
                stacklevel=2,
            )
            return

        indent = '    ' * depth
        cluster_id = self._sanitize_id(group.id)
        label = self._escape_label(group.label or cluster_id)

        lines.extend(
            (f'{indent}subgraph {self.config.cluster_prefix}{cluster_id} {{', f'{indent}    label="{label}";')
        )

        for child_id in group.children:
            child_group = groups_by_id.get(child_id)
            if child_group:
                self._write_cluster(child_group, shapes_by_id, groups_by_id, lines, depth + 1)
                continue
            child = shapes_by_id.get(child_id)
            if child:
                lines.append(self._format_node(child, indent=indent + '    '))

        lines.append(f'{indent}}}')

    def _format_node(self, shape: Shape, indent: str = '    ') -> str:
        """Format a GraphViz node."""
        node_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or node_id)

        # Determine node shape
        node_shape = self._get_node_shape(shape)

        # Build attribute list
        attrs = [f'label="{label}"']

        if node_shape != 'box':  # box is default
            attrs.append(f'shape="{node_shape}"')

        # Add styling
        if shape.style.fill_color:
            attrs.extend((f'fillcolor="{shape.style.fill_color}"', 'style="filled"'))

        if shape.style.stroke_color:
            attrs.append(f'color="{shape.style.stroke_color}"')

        if shape.style.stroke_width:
            attrs.append(f'penwidth="{shape.style.stroke_width}"')

        # Join attributes
        attr_str = ', '.join(attrs)
        return f'{indent}{node_id} [{attr_str}];'

    def _get_node_shape(self, shape: Shape) -> str:
        """Get GraphViz node shape based on semantic or geometric type."""
        semantic = visual_semantic(shape, self._diagram)
        if semantic in self.config.node_shape_map:
            return self.config.node_shape_map[semantic]
        return _DOT_SHAPES.get(canonical_shape(shape.shape_type), 'box')

    def _cluster_endpoint(self, endpoint_id: str, other_id: str) -> tuple[str, str | None] | None:
        """Resolve an endpoint to (node id, cluster name); None when a cluster has no usable node.

        DOT edges join nodes, so an edge to a cluster attaches to a node
        inside it and is clipped at the cluster border with lhead/ltail.
        """
        group = self._containers.group_for(endpoint_id) if self.config.use_clusters else None
        if group is None:
            return (self._sanitize_id(endpoint_id), None)
        anchors = [leaf for leaf in self._containers.leaves(group) if leaf != other_id]
        if not anchors:
            return None
        return (self._sanitize_id(anchors[0]), f'{self.config.cluster_prefix}{self._sanitize_id(group.id)}')

    def _format_edge(self, conn: Connection) -> str | None:
        """Format a GraphViz edge, or None when it cannot be expressed in DOT."""
        source = self._cluster_endpoint(conn.from_id, conn.to_id)
        target = self._cluster_endpoint(conn.to_id, conn.from_id)
        if source is None or target is None or self._containers.links_container_to_own_content(conn):
            warnings.warn(
                f'Dropping connection between container and its own content: {conn.from_id} -> {conn.to_id}',
                stacklevel=2,
            )
            return None
        from_id, ltail = source
        to_id, lhead = target

        # Determine arrow type
        dir_attr = None
        if self.config.graph_type == 'graph':  # Undirected
            arrow = '--'
        elif conn.connection_type == 'bidirectional':
            arrow = '->'
            dir_attr = 'dir="both"'
        elif conn.connection_type == 'undirected':
            arrow = '->'
            dir_attr = 'dir="none"'
        else:
            arrow = '->'

        # Build attribute list
        attrs = []

        if conn.label:
            label = self._escape_label(conn.label)
            attrs.append(f'label="{label}"')

        if conn.style.stroke_style in {'dashed', 'dotted'}:
            attrs.append(f'style="{conn.style.stroke_style}"')

        if conn.style.stroke_color:
            attrs.append(f'color="{conn.style.stroke_color}"')

        if conn.style.stroke_width:
            attrs.append(f'penwidth="{conn.style.stroke_width}"')

        if dir_attr:
            attrs.append(dir_attr)

        if ltail:
            attrs.append(f'ltail="{ltail}"')
        if lhead:
            attrs.append(f'lhead="{lhead}"')

        # Format edge
        if attrs:
            attr_str = ', '.join(attrs)
            return f'    {from_id} {arrow} {to_id} [{attr_str}];'

        return f'    {from_id} {arrow} {to_id};'

    def _sanitize_id(self, id_str: str) -> str:
        """Sanitize ID for DOT format."""
        # Replace invalid characters
        sanitized = id_str.replace('-', '_').replace(':', '_').replace(' ', '_')

        # Ensure starts with letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
            sanitized = 'n_' + sanitized

        return sanitized or 'node'

    def _escape_label(self, label: str) -> str:
        """Escape label for DOT format."""
        # Escape backslashes and quotes
        return label.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
