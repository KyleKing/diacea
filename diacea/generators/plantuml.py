"""PlantUML generators - converts IR to PlantUML formats."""

from __future__ import annotations

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape
from ._text import sanitize_alnum_id, top_level_groups


def _escape_plantuml_label(label: str) -> str:
    escaped = label.replace('\\', '\\\\')
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n')
    escaped = escaped.replace('<', '~<')
    escaped = escaped.replace('>', '~>')
    return escaped.replace('&', '&amp;')


class PlantUMLGenerator(Generator):
    """Generate basic PlantUML from IR."""

    def generate(self, diagram: Diagram) -> str:
        """Generate PlantUML diagram from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            PlantUML string
        """
        lines = ['@startuml']

        # Get elements
        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        group_source_ids = {g.source_shape_id for g in groups}
        child_ids = {child_id for g in groups for child_id in g.children}
        for shape in shapes:
            if shape.id in child_ids or shape.id in group_source_ids:
                continue
            lines.append(self._generate_shape(shape))

        shapes_by_id = {s.id: s for s in shapes}
        groups_by_id = {g.id: g for g in groups}
        for group in top_level_groups(groups):
            lines.extend(self._generate_group(group, shapes_by_id, groups_by_id, depth=0))

        # Generate connections
        lines.extend(self._generate_connection(conn) for conn in connections)

        lines.append('@enduml')
        return '\n'.join(lines)

    def _generate_shape(self, shape: Shape) -> str:
        """Generate PlantUML for a shape."""
        plantuml_type = self._map_shape_type(shape)
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or safe_id)
        return f'{plantuml_type} "{label}" as {safe_id}'

    def _generate_group(
        self,
        group: Group,
        shapes_by_id: dict[str, Shape],
        groups_by_id: dict[str, Group],
        depth: int,
    ) -> list[str]:
        """Generate PlantUML rectangle for a group, recursing into child groups."""
        indent = '  ' * depth
        safe_id = self._sanitize_id(group.id)
        label = self._escape_label(group.label or safe_id)
        lines = [f'{indent}rectangle "{label}" as {safe_id} {{']

        for child_id in group.children:
            child_group = groups_by_id.get(child_id)
            if child_group:
                lines.extend(self._generate_group(child_group, shapes_by_id, groups_by_id, depth + 1))
                continue
            child_shape = shapes_by_id.get(child_id)
            if child_shape:
                lines.append(f'{indent}  {self._generate_shape(child_shape)}')

        lines.append(f'{indent}}}')
        return lines

    def _generate_connection(self, conn: Connection) -> str:
        """Generate PlantUML arrow."""
        from_id = self._sanitize_id(conn.from_id)
        to_id = self._sanitize_id(conn.to_id)

        # Determine arrow type
        arrow = '<-->' if conn.connection_type == 'bidirectional' else '-->'

        if conn.label:
            label = self._escape_label(conn.label)
            return f'{from_id} {arrow} {to_id} : "{label}"'
        return f'{from_id} {arrow} {to_id}'

    def _map_shape_type(self, shape: Shape) -> str:
        """Map IR shape type to PlantUML type."""
        # Use semantic type if available
        if shape.semantic_type:
            semantic = shape.semantic_type
            if semantic == SemanticType.DATABASE:
                return 'database'
            if semantic == SemanticType.QUEUE:
                return 'queue'
            if semantic == SemanticType.STORAGE:
                return 'storage'
            if semantic == SemanticType.CLOUD:
                return 'cloud'

        # Fallback to geometric shape
        shape_map = {
            'rectangle': 'rectangle',
            'ellipse': 'actor',  # PlantUML uses 'actor' for people
            'diamond': 'hexagon',
        }
        return shape_map.get(shape.shape_type, 'rectangle')

    _sanitize_id = staticmethod(sanitize_alnum_id)
    _escape_label = staticmethod(_escape_plantuml_label)


class C4PlantUMLGenerator(Generator):
    """Generate C4-PlantUML from IR."""

    def generate(self, diagram: Diagram) -> str:
        """Generate C4-PlantUML diagram from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            C4-PlantUML string
        """
        lines = [
            '@startuml',
            '!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml',
            '',
            'LAYOUT_WITH_LEGEND()',
            '',
        ]

        # Get elements
        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        systems = []
        containers = []
        components = []
        databases = []
        people = []

        group_source_ids = {g.source_shape_id for g in groups}
        child_ids = {child_id for g in groups for child_id in g.children}
        for shape in shapes:
            if shape.id in child_ids or shape.id in group_source_ids:
                continue
            semantic = shape.semantic_type
            if semantic == SemanticType.SYSTEM:
                systems.append(shape)
            elif semantic == SemanticType.CONTAINER:
                containers.append(shape)
            elif semantic == SemanticType.COMPONENT:
                components.append(shape)
            elif semantic == SemanticType.DATABASE:
                databases.append(shape)
            elif semantic == SemanticType.PERSON:
                people.append(shape)
            else:
                # Default to container for unknown types
                containers.append(shape)

        # Generate people
        lines.extend(self._generate_person(person) for person in people)

        # Generate systems
        lines.extend(self._generate_system(system) for system in systems)

        # Generate containers
        lines.extend(self._generate_container(container) for container in containers)

        # Generate components
        lines.extend(self._generate_component(component) for component in components)

        # Generate databases
        lines.extend(self._generate_database(database) for database in databases)

        lines.append('')

        # Generate groups as system boundaries
        shapes_by_id = {s.id: s for s in shapes}
        groups_by_id = {g.id: g for g in groups}
        declared_ids = {s.id for s in shapes if s.id not in child_ids and s.id not in group_source_ids}
        for group in top_level_groups(groups):
            lines.extend(self._generate_boundary(group, shapes_by_id, groups_by_id, declared_ids, depth=0))

        lines.append('')

        # Generate relationships; endpoints naming a suppressed container shape
        # remap to that group's declared boundary alias
        boundary_alias_by_source = {g.source_shape_id: g.id for g in groups}
        lines.extend(self._generate_relationship(conn, boundary_alias_by_source) for conn in connections)

        lines.append('@enduml')
        return '\n'.join(lines)

    def _generate_person(self, shape: Shape) -> str:
        """Generate C4 Person element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or safe_id)
        return f'Person({safe_id}, "{label}")'

    def _generate_system(self, shape: Shape) -> str:
        """Generate C4 System element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or safe_id)
        return f'System({safe_id}, "{label}")'

    def _generate_container(self, shape: Shape) -> str:
        """Generate C4 Container element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or safe_id)
        tech = shape.metadata.get('technology', '')
        if tech:
            tech = self._escape_label(tech)
            return f'Container({safe_id}, "{label}", "{tech}")'
        return f'Container({safe_id}, "{label}")'

    def _generate_component(self, shape: Shape) -> str:
        """Generate C4 Component element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or safe_id)
        return f'Component({safe_id}, "{label}")'

    def _generate_database(self, shape: Shape) -> str:
        """Generate C4 Database element."""
        safe_id = self._sanitize_id(shape.id)
        raw_label = shape.label or safe_id
        label = self._escape_label(raw_label)
        label_lower = raw_label.lower()
        tech = ''
        if 'postgres' in label_lower:
            tech = 'PostgreSQL'
        elif 'mysql' in label_lower:
            tech = 'MySQL'
        elif 'mongodb' in label_lower or 'mongo' in label_lower:
            tech = 'MongoDB'
        elif 'redis' in label_lower:
            tech = 'Redis'

        if tech:
            return f'ComponentDb({safe_id}, "{label}", "{tech}")'
        return f'ComponentDb({safe_id}, "{label}")'

    def _generate_boundary(
        self,
        group: Group,
        shapes_by_id: dict[str, Shape],
        groups_by_id: dict[str, Group],
        declared_ids: set[str],
        depth: int,
    ) -> list[str]:
        """Generate C4 System_Boundary for a group, recursing into child groups."""
        indent = '  ' * depth
        safe_id = self._sanitize_id(group.id)
        label = self._escape_label(group.label or self._sanitize_id(group.source_shape_id))
        lines = [f'{indent}System_Boundary({safe_id}, "{label}") {{']

        for child_id in group.children:
            child_group = groups_by_id.get(child_id)
            if child_group:
                lines.extend(self._generate_boundary(child_group, shapes_by_id, groups_by_id, declared_ids, depth + 1))
                continue
            child_shape = shapes_by_id.get(child_id)
            if child_shape and child_shape.id not in declared_ids:
                declared_ids.add(child_shape.id)
                lines.append(f'{indent}  {self._generate_boundary_element(child_shape)}')

        lines.append(f'{indent}}}')
        return lines

    def _generate_boundary_element(self, shape: Shape) -> str:
        semantic = shape.semantic_type
        if semantic == SemanticType.COMPONENT:
            return self._generate_component(shape)
        if semantic == SemanticType.DATABASE:
            return self._generate_database(shape)
        if semantic == SemanticType.PERSON:
            return self._generate_person(shape)
        if semantic == SemanticType.SYSTEM:
            return self._generate_system(shape)
        return self._generate_container(shape)

    def _generate_relationship(self, conn: Connection, boundary_alias_by_source: dict[str, str]) -> str:
        """Generate C4 Rel (relationship)."""
        from_id = self._sanitize_id(boundary_alias_by_source.get(conn.from_id, conn.from_id))
        to_id = self._sanitize_id(boundary_alias_by_source.get(conn.to_id, conn.to_id))
        label = self._escape_label(conn.label or 'uses')
        return f'Rel({from_id}, {to_id}, "{label}")'

    _sanitize_id = staticmethod(sanitize_alnum_id)
    _escape_label = staticmethod(_escape_plantuml_label)
