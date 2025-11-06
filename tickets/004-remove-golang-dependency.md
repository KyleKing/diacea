# Ticket 004: Remove Golang Dependency

## Goal

Delete the `_golang/` directory and ensure all functionality exists in Python. Update all documentation references.

## Current State

- Golang implementation exists in `_golang/` directory
- Python implementation has equivalent functionality (after tickets 001-003)
- Documentation may reference golang code
- Goal is Python-only implementation

## Requirements

1. Verify all golang functionality exists in Python:
   - [ ] Excalidraw JSON parsing
   - [ ] Relative format conversion (multiple algorithms)
   - [ ] Basic PlantUML generation
   - [ ] C4-PlantUML generation
   - [ ] CLI interface
2. Delete `_golang/` directory and all contents
3. Update documentation:
   - Remove references to golang code
   - Update README.md if it mentions golang
   - Update DEVELOPER.md if it mentions golang
   - Update AGENTS.md if it references golang
4. Update `.gitignore` if needed
5. Verify tests still pass

## Implementation Steps

1. **Audit golang functionality**:
   - List all features in `_golang/pkg/converter/converter.go`
   - Verify each feature exists in Python
   - Document any missing features (create new tickets if needed)
2. **Backup reference** (optional):
   - Note key logic from golang before deletion
   - Ensure Python implementation matches behavior
3. **Delete golang directory**:
   ```bash
   rm -rf _golang/
   ```
4. **Update documentation**:
   - Search for "golang" or "go" references
   - Update or remove as appropriate
5. **Update AGENTS.md**:
   - Remove golang reference section
   - Update "Key Files to Modify" section
6. **Run full test suite**:
   ```bash
   ./run test
   ```
7. **Verify CLI still works**:
   ```bash
   diacea -i tests/data/excalidraw.json -o test.puml
   ```

## Acceptance Criteria

- [ ] `_golang/` directory is deleted
- [ ] All Python functionality works without golang
- [ ] No references to golang in documentation
- [ ] All tests pass
- [ ] CLI works end-to-end
- [ ] Demo: Full conversion pipeline works in Python only

## Files to Delete

- `_golang/cmd/excalidraw2plantuml/main.go`
- `_golang/pkg/converter/converter.go`
- `_golang/pkg/converter/converter_test.go`
- `_golang/pkg/models/excalidraw.go`
- `_golang/go.mod`
- `_golang/README.md`
- `_golang/diagram.puml` (generated file)
- `_golang/excalidraw.pretty.json` (test data - may want to move to tests/data/)
- `_golang/excalidraw2plantuml` (binary - should be gitignored)

## Demo

```bash
# Verify Python-only workflow
diacea -i tests/data/excalidraw.json -o output.puml

# Verify output is valid
cat output.puml | head -20

# Verify no golang references
grep -r "golang\|_golang" . --exclude-dir=.git

# Should return no results (or only in this ticket file)
```

## Notes

- Consider moving `_golang/excalidraw.pretty.json` to `tests/data/` before deletion if it's useful test data
- Keep this ticket until all other tickets are complete
- This is a cleanup ticket, should be done after core functionality is ported

