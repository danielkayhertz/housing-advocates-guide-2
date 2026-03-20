# 2026 Guide for Chicago Housing Advocates — Web Edition

A comprehensive, single-page web reference covering Chicago's housing policy landscape: institutions, funding sources, programs, ordinances, and advocacy resources.

**Published by [Impact for Equity](https://impactforequity.org)**

## Quick Start

Open `chicago-housing-guide-2.0.html` in any browser. The file is fully self-contained — no server, build step, or internet connection required.

## Build Pipeline

The HTML is generated from a Word document (.docx) through a three-stage pipeline:

1. **Extract text** — `python extract_docx.py` parses the DOCX XML directly (stdlib only, no pip installs) and outputs `advocates_guide_extracted.md`
2. **Extract images** — `python extract_images.py` pulls embedded images from the DOCX into `images/` with a manifest
3. **Build HTML** — `python build_guide.py` converts the extracted markdown into the final self-contained HTML page

The DOCX source file is not included in this repository due to size. To rebuild, place the source DOCX in this directory and update the filename constants at the top of `extract_docx.py` and `build_guide.py`.

## Features

- Hash-based navigation across 8 sections (Home, Introduction, Parts 1-7)
- Full-text search with type-ahead and context snippets
- Category filters on Institutions and Programs
- Responsive layout with sticky TOC bar
- Collapsible per-section table of contents
- Cross-reference links between entries
- Print-optimized styles
- Back-to-top button

## Project Structure

```
chicago-housing-guide-2.0.html  — Production output (open in browser)
build_guide.py                  — HTML build script
extract_docx.py                 — DOCX-to-Markdown extraction
extract_images.py               — DOCX image extraction + manifest
advocates_guide_extracted.md    — Extracted markdown (intermediate)
images/                         — Extracted images + manifest
CLAUDE.md                       — Claude Code project instructions
```

## License

Content is published by Impact for Equity. Contact the organization for reuse permissions.
