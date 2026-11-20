# Troubleshooting a Conversion

diacea reads a diagram into an intermediate representation and then writes that out in another format. When the result is not what you drew, the cause is almost always in the first step, and you can see and correct it yourself.

## 1. Look at what diacea read

```bash
diacea inspect flow.mmd
```

```
Format: mermaid
Elements: 5
  web: label='Web App' semantic=system confidence=0.80
  db: label='Orders' semantic=component confidence=0.40
  q: label='Jobs' semantic=queue confidence=1.00
  edge-0: label='' semantic=- confidence=0.00
  edge-1: label='' semantic=- confidence=0.00
```

Every box, group, text, and connection is listed with its label and the type diacea assigned. Add `--json` for the same report with each element's kind and shape, and its `source_id` in the original file.

For a picture instead of a list, convert to SVG. It needs no other tool and draws exactly what was read: the labels, which boxes sit in which group, and where each arrow starts and ends.

```bash
diacea sketch.excalidraw -o what-diacea-read.svg
```

## 2. Check that nothing was lost

```bash
diacea sketch.excalidraw -o architecture.mmd --verify
```

`--verify` parses the generated file back and compares it with the source. It prints `Verified: ...` when every node, group, and connection survived, and otherwise names what is missing and exits with status 1.

Losses that diacea knows about are printed as `Warning:` lines whether or not you verify (and are listed under `warnings` with `--json`).

## 3. Fix what was read

### An element has the wrong type

Types such as `database`, `person`, and `queue` decide whether a box becomes a cylinder, an actor, or a `ContainerDb`. A confidence below 0.90 means the type was guessed from the label or shape. State it yourself in either way:

- Add a stereotype to the label in the source diagram: `Orders <<database>>`. This works in any drawing tool and any text format, travels with the file, and is removed from the label in the output
- Pass `--hint 'Orders=database'` on the command line. The left side is the element's label or id, and the flag can be repeated

`diacea formats` lists the type names.

Guessing looks at the last keyword in the first line of a label, so `Customer Database` is a database and `User Input` is not a person. In text formats (Mermaid, PlantUML, DOT, D2), a guess never changes a shape you chose: a plain box labelled `Orders database` stays a box unless you write it as a cylinder or add a stereotype.

### A box has no label, or the wrong one (Excalidraw, TLDraw)

A text becomes the label of:

1. the shape it is bound to (double-click the shape and type), else
2. the smallest shape that contains the text's center, else
3. the only shape it is grouped with, else
4. an unlabeled shape it sits directly above, below, or beside

When a shape has several texts, the largest (then the topmost) is the label and the others become its description. If a label lands on the wrong box, bind the text to its shape or move it fully inside.

### An arrow is missing or attached to the wrong box

- Drag each end of the arrow onto a shape until it snaps. A bound arrow is always read correctly
- An unbound end attaches to the shape it is inside, or else the nearest one, which may not be the one you meant
- An arrow that points at a loose text is kept, and the text becomes a node

### A box is in the wrong group

Excalidraw frames and grouped elements are used as drawn. Otherwise a shape belongs to the smallest larger shape that covers its center, so a box that straddles a container's border belongs to whichever side holds its center. Move the box so that it is clearly inside or outside.

### A group or relation disappeared in the output

Some structure has no equivalent in the target format, and each case is reported as a warning:

- `Dropping connection between container and its own content`: Mermaid, D2, and DOT cannot link a container to something inside it
- `Re-pointing C4 Rel from boundary ...`: Mermaid C4 cannot link a boundary, so the relation is attached to an element inside it
- `exceeds max subgraph depth`: Mermaid output nests subgraphs three levels deep

If you need that structure, pick an output format that has it (PlantUML and Excalidraw keep container links).

### Part of a text diagram was skipped

Text parsers cover the structural core of each language and skip the rest with a warning that names the line, for example `line 12: skipped 'classDef' directive`. Skipped syntax never fails a conversion. Not supported at all: Mermaid diagram types other than flowchart, sequence, and C4, and PlantUML sequence and activity diagrams.

## 4. The file is not recognized

```
Error: Could not detect input format (supported: d2, excalidraw, graphviz, ...)
```

Detection looks at the content first and the file extension second. D2 has no header to recognize, so name `.d2` files accordingly or pass `--input-format d2`. Any format can be forced with `--input-format`.

Exit status 2 with `parsed 0 elements` means the file was recognized but nothing in it was understood, which usually indicates a newer or unusual schema.

## 5. Review many diagrams at once

From a checkout of the repository:

```bash
uv run python scripts/render_fixtures.py path/to/diagrams --out review
```

This converts every diagram to every format, runs the `--verify` check on each, renders each with its native tool when that tool is installed (`mmdc`, `d2`, `dot`, `plantuml`), and writes `review/index.html` with diacea's own drawing of each input beside every rendered output.

## Reporting a problem

Open an issue with the diagram (or a reduced copy of it) and the output of:

```bash
diacea inspect your-diagram --json
diacea your-diagram -f <format> --verify
```
