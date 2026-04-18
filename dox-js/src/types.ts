/**
 * .dox TypeScript type definitions — mirrors the Python data model.
 */

// ---------------------------------------------------------------------------
// Spatial primitives
// ---------------------------------------------------------------------------

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

// ---------------------------------------------------------------------------
// Elements (Layer 0)
// ---------------------------------------------------------------------------

export type ElementType =
  | "heading"
  | "paragraph"
  | "table"
  | "codeblock"
  | "mathblock"
  | "formfield"
  | "chart"
  | "annotation"
  | "figure"
  | "footnote"
  | "listblock"
  | "crossref";

export interface BaseElement {
  type: ElementType;
  bbox?: BoundingBox;
  confidence?: number;
  elementId?: string;
  page?: number;
  dirty?: boolean;
}

export interface Heading extends BaseElement {
  type: "heading";
  level: number;
  text: string;
}

export interface Paragraph extends BaseElement {
  type: "paragraph";
  text: string;
}

export interface TableCell {
  text: string;
  bbox?: BoundingBox;
  isHeader: boolean;
  colspan: number;
  rowspan: number;
}

export interface TableRow {
  cells: TableCell[];
  bbox?: BoundingBox;
  isHeader: boolean;
}

export interface Table extends BaseElement {
  type: "table";
  rows: TableRow[];
  caption?: string;
  nested: boolean;
  tableId?: string;
}

export interface CodeBlock extends BaseElement {
  type: "codeblock";
  code: string;
  language?: string;
}

export interface MathBlock extends BaseElement {
  type: "mathblock";
  expression: string;
  displayMode: boolean;
}

export type FormFieldType = "text" | "checkbox" | "radio" | "select" | "textarea";

export interface FormField extends BaseElement {
  type: "formfield";
  fieldName: string;
  fieldType: FormFieldType;
  value: string;
}

export interface Chart extends BaseElement {
  type: "chart";
  chartType: string;
  dataRef?: string;
  xField?: string;
  yField?: string;
  extra: Record<string, string>;
}

export interface Annotation extends BaseElement {
  type: "annotation";
  annotationType: string;
  text: string;
}

export interface Figure extends BaseElement {
  type: "figure";
  caption: string;
  source: string;
  figureId?: string;
}

export interface Footnote extends BaseElement {
  type: "footnote";
  number: number;
  text: string;
}

export interface ListItem {
  text: string;
  children: ListItem[];
  checked?: boolean;
}

export interface ListBlock extends BaseElement {
  type: "listblock";
  items: ListItem[];
  ordered: boolean;
  start: number;
}

export interface CrossRef extends BaseElement {
  type: "crossref";
  refType: string;
  refId: string;
}

export type Element =
  | Heading
  | Paragraph
  | Table
  | CodeBlock
  | MathBlock
  | FormField
  | Chart
  | Annotation
  | Figure
  | Footnote
  | ListBlock
  | CrossRef;

// ---------------------------------------------------------------------------
// Spatial (Layer 1)
// ---------------------------------------------------------------------------

export interface SpatialAnnotation {
  lineText: string;
  bbox?: BoundingBox;
  cellBboxes?: BoundingBox[];
}

export interface SpatialBlock {
  page: number;
  gridWidth: number;
  gridHeight: number;
  annotations: SpatialAnnotation[];
  dirty: boolean;
}

// ---------------------------------------------------------------------------
// Metadata (Layer 2)
// ---------------------------------------------------------------------------

export interface VersionEntry {
  timestamp: string;
  agent: string;
  action: string;
}

export interface Confidence {
  overall: number;
  elements: Record<string, number>;
}

export interface Provenance {
  sourceHash: string;
  extractionPipeline: string[];
}

export interface Metadata {
  extractedBy: string;
  extractedAt?: string;
  confidence: Confidence;
  provenance: Provenance;
  versionHistory: VersionEntry[];
  extra: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Frontmatter
// ---------------------------------------------------------------------------

export interface Frontmatter {
  version: string;
  source: string;
  pages?: number;
  lang: string;
  extra: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------

export interface DoxDocument {
  frontmatter: Frontmatter;
  elements: Element[];
  spatialBlocks: SpatialBlock[];
  metadata?: Metadata;
}
