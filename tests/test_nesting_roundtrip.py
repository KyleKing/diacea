"""Round-trip tests asserting nested group structure survives IR conversions.

Byte equality is out of scope; the group-containment DAG is compared by label
because parsers and generators may sanitize ids.
"""

from textwrap import dedent

import pytest

from diacea.generators import C4PlantUMLGenerator, MermaidGenerator, PlantUMLGenerator
from diacea.parsers import MermaidParser, PlantUMLParser

MERMAID_SOURCES = {
    2: dedent("""\
        flowchart TD
            subgraph outer[Outer]
                subgraph inner[Inner]
                    a[Alpha]
                end
                b[Beta]
            end
            c[Gamma]
            d[Delta]
            a --> b
            c --> d
        """),
    3: dedent("""\
        flowchart TD
            subgraph outer[Outer]
                subgraph inner[Inner]
                    subgraph core[Core]
                        a[Alpha]
                    end
                    b[Beta]
                end
                c[Gamma]
            end
            d[Delta]
            a --> b
            c --> d
        """),
}

PLANTUML_SOURCES = {
    2: dedent("""\
        @startuml
        package "Outer" as outer {
          package "Inner" as inner {
            rectangle "Alpha" as a
          }
          rectangle "Beta" as b
        }
        rectangle "Gamma" as c
        rectangle "Delta" as d
        a --> b
        c --> d
        @enduml
        """),
    3: dedent("""\
        @startuml
        package "Outer" as outer {
          package "Inner" as inner {
            package "Core" as core {
              rectangle "Alpha" as a
            }
            rectangle "Beta" as b
          }
          rectangle "Gamma" as c
        }
        rectangle "Delta" as d
        a --> b
        c --> d
        @enduml
        """),
}

C4_SOURCES = {
    2: dedent("""\
        @startuml
        System_Boundary(outer, "Outer") {
          System_Boundary(inner, "Inner") {
            System(a, "Alpha")
          }
          System(b, "Beta")
        }
        System(c, "Gamma")
        System(d, "Delta")
        Rel(a, b, "calls")
        Rel(c, d, "calls")
        @enduml
        """),
    3: dedent("""\
        @startuml
        System_Boundary(outer, "Outer") {
          System_Boundary(inner, "Inner") {
            System_Boundary(core, "Core") {
              System(a, "Alpha")
            }
            System(b, "Beta")
          }
          System(c, "Gamma")
        }
        System(d, "Delta")
        Rel(a, b, "calls")
        Rel(c, d, "calls")
        @enduml
        """),
}

EXPECTED_CONTAINMENT = {
    2: {
        'Outer': ({'Inner'}, {'Beta'}),
        'Inner': (set(), {'Alpha'}),
    },
    3: {
        'Outer': ({'Inner'}, {'Gamma'}),
        'Inner': ({'Core'}, {'Beta'}),
        'Core': (set(), {'Alpha'}),
    },
}


def _containment(diagram):
    """Map each labeled group to its (child group labels, child shape labels), skipping empty labels."""
    group_labels = {group.id: group.label for group in diagram.get_groups()}
    shape_labels = {shape.id: shape.label for shape in diagram.get_shapes()}
    tree = {}
    for group in diagram.get_groups():
        if not group.label:
            continue
        child_groups = {group_labels[child_id] for child_id in group.children if group_labels.get(child_id)}
        child_shapes = {shape_labels[child_id] for child_id in group.children if shape_labels.get(child_id)}
        tree[group.label] = (child_groups, child_shapes)
    return tree


@pytest.mark.parametrize('depth', [2, 3])
def test_mermaid_roundtrip_preserves_nesting(depth):
    diagram = MermaidParser().parse(MERMAID_SOURCES[depth])
    assert _containment(diagram) == EXPECTED_CONTAINMENT[depth]

    regenerated = MermaidGenerator().generate(diagram)
    reparsed = MermaidParser().parse(regenerated)

    assert _containment(reparsed) == EXPECTED_CONTAINMENT[depth]


@pytest.mark.parametrize('depth', [2, 3])
def test_plantuml_roundtrip_preserves_nesting(depth):
    diagram = PlantUMLParser().parse(PLANTUML_SOURCES[depth])
    assert _containment(diagram) == EXPECTED_CONTAINMENT[depth]

    regenerated = PlantUMLGenerator().generate(diagram)
    reparsed = PlantUMLParser().parse(regenerated)

    assert _containment(reparsed) == EXPECTED_CONTAINMENT[depth]


@pytest.mark.parametrize('depth', [2, 3])
def test_c4_roundtrip_preserves_nesting(depth):
    diagram = PlantUMLParser().parse(C4_SOURCES[depth])
    assert _containment(diagram) == EXPECTED_CONTAINMENT[depth]

    regenerated = C4PlantUMLGenerator().generate(diagram)
    reparsed = PlantUMLParser().parse(regenerated)

    assert _containment(reparsed) == EXPECTED_CONTAINMENT[depth]


@pytest.mark.parametrize('depth', [2, 3])
def test_mermaid_to_plantuml_preserves_nesting(depth):
    diagram = MermaidParser().parse(MERMAID_SOURCES[depth])
    assert _containment(diagram) == EXPECTED_CONTAINMENT[depth]

    generated = PlantUMLGenerator().generate(diagram)
    reparsed = PlantUMLParser().parse(generated)

    assert _containment(reparsed) == EXPECTED_CONTAINMENT[depth]
