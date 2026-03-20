"""
extract_images.py — Extract embedded images from DOCX and generate image manifest.

Reads the .docx as a ZIP, copies all files from word/media/ into images/,
then parses advocates_guide_extracted.md to build a manifest mapping each
image to its heading context and surrounding text.

Run from web_version_2.0/:
    python extract_images.py
"""

import os
import re
import shutil
import zipfile
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

DOCX         = "Advocate's Guide_3.13.26_digital version.docx"
EXTRACTED_MD = "advocates_guide_extracted.md"
OUTPUT_DIR   = "images"

# ── Step 1: Extract media from DOCX ZIP ───────────────────────────────────────

def extract_media(docx_path: str, output_dir: str) -> list[str]:
    """Binary-copy every file under word/media/ to output_dir."""
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    extracted = []
    with zipfile.ZipFile(docx_path, "r") as zf:
        media_names = [n for n in zf.namelist() if n.startswith("word/media/")]
        for name in sorted(media_names):
            filename = Path(name).name
            dest = out / filename
            with zf.open(name) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(filename)

    return extracted

# ── Step 2: Parse MD for image context ────────────────────────────────────────

IMAGE_RE   = re.compile(r"<!--\s*\[image:\s*word/media/([^\]]+)\]\s*-->")
HEADING_RE = re.compile(r"^#{1,6}\s")

def parse_md_for_image_context(md_path: str) -> list[dict]:
    """
    Returns a list of dicts, one per image placeholder found in the MD:
      {
        "filename": str,
        "line_number": int,   # 1-based
        "heading": str | None,
        "context_before": list[str],
        "context_after": list[str],
      }
    """
    with open(md_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Strip trailing newlines for easier processing
    lines = [l.rstrip("\n") for l in lines]

    # Find all image placeholder positions
    image_positions = []
    for i, line in enumerate(lines):
        m = IMAGE_RE.search(line)
        if m:
            image_positions.append((i, m.group(1)))

    results = []
    for idx, filename in image_positions:
        # ── Nearest preceding heading ──────────────────────────────────────
        heading = None
        for j in range(idx - 1, -1, -1):
            if HEADING_RE.match(lines[j]) and lines[j].strip() not in ("#", ""):
                heading = lines[j].strip()
                break

        # ── Up to 3 non-empty, non-comment body lines before placeholder ──
        before = []
        for j in range(idx - 1, -1, -1):
            if len(before) == 3:
                break
            line = lines[j].strip()
            if not line:
                continue
            if IMAGE_RE.search(line):
                continue
            if HEADING_RE.match(line):
                continue
            before.insert(0, line)

        # ── Up to 3 non-empty, non-comment body lines after placeholder ───
        after = []
        for j in range(idx + 1, len(lines)):
            if len(after) == 3:
                break
            line = lines[j].strip()
            if not line:
                continue
            if IMAGE_RE.search(line):
                continue
            if HEADING_RE.match(line):
                continue
            after.append(line)

        results.append({
            "filename":      filename,
            "line_number":   idx + 1,   # 1-based
            "heading":       heading,
            "context_before": before,
            "context_after":  after,
        })

    return results

# ── Step 3: Classify ──────────────────────────────────────────────────────────

def find_first_heading_line(md_path: str) -> int:
    """Return 1-based line number of the first non-empty heading in the MD."""
    with open(md_path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            stripped = line.strip()
            if HEADING_RE.match(stripped) and stripped not in ("#", ""):
                return i
    return 0

def classify(entry: dict, first_heading_line: int) -> str:
    """
    decorative: front-matter images (before first heading) OR empty context
    explanatory: everything else
    """
    if entry["line_number"] < first_heading_line:
        return "decorative"
    surrounding = entry["context_before"] + entry["context_after"]
    if not any(t.strip() for t in surrounding):
        return "decorative"
    return "explanatory"

# ── Step 4: Write manifest ────────────────────────────────────────────────────

def write_manifest(entries: list[dict], output_dir: str, md_filename: str) -> str:
    manifest_path = Path(output_dir) / "image_manifest.md"

    lines = [
        "# Image Manifest — Guide for Chicago Housing Advocates",
        "",
        f"Generated from `{md_filename}`. Each entry links an image file",
        "to its location in the extracted text and provides surrounding context.",
        "",
        "---",
        "",
    ]

    for e in entries:
        filename      = e["filename"]
        classification = e["classification"]
        line_num       = e["line_number"]
        heading        = e["heading"] or "*(front matter — no heading)*"
        before_text    = " / ".join(e["context_before"]) if e["context_before"] else "*(none)*"
        after_text     = " / ".join(e["context_after"])  if e["context_after"]  else "*(none)*"

        lines += [
            f"## {filename}",
            f"- **File**: `{output_dir}/{filename}`",
            f"- **Classification**: {classification}",
            f"- **Source line**: {line_num}",
            f"- **Associated heading**: {heading}",
            f"- **Context before**: {before_text}",
            f"- **Context after**: {after_text}",
            "",
        ]

    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return str(manifest_path)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # 1. Extract media
    print(f"Extracting media from {DOCX!r} -> {OUTPUT_DIR}/")
    extracted_files = extract_media(DOCX, OUTPUT_DIR)
    print(f"  {len(extracted_files)} file(s) extracted: {', '.join(extracted_files)}")

    # 2. Parse MD for image context
    print(f"\nParsing image placeholders in {EXTRACTED_MD!r}…")
    entries = parse_md_for_image_context(EXTRACTED_MD)
    print(f"  {len(entries)} image placeholder(s) found")

    # 3. Classify
    first_heading = find_first_heading_line(EXTRACTED_MD)
    print(f"  First heading at line {first_heading}")
    for e in entries:
        e["classification"] = classify(e, first_heading)

    decorative  = [e for e in entries if e["classification"] == "decorative"]
    explanatory = [e for e in entries if e["classification"] == "explanatory"]
    print(f"  Decorative: {len(decorative)}, Explanatory: {len(explanatory)}")

    # 4. Write manifest
    manifest_path = write_manifest(entries, OUTPUT_DIR, EXTRACTED_MD)
    print(f"\nManifest written -> {manifest_path}")

    # Summary
    print("\n-- Summary --------------------------------------------------")
    for e in entries:
        flag = "D" if e["classification"] == "decorative" else "E"
        print(f"  [{flag}] line {e['line_number']:>4}  {e['filename']}")
    print(f"\nDone. {len(extracted_files)} image(s) in {OUTPUT_DIR}/  |  "
          f"{len(entries)} manifest entries  |  "
          f"{len(decorative)} decorative / {len(explanatory)} explanatory")

if __name__ == "__main__":
    main()
