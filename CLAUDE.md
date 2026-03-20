# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Folder Is

This folder is the production pipeline for the **Guide for Chicago Housing Advocates** web rebuild. It contains:
- The source `.docx` (print-layout, two-column, ~12 MB)
- A ready-to-read print PDF
- `extract_docx.py` — stdlib-only DOCX→Markdown extraction script (no pip installs)
- `advocates_guide_extracted.md` — the output: clean body text ready for a web CMS

## Running the Extraction

```bash
python extract_docx.py
```

Run from this directory. Input and output filenames are hardcoded at the top of the script:

```python
DOCX   = "Advocate's Guide_3.13.26_digital version.docx"
OUTPUT = "advocates_guide_extracted.md"
```

Change these constants to process a different file. The script logs extraction stats to stdout (hyperlinks resolved, images found, sidebar patterns collected).

## Architecture of extract_docx.py

The script reads the `.docx` ZIP archive directly via `zipfile` + `xml.etree.ElementTree` — no `python-docx` or other libraries.

**Pre-pass — load supporting data:**
- `word/_rels/document.xml.rels` → `{rId: url}` for hyperlinks and images
- `word/styles.xml` → style inheritance map (walks `basedOn` chain to resolve effective bold/italic per paragraph style)
- `word/numbering.xml` → `{numId: {ilvl: numFmt}}` to drive `- ` vs `1. ` list prefixes

**Section map** (`build_section_map`): walks `document.xml` body children and tags each paragraph with its section index. Sections are delimited by `<w:sectPr>` embedded in paragraph `<w:pPr>` — each sectPr *ends* the section up to and including that paragraph. Sections with `<w:cols num="2">` are two-column; others are single-column.

**ToC detection** (`find_toc_sections`): finds paragraphs containing `<w:instrText>` with "TOC" or a "Table of Contents" heading — marks the enclosing section for omission.

**Two-column sidebar exclusion** — the hardest problem, solved in two layers:

1. **State machine** (`extract_document` main loop): tracks `in_sidebar` (bool). Two-column sections start in the left (sidebar) column. Column breaks (`<w:br w:type="column"/>`) transition columns using a heading-based rule:
   - Colbreak + heading style → entering body (right column), `in_sidebar = False`
   - Colbreak + non-heading style → entering sidebar (left column), `in_sidebar = True`
   This is more reliable than a simple toggle because Word only emits explicit colbreaks for forced transitions; page-boundary right→left wraps have no XML marker.

2. **Text pattern filter** (`build_sidebar_text_set`): a pre-pass collects raw text of all confirmed sidebar paragraphs (initial sidebar blocks before the first heading-colbreak in each two-column section). During extraction, any body-state paragraph whose raw text is in this set is silently suppressed — this catches sidebar nav content that leaks due to implicit page-boundary column switches.

**Paragraph processing** (`process_paragraph_segment`): converts a list of run elements to a Markdown line. Applies heading prefix (`#`/`##`/`###`/`####`), list prefix from numbering lookup, bold/italic via style inheritance, hyperlinks as `[text](url)`, and images as `<!-- [image: word/media/imageN.png] -->`.

**Bold/italic merging**: adjacent runs with the same formatting produce `**foo****bar**` — a post-processing regex collapses `****` → `` and `******` → `` to produce clean `**foobar**`.

## Key Document Facts (for debugging or re-running)

- **Two-column sections**: left col = 1,872 twips (sidebar nav), right col = 6,048 twips (body). `eq=0` (unequal columns).
- **Headings always appear in the body (right) column.** If a heading is missing from output, check whether its column break was incorrectly classified.
- **Sidebar nav** is a repeating navigation list (same text on every page, never uses Heading styles). The sidebar text set collects ~180 patterns.
- **Headers/footers** are in separate XML files (`word/header*.xml`) and never appear in `document.xml` body — no filtering needed.
- **No footnotes** in this document (the footnotes.xml is empty).
- **Tracked changes**: deletions (`<w:del>`) are skipped; insertions (`<w:ins>`) are accepted.
