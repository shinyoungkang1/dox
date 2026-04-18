# DOX World-Class Checklist

This checklist converts the independent audit into an execution plan for making `dox` a trustworthy canonical document format rather than a promising prototype.

## Target

`dox` should be able to serve as:

- a lossless canonical document interchange format
- a stable parser target for OCR / layout / table / figure extraction
- a format that survives serializer → parser → converter round-trips without silent corruption
- a format usable by both humans and downstream agents

## Success Criteria

- `.dox` text round-trip preserves all supported canonical fields for core elements
- escaping rules are explicit and tested for quotes, backslashes, brackets, and parentheses
- table validation uses semantic width, not raw cell count
- schema, JSON conversion, serializer, parser, and README agree on the same contract
- regression tests cover high-risk edge cases, not just happy-path fixtures

## P0 Canonical Integrity

- [x] Preserve base element metadata in `.dox` text for the main element families
- [x] Preserve `reading_order`, `lang`, and `is_furniture` through serializer/parser round-trip
- [x] Preserve `CodeBlock` metadata through fenced code syntax
- [x] Preserve `Table` metadata through table header attributes
- [x] Preserve `Figure.image_type` and `Figure.image_data` when present
- [x] Remove silent metadata loss for `CrossRef` where feasible

Acceptance:

- `serialize(parse(x))` and `parse(serialize(x))` do not drop supported fields on canonical fixtures

## P0 Grammar And Escaping

- [x] Replace naive `key="value"` parsing with escaped-string aware parsing
- [x] Support `\"` and `\\` round-trip for inline block attributes
- [x] Fix figure parsing so escaped `]` in captions does not collapse figures into paragraphs
- [x] Escape and unescape figure captions and sources consistently
- [x] Normalize metadata parsing into shared helpers instead of element-specific drift

Acceptance:

- quoted keys and values survive round-trip
- figure captions with brackets and quotes survive round-trip

## P0 Table Semantics

- [x] Compute semantic table width using `colspan`
- [x] Validate row width by effective span width, not raw cell count
- [x] Keep current merged-cell syntax but make validation match it
- [x] Add regression coverage for merged headers and mixed span rows

Acceptance:

- valid merged-header tables do not emit false warnings
- malformed tables still emit warnings

## P1 Contract Consistency

- [x] Make README syntax match parser and serializer behavior
- [x] Align schema with actual canonical fields
- [x] Decide that canonical JSON is lossless rather than lightweight-only
- [x] If JSON is canonical, include fields required for full round-trip
- [x] Document that JSON is intended as the canonical machine representation

Acceptance:

- README examples parse successfully with the library
- schema validation does not reject serializer output

## P1 Regression Coverage

- [x] Add round-trip tests for metadata-rich headings, paragraphs, tables, code blocks, figures, and crossrefs
- [x] Add parsing tests for escaped attributes
- [x] Add validator tests for colspan-aware width checks
- [x] Add spec regression tests for page-break syntax

Acceptance:

- new tests fail on the pre-audit code and pass on the fixed code

## P2 Format Hardening

- [x] Expand code fence language parsing beyond `\\w*`
- [x] Audit list metadata strategy and decide whether lists get canonical block metadata
- [x] Audit page-break metadata semantics and whether they should carry element metadata at all
- [x] Review converters for assumptions that break on newly preserved fields
- [ ] Add fuzz-style tests for escaping and mixed-content fixtures

## P2 Enterprise Readiness

- [ ] Add golden fixtures for invoices, reports, scientific PDFs, forms, and slide-like docs
- [ ] Benchmark `.dox` fidelity against public parser gold on hard pages
- [ ] Track loss rates for tables, figures, math, footnotes, and metadata separately
- [ ] Add a documented compatibility policy for format evolution

## Current Execution Order

1. Fix metadata round-trip and shared metadata grammar. Done.
2. Fix attribute escaping and figure parsing. Done.
3. Fix table semantic-width validation. Done.
4. Update schema and docs to match implementation. Done for current core contract.
5. Add regression tests and rerun targeted suites. Done.

## Non-Goals For This Pass

- redesigning the entire list syntax
- adding a binary asset container format
- solving every exporter/converter edge case before the canonical parser contract is stable
