# Deletion Plan

This document identifies files and directories that should be deleted as part of the Python-only implementation and documentation consolidation.

## Golang Implementation (To Be Deleted)

The entire `_golang/` directory should be removed once Python implementation is complete (see ticket 004).

### Directory: `_golang/`

**Reason**: Moving to Python-only implementation. All functionality will be ported to Python.

**Files to delete**:
- `_golang/cmd/excalidraw2plantuml/main.go` - CLI entry point
- `_golang/pkg/converter/converter.go` - Main conversion logic (reference before deletion)
- `_golang/pkg/converter/converter_test.go` - Go tests
- `_golang/pkg/models/excalidraw.go` - Data models
- `_golang/go.mod` - Go module file
- `_golang/README.md` - Go-specific documentation
- `_golang/diagram.puml` - Generated output file
- `_golang/excalidraw2plantuml` - Compiled binary (should be gitignored)

**Files to potentially preserve** (move to tests/data/):
- `_golang/excalidraw.pretty.json` - Complex test data, useful for Python tests

**When to delete**: After ticket 004 is complete (all functionality ported to Python)

## Redundant Documentation Files (To Be Deleted)

These markdown files should be deleted after their content is merged into the consolidated documentation files.

### Files to Delete After Consolidation

1. **`docs/docs/DEVELOPER_GUIDE.md`**
   - **Status**: Content merged into `DEVELOPER.md`
   - **Reason**: Consolidated into root-level DEVELOPER.md
   - **Action**: Delete after verifying content is in DEVELOPER.md

2. **`docs/docs/STYLE_GUIDE.md`**
   - **Status**: Content merged into `DEVELOPER.md` (Git commit style section)
   - **Reason**: Consolidated into DEVELOPER.md
   - **Action**: Delete after verifying Git style guide is in DEVELOPER.md

3. **`docs/README.md`**
   - **Status**: Content merged into root `README.md`
   - **Reason**: Duplicate of root README, consolidated
   - **Action**: Delete after verifying content is in root README.md

4. **`_golang/README.md`**
   - **Status**: Will be deleted with `_golang/` directory
   - **Reason**: Go-specific, not needed for Python-only implementation
   - **Action**: Delete with golang directory (ticket 004)

5. **`scripts/README.md`**
   - **Status**: Content merged into `DEVELOPER.md` (Scripts section)
   - **Reason**: Minimal content, better in DEVELOPER.md
   - **Action**: Delete after verifying scripts section is in DEVELOPER.md

6. **`tests/data/README.md`**
   - **Status**: Content merged into `DEVELOPER.md` (Test Data section)
   - **Reason**: Minimal content, better in DEVELOPER.md
   - **Action**: Delete after verifying test data section is in DEVELOPER.md

### Files to Keep

1. **`docs/docs/CHANGELOG.md`**
   - **Status**: Keep in `docs/docs/` directory
   - **Reason**: Changelog is referenced from README.md and should remain in docs
   - **Action**: Keep as-is, reference from main docs

## Deletion Checklist

Before deleting any files, verify:

- [ ] Content has been merged into consolidated documentation
- [ ] All references to deleted files have been updated
- [ ] No broken links in documentation
- [ ] Git history preserves deleted files (if needed for reference)

## Deletion Order

1. **Phase 1 - Documentation Consolidation** (Can do now):
   - Delete `docs/docs/DEVELOPER_GUIDE.md` (after merge verification)
   - Delete `docs/docs/STYLE_GUIDE.md` (after merge verification)
   - Delete `docs/README.md` (after merge verification)
   - Delete `scripts/README.md` (after merge verification)
   - Delete `tests/data/README.md` (after merge verification)

2. **Phase 2 - Golang Removal** (After ticket 004):
   - Delete entire `_golang/` directory
   - Move `_golang/excalidraw.pretty.json` to `tests/data/` if useful
   - Update all documentation references

## Verification Commands

After deletions, verify no broken references:

```bash
# Check for references to deleted files
grep -r "DEVELOPER_GUIDE\|STYLE_GUIDE" . --exclude-dir=.git
grep -r "_golang" . --exclude-dir=.git --exclude="tickets/*"

# Verify documentation links work
# (manual check of README.md, DEVELOPER.md, etc.)
```

## Notes

- All deletions should be done via git commits for history
- Consider creating a backup branch before mass deletions
- Some files may be referenced in git history - that's fine
- Focus on removing files that cause confusion or duplication

