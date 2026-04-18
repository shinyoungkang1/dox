# dox

`dox` is a document interchange format designed to preserve human readability while carrying enough structure for OCR, layout extraction, tables, figures, forms, and downstream agent workflows.

This repository currently contains:

- `dox-py`: the Python reference implementation, parser, serializer, converters, validator, and tests
- `dox-js`: the JavaScript package
- `vscode-dox`: editor support for `.dox`
- `DOX_WORLD_CLASS_CHECKLIST.md`: the current hardening roadmap and completed work log
- `FORMAT_COMPATIBILITY_POLICY.md`: rules for evolving the format without breaking stored data and downstream tools

## Current focus

The active work in this repository is to make `.dox` a trustworthy canonical format:

- lossless enough for parser output and document regeneration workflows
- explicit and testable around escaping and round-trip behavior
- stable across tables, figures, page boundaries, and metadata-rich enterprise documents

## Quick start

For the Python implementation, see [dox-py/README.md](dox-py/README.md).
