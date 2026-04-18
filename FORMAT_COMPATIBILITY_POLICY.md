# Format Compatibility Policy

This document defines how `.dox` should evolve without breaking downstream parsers, exporters, stored corpora, or training data pipelines.

## Compatibility Goal

`.dox` is intended to be stable enough to serve as:

- a canonical parser output format
- a persisted interchange format in document pipelines
- a training and evaluation substrate for downstream systems

That means format changes should default to preserving old data and old readers whenever reasonably possible.

## Versioning Rules

### Additive Changes

The following changes are considered additive and should remain backward-compatible within the same major format generation:

- adding new optional element attributes
- adding new optional metadata fields
- adding new optional JSON properties
- adding new element types when older readers can safely ignore them
- adding new converter behavior that preserves existing output contracts

These changes may ship in the same `.dox` major version as long as:

- old files continue to parse
- existing syntax does not change meaning
- omitted new fields still preserve valid semantics

### Breaking Changes

The following changes require a format version bump and explicit migration guidance:

- changing the meaning of an existing syntax form
- removing an element type or required field
- changing how an existing field is serialized in a non-lossless way
- making previously optional fields required
- altering escaping rules so old files parse differently

## Layer-Specific Policy

### Layer 0 Content

Human-readable `.dox` syntax must stay readable and mostly Markdown-shaped. When richer fidelity is needed:

- prefer optional preambles or attributes over replacing the base syntax
- preserve plain-text readability for the common case
- ensure serializer output still parses with the reference parser

### Layer 1 Spatial

Spatial annotations are optional and may grow additively, but existing coordinate semantics must not change without a version bump.

### Layer 2 Metadata

Metadata is expected to evolve additively. New provenance or confidence fields should be optional by default.

## Canonical Representations

- `.dox` text is the canonical human-readable representation.
- `to_json()` is the canonical machine-readable representation.
- Markdown, HTML, DOCX, and PDF exports are derived views, not canonical persistence formats.

## Parser And Serializer Guarantees

The reference implementation should maintain these guarantees:

- `parse(serialize(doc))` should preserve supported canonical fields
- `serialize(parse(text))` should not introduce silent corruption
- escaping changes must be accompanied by regression tests
- edge-case fixes should add targeted tests and, when useful, fuzz-style regression coverage

## Enterprise-Grade Change Process

Any future format-affecting change should ship with:

1. a test that fails before the change and passes after it
2. a note in the checklist or changelog if the contract changed materially
3. a decision about whether the change is additive or breaking
4. a migration note if stored `.dox` or canonical JSON needs adaptation

## Current Interpretation

Under this policy, the current hardening work is treated as backward-compatible because it:

- preserves existing simple syntax
- fixes silent data loss and parser ambiguity
- adds optional representational power without invalidating old files
