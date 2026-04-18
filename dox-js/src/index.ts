/**
 * dox-js — TypeScript reference implementation for .dox format.
 */

export { parseDox } from "./parser.js";
export type {
  BoundingBox,
  DoxDocument,
  Element,
  Frontmatter,
  Heading,
  Paragraph,
  Table,
  TableRow,
  TableCell,
  CodeBlock,
  MathBlock,
  FormField,
  Chart,
  Annotation,
  Figure,
  Footnote,
  ListBlock,
  CrossRef,
  SpatialBlock,
  SpatialAnnotation,
  Metadata,
  Confidence,
  Provenance,
  VersionEntry,
} from "./types.js";
