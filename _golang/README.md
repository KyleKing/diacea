# Excalidraw to PlantUML Converter

A command-line tool that converts Excalidraw JSON exports to PlantUML diagrams. This tool helps bridge the gap between Excalidraw's visual diagramming and PlantUML's text-based diagramming.

## Features

- Converts Excalidraw rectangles to PlantUML elements
- Preserves text labels and relationships
- Maintains arrow connections between elements
- Handles standalone text elements as notes
- Supports automatic element naming

## Installation

```bash
go install github.com/kyleking/excalidraw2plantuml/cmd/excalidraw2plantuml@latest
```

## Usage

```bash
excalidraw2plantuml -input your-diagram.json [-output output.puml]
```

### Arguments

- `-input`: Path to the Excalidraw JSON file (required)
- `-output`: Path to the output PlantUML file (optional, defaults to input filename with .puml extension)

### Example

```bash
excalidraw2plantuml -input diagram.json -output diagram.puml
```

## How it Works

1. The tool reads an Excalidraw JSON export file
2. Converts rectangles to PlantUML elements
3. Preserves text labels from bound text elements
4. Converts arrows to PlantUML relationships
5. Generates a PlantUML file that can be rendered using any PlantUML-compatible tool

## Development

To build from source:

```bash
git clone https://github.com/kyleking/excalidraw2plantuml.git
cd excalidraw2plantuml
go build -o excalidraw2plantuml cmd/excalidraw2plantuml/main.go
```

To run tests:

```bash
go test ./...
```

HACK: To regenerate from the sample JSON

```sh
go build -o excalidraw2plantuml cmd/excalidraw2plantuml/main.go && ./excalidraw2plantuml -input excalidraw.pretty.json -output diagram.puml
```

## License

MIT License
