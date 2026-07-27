"""Tests for TLDraw parser."""

import json
from pathlib import Path
from typing import Any

import pytest

from diacea.cli import detect_input_format
from diacea.ir import Connection, Group, Shape, Text
from diacea.parsers import TLDrawParser

V2_FIXTURE = Path(__file__).parent / "data" / "tldraw_v2.tldr"


class TestTLDrawParser:
    """Test TLDraw parser."""

    def test_parse_simple_shape(self):
        """Test parsing simple rectangle."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [100, 100],
                                "size": [200, 100],
                                "label": "My Component",
                                "style": {
                                    "color": "blue",
                                    "isFilled": True,
                                },
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        assert len(diagram.elements) == 1
        shape = diagram.elements[0]
        assert isinstance(shape, Shape)
        assert shape.label == "My Component"
        assert shape.position.x == 100
        assert shape.position.y == 100
        assert shape.size.width == 200
        assert shape.size.height == 100

    def test_parse_arrow_with_bindings(self):
        """Test parsing arrow with bindings."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [0, 0],
                                "size": [100, 50],
                                "label": "A",
                            },
                            "rect2": {
                                "id": "rect2",
                                "type": "rectangle",
                                "point": [200, 0],
                                "size": [100, 50],
                                "label": "B",
                            },
                            "arrow1": {
                                "id": "arrow1",
                                "type": "arrow",
                                "point": [100, 25],
                                "handles": {
                                    "start": {"id": "start", "bindingId": "bind1"},
                                    "end": {"id": "end", "bindingId": "bind2"},
                                },
                                "label": "connects",
                            },
                        },
                        "bindings": {
                            "bind1": {
                                "id": "bind1",
                                "fromId": "arrow1",
                                "toId": "rect1",
                            },
                            "bind2": {
                                "id": "bind2",
                                "fromId": "arrow1",
                                "toId": "rect2",
                            },
                        },
                    }
                }
            }
        }

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        # Should have 2 shapes and 1 connection
        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        connections = [e for e in diagram.elements if isinstance(e, Connection)]

        assert len(shapes) == 2
        assert len(connections) == 1

        conn = connections[0]
        assert conn.from_id == "rect1"
        assert conn.to_id == "rect2"
        assert conn.label == "connects"

    def test_parse_group(self):
        """Test parsing grouped shapes."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "group1": {
                                "id": "group1",
                                "type": "group",
                                "point": [0, 0],
                                "size": [300, 200],
                                "label": "System",
                                "children": ["child1", "child2"],
                            },
                            "child1": {
                                "id": "child1",
                                "type": "rectangle",
                                "point": [10, 10],
                                "size": [100, 50],
                                "label": "Component 1",
                            },
                            "child2": {
                                "id": "child2",
                                "type": "rectangle",
                                "point": [150, 10],
                                "size": [100, 50],
                                "label": "Component 2",
                            },
                        },
                        "bindings": {},
                    }
                }
            }
        }

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        assert len(groups) == 1
        assert groups[0].label == "System"
        assert len(groups[0].children) == 2

    def test_style_parsing(self):
        """Test style conversion."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [0, 0],
                                "size": [100, 50],
                                "style": {
                                    "color": "red",
                                    "size": "large",
                                    "isFilled": True,
                                    "dash": "dashed",
                                },
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        shape = diagram.elements[0]
        assert shape.style.stroke_color == "#ff0000"
        assert shape.style.fill_color == "#ff0000"
        assert shape.style.stroke_width == 5.0
        assert shape.style.stroke_style == "dashed"

    def test_empty_document(self):
        """Test parsing empty document."""
        tldraw_data: dict[str, Any] = {"document": {"pages": {}}}

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        assert len(diagram.elements) == 0

    def test_text_element(self):
        """Test parsing text element."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "text1": {
                                "id": "text1",
                                "type": "text",
                                "point": [50, 50],
                                "size": [150, 30],
                                "label": "Important Note",
                            }
                        },
                        "bindings": {},
                    }
                }
            }
        }

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        assert len(diagram.elements) == 1
        text = diagram.elements[0]
        assert isinstance(text, Text)
        assert text.content == "Important Note"

    def test_bidirectional_arrow(self):
        """Test parsing bidirectional arrow."""
        tldraw_data = {
            "document": {
                "pages": {
                    "page1": {
                        "id": "page1",
                        "shapes": {
                            "rect1": {
                                "id": "rect1",
                                "type": "rectangle",
                                "point": [0, 0],
                                "size": [100, 50],
                            },
                            "rect2": {
                                "id": "rect2",
                                "type": "rectangle",
                                "point": [200, 0],
                                "size": [100, 50],
                            },
                            "arrow1": {
                                "id": "arrow1",
                                "type": "arrow",
                                "point": [100, 25],
                                "handles": {
                                    "start": {"bindingId": "b1"},
                                    "end": {"bindingId": "b2"},
                                },
                                "decorations": {
                                    "start": "arrow",
                                    "end": "arrow",
                                },
                            },
                        },
                        "bindings": {
                            "b1": {"fromId": "arrow1", "toId": "rect1"},
                            "b2": {"fromId": "arrow1", "toId": "rect2"},
                        },
                    }
                }
            }
        }

        parser = TLDrawParser()
        diagram = parser.parse(tldraw_data)

        connections = [e for e in diagram.elements if isinstance(e, Connection)]
        assert len(connections) == 1
        assert connections[0].connection_type == "bidirectional"


class TestTLDrawCLI:
    """Test TLDraw CLI integration."""

    def test_auto_detect_tldraw(self):
        """Test auto-detection of TLDraw format."""
        tldraw_data: dict[str, Any] = {"document": {"pages": {}}}
        format_type = detect_input_format(tldraw_data)
        assert format_type == "tldraw"

    def test_auto_detect_excalidraw(self):
        """Test auto-detection of Excalidraw format."""
        excalidraw_data: dict[str, Any] = {"elements": []}
        format_type = detect_input_format(excalidraw_data)
        assert format_type == "excalidraw"

    def test_auto_detect_excalidraw_clipboard(self):
        """Test auto-detection of Excalidraw clipboard format."""
        excalidraw_data = {"type": "excalidraw/clipboard", "elements": []}
        format_type = detect_input_format(excalidraw_data)
        assert format_type == "excalidraw"

    def test_auto_detect_unknown(self):
        """Test error on unknown format."""
        unknown_data = {"something": "else"}
        with pytest.raises(ValueError, match="Unknown input format"):
            detect_input_format(unknown_data)


@pytest.fixture
def sample_tldraw_architecture():
    """Sample TLDraw architecture diagram."""
    return {
        "document": {
            "id": "doc1",
            "pages": {
                "page1": {
                    "id": "page1",
                    "name": "Architecture",
                    "shapes": {
                        "user": {
                            "id": "user",
                            "type": "ellipse",
                            "point": [50, 50],
                            "size": [80, 80],
                            "label": "User",
                        },
                        "system": {
                            "id": "system",
                            "type": "rectangle",
                            "point": [300, 50],
                            "size": [500, 400],
                            "label": "System",
                            "children": ["api", "db"],
                            "style": {"color": "blue", "isFilled": False},
                        },
                        "api": {
                            "id": "api",
                            "type": "rectangle",
                            "point": [350, 100],
                            "size": [150, 100],
                            "label": "API",
                        },
                        "db": {
                            "id": "db",
                            "type": "ellipse",
                            "point": [550, 100],
                            "size": [120, 100],
                            "label": "Database",
                        },
                        "arrow1": {
                            "id": "arrow1",
                            "type": "arrow",
                            "point": [130, 90],
                            "handles": {
                                "start": {"bindingId": "b1"},
                                "end": {"bindingId": "b2"},
                            },
                            "label": "uses",
                        },
                        "arrow2": {
                            "id": "arrow2",
                            "type": "arrow",
                            "point": [500, 150],
                            "handles": {
                                "start": {"bindingId": "b3"},
                                "end": {"bindingId": "b4"},
                            },
                            "label": "queries",
                        },
                    },
                    "bindings": {
                        "b1": {"fromId": "arrow1", "toId": "user"},
                        "b2": {"fromId": "arrow1", "toId": "api"},
                        "b3": {"fromId": "arrow2", "toId": "api"},
                        "b4": {"fromId": "arrow2", "toId": "db"},
                    },
                }
            },
        }
    }


class TestTLDrawArchitectureDiagram:
    """Test parsing complex TLDraw architecture diagram."""

    def test_parse_architecture_diagram(self, sample_tldraw_architecture):
        """Test parsing complete architecture diagram."""
        parser = TLDrawParser()
        diagram = parser.parse(sample_tldraw_architecture)

        # Count elements by type
        shapes = [e for e in diagram.elements if isinstance(e, Shape)]
        groups = [e for e in diagram.elements if isinstance(e, Group)]
        connections = [e for e in diagram.elements if isinstance(e, Connection)]

        # Should have shapes for user, api, db (system is a group)
        assert len(shapes) >= 3
        assert len(groups) == 1
        assert len(connections) == 2

        # Check group structure
        system_group = groups[0]
        assert system_group.label == "System"
        assert "api" in system_group.children
        assert "db" in system_group.children


@pytest.fixture
def tldraw_v2_data():
    """Load the tldraw v2 record-store fixture."""
    return json.loads(V2_FIXTURE.read_text())


class TestTLDrawV2Parser:
    """Test parsing modern tldraw v2 .tldr files."""

    def test_auto_detect_v2(self, tldraw_v2_data):
        """Test auto-detection of v2 record-store format."""
        assert detect_input_format(tldraw_v2_data) == "tldraw"

    def test_parse_fixture_shapes(self, tldraw_v2_data):
        """Test geo shapes parse with labels and shape types."""
        diagram = TLDrawParser().parse(tldraw_v2_data)

        shapes = {s.id: s for s in diagram.elements if isinstance(s, Shape)}
        assert "shape:api" in shapes
        assert "shape:db" in shapes

        api = shapes["shape:api"]
        assert api.label == "API Server"
        assert api.shape_type == "rectangle"
        assert api.size.width == 200
        assert api.size.height == 100

        db = shapes["shape:db"]
        assert db.label == "Database"
        assert db.shape_type == "ellipse"

    def test_parse_fixture_frame_as_group(self, tldraw_v2_data):
        """Test frame becomes a Group containing its children."""
        diagram = TLDrawParser().parse(tldraw_v2_data)

        groups = [e for e in diagram.elements if isinstance(e, Group)]
        assert len(groups) == 1
        assert groups[0].id == "shape:frame1"
        assert groups[0].label == "Backend"
        assert groups[0].children == ["shape:api"]

    def test_parse_fixture_bound_arrow(self, tldraw_v2_data):
        """Test arrow with binding records becomes a Connection."""
        diagram = TLDrawParser().parse(tldraw_v2_data)

        connections = [e for e in diagram.elements if isinstance(e, Connection)]
        assert len(connections) == 1

        conn = connections[0]
        assert conn.from_id == "shape:api"
        assert conn.to_id == "shape:db"
        assert conn.label == "queries"
        assert conn.connection_type == "directed"

    def test_parse_fixture_text_shape(self, tldraw_v2_data):
        """Test text shape becomes a Text element."""
        diagram = TLDrawParser().parse(tldraw_v2_data)

        texts = [e for e in diagram.elements if isinstance(e, Text)]
        assert len(texts) == 1
        assert texts[0].content == "Architecture Notes"

    def test_parse_fixture_styles(self, tldraw_v2_data):
        """Test named color, fill, dash, and size mapping."""
        diagram = TLDrawParser().parse(tldraw_v2_data)
        shapes = {s.id: s for s in diagram.elements if isinstance(s, Shape)}

        api = shapes["shape:api"]
        assert api.style.stroke_color == "#4465e9"
        assert api.style.fill_color == "#4465e9"
        assert api.style.stroke_style == "solid"

        db = shapes["shape:db"]
        assert db.style.stroke_color == "#099268"
        assert db.style.fill_color is None
        assert db.style.stroke_style == "dashed"
        assert db.style.stroke_width == 5.0

    def test_parse_fixture_metadata(self, tldraw_v2_data):
        """Test format metadata preserved for round-tripping."""
        diagram = TLDrawParser().parse(tldraw_v2_data)

        assert diagram.name == "Architecture"
        assert diagram.metadata["tldraw"]["tldrawFileFormatVersion"] == 1
        assert "sequences" in diagram.metadata["tldraw"]["schema"]

        shapes = {s.id: s for s in diagram.elements if isinstance(s, Shape)}
        assert shapes["shape:api"].metadata["tldraw"]["parentId"] == "shape:frame1"
        assert shapes["shape:api"].metadata["tldraw"]["props"]["geo"] == "rectangle"

    def test_plain_text_prop(self):
        """Test older v2 files with plain text prop instead of richText."""
        data = {
            "tldrawFileFormatVersion": 1,
            "schema": {"schemaVersion": 1},
            "records": [
                {"id": "page:p1", "typeName": "page", "name": "Page 1", "index": "a1"},
                {
                    "id": "shape:s1",
                    "typeName": "shape",
                    "type": "geo",
                    "x": 0,
                    "y": 0,
                    "parentId": "page:p1",
                    "index": "a1",
                    "props": {"w": 100, "h": 50, "geo": "diamond", "text": "Decide"},
                },
            ],
        }

        diagram = TLDrawParser().parse(data)

        assert len(diagram.elements) == 1
        decision = diagram.elements[0]
        assert isinstance(decision, Shape)
        assert decision.label == "Decide"
        assert decision.shape_type == "diamond"

    def test_rich_text_multiline_extraction(self):
        """Test multi-paragraph richText extraction."""
        rich_text = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Line 1"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Line 2"}]},
            ],
        }
        data = {
            "tldrawFileFormatVersion": 1,
            "schema": {"schemaVersion": 2},
            "records": [
                {"id": "page:p1", "typeName": "page", "name": "Page 1", "index": "a1"},
                {
                    "id": "shape:s1",
                    "typeName": "shape",
                    "type": "geo",
                    "x": 0,
                    "y": 0,
                    "parentId": "page:p1",
                    "index": "a1",
                    "props": {"w": 100, "h": 50, "geo": "rectangle", "richText": rich_text},
                },
            ],
        }

        diagram = TLDrawParser().parse(data)

        multiline = diagram.elements[0]
        assert isinstance(multiline, Shape)
        assert multiline.label == "Line 1\nLine 2"

    def test_unbound_arrow_falls_back_to_points(self):
        """Test unbound arrow resolves endpoints spatially from start/end."""
        data = {
            "tldrawFileFormatVersion": 1,
            "schema": {"schemaVersion": 2},
            "records": [
                {"id": "page:p1", "typeName": "page", "name": "Page 1", "index": "a1"},
                {
                    "id": "shape:a",
                    "typeName": "shape",
                    "type": "geo",
                    "x": 0,
                    "y": 0,
                    "parentId": "page:p1",
                    "index": "a1",
                    "props": {"w": 100, "h": 100, "geo": "rectangle", "text": "A"},
                },
                {
                    "id": "shape:b",
                    "typeName": "shape",
                    "type": "geo",
                    "x": 300,
                    "y": 0,
                    "parentId": "page:p1",
                    "index": "a2",
                    "props": {"w": 100, "h": 100, "geo": "rectangle", "text": "B"},
                },
                {
                    "id": "shape:arrow",
                    "typeName": "shape",
                    "type": "arrow",
                    "x": 110,
                    "y": 50,
                    "parentId": "page:p1",
                    "index": "a3",
                    "props": {
                        "start": {"x": 0, "y": 0},
                        "end": {"x": 180, "y": 0},
                        "arrowheadStart": "none",
                        "arrowheadEnd": "arrow",
                        "text": "",
                    },
                },
            ],
        }

        diagram = TLDrawParser().parse(data)

        connections = [e for e in diagram.elements if isinstance(e, Connection)]
        assert len(connections) == 1
        assert connections[0].from_id == "shape:a"
        assert connections[0].to_id == "shape:b"

    def test_draw_shape_included_with_flag(self):
        """Test freehand draw shape converts to bounding-box shape when enabled."""
        data = {
            "tldrawFileFormatVersion": 1,
            "schema": {"schemaVersion": 2},
            "records": [
                {"id": "page:p1", "typeName": "page", "name": "Page 1", "index": "a1"},
                {
                    "id": "shape:d1",
                    "typeName": "shape",
                    "type": "draw",
                    "x": 10,
                    "y": 20,
                    "parentId": "page:p1",
                    "index": "a1",
                    "props": {
                        "segments": [
                            {
                                "type": "free",
                                "points": [
                                    {"x": 0, "y": 0, "z": 0.5},
                                    {"x": 30, "y": 10, "z": 0.5},
                                    {"x": 60, "y": 40, "z": 0.5},
                                ],
                            }
                        ],
                        "isComplete": True,
                        "isClosed": False,
                    },
                },
            ],
        }

        assert len(TLDrawParser().parse(data).elements) == 0

        diagram = TLDrawParser(include_freehand=True).parse(data)
        assert len(diagram.elements) == 1
        shape = diagram.elements[0]
        assert isinstance(shape, Shape)
        assert shape.shape_type == "freehand"
        assert shape.position.x == 10
        assert shape.position.y == 20
        assert shape.size.width == 60
        assert shape.size.height == 40

    def test_multi_page_selection(self):
        """Test page selection by index across multiple page records."""
        records = [
            {"id": "page:p1", "typeName": "page", "name": "First", "index": "a1"},
            {"id": "page:p2", "typeName": "page", "name": "Second", "index": "a2"},
            {
                "id": "shape:s1",
                "typeName": "shape",
                "type": "geo",
                "x": 0,
                "y": 0,
                "parentId": "page:p1",
                "index": "a1",
                "props": {"w": 100, "h": 50, "geo": "rectangle", "text": "One"},
            },
            {
                "id": "shape:s2",
                "typeName": "shape",
                "type": "geo",
                "x": 0,
                "y": 0,
                "parentId": "page:p2",
                "index": "a1",
                "props": {"w": 100, "h": 50, "geo": "rectangle", "text": "Two"},
            },
        ]
        data = {"tldrawFileFormatVersion": 1, "schema": {}, "records": records}

        first = TLDrawParser(page_index=0).parse(data)
        assert first.name == "First"
        assert [s.label for s in first.get_shapes()] == ["One"]

        second = TLDrawParser(page_index=1).parse(data)
        assert second.name == "Second"
        assert [s.label for s in second.get_shapes()] == ["Two"]

        both = TLDrawParser(page_index=None).parse(data)
        assert len(both.elements) == 2

        by_id = TLDrawParser(page_id="page:p2").parse(data)
        assert [s.label for s in by_id.get_shapes()] == ["Two"]
