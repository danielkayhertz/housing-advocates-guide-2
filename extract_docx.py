"""
extract_docx.py
Extract body text from Advocate's Guide .docx to Markdown.
Handles: two-column layout (sidebar exclusion), headings, bold/italic,
hyperlinks, images, lists, tracked changes, no footnotes in this doc.
Uses only stdlib: zipfile, xml.etree.ElementTree
"""

import zipfile
import xml.etree.ElementTree as ET
import re
import sys

DOCX = "Advocate's Guide_3.13.26_digital version.docx"
OUTPUT = "advocates_guide_extracted.md"

# ── Namespaces ──────────────────────────────────────────────────────────────
W  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A  = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"

def wt(tag): return f"{{{W}}}{tag}"
def rt(tag): return f"{{{R}}}{tag}"
def at(tag): return f"{{{A}}}{tag}"

NS = {"w": W, "r": R, "a": A, "pic": PIC}

# ── 1. Load supporting files ─────────────────────────────────────────────────

def load_rels(zf):
    """Returns {rId: target} for hyperlinks and images."""
    rels = {}
    with zf.open("word/_rels/document.xml.rels") as f:
        root = ET.fromstring(f.read())
    for r in root:
        rid = r.get("Id")
        target = r.get("Target", "")
        rels[rid] = target
    return rels


def load_styles(zf):
    """
    Returns:
      style_map: {styleId: {"bold": bool|None, "italic": bool|None,
                             "basedOn": str|None, "name": str}}
      doc_defaults: {"bold": bool, "italic": bool}
    """
    with zf.open("word/styles.xml") as f:
        root = ET.fromstring(f.read())

    def get_rpr_flags(rpr_el):
        """Extract bold/italic from a w:rPr element; returns (bold, italic) each True/False/None."""
        if rpr_el is None:
            return None, None
        # <w:b/> or <w:b w:val="0"/> — absence means inherit
        b_el = rpr_el.find(f"{{{W}}}b")
        i_el = rpr_el.find(f"{{{W}}}i")
        def flag(el):
            if el is None:
                return None
            val = el.get(f"{{{W}}}val", "true")
            return val.lower() not in ("0", "false", "off")
        return flag(b_el), flag(i_el)

    # Document defaults
    dd_rpr = root.find(f".//{{{W}}}docDefaults/{{{W}}}rPrDefault/{{{W}}}rPr")
    def_b, def_i = get_rpr_flags(dd_rpr)
    doc_defaults = {"bold": bool(def_b), "italic": bool(def_i)}

    style_map = {}
    for style_el in root.findall(f"{{{W}}}style"):
        sid = style_el.get(f"{{{W}}}styleId")
        if not sid:
            continue
        name_el = style_el.find(f"{{{W}}}name")
        name = name_el.get(f"{{{W}}}val", "") if name_el is not None else ""
        based_el = style_el.find(f"{{{W}}}basedOn")
        based = based_el.get(f"{{{W}}}val") if based_el is not None else None
        rpr = style_el.find(f"{{{W}}}rPr")
        b, i = get_rpr_flags(rpr)
        style_map[sid] = {"bold": b, "italic": i, "basedOn": based, "name": name}

    return style_map, doc_defaults


def resolve_style_flag(flag_name, style_id, style_map, doc_defaults):
    """Walk basedOn chain to resolve effective bold or italic for a style."""
    visited = set()
    sid = style_id
    while sid and sid not in visited:
        visited.add(sid)
        entry = style_map.get(sid)
        if entry is None:
            break
        val = entry.get(flag_name)
        if val is not None:
            return val
        sid = entry.get("basedOn")
    return doc_defaults.get(flag_name, False)


def load_numbering(zf):
    """Returns {numId: {ilvl: numFmt_string}}."""
    try:
        with zf.open("word/numbering.xml") as f:
            root = ET.fromstring(f.read())
    except KeyError:
        return {}

    # Map abstractNumId -> {ilvl -> numFmt}
    abstract_map = {}
    for an in root.findall(f"{{{W}}}abstractNum"):
        aid = an.get(f"{{{W}}}abstractNumId")
        lvls = {}
        for lvl in an.findall(f"{{{W}}}lvl"):
            ilvl = int(lvl.get(f"{{{W}}}ilvl", 0))
            nf_el = lvl.find(f"{{{W}}}numFmt")
            nf = nf_el.get(f"{{{W}}}val", "bullet") if nf_el is not None else "bullet"
            lvls[ilvl] = nf
        abstract_map[aid] = lvls

    # Map numId -> abstractNumId (with possible overrides)
    num_map = {}
    for nm in root.findall(f"{{{W}}}num"):
        nid = nm.get(f"{{{W}}}numId")
        an_ref = nm.find(f"{{{W}}}abstractNumId")
        if an_ref is None:
            continue
        aid = an_ref.get(f"{{{W}}}val")
        base = dict(abstract_map.get(aid, {}))
        # Level overrides
        for lo in nm.findall(f"{{{W}}}lvlOverride"):
            ilvl = int(lo.get(f"{{{W}}}ilvl", 0))
            lvl_el = lo.find(f"{{{W}}}lvl")
            if lvl_el is not None:
                nf_el = lvl_el.find(f"{{{W}}}numFmt")
                if nf_el is not None:
                    base[ilvl] = nf_el.get(f"{{{W}}}val", "bullet")
        num_map[nid] = base

    return num_map


# ── 2. Build section map ─────────────────────────────────────────────────────

def build_section_map(paras):
    """
    Returns list of (section_index, num_cols) per paragraph index.
    sectPr in pPr ends the section UP TO AND INCLUDING that paragraph.
    """
    sections = []  # list of (end_idx, num_cols)
    for i, p in enumerate(paras):
        tag = p.tag.split("}")[1] if "}" in p.tag else p.tag
        if tag == "p":
            ppr = p.find(f"{{{W}}}pPr")
            if ppr is not None:
                sect = ppr.find(f"{{{W}}}sectPr")
                if sect is not None:
                    cols = sect.find(f"{{{W}}}cols")
                    num = int(cols.get(f"{{{W}}}num", 1)) if cols is not None else 1
                    sections.append((i, num))
        elif tag == "sectPr":
            # Final body-level sectPr
            cols = p.find(f"{{{W}}}cols")
            num = int(cols.get(f"{{{W}}}num", 1)) if cols is not None else 1
            sections.append((i, num))

    # Assign section index to each paragraph
    para_section = []
    sec_idx = 0
    for i in range(len(paras)):
        if sec_idx < len(sections) and i > sections[sec_idx][0]:
            sec_idx += 1
        para_section.append(sec_idx)

    return para_section, sections


def get_section_cols(sec_idx, sections):
    if sec_idx >= len(sections):
        return 1
    return sections[sec_idx][1]


# ── 3. Detect ToC section ────────────────────────────────────────────────────

def find_toc_sections(paras, para_section, sections):
    """
    Return set of section indices that are ToC sections.
    Detect by: presence of w:fldChar begin + instrText containing 'TOC',
    or presence of NoSpacing paragraphs with page-number-like content
    near a 'Table of Contents' heading (backup heuristic).
    """
    toc_sections = set()

    # Primary: find paragraphs with TOC field
    in_toc_field = False
    for i, p in enumerate(paras):
        tag = p.tag.split("}")[1] if "}" in p.tag else p.tag
        if tag != "p":
            continue
        for fc in p.findall(f".//{{{W}}}fldChar"):
            ftype = fc.get(f"{{{W}}}fldCharType", "")
            if ftype == "begin":
                in_toc_field = True
            elif ftype == "end":
                in_toc_field = False
        for it in p.findall(f".//{{{W}}}instrText"):
            if it.text and "TOC" in it.text:
                toc_sections.add(para_section[i])
                print(f"  [ToC detect] Para {i} in section {para_section[i]}: instrText='{it.text.strip()[:60]}'")

    # Secondary: find 'Table of Contents' heading and mark its section
    for i, p in enumerate(paras):
        tag = p.tag.split("}")[1] if "}" in p.tag else p.tag
        if tag != "p":
            continue
        texts = [r.text for r in p.findall(f".//{{{W}}}t") if r.text]
        full = "".join(texts).strip()
        if full == "Table of Contents":
            sec = para_section[i]
            toc_sections.add(sec)
            print(f"  [ToC detect] Para {i} in section {sec}: heading 'Table of Contents'")

    if toc_sections:
        print(f"  [ToC] Omitting sections: {sorted(toc_sections)}")
    return toc_sections


# ── 4. Run extraction ────────────────────────────────────────────────────────

def get_para_style(p):
    ppr = p.find(f"{{{W}}}pPr")
    if ppr is None:
        return None
    ps = ppr.find(f"{{{W}}}pStyle")
    if ps is None:
        return None
    return ps.get(f"{{{W}}}val")


def get_num_info(p):
    """Returns (numId, ilvl) or (None, None)."""
    ppr = p.find(f"{{{W}}}pPr")
    if ppr is None:
        return None, None
    num_pr = ppr.find(f"{{{W}}}numPr")
    if num_pr is None:
        return None, None
    nid_el = num_pr.find(f"{{{W}}}numId")
    ilvl_el = num_pr.find(f"{{{W}}}ilvl")
    nid = nid_el.get(f"{{{W}}}val") if nid_el is not None else None
    ilvl = int(ilvl_el.get(f"{{{W}}}val", 0)) if ilvl_el is not None else 0
    return nid, ilvl


def resolve_bold_italic(run_rpr, para_style, style_map, doc_defaults):
    """
    Resolve effective bold and italic for a run.
    Order: run rPr > para style > style chain > doc defaults.
    """
    def flag(el_name, rpr):
        if rpr is None:
            return None
        el = rpr.find(f"{{{W}}}{el_name}")
        if el is None:
            return None
        val = el.get(f"{{{W}}}val", "true")
        return val.lower() not in ("0", "false", "off")

    # Run-level
    run_b = flag("b", run_rpr)
    run_i = flag("i", run_rpr)

    # If run explicitly sets bold/italic, use it
    if run_b is not None and run_i is not None:
        return run_b, run_i

    # Style chain fallback
    style_b = resolve_style_flag("bold", para_style, style_map, doc_defaults) if para_style else doc_defaults.get("bold", False)
    style_i = resolve_style_flag("italic", para_style, style_map, doc_defaults) if para_style else doc_defaults.get("italic", False)

    b = run_b if run_b is not None else style_b
    i = run_i if run_i is not None else style_i
    return b, i


def extract_run_text(run, para_style, style_map, doc_defaults, rels):
    """
    Extract text from a single w:r, applying bold/italic.
    Returns markdown-formatted string.
    Skips deleted content (handled upstream).
    """
    # Check for image
    for drawing in run.findall(f"{{{W}}}drawing"):
        for blip in drawing.iter(f"{{{A}}}blip"):
            rid = blip.get(f"{{{R}}}embed")
            target = rels.get(rid, "unknown")
            # Normalize target to just filename
            fname = target.split("/")[-1] if "/" in target else target
            return f"\n<!-- [image: word/media/{fname}] -->\n"

    # Text elements
    texts = []
    for t in run.findall(f"{{{W}}}t"):
        if t.text:
            texts.append(t.text)
    text = "".join(texts)
    if not text:
        return ""

    rpr = run.find(f"{{{W}}}rPr")
    bold, italic = resolve_bold_italic(rpr, para_style, style_map, doc_defaults)

    # Apply formatting (avoid double-wrapping spaces)
    stripped = text.strip()
    if stripped:
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        mid = text.strip()
        if bold and italic:
            mid = f"***{mid}***"
        elif bold:
            mid = f"**{mid}**"
        elif italic:
            mid = f"*{mid}*"
        text = lead + mid + trail

    return text


def process_paragraph_segment(p, runs, para_style, style_map, doc_defaults, rels, num_map):
    """
    Given a list of run elements (a segment of the paragraph),
    return the Markdown line(s) for them.
    """
    # Style → heading prefix
    heading_prefix = {
        "Heading1": "# ",
        "Heading2": "## ",
        "Heading3": "### ",
        "Heading4": "#### ",
        "Title": "# ",
    }
    prefix = heading_prefix.get(para_style, "")

    # List prefix
    list_prefix = ""
    nid, ilvl = get_num_info(p)
    if nid and nid in num_map:
        fmt = num_map[nid].get(ilvl, "bullet")
        indent = "  " * ilvl
        if fmt == "bullet":
            list_prefix = indent + "- "
        else:
            list_prefix = indent + "1. "

    # Gather text from runs
    parts = []
    for run in runs:
        tag = run.tag.split("}")[1] if "}" in run.tag else run.tag
        if tag == "r":
            parts.append(extract_run_text(run, para_style, style_map, doc_defaults, rels))
        elif tag == "hyperlink":
            rid = run.get(f"{{{R}}}id")
            anchor = run.get(f"{{{W}}}anchor")
            link_texts = []
            for sub_run in run.findall(f"{{{W}}}r"):
                link_texts.append(extract_run_text(sub_run, para_style, style_map, doc_defaults, rels))
            link_text = "".join(link_texts)
            if anchor:
                # Internal bookmark → plain text
                parts.append(link_text)
            elif rid and rid in rels:
                url = rels[rid]
                parts.append(f"[{link_text}]({url})")
            else:
                parts.append(link_text)

    text = "".join(parts).strip()
    if not text and not prefix and not list_prefix:
        return ""

    # Merge adjacent bold/italic markers Word splits across runs:
    # **foo****bar** → **foobar**, ***foo******bar*** → ***foobar***
    # Apply repeatedly until stable
    for _ in range(5):
        new = re.sub(r'\*{3}\*{3}', '', text)   # ****** → (merge bold+italic)
        new = re.sub(r'\*{2}\*{2}', '', new)    # **** → (merge bold)
        new = re.sub(r'\*\*\s+\*\*', ' ', new)  # ** text** →  text (orphaned markers)
        if new == text:
            break
        text = new

    return (prefix or list_prefix) + text


def split_paragraph_at_colbreak(p):
    """
    Walk direct children of p (runs, hyperlinks, bookmarks, etc.)
    Split at the first w:r containing w:br[@w:type='column'].
    Returns (pre_runs, post_runs, break_at_start).
    break_at_start = True if the colbreak is the very first meaningful run.
    """
    children = list(p)
    # Skip pPr
    content_children = [c for c in children if c.tag != f"{{{W}}}pPr"]

    break_idx = None
    for ci, child in enumerate(content_children):
        tag = child.tag.split("}")[1] if "}" in child.tag else child.tag
        if tag == "r":
            br = child.find(f"{{{W}}}br[@{{{W}}}type='column']")
            if br is not None:
                break_idx = ci
                break

    if break_idx is None:
        return content_children, [], False

    # Check if break_at_start: the run containing the break has no text before break
    break_run = content_children[break_idx]
    pre_break_run_children = list(break_run)
    has_text_before = False
    for rc in pre_break_run_children:
        rtag = rc.tag.split("}")[1] if "}" in rc.tag else rc.tag
        if rtag == "br" and rc.get(f"{{{W}}}type") == "column":
            break
        if rtag == "t" and rc.text:
            has_text_before = True
            break

    pre_runs = content_children[:break_idx]
    post_runs = content_children[break_idx + 1:]

    # If there's text before the break in the break run, include it in pre
    if has_text_before:
        # Create a synthetic run from the text before the break
        # Actually just collect them: everything before the <w:br> in the run
        pre_break_parts = []
        post_break_parts = []
        found_break = False
        for rc in pre_break_run_children:
            rtag = rc.tag.split("}")[1] if "}" in rc.tag else rc.tag
            if rtag == "br" and rc.get(f"{{{W}}}type") == "column":
                found_break = True
                continue
            if not found_break:
                pre_break_parts.append(rc)
            else:
                post_break_parts.append(rc)
        # Wrap in synthetic run elements
        if pre_break_parts:
            syn_pre = ET.Element(f"{{{W}}}r")
            rpr = break_run.find(f"{{{W}}}rPr")
            if rpr is not None:
                syn_pre.append(rpr)
            for x in pre_break_parts:
                syn_pre.append(x)
            pre_runs = pre_runs + [syn_pre]
        if post_break_parts:
            syn_post = ET.Element(f"{{{W}}}r")
            rpr = break_run.find(f"{{{W}}}rPr")
            if rpr is not None:
                syn_post.append(rpr)
            for x in post_break_parts:
                syn_post.append(x)
            post_runs = [syn_post] + post_runs

    break_at_start = not has_text_before
    return pre_runs, post_runs, break_at_start


def is_deleted_run(run):
    """Check if run is inside a w:del element (handled by skipping w:del children)."""
    return False  # We skip w:del elements at iteration level


HEADING_STYLES = {"Heading1", "Heading2", "Heading3", "Heading4", "Title"}


def build_sidebar_text_set(paras, para_section, sections, toc_sections):
    """
    Pre-pass: collect raw text of all paragraphs that are DEFINITELY sidebar.
    These are paragraphs in 2-col sections that appear before the first
    colbreak in that section (the initial sidebar block), or after an explicit
    non-heading colbreak (which definitively enters the sidebar).

    The resulting set is used in the main loop to filter sidebar content that
    leaks into the body column due to implicit page-boundary column switches
    (Word doesn't emit a colbreak when the text wraps across page boundaries).
    """
    sidebar_texts = set()

    current_section = -1
    in_sidebar = False

    for i, p in enumerate(paras):
        tag = p.tag.split("}")[1] if "}" in p.tag else p.tag
        if tag != "p":
            continue

        sec_idx = para_section[i]
        if sec_idx in toc_sections:
            continue

        num_cols = get_section_cols(sec_idx, sections)
        is_two_col = num_cols >= 2

        if sec_idx != current_section:
            current_section = sec_idx
            in_sidebar = is_two_col  # 2-col sections start in sidebar

        if not is_two_col:
            continue

        has_colbreak = p.find(f".//{{{W}}}br[@{{{W}}}type='column']") is not None

        if has_colbreak:
            # Determine if colbreak toggles to body or sidebar
            para_style = get_para_style(p)
            if para_style in HEADING_STYLES:
                in_sidebar = False  # Heading colbreak always enters body
            else:
                in_sidebar = True   # Non-heading colbreak always enters sidebar
            # If we just entered sidebar, collect the post-break text too
            if in_sidebar:
                texts = [r.text for r in p.findall(f".//{{{W}}}t") if r.text]
                raw = "".join(texts).strip()
                if raw:
                    sidebar_texts.add(raw)
            continue

        if in_sidebar:
            # Confirmed sidebar paragraph — collect its raw text
            texts = [r.text for r in p.findall(f".//{{{W}}}t") if r.text]
            raw = "".join(texts).strip()
            if raw:
                sidebar_texts.add(raw)

    print(f"  Sidebar text patterns collected: {len(sidebar_texts)}")
    return sidebar_texts


def extract_document(docx_path):
    print(f"Opening {docx_path}...")
    with zipfile.ZipFile(docx_path) as zf:
        rels = load_rels(zf)
        style_map, doc_defaults = load_styles(zf)
        num_map = load_numbering(zf)

        with zf.open("word/document.xml") as f:
            doc_root = ET.fromstring(f.read())

    print(f"  Relationships loaded: {len(rels)} entries")
    print(f"  Styles loaded: {len(style_map)} styles")
    print(f"  Numbering: {len(num_map)} numIds")

    body = doc_root.find(f".//{{{W}}}body")
    paras = list(body)
    print(f"  Body children: {len(paras)}")

    # Section map
    para_section, sections = build_section_map(paras)

    # ToC detection
    print("Detecting ToC sections...")
    toc_sections = find_toc_sections(paras, para_section, sections)

    # Build sidebar text filter (pre-pass)
    print("Building sidebar text filter...")
    sidebar_text_set = build_sidebar_text_set(paras, para_section, sections, toc_sections)

    # Stats
    hyperlinks_total = 0
    hyperlinks_resolved = 0
    images_total = 0
    deleted_runs_skipped = 0

    # Output accumulator: list of markdown lines
    output_lines = []

    # Column state machine
    # For 2-col sections: start in left col (sidebar = True)
    # Track per-section state
    current_section = -1
    in_sidebar = False  # Start single-col as body

    print("Extracting paragraphs...")

    for i, p in enumerate(paras):
        tag = p.tag.split("}")[1] if "}" in p.tag else p.tag

        # Skip non-paragraph elements (sectPr at body level, etc.)
        if tag != "p":
            continue

        sec_idx = para_section[i]

        # Skip ToC sections
        if sec_idx in toc_sections:
            continue

        # Section change: reset column state
        if sec_idx != current_section:
            current_section = sec_idx
            num_cols = get_section_cols(sec_idx, sections)
            if num_cols >= 2:
                # Starting a new 2-col section: begin in left (sidebar) column
                in_sidebar = True
            else:
                # Single-col section: always body
                in_sidebar = False

        num_cols = get_section_cols(sec_idx, sections)
        is_two_col = num_cols >= 2

        # Check for column break
        has_colbreak = p.find(f".//{{{W}}}br[@{{{W}}}type='column']") is not None

        if has_colbreak and is_two_col:
            pre_runs, post_runs, break_at_start = split_paragraph_at_colbreak(p)
            para_style = get_para_style(p)

            if break_at_start:
                # Heading colbreak → body; non-heading colbreak → sidebar
                if para_style in HEADING_STYLES:
                    in_sidebar = False
                else:
                    in_sidebar = True

                if not in_sidebar:
                    # Now in body column — process post_runs as a full paragraph
                    text = process_paragraph_segment(p, post_runs, para_style, style_map, doc_defaults, rels, num_map)
                    if text:
                        output_lines.append(text)
                    else:
                        output_lines.append("")
                # else: entered sidebar, skip post_runs
            else:
                # Mid-paragraph break: pre-break in current column
                if not in_sidebar and pre_runs:
                    text = process_paragraph_segment(p, pre_runs, para_style, style_map, doc_defaults, rels, num_map)
                    if text:
                        output_lines.append(text)

                # Determine new column from style
                if para_style in HEADING_STYLES:
                    in_sidebar = False
                else:
                    in_sidebar = True

                # Post-break segment in new column
                if not in_sidebar and post_runs:
                    text = process_paragraph_segment(p, post_runs, para_style, style_map, doc_defaults, rels, num_map)
                    if text:
                        output_lines.append(text)
        else:
            # No column break in this paragraph
            if is_two_col and in_sidebar:
                # Sidebar content — skip
                continue

            # Also filter paragraphs that match confirmed sidebar text patterns
            # (catches sidebar content that leaked due to implicit page-boundary switches)
            if is_two_col:
                raw_texts = [r.text for r in p.findall(f".//{{{W}}}t") if r.text]
                raw = "".join(raw_texts).strip()
                if raw and raw in sidebar_text_set:
                    continue  # Suppress leaked sidebar content

            # Body paragraph (or single-col)
            para_style = get_para_style(p)

            # Collect child elements, skipping w:del
            body_runs = []
            for child in p:
                ctag = child.tag.split("}")[1] if "}" in child.tag else child.tag
                if ctag in ("pPr", "bookmarkStart", "bookmarkEnd", "proofErr"):
                    continue
                if ctag == "del":
                    # Count deleted runs
                    deleted_runs_skipped += len(child.findall(f"{{{W}}}r"))
                    continue
                if ctag == "ins":
                    # Accept inserted content
                    body_runs.extend(list(child))
                    continue
                body_runs.append(child)

            # Count hyperlinks for stats
            for child in body_runs:
                ctag = child.tag.split("}")[1] if "}" in child.tag else child.tag
                if ctag == "hyperlink":
                    hyperlinks_total += 1
                    rid = child.get(f"{{{R}}}id")
                    if rid and rid in rels:
                        hyperlinks_resolved += 1
                # Count images
                for drawing in child.iter(f"{{{W}}}drawing"):
                    for blip in drawing.iter(f"{{{A}}}blip"):
                        images_total += 1

            text = process_paragraph_segment(p, body_runs, para_style, style_map, doc_defaults, rels, num_map)
            output_lines.append(text)

    # Post-process: collapse excessive blank lines
    result_lines = []
    blank_count = 0
    for line in output_lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                result_lines.append("")
        else:
            blank_count = 0
            result_lines.append(line)

    # Final output
    result = "\n".join(result_lines).strip() + "\n"

    print(f"\n=== Extraction Stats ===")
    print(f"  Hyperlinks: {hyperlinks_resolved}/{hyperlinks_total} resolved")
    print(f"  Images placeholdered: {images_total}")
    print(f"  Deleted runs skipped: {deleted_runs_skipped}")
    print(f"  Output lines: {len(result_lines)}")
    print(f"  Output words (approx): {len(result.split())}")

    return result


def main():
    result = extract_document(DOCX)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()
