# Handoff — 2026-03-14

## Session Topic
Advocate's Guide web_version_2.0: implemented `extract_images.py` — extracts images from DOCX and generates image manifest

## Key Decisions
- 17 images binary-extracted from DOCX ZIP into `images/`; 12 have manifest entries (5 from filtered sidebar/ToC sections are in the folder but not in the manifest)
- `image3.png` classified explanatory (after first heading); may need revisiting if it's a cover illustration
- Windows cp1252 print encoding fixed in-script (use ASCII instead of Unicode in print statements)

## Open Follow-ups
- [ ] Spot-check extracted PNGs for full resolution / no corruption
- [ ] Decide how images integrate into web HTML — inline `<img>` replacing placeholders, or separate asset pipeline?
- [ ] Revisit `image3.png` classification (decorative vs. explanatory)

## Context for Next Session
`web_version_2.0/` now has `extract_docx.py` (markdown extraction, existing) and `extract_images.py` (image extraction + manifest, new). Both run from the `web_version_2.0/` directory. The manifest at `images/image_manifest.md` has 12 entries with heading context and surrounding text — ready to inform how images are placed in the web layout.
