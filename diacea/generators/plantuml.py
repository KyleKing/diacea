"""PlantUML generators - converts IR to PlantUML formats."""

from __future__ import annotations

from ..ir import Connection, Diagram, Generator, Group, SemanticType, Shape
from ._text import sanitize_alnum_id


def _escape_plantuml_label(label: str) -> str:
    escaped = label.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n")
    escaped = escaped.replace("<", "~<")
    escaped = escaped.replace(">", "~>")
    escaped = escaped.replace("&", "&amp;")
    return escaped


class PlantUMLGenerator(Generator):
    """Generate basic PlantUML from IR."""

    def generate(self, diagram: Diagram) -> str:
        """Generate PlantUML diagram from IR.

        Args:
            diagram: IR Diagram object

        Returns:
            PlantUML string
        """
        lines = ["@startuml"]

        # Get elements
        shapes = diagram.get_shapes()
        connections = diagram.get_connections()
        groups = diagram.get_groups()

        group_source_ids = {g.source_shape_id for g in groups}
        for shape in shapes:
            if any(shape.id in group.children for group in groups):
                continue
            if shape.id in group_source_ids:
                continue
            lines.append(self._generate_shape(shape))

        # Generate groups/packages
        for group in groups:
            lines.extend(self._generate_group(group, shapes))

        # Generate connections
        for conn in connections:
            lines.append(self._generate_connection(conn))

        lines.append("@enduml")
        return "\n".join(lines)

    def _generate_shape(self, shape: Shape) -> str:
        """Generate PlantUML for a shape."""
        plantuml_type = self._map_shape_type(shape)
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or safe_id)
        return f'{plantuml_type} "{label}" as {safe_id}'

    def _generate_group(self, group: Group, all_shapes: list[Shape]) -> list[str]:
        """Generate PlantUML package/rectangle for a group."""
        lines = []
        safe_id = self._sanitize_id(group.id)
        label = self._escape_label(group.label or safe_id)
        lines.append(f'rectangle "{label}" as {safe_id} {{')

        # Add child shapes
        for child_id in group.children:
            child_shape = next((s for s in all_shapes if s.id == child_id), None)
            if child_shape:
                lines.append(f"  {self._generate_shape(child_shape)}")

        lines.append("}")
        return lines

    def _generate_connection(self, conn: Connection) -> str:
        """Generate PlantUML arrow."""
        from_id = self._sanitize_id(conn.from_id)
        to_id = self._sanitize_id(conn.to_id)

        # Determine arrow type
        if conn.connection_type == "bidirectional":
            arrow = "<-->"
        else:
            arrow = "-->"

        if conn.label:
            label = self._escape_label(conn.label)
            return f'{from_id} {arrow} {to_id} : "{label}"'
        return f"{from_id} {arrow} {to_id}"

    def _map_shape_type(self, shape: Shape) -> str:
        """Map IR shape type to PlantUML type."""
        # Use semantic type if available
        if shape.semantic_type:
            semantic = shape.semantic_type
            if semantic == SemanticType.DATABASE:
                return "database"
            elif semantic == SemanticType.QUEUE:
                return "queue"
            elif semantic == SemanticType.STORAGE:
                return "storage"
            elif semantic == SemanticType.CLOUD:
                return "cloud"

        # Fallback to geometric shape
        shape_map = {
            "rectangle": "rectangle",
            "ellipse": "actor",  # PlantUML uses 'actor' for people
            "diamond": "hexagon",
        }
        return shape_map.get(shape.shape_type, "rectangle")

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
            "@startuml",
            "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml",
            "",
            "LAYOUT_WITH_LEGEND()",
            "",
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
        for shape in shapes:
            if any(shape.id in group.children for group in groups):
                continue
            if shape.id in group_source_ids:
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
        for person in people:
            lines.append(self._generate_person(person))

        # Generate systems
        for system in systems:
            lines.append(self._generate_system(system))

        # Generate containers
        for container in containers:
            lines.append(self._generate_container(container))

        # Generate components
        for component in components:
            lines.append(self._generate_component(component))

        # Generate databases
        for database in databases:
            lines.append(self._generate_database(database))

        lines.append("")

        # Generate groups as system boundaries
        for group in groups:
            lines.extend(self._generate_boundary(group, shapes))

        lines.append("")

        # Generate relationships
        for conn in connections:
            lines.append(self._generate_relationship(conn))

        lines.append("@enduml")
        return "\n".join(lines)

    def _generate_person(self, shape: Shape) -> str:
        """Generate C4 Person element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or "Person")
        return f'Person({safe_id}, "{label}")'

    def _generate_system(self, shape: Shape) -> str:
        """Generate C4 System element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or "System")
        return f'System({safe_id}, "{label}")'

    def _generate_container(self, shape: Shape) -> str:
        """Generate C4 Container element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or "Container")
        tech = shape.metadata.get("technology", "")
        if tech:
            tech = self._escape_label(tech)
            return f'Container({safe_id}, "{label}", "{tech}")'
        return f'Container({safe_id}, "{label}")'

    def _generate_component(self, shape: Shape) -> str:
        """Generate C4 Component element."""
        safe_id = self._sanitize_id(shape.id)
        label = self._escape_label(shape.label or "Component")
        return f'Component({safe_id}, "{label}")'

    def _generate_database(self, shape: Shape) -> str:
        """Generate C4 Database element."""
        safe_id = self._sanitize_id(shape.id)
        raw_label = shape.label or "Database"
        label = self._escape_label(raw_label)
        label_lower = raw_label.lower()
        tech = ""
        if "postgres" in label_lower:
            tech = "PostgreSQL"
        elif "mysql" in label_lower:
            tech = "MySQL"
        elif "mongodb" in label_lower or "mongo" in label_lower:
            tech = "MongoDB"
        elif "redis" in label_lower:
            tech = "Redis"

        if tech:
            return f'ComponentDb({safe_id}, "{label}", "{tech}")'
        return f'ComponentDb({safe_id}, "{label}")'

    def _generate_boundary(self, group: Group, all_shapes: list[Shape]) -> list[str]:
        """Generate C4 System_Boundary for a group."""
        lines = []
        safe_id = self._sanitize_id(group.id)
        label = self._escape_label(group.label or "System")
        lines.append(f'System_Boundary({safe_id}, "{label}") {{')

        # Add child elements
        for child_id in group.children:
            child_shape = next((s for s in all_shapes if s.id == child_id), None)
            if child_shape:
                semantic = child_shape.semantic_type
                if semantic == SemanticType.CONTAINER:
                    lines.append(f"  {self._generate_container(child_shape)}")
                elif semantic == SemanticType.COMPONENT:
                    lines.append(f"  {self._generate_component(child_shape)}")
                elif semantic == SemanticType.DATABASE:
                    lines.append(f"  {self._generate_database(child_shape)}")
                else:
                    # Default to container
                    lines.append(f"  {self._generate_container(child_shape)}")

        lines.append("}")
        return lines

    def _generate_relationship(self, conn: Connection) -> str:
        """Generate C4 Rel (relationship)."""
        from_id = self._sanitize_id(conn.from_id)
        to_id = self._sanitize_id(conn.to_id)
        label = self._escape_label(conn.label or "uses")
        return f'Rel({from_id}, {to_id}, "{label}")'

    _sanitize_id = staticmethod(sanitize_alnum_id)
    _escape_label = staticmethod(_escape_plantuml_label)
