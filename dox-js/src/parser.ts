/**
 * Core .dox parser for TypeScript/JavaScript.
 *
 * Mirrors the Python DoxParser — reads a .dox string and produces a DoxDocument.
 */

import YAML from "yaml";
import type {
  Annotation,
  BoundingBox,
  Chart,
  CodeBlock,
  CrossRef,
  DoxDocument,
  Element,
  Figure,
  Footnote,
  FormField,
  FormFieldType,
  Frontmatter,
  Heading,
  ListBlock,
  ListItem,
  MathBlock,
  Metadata,
  Paragraph,
  SpatialAnnotation,
  SpatialBlock,
  Table,
  TableCell,
  TableRow,
} from "./types.js";

// ---------------------------------------------------------------------------
// Regex patterns
// ---------------------------------------------------------------------------

const FRONTMATTER_RE = /^---dox\s*\n([\s\S]*?)\n---\s*$/m;
const SPATIAL_RE = /^---spatial\s+(.*?)\n([\s\S]*?)\n---\/spatial\s*$/gm;
const META_RE = /^---meta\s*\n([\s\S]*?)\n---\/meta\s*$/m;
const HEADING_RE = /^(#{1,6})\s+(.+)$/;
const TABLE_START_RE = /^\|\|\|\s*table\s*(.*)$/;
const TABLE_END_RE = /^\|\|\|\s*$/;
const TABLE_ROW_RE = /^\|(.+)\|$/;
const SEPARATOR_RE = /^[\s|:-]+$/;
const MATH_BLOCK_RE = /^\$\$(.*?)\$\$\s*(\{math:\s*(\w+)\})?$/;
const INLINE_BLOCK_RE = /^::(\w+)\s+(.*?)::\s*$/;
const CODE_FENCE_START_RE = /^```(\w*)\s*$/;
const CODE_FENCE_END_RE = /^```\s*$/;
const FIGURE_RE = /^!\[([^\]]*)\]\(([^)]+)\)\s*(\{figure:\s*id="([^"]+)"\})?/;
const FOOTNOTE_DEF_RE = /^\[\^(\d+)\]:\s*(.+)$/;
const BBOX_RE = /@\[(\d+),(\d+),(\d+),(\d+)\]/g;
const LIST_RE = /^(\s*)([-*+]|\d+\.)\s+(.*)$/;
const ATTR_RE = /(\w[\w-]*)="([^"]*)"/g;

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

export function parseDox(text: string): DoxDocument {
  const doc: DoxDocument = {
    frontmatter: { version: "1.0", source: "", lang: "en", extra: {} },
    elements: [],
    spatialBlocks: [],
  };

  // 1. Frontmatter
  text = parseFrontmatter(text, doc);

  // 2. Spatial
  text = parseSpatialBlocks(text, doc);

  // 3. Metadata
  text = parseMetadata(text, doc);

  // 4. Content
  parseContent(text, doc);

  return doc;
}

function parseFrontmatter(text: string, doc: DoxDocument): string {
  const match = text.match(FRONTMATTER_RE);
  if (match) {
    const raw = YAML.parse(match[1]) ?? {};
    doc.frontmatter = {
      version: String(raw.version ?? "1.0"),
      source: raw.source ?? "",
      pages: raw.pages,
      lang: raw.lang ?? "en",
      extra: Object.fromEntries(
        Object.entries(raw).filter(
          ([k]) => !["version", "source", "pages", "lang"].includes(k)
        )
      ),
    };
    text = text.slice(0, match.index!) + text.slice(match.index! + match[0].length);
  }
  return text;
}

function parseSpatialBlocks(text: string, doc: DoxDocument): string {
  let match: RegExpExecArray | null;
  const re = new RegExp(SPATIAL_RE.source, SPATIAL_RE.flags);
  while ((match = re.exec(text)) !== null) {
    const headerStr = match[1];
    const body = match[2];

    const block: SpatialBlock = {
      page: 1,
      gridWidth: 1000,
      gridHeight: 1000,
      annotations: [],
      dirty: false,
    };

    for (const part of headerStr.split(/\s+/)) {
      if (part.startsWith("page=")) block.page = parseInt(part.split("=")[1]);
      if (part.startsWith("grid=")) {
        const [w, h] = part.split("=")[1].split("x").map(Number);
        block.gridWidth = w;
        block.gridHeight = h;
      }
    }

    for (const line of body.trim().split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      const ann: SpatialAnnotation = { lineText: trimmed };
      const bboxMatch = /@\[(\d+),(\d+),(\d+),(\d+)\]/.exec(trimmed);
      if (bboxMatch) {
        ann.bbox = {
          x1: parseInt(bboxMatch[1]),
          y1: parseInt(bboxMatch[2]),
          x2: parseInt(bboxMatch[3]),
          y2: parseInt(bboxMatch[4]),
        };
        ann.lineText = trimmed.slice(0, bboxMatch.index).trim();
      }

      block.annotations.push(ann);
    }

    doc.spatialBlocks.push(block);
  }

  return text.replace(new RegExp(SPATIAL_RE.source, SPATIAL_RE.flags), "");
}

function parseMetadata(text: string, doc: DoxDocument): string {
  const match = text.match(META_RE);
  if (match) {
    const raw = YAML.parse(match[1]) ?? {};
    const confRaw = raw.confidence ?? {};
    const overall = confRaw.overall ?? 0;
    delete confRaw.overall;

    const provRaw = raw.provenance ?? {};
    const vhRaw: any[] = raw.version_history ?? [];

    doc.metadata = {
      extractedBy: raw.extracted_by ?? "",
      extractedAt: raw.extracted_at,
      confidence: { overall, elements: confRaw },
      provenance: {
        sourceHash: provRaw.source_hash ?? "",
        extractionPipeline: provRaw.extraction_pipeline ?? [],
      },
      versionHistory: vhRaw.map((v: any) => ({
        timestamp: v.ts ?? "",
        agent: v.agent ?? "",
        action: v.action ?? "",
      })),
      extra: {},
    };

    text = text.slice(0, match.index!) + text.slice(match.index! + match[0].length);
  }
  return text;
}

function parseContent(text: string, doc: DoxDocument): void {
  const lines = text.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const stripped = line.trim();

    if (!stripped) {
      i++;
      continue;
    }

    // Heading
    const headingMatch = stripped.match(HEADING_RE);
    if (headingMatch) {
      doc.elements.push({
        type: "heading",
        level: headingMatch[1].length,
        text: headingMatch[2].trim(),
      });
      i++;
      continue;
    }

    // Code block
    const codeMatch = stripped.match(CODE_FENCE_START_RE);
    if (codeMatch) {
      const lang = codeMatch[1] || undefined;
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !CODE_FENCE_END_RE.test(lines[i].trim())) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      doc.elements.push({ type: "codeblock", code: codeLines.join("\n"), language: lang });
      continue;
    }

    // Table
    const tableMatch = stripped.match(TABLE_START_RE);
    if (tableMatch) {
      const table = parseTableBlock(lines, i, tableMatch[1] ?? "");
      i++;
      while (i < lines.length && !TABLE_END_RE.test(lines[i].trim())) i++;
      i++; // skip closing |||
      doc.elements.push(table);
      continue;
    }

    // Inline block
    const inlineMatch = stripped.match(INLINE_BLOCK_RE);
    if (inlineMatch) {
      const el = parseInlineBlock(inlineMatch[1], inlineMatch[2]);
      if (el) doc.elements.push(el);
      i++;
      continue;
    }

    // Figure
    const figMatch = stripped.match(FIGURE_RE);
    if (figMatch) {
      doc.elements.push({
        type: "figure",
        caption: figMatch[1],
        source: figMatch[2],
        figureId: figMatch[4],
      });
      i++;
      continue;
    }

    // Footnote
    const fnMatch = stripped.match(FOOTNOTE_DEF_RE);
    if (fnMatch) {
      doc.elements.push({
        type: "footnote",
        number: parseInt(fnMatch[1]),
        text: fnMatch[2],
      });
      i++;
      continue;
    }

    // List
    const listMatch = stripped.match(LIST_RE);
    if (listMatch) {
      const items: ListItem[] = [];
      while (i < lines.length) {
        const lm = lines[i].match(LIST_RE);
        if (!lm) break;
        items.push({ text: lm[3], children: [] });
        i++;
      }
      const ordered = /^\d+\./.test(listMatch[2]);
      doc.elements.push({ type: "listblock", items, ordered, start: 1 });
      continue;
    }

    // Math block
    const mathMatch = stripped.match(MATH_BLOCK_RE);
    if (mathMatch) {
      doc.elements.push({
        type: "mathblock",
        expression: mathMatch[1].trim(),
        displayMode: true,
      });
      i++;
      continue;
    }

    // Paragraph
    const paraLines: string[] = [];
    while (i < lines.length) {
      const ln = lines[i].trim();
      if (
        !ln ||
        HEADING_RE.test(ln) ||
        TABLE_START_RE.test(ln) ||
        CODE_FENCE_START_RE.test(ln) ||
        INLINE_BLOCK_RE.test(ln) ||
        FIGURE_RE.test(ln) ||
        FOOTNOTE_DEF_RE.test(ln) ||
        LIST_RE.test(ln)
      )
        break;
      paraLines.push(ln);
      i++;
    }
    if (paraLines.length > 0) {
      doc.elements.push({ type: "paragraph", text: paraLines.join(" ") });
    } else {
      i++;
    }
  }
}

function parseTableBlock(lines: string[], start: number, attrsStr: string): Table {
  const attrs = parseAttrs(attrsStr);
  const table: Table = {
    type: "table",
    rows: [],
    caption: attrs.caption,
    nested: attrsStr.toLowerCase().includes("nested"),
    tableId: attrs.id,
    elementId: attrs.id,
  };

  let i = start + 1;
  let headerPassed = false;

  while (i < lines.length) {
    const stripped = lines[i].trim();
    if (TABLE_END_RE.test(stripped)) break;

    if (SEPARATOR_RE.test(stripped) && stripped.includes("|")) {
      headerPassed = true;
      i++;
      continue;
    }

    const rowMatch = stripped.match(TABLE_ROW_RE);
    if (rowMatch) {
      const cellTexts = rowMatch[1].split("|").map((c) => c.trim());
      const cells: TableCell[] = cellTexts.map((text) => ({
        text,
        isHeader: !headerPassed,
        colspan: 1,
        rowspan: 1,
      }));
      const row: TableRow = { cells, isHeader: !headerPassed };
      table.rows.push(row);
    }

    i++;
  }

  return table;
}

function parseInlineBlock(blockType: string, attrsStr: string): Element | null {
  const attrs = parseAttrs(attrsStr);
  // Also parse unquoted key=value
  for (const m of attrsStr.matchAll(/([\w-]+)=(\S+)/g)) {
    const key = m[1];
    const val = m[2].replace(/"/g, "");
    if (!(key in attrs)) attrs[key] = val;
  }

  if (blockType === "form") {
    return {
      type: "formfield",
      fieldName: attrs.field ?? "",
      fieldType: (attrs.type ?? "text") as FormFieldType,
      value: attrs.value ?? "",
    };
  }
  if (blockType === "chart") {
    return {
      type: "chart",
      chartType: attrs.type ?? "bar",
      dataRef: attrs["data-ref"],
      xField: attrs.x,
      yField: attrs.y,
      extra: {},
    };
  }
  if (blockType === "annotation") {
    return {
      type: "annotation",
      annotationType: attrs.type ?? "handwriting",
      text: attrs.text ?? "",
      confidence: attrs.confidence ? parseFloat(attrs.confidence) : undefined,
    };
  }
  return null;
}

function parseAttrs(str: string): Record<string, string> {
  const result: Record<string, string> = {};
  const re = new RegExp(ATTR_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(str)) !== null) {
    result[m[1]] = m[2];
  }
  return result;
}

export default parseDox;
