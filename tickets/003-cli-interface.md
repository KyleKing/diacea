# Ticket 003: CLI Interface

## Goal

Create a command-line interface for diacea that accepts Excalidraw JSON files and outputs PlantUML files.

## Current State

- PlantUML generation exists (tickets 001, 002)
- No command-line interface
- Users must write Python code to use the library

## Requirements

1. Create `diacea/cli.py` module with CLI entry point
2. Support command-line arguments:
   - `--input` or `-i`: Path to Excalidraw JSON file (required)
   - `--output` or `-o`: Path to output PlantUML file (optional, defaults to input filename with `.puml` extension)
   - `--algorithm` or `-a`: Algorithm to use (default: `graph_based_approach`)
   - `--format` or `-f`: Output format (`basic` or `c4`, default: `c4`)
3. Add CLI entry point to `pyproject.toml`:
   ```toml
   [project.scripts]
   diacea = "diacea.cli:main"
   ```
4. Handle errors gracefully with clear messages
5. Support both basic and C4-PlantUML formats

## Implementation Steps

1. Create `diacea/cli.py` with `main()` function
2. Use `argparse` for argument parsing
3. Load Excalidraw JSON file
4. Select algorithm based on `--algorithm` flag
5. Convert to relative format
6. Generate PlantUML (basic or C4 based on `--format`)
7. Write output to file
8. Add basic error handling (file not found, invalid JSON, etc.)
9. Add tests for CLI in `tests/test_cli.py`

## Acceptance Criteria

- [ ] CLI can be invoked as `diacea` command (after installation)
- [ ] Required `--input` argument works
- [ ] Optional `--output` argument works with default behavior
- [ ] `--algorithm` selects correct conversion algorithm
- [ ] `--format` selects basic or C4 output
- [ ] Clear error messages for invalid inputs
- [ ] Demo: Run `diacea -i tests/data/excalidraw.json -o output.puml` and verify output

## Demo

```bash
# Basic usage
diacea -i diagram.json -o diagram.puml

# Specify algorithm
diacea -i diagram.json -a quadtree_approach

# Use basic format instead of C4
diacea -i diagram.json -f basic

# Should produce valid PlantUML file
cat diagram.puml
```

## Example CLI Code Structure

```python
def main():
    parser = argparse.ArgumentParser(description='Convert Excalidraw to PlantUML')
    parser.add_argument('-i', '--input', required=True, help='Input Excalidraw JSON file')
    parser.add_argument('-o', '--output', help='Output PlantUML file')
    parser.add_argument('-a', '--algorithm', default='graph_based_approach', 
                       choices=['convert_to_relative', 'rule_based_approach', ...])
    parser.add_argument('-f', '--format', default='c4', choices=['basic', 'c4'])
    
    args = parser.parse_args()
    # ... implementation
```

## Notes

- Follow Python CLI best practices
- Use `sys.exit()` with appropriate codes
- Provide helpful error messages
- Consider adding `--version` flag
- Make output file path optional with sensible default

