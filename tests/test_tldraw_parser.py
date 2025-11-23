"""Tests for TLDraw parser."""

import pytest

from diacea.cli import detect_input_format
from diacea.ir import Connection, Group, Shape, Text
from diacea.parsers import TLDrawParser


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
        tldraw_data = {"document": {"pages": {}}}

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
        tldraw_data = {"document": {"pages": {}}}
        format_type = detect_input_format(tldraw_data)
        assert format_type == "tldraw"

    def test_auto_detect_excalidraw(self):
        """Test auto-detection of Excalidraw format."""
        excalidraw_data = {"elements": []}
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
