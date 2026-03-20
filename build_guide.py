#!/usr/bin/env python3
"""
build_guide.py - Build script for the 2026 Guide for Chicago Housing Advocates v2.0

Parses advocates_guide_extracted.md, inlines HTML graphics and images,
and emits a single self-contained chicago-housing-guide-2.0.html file.

Security note: All content is build-time static from trusted source files.
No user-generated content is rendered at runtime.

Usage: python build_guide.py
"""

import re
import os
import sys
import base64
import io
from html import escape as html_escape

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MD_FILE = os.path.join(SCRIPT_DIR, 'advocates_guide_extracted.md')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'chicago-housing-guide-2.0.html')
IMAGES_DIR = os.path.join(SCRIPT_DIR, 'images')
GRAPHICS_DIR = os.path.join(PROJECT_DIR, 'graphics')
LOGOS_DIR = os.path.join(PROJECT_DIR, 'impact-for-equity-brand', 'assets', 'logos')

HERO_IMAGE = os.path.join(IMAGES_DIR, 'image3.png')
DIVIDER_IMAGE = os.path.join(IMAGES_DIR, 'image8.png')
LOGO_IMAGE = os.path.join(LOGOS_DIR, 'logo-horizontal.png')

MAX_IMAGE_WIDTH = 900  # Resize hero to keep file size down

# Part anchors: (regex, part_id, title, chapter_number)
PART_ANCHORS = [
    (r'^\*\*Part 1:', 'institutions', 'Institutions and Organizations', '01'),
    (r'^\*\*Part 2:', 'funding', 'Funding Sources', '02'),
    (r'^## \*\*Part 3:', 'programs', 'Programs', '03'),
    (r'^## \*\*Part 4:', 'ordinances', 'Significant Ordinances and Laws', '04'),
    (r'^## \*\*Part 5:', 'legislative', 'How City Ordinances and Budgets are Passed', '05'),
    (r'^## \*\*Part 6:', 'resources', 'Chicago Housing and Advocacy Resources', '06'),
    (r'^## \*\*Part 7:', 'glossary', 'Glossary', '07'),
]

# Category headings per Part (H2 text -> category slug)
CATEGORY_MAP = {
    'institutions': {
        'City of Chicago': 'city-of-chicago',
        'Other City- and County-Based Organizations': 'other-city-county',
        'State': 'state',
        'Private Organizations': 'private-organizations',
    },
    'programs': {
        'Homeownership Production and Purchase Assistance': 'homeownership',
        'Rental Production and Assistance for Renters': 'rental',
        'Rental Production and Assistance for Renters – Department of Housing': 'rental',
        'Other Administrating Agencies': 'rental',
        'Rehabilitation and Preservation': 'rehabilitation',
        'Service Centers': 'service-centers',
    },
}

CATEGORY_LABELS = {
    'institutions': [
        ('city-of-chicago', 'City of Chicago'),
        ('other-city-county', 'Other City/County'),
        ('state', 'State'),
        ('private-organizations', 'Private Organizations'),
    ],
    'programs': [
        ('homeownership', 'Homeownership & Purchase'),
        ('rental', 'Rental Production & Assistance'),
        ('rehabilitation', 'Rehab & Preservation'),
        ('service-centers', 'Service Centers'),
    ],
}

# Cross-reference aliases (from build_html.py lines 76-161)
ALIASES = {
    'department-of-housing-doh': 'doh',
    'department-of-planning-and-development-dpd': 'dpd',
    'department-of-buildings-dob': 'dob',
    'department-of-family-and-support-services-dfss': 'dfss',
    'department-of-public-health-cdph': 'cdph',
    'mayors-office-for-people-with-disabilities-mopd': 'mopd',
    'department-of-the-environment-doe': 'doe',
    'mayors-office': 'mayors-office',
    'chicago-city-council': 'city-council',
    'community-development-commission-cdc': 'cdc',
    'chicago-plan-commission-cpc': 'cpc',
    'zoning-board-of-appeals-zba': 'zba',
    'chicago-housing-authority-cha': 'cha',
    'chicago-low-income-housing-trust-fund-clihtf': 'clihtf',
    'chicago-housing-trust-formerly-chicago-community-l': 'chicago-housing-trust',
    'chicago-continuum-of-care-coc': 'coc',
    'cook-county-land-bank-authority-cclba': 'cclba',
    'chicago-residential-investment-fund-crif': 'crif',
    'community-development-financial-institutions-cdfis': 'cdfi',
    'community-development-corporations-cdcs': 'cdcs',
    'illinois-housing-development-authority-ihda': 'ihda',
    'illinois-department-of-human-services-idhs': 'idhs',
    'department-of-commerce-and-economic-opportunity-dce': 'dceo',
    'governors-office': 'governors-office',
    'illinois-general-assembly': 'il-general-assembly',
    'corporate-fund': 'corporate-fund',
    'affordable-housing-opportunity-fund-ahof': 'ahof',
    'tax-increment-financing-tif': 'tif',
    'housing-and-economic-development-hed-bond': 'hed-bond',
    'low-income-housing-tax-credit-lihtc': 'lihtc',
    'community-development-block-grant-cdbg': 'cdbg',
    'home-investment-partnership-grant': 'home',
    'illinois-affordable-housing-trust-fund': 'iahtf',
    'illinois-affordable-housing-tax-credits-donation-t': 'iahtc',
    'emergency-heating-repairs-program': 'emergency-heating',
    'right-to-counsel-pilot-program': 'right-to-counsel',
    'home-repair-program-hrp': 'home-repair',
    'multi-year-affordability-through-upfront-investmen': 'maui',
    'multifamily-tif-purchase-rehab': 'multifamily-tif',
    'public-housing-section-9': 'section-9',
    'housing-choice-vouchers-and-project-based-vouchers': 'section-8',
    'moving-to-work': 'mtw',
    'flexible-housing-pool': 'flexible-housing',
    'troubled-buildings-initiative': 'troubled-buildings',
    'rental-subsidy-program-rsp': 'rsp',
    'green-social-housing-gsh': 'gsh',
    'rental-assistance-program-rap': 'rap',
    'rental-assistance-demonstration-rad': 'rad',
    'restore-rebuild-formerly-faircloth-to-rad': 'restore-rebuild',
    'chicago-bungalow-initiative': 'bungalow-initiative',
    'chicago-neighborhood-rebuild-program': 'neighborhood-rebuild',
    'home-modification-program': 'home-modification',
    'heat-receiver-program': 'heat-receiver',
    'community-receiver-program': 'community-receiver',
    'housing-counseling-centers': 'housing-counseling',
    'community-service-centers': 'community-service-centers',
    'chicago-rents': 'chicago-rents',
    'multi-family-financial-assistance': 'multi-family-financial',
    'building-neighborhoods-and-affordable-homes': 'building-neighborhoods',
    'choose-to-own': 'choose-to-own',
    'city-lots-for-working-families-cl4wf': 'cl4wf',
    'missing-middle-infill-initiative': 'missing-middle',
    'homegrown-purchase-assistance-grant-program': 'homegrown',
    'neighborhood-lending-program-nlp-purchase-assistan': 'nlp',
    'reclaiming-chicago-communities-initiative': 'reclaiming-chicago',
    'shared-equity-investment-program': 'shared-equity',
    'woodlawn-long-term-homeowner-repair-grant-program': 'woodlawn-repair',
    'affordable-requirements-ordinance-aro': 'aro',
    'residential-landlord-tenant-ordinance-rlto': 'rlto',
    'keep-chicago-renting-ordinance-kcro': 'keep-chicago-renting',
    'additional-dwelling-units-ordinance': 'adu',
    'single-room-occupancy-preservation-ordinance-sropo': 'sro-preservation',
    'transit-oriented-development-tod-ordinances': 'tod',
    'affordable-housing-special-assessment-program-ahsa': 'ahsap',
    'anti-displacement-ordinances': 'anti-displacement',
    'cut-the-tape-ordinances': 'cut-the-tape',
    'proactive-rezonings': 'proactive-rezonings',
    'delegate-agencies': 'delegate-agencies',
    'department-of-environment': 'doe',
    'the-mayors-office': 'mayors-office',
    'the-governors-office': 'governors-office',
    'home-ownership-made-easy': 'home-ownership-made-easy',
    'just-housing-amendment': 'just-housing',
    # Additional exact slugs from extracted markdown
    'residential-landlord-and-tenant-ordinance': 'rlto',
    'emergency-heating-repair-program': 'emergency-heating',
    'home-repair-program': 'home-repair',
    'multi-family-tif-purchase-rehab-program': 'multifamily-tif',
    'home-ownership-made-easy': 'home-ownership-made-easy',
    'homegrown-purchase-assistance-grant-program': 'homegrown',
    'neighborhood-lending-program-purchase-assistance': 'nlp',
    'rental-assistance-demonstration': 'rad',
    'community-development-financial-institutions': 'cdfi',
    'community-development-corporations': 'cdcs',
    'chicago-low-income-housing-trust-fund': 'clihtf',
    'chicago-housing-trust': 'chicago-housing-trust',
    'chicago-continuum-of-care': 'coc',
    'cook-county-land-bank-authority': 'cclba',
    'chicago-residential-investment-fund': 'crif',
    'illinois-housing-development-authority': 'ihda',
    'illinois-department-of-human-services': 'idhs',
    'department-of-commerce-and-economic-opportunity': 'dceo',
    'illinois-general-assembly': 'il-general-assembly',
    'chicago-housing-authority': 'cha',
    'community-service-centers-cscs': 'community-service-centers',
    'housing-counseling-centers-hccs': 'housing-counseling',
    'multi-year-affordability-through-upfront-investment': 'maui',
    'rental-subsidy-program': 'rsp',
    'green-social-housing': 'gsh',
    'rental-assistance-program': 'rap',
    'chicago-bungalow-initiative': 'bungalow-initiative',
    'chicago-neighborhood-rebuild-program': 'neighborhood-rebuild',
    'home-modification-program': 'home-modification',
    'heat-receiver-program': 'heat-receiver',
    'community-receiver-program': 'community-receiver',
    'shared-equity-investment-program-seip': 'shared-equity',
    'woodlawn-long-term-homeowner-repair-grant-program': 'woodlawn-repair',
    'affordable-requirements-ordinance': 'aro',
    'keep-chicago-renting-ordinance': 'keep-chicago-renting',
    'additional-dwelling-units-ordinance': 'adu',
    'single-room-occupancy-preservation-ordinance': 'sro-preservation',
    'transit-oriented-development-ordinances': 'tod',
    'affordable-housing-special-assessment-program': 'ahsap',
    'cut-the-tape-ordinances': 'cut-the-tape',
    'proactive-rezonings': 'proactive-rezonings',
    'corporate-fund': 'corporate-fund',
    'affordable-housing-opportunity-fund': 'ahof',
    'tax-increment-financing': 'tif',
    'housing-and-economic-development-bond': 'hed-bond',
    'low-income-housing-tax-credit': 'lihtc',
    'community-development-block-grant': 'cdbg',
    'home-investment-partnership-grant': 'home',
    'illinois-affordable-housing-trust-fund': 'iahtf',
    'illinois-affordable-housing-tax-credits-donation-tax-credits': 'iahtc',
}

# Graphic placement: (graphic_file -> (part_id, placement_id))
GRAPHIC_PLACEMENTS = {
    'housing_continuum.html': ('introduction', 'housing-continuum'),
    'income_limits.html': ('introduction', 'income-limits'),
    'combined_housing_bodies.html': ('institutions', 'combined-housing-bodies'),
    'programs_by_department.html': ('programs', 'programs-by-department'),
    'legislative_process.html': ('legislative', 'legislative-process'),
    'state_of_illinois_chart.html': ('institutions', 'state-of-illinois'),
}


# ---------------------------------------------------------------------------
# Step 1: Markdown Parser
# ---------------------------------------------------------------------------

def slugify(text):
    """Convert text to URL-friendly slug."""
    text = re.sub(r'\*+', '', text)
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def parse_markdown(md_text):
    """Parse the extracted markdown into a structured dict."""
    lines = md_text.split('\n')

    # Find Part boundaries
    part_starts = []
    for i, line in enumerate(lines):
        for anchor_re, part_id, title, chapter_num in PART_ANCHORS:
            if re.match(anchor_re, line.strip()):
                part_starts.append((i, part_id, title, chapter_num))
                break

    # Validate all 7 anchors found
    found_ids = [ps[1] for ps in part_starts]
    for _, part_id, title, _ in PART_ANCHORS:
        if part_id not in found_ids:
            print(f"ERROR: Part anchor not found: {part_id} ({title})")
            sys.exit(1)
    print(f"  Found all {len(part_starts)} Part anchors")

    # Extract front matter + introduction (before first Part)
    intro_lines = lines[:part_starts[0][0]]
    front_matter = parse_front_matter(intro_lines)
    introduction = parse_introduction(intro_lines)

    # Extract each Part
    parts = []
    for idx, (start_line, part_id, title, chapter_num) in enumerate(part_starts):
        end_line = part_starts[idx + 1][0] if idx + 1 < len(part_starts) else len(lines)
        part_lines = lines[start_line:end_line]
        sections = parse_part_sections(part_id, part_lines)
        parts.append({
            'id': part_id,
            'title': title,
            'chapter_num': chapter_num,
            'intro_lines': extract_part_intro(part_lines, part_id),
            'sections': sections,
        })

    return {
        'front_matter': front_matter,
        'introduction': introduction,
        'parts': parts,
    }


def parse_front_matter(lines):
    """Extract authors and acknowledgment from front matter."""
    authors = []
    acknowledgment = ''
    for line in lines:
        line_s = line.strip()
        if line_s.startswith('**') and any(role in line_s for role in
            ['Director', 'Fellow', 'Counsel', 'Managing Director', 'Executive Director']):
            name = re.sub(r'\*+', '', line_s).strip()
            authors.append(name)
        if 'Polk Bros' in line_s:
            acknowledgment = re.sub(r'\*+', '', line_s).strip()
    return {'authors': authors, 'acknowledgment': acknowledgment}


def parse_introduction(lines):
    """Extract introduction content (from ## Introduction to first Part)."""
    intro_start = None
    for i, line in enumerate(lines):
        if re.match(r'^##\s+\*\*Introduction\*\*', line.strip()):
            intro_start = i
            break
    if intro_start is None:
        return []
    return lines[intro_start:]


def extract_part_intro(lines, part_id):
    """Extract introductory prose before the first H2 category or H3 entry."""
    intro = []
    started = False
    for line in lines:
        line_s = line.strip()
        if not started:
            # Skip the Part title line(s) — including multi-line titles like
            # "## **Part 5:**" / "## **How City Ordinances**" / "## **and Budgets are Passed**"
            if re.match(r'^(##\s+)?\*\*Part \d', line_s):
                continue
            if re.match(r'^##\s+\*\*', line_s):
                # Still a continuation of the Part heading (before any content)
                continue
            started = True
        if re.match(r'^## \*\*', line_s):
            break
        if re.match(r'^### \*\*', line_s):
            break
        intro.append(line)
    return intro


def parse_part_sections(part_id, lines):
    """Parse H2 categories and H3 entries within a Part.

    H3 headings create entries as before. H2 headings that act as category
    labels (with child H3s) set the current category. H2 headings that have
    content but no child H3 are promoted to entries themselves — this handles
    Resources, Legislative ("Ordinances and the Municipal Code", "Budgets"),
    and Glossary ("A Note on Sources", "Terms to Know") sections.
    """
    sections = []
    current_category = 'uncategorized'
    current_entry = None
    cat_map = CATEGORY_MAP.get(part_id, {})
    # Track orphan content under H2 headings that have no child H3
    orphan_h2_title = None
    orphan_h2_lines = []
    # Skip H2 continuation lines of multi-line Part titles (before any content)
    seen_content = False

    def _flush_orphan():
        """If we accumulated content under an H2 with no child H3, emit it as an entry."""
        nonlocal orphan_h2_title, orphan_h2_lines
        if orphan_h2_title and any(l.strip() for l in orphan_h2_lines):
            title = orphan_h2_title
            # If content starts with **Overview:** about a named entity, use that as title
            # (handles CHA content under "Other City- and County-Based Organizations" H2)
            first_content = next((l.strip() for l in orphan_h2_lines if l.strip()), '')
            overview_m = re.match(r'^\*\*Overview:\*\*\s+The\s+(.+?)\s+(?:is|are|was)\s', first_content)
            if overview_m:
                title = overview_m.group(1).strip().rstrip(',')
            entry_slug = slugify(title)
            short_slug = ALIASES.get(entry_slug, entry_slug)
            sections.append({
                'id': short_slug,
                'full_id': entry_slug,
                'title': title,
                'category': current_category,
                'content_lines': orphan_h2_lines[:],
            })
        orphan_h2_title = None
        orphan_h2_lines = []

    for line in lines:
        line_s = line.strip()

        # Detect H2 category headings
        h2_match = re.match(r'^## \*\*(.+?)\*\*\s*$', line_s)
        if h2_match:
            h2_text = h2_match.group(1).strip()
            if h2_text.startswith('Part ') or not h2_text:
                continue
            # Skip H2 continuation lines of multi-line Part titles
            # (e.g. "## **How City Ordinances**" / "## **and Budgets are Passed**"
            #  or "## **Chicago Housing and Advocacy Resources**")
            # These appear before any non-H2 content in the part.
            if not seen_content:
                continue
            # Flush any prior orphan H2 content
            _flush_orphan()
            if current_entry:
                sections.append(current_entry)
                current_entry = None
            # Set category if mapped, otherwise use slug
            for cat_text, cat_slug in cat_map.items():
                if cat_text.lower() in h2_text.lower() or h2_text.lower() in cat_text.lower():
                    current_category = cat_slug
                    break
            else:
                current_category = slugify(h2_text) or 'uncategorized'
            # Start tracking this H2 as a potential orphan entry
            orphan_h2_title = h2_text
            orphan_h2_lines = []
            continue

        # Detect H3 entries
        h3_match = re.match(r'^### \*\*(.+?)\*\*\s*$', line_s)
        if h3_match:
            # If the H2 had direct content before this H3, emit it as an entry
            _flush_orphan()
            if current_entry:
                sections.append(current_entry)
            title = h3_match.group(1).strip()
            entry_slug = slugify(title)
            # Try exact match first, then prefix match on alias keys
            short_slug = ALIASES.get(entry_slug)
            if not short_slug:
                for alias_key, alias_val in ALIASES.items():
                    if alias_key.startswith(entry_slug) or entry_slug.startswith(alias_key):
                        short_slug = alias_val
                        break
            if not short_slug:
                short_slug = entry_slug
            current_entry = {
                'id': short_slug,
                'full_id': entry_slug,
                'title': title,
                'category': current_category,
                'content_lines': [],
            }
            continue

        # Mark that we've passed the Part title heading lines
        if not seen_content and line_s:
            seen_content = True

        # Accumulate content lines
        if current_entry:
            current_entry['content_lines'].append(line)
        elif orphan_h2_title is not None:
            orphan_h2_lines.append(line)

    # Flush final entry/orphan
    if current_entry:
        sections.append(current_entry)
    _flush_orphan()
    return sections


# ---------------------------------------------------------------------------
# Step 2: Markdown to HTML Converter
# ---------------------------------------------------------------------------

EXT_LINK_ICON = ('<svg class="ext-icon" xmlns="http://www.w3.org/2000/svg" '
    'width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>'
    '<polyline points="15 3 21 3 21 9"></polyline>'
    '<line x1="10" y1="14" x2="21" y2="3"></line></svg>')


def md_to_html(text):
    """Convert markdown text to HTML. All input is from trusted build-time sources."""
    if isinstance(text, list):
        text = '\n'.join(text)

    text = re.sub(r'<!--\s*\[image:.*?\]\s*-->', '', text)
    lines = text.split('\n')
    html_parts = []
    in_list = False
    list_type = None
    list_items = []
    i = 0

    def flush_list():
        nonlocal in_list, list_type, list_items
        if in_list and list_items:
            tag = list_type
            items_html = '\n'.join(f'<li>{item}</li>' for item in list_items)
            html_parts.append(f'<{tag}>\n{items_html}\n</{tag}>')
            list_items = []
            in_list = False
            list_type = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            if in_list and i + 1 < len(lines):
                next_s = lines[i + 1].strip()
                if re.match(r'^[-*]\s', next_s) or re.match(r'^\d+\.\s', next_s):
                    i += 1
                    continue
                if lines[i + 1].startswith('  ') and next_s:
                    i += 1
                    continue
            flush_list()
            i += 1
            continue

        # Headings with bold
        h_match = re.match(r'^(#{1,4})\s+\*\*(.+?)\*\*\s*$', stripped)
        if h_match:
            flush_list()
            level = len(h_match.group(1))
            heading_text = inline_format(h_match.group(2))
            heading_id = slugify(h_match.group(2))
            html_parts.append(f'<h{level} id="{heading_id}">{heading_text}</h{level}>')
            i += 1
            continue

        # Headings without bold
        h_match2 = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if h_match2 and not stripped.startswith('###'):
            flush_list()
            level = len(h_match2.group(1))
            heading_text = inline_format(h_match2.group(2).strip())
            heading_id = slugify(h_match2.group(2))
            if heading_text.strip():
                html_parts.append(
                    f'<h{level} id="{heading_id}">{heading_text}</h{level}>')
            i += 1
            continue

        # Bullet list
        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match:
            if not in_list or list_type != 'ul':
                flush_list()
                in_list = True
                list_type = 'ul'
            item_text = bullet_match.group(1)
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                next_s = next_line.strip()
                if (next_s and next_line.startswith('  ')
                    and not re.match(r'^[-*]\s', next_s)
                    and not re.match(r'^\d+\.\s', next_s)):
                    item_text += ' ' + next_s
                    i += 1
                else:
                    break
            list_items.append(inline_format(item_text))
            i += 1
            continue

        # Numbered list
        num_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if num_match:
            if not in_list or list_type != 'ol':
                flush_list()
                in_list = True
                list_type = 'ol'
            item_text = num_match.group(2)
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                next_s = next_line.strip()
                if (next_s and next_line.startswith('  ')
                    and not re.match(r'^[-*]\s', next_s)
                    and not re.match(r'^\d+\.\s', next_s)):
                    item_text += ' ' + next_s
                    i += 1
                else:
                    break
            list_items.append(inline_format(item_text))
            i += 1
            continue

        # Regular paragraph
        flush_list()
        para_lines = [stripped]
        while i + 1 < len(lines):
            next_s = lines[i + 1].strip()
            if not next_s:
                break
            if re.match(r'^#{1,4}\s', next_s):
                break
            if re.match(r'^[-*]\s', next_s):
                break
            if re.match(r'^\d+\.\s', next_s):
                break
            if next_s.startswith('<!--'):
                break
            para_lines.append(next_s)
            i += 1
        para_text = ' '.join(para_lines)
        html_parts.append(f'<p>{inline_format(para_text)}</p>')
        i += 1

    flush_list()
    return '\n'.join(html_parts)


def inline_format(text):
    """Apply inline formatting: bold, italic, links."""
    # Links with bold inside
    text = re.sub(
        r'\[(\*\*[^]]+?\*\*)\]\(([^)]+)\)',
        lambda m: make_link(
            re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', m.group(1)),
            m.group(2)),
        text)
    # Regular links
    text = re.sub(
        r'\[([^]]+?)\]\(([^)]+)\)',
        lambda m: make_link(m.group(1), m.group(2)),
        text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic (not **)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    # Collapse adjacent bold
    text = text.replace('</strong><strong>', '')
    return text


def make_link(text, url):
    """Create a link element. External links open in new tab with icon."""
    url = url.strip()
    is_external = url.startswith('http://') or url.startswith('https://')
    if is_external:
        clean_text = re.sub(r'<[^>]+>', '', text)
        return (f'<a href="{html_escape(url)}" target="_blank" rel="noopener" '
                f'aria-label="{html_escape(clean_text)} (opens in new tab)">'
                f'{text}{EXT_LINK_ICON}</a>')
    return f'<a href="{html_escape(url)}">{text}</a>'


# ---------------------------------------------------------------------------
# Step 3: Cross-Reference Builder
# ---------------------------------------------------------------------------

def build_cross_ref_data(parsed):
    """Build lookup from display names to slugs."""
    name_to_slug = {}
    for part in parsed['parts']:
        for section in part['sections']:
            title = re.sub(r'\*+', '', section['title']).strip()
            name_to_slug[title] = section['id']
            abbrev_match = re.search(r'\(([A-Z]{2,})\)', title)
            if abbrev_match:
                name_to_slug[abbrev_match.group(1)] = section['id']
    return name_to_slug


def build_entry_to_part_map(parsed):
    """Build map from entry slug -> part_id."""
    entry_map = {}
    for part in parsed['parts']:
        for section in part['sections']:
            entry_map[section['id']] = part['id']
            entry_map[section['full_id']] = part['id']
    for full_id, short_id in ALIASES.items():
        if full_id in entry_map:
            entry_map[short_id] = entry_map[full_id]
    return entry_map


# ---------------------------------------------------------------------------
# Step 4: HTML Graphics Extractor
# ---------------------------------------------------------------------------

def extract_graphic(filepath, scope_class):
    """Extract and scope a standalone HTML graphic for embedding."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    style_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    css = style_match.group(1) if style_match else ''

    body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
    if body_match:
        body = body_match.group(1)
    else:
        body = re.sub(r'^.*?</style>\s*', '', content, flags=re.DOTALL)
        body = re.sub(r'</html>\s*$', '', body, flags=re.DOTALL)

    scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
    js = '\n'.join(scripts)

    # Remove script tags from body since we extract them separately
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)

    scoped_css = scope_css(css, scope_class)

    return {
        'css': scoped_css,
        'html': body.strip(),
        'js': js.strip() if js.strip() else None,
        'scope_class': scope_class,
    }


def scope_css(css, scope_class):
    """Prefix all CSS selectors with a scope class."""
    css = re.sub(r'@charset\s+"[^"]+"\s*;', '', css)
    result = []
    i = 0

    while i < len(css):
        while i < len(css) and css[i] in ' \t\n\r':
            i += 1
        if i >= len(css):
            break

        if css[i] == '@':
            at_end = css.find('{', i)
            if at_end == -1:
                break
            at_rule = css[i:at_end].strip()
            brace_count = 0
            j = at_end
            while j < len(css):
                if css[j] == '{':
                    brace_count += 1
                elif css[j] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        break
                j += 1
            inner = css[at_end + 1:j]
            scoped_inner = scope_css(inner, scope_class)
            result.append(f'{at_rule} {{\n{scoped_inner}\n}}')
            i = j + 1
            continue

        brace_pos = css.find('{', i)
        if brace_pos == -1:
            break
        selector = css[i:brace_pos].strip()
        close_pos = css.find('}', brace_pos)
        if close_pos == -1:
            break
        declarations = css[brace_pos + 1:close_pos].strip()

        if selector:
            scoped_selectors = []
            for sel in selector.split(','):
                sel = sel.strip()
                if not sel:
                    continue
                if sel in ('html', 'body', ':root'):
                    scoped_selectors.append(f'.{scope_class}')
                elif sel.startswith('html ') or sel.startswith('body '):
                    sel = re.sub(r'^(html|body)\s+', '', sel)
                    scoped_selectors.append(f'.{scope_class} {sel}')
                else:
                    scoped_selectors.append(f'.{scope_class} {sel}')
            selector_str = ', '.join(scoped_selectors)
            result.append(f'{selector_str} {{ {declarations} }}')

        i = close_pos + 1
    return '\n'.join(result)


# ---------------------------------------------------------------------------
# Step 5: Image Handling
# ---------------------------------------------------------------------------

def load_and_encode_image(filepath, max_width=None):
    """Load image, optionally resize, return base64 data URI."""
    if not os.path.exists(filepath):
        print(f"  WARNING: Image not found: {filepath}")
        return None

    file_size = os.path.getsize(filepath)
    print(f"  Image: {os.path.basename(filepath)} - {file_size:,} bytes")

    if max_width and file_size > 300000:
        try:
            from PIL import Image
            img = Image.open(filepath)
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)
                print(f"    Resized to {max_width}x{new_height}")
            # Convert to JPEG for better compression on photo images
            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80, optimize=True)
            data = buf.getvalue()
            print(f"    After resize+JPEG: {len(data):,} bytes")
            encoded = base64.b64encode(data).decode('ascii')
            print(f"    Base64 size: {len(encoded):,} chars")
            return f'data:image/jpeg;base64,{encoded}'
        except ImportError:
            print("    WARNING: PIL not available, using original image")
            with open(filepath, 'rb') as f:
                data = f.read()
    else:
        with open(filepath, 'rb') as f:
            data = f.read()

    encoded = base64.b64encode(data).decode('ascii')
    print(f"    Base64 size: {len(encoded):,} chars")
    return f'data:image/png;base64,{encoded}'


# ---------------------------------------------------------------------------
# Step 6: HTML Generator
# ---------------------------------------------------------------------------

def generate_css():
    """Generate the complete CSS."""
    return """
*, *::before, *::after { box-sizing: border-box; }
html { font-size: 19px; scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: "Gotham", "Calibri", "Segoe UI", sans-serif;
  font-weight: 400; font-size: 1rem; line-height: 1.7;
  color: #51585E; background: #FFFFFF;
}
img { max-width: 100%; display: block; }
:root {
  --ife-navy: #003F70; --ife-blue: #005198;
  --ife-sky: #2899D5; --ife-light-blue: #84B8E3;
  --ife-orange: #F37021; --ife-lime: #CBDC00;
  --ife-slate: #67808E; --ife-charcoal: #51585E;
  --ife-gray: #919191; --ife-white: #FFFFFF;
  --ife-off-white: #F5F7FA;
  --content-max-width: 780px; --content-padding: 48px;
  --runner-width: 72px; --toc-height: 44px;
  --space-1: 8px; --space-2: 16px; --space-3: 24px;
  --space-4: 32px; --space-6: 48px; --space-8: 64px;
}
.page-runner {
  position: fixed; left: 0; top: 0;
  width: var(--runner-width); height: 100vh;
  background: linear-gradient(180deg, var(--ife-navy) 0%, var(--ife-blue) 40%, var(--ife-sky) 70%, var(--ife-light-blue) 100%);
  opacity: 0.08; z-index: 1; pointer-events: none;
}
.skip-link {
  position: absolute; top: -100px; left: 16px;
  background: var(--ife-navy); color: white;
  padding: 8px 16px; border-radius: 0 0 4px 4px;
  z-index: 300; font-size: 0.875rem; text-decoration: none;
  transition: top 0.2s;
}
.skip-link:focus { top: 0; }
#progress-bar {
  position: fixed; top: 0; left: 0; height: 3px;
  width: 0%; background: var(--ife-orange);
  z-index: 300; transition: width 0.1s linear; pointer-events: none;
}
.hero {
  background: var(--ife-off-white);
  padding: var(--space-8) var(--space-4) var(--space-6);
  text-align: center; position: relative; overflow: hidden;
}
.hero-inner {
  max-width: var(--content-max-width); margin: 0 auto;
  position: relative; z-index: 2;
}
.hero-logo { height: 48px; margin: 0 auto var(--space-3); }
.hero-title {
  font-size: clamp(1.875rem, 5vw, 3rem); font-weight: 700;
  color: var(--ife-navy); margin: 0 0 var(--space-2); line-height: 1.1;
}
.hero-meta {
  display: flex; justify-content: center; gap: var(--space-1);
  font-size: 0.875rem; color: var(--ife-slate);
  flex-wrap: wrap; align-items: center; margin: 0 0 var(--space-2);
}
.toc-bar {
  position: sticky; top: 0; z-index: 100;
  background: var(--ife-off-white); border-bottom: 1px solid #D0DCE5;
}
.toc-bar-inner {
  max-width: var(--content-max-width); margin: 0 auto;
  padding: 0 var(--space-4); display: flex; align-items: center;
}
.toc-bar-toggle {
  display: none; background: none; border: none;
  font-family: inherit; font-size: 0.875rem; font-weight: 700;
  color: var(--ife-navy); padding: 12px 0; cursor: pointer;
  width: 100%; text-align: left;
}
.toc-bar-toggle::after { content: ' \\25BE'; font-size: 0.75em; }
.toc-tabs {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-wrap: nowrap; gap: 0; flex: 1;
  overflow-x: auto; -ms-overflow-style: none; scrollbar-width: none;
}
.toc-tabs::-webkit-scrollbar { display: none; }
.toc-tab {
  display: block; padding: 12px 14px;
  border-bottom: 3px solid transparent;
  color: var(--ife-navy); text-decoration: none;
  font-size: 0.8rem; font-weight: 400; line-height: 1.4;
  white-space: nowrap; cursor: pointer; background: none;
  border-top: none; border-left: none; border-right: none;
  font-family: inherit;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}
.toc-tab:hover { color: var(--ife-sky); background: rgba(0,63,112,0.04); }
.toc-tab[aria-selected="true"] {
  color: var(--ife-navy); border-bottom-color: var(--ife-orange); font-weight: 700;
}
.toc-minimal .toc-tabs { display: none; }
.toc-minimal .toc-bar-toggle { display: none; }
.toc-search-btn {
  background: none; border: none; cursor: pointer;
  padding: 8px; color: var(--ife-navy); flex-shrink: 0; margin-left: auto;
}
.toc-search-btn:hover { color: var(--ife-sky); }
.toc-search-btn svg { width: 18px; height: 18px; }
.cards-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3); margin: var(--space-4) 0;
}
.section-card {
  display: flex; flex-direction: column; background: white;
  border-radius: 8px; overflow: hidden; text-decoration: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); padding: var(--space-3);
  cursor: pointer; border: 1px solid #E8ECF0;
  transition: background 0.2s, box-shadow 0.2s;
}
.section-card:hover { background: #EBF4FB; box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
.section-card-num {
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ife-slate); margin: 0 0 4px;
}
.section-card-title {
  font-size: 1rem; font-weight: 700; color: var(--ife-navy);
  margin: 0 0 8px; line-height: 1.3;
}
.section-card-desc { font-size: 0.8rem; color: var(--ife-charcoal); margin: 0; line-height: 1.5; }
.content-well {
  max-width: var(--content-max-width); margin: 0 auto;
  padding: var(--space-4) var(--content-padding);
  scroll-margin-top: var(--toc-height);
}
.part-view { display: none; }
.part-view.active { display: block; }
.chapter-divider {
  background: linear-gradient(135deg, var(--ife-navy) 0%, var(--ife-blue) 100%);
  padding: var(--space-6) var(--space-4); text-align: center;
  position: relative; overflow: hidden;
}
.chapter-divider-inner { max-width: var(--content-max-width); margin: 0 auto; }
.chapter-number { font-size: 4.5rem; font-weight: 700; color: rgba(255,255,255,0.15); line-height: 1; }
.chapter-title { font-size: 1.875rem; font-weight: 700; color: white; margin: 0; }
.category-filters {
  display: flex; flex-wrap: wrap; gap: 8px; margin: var(--space-3) 0 var(--space-4);
}
.cat-btn {
  display: inline-block; padding: 6px 16px; border-radius: 9999px;
  border: 1px solid #D0DCE5; background: white; color: var(--ife-charcoal);
  font-family: inherit; font-size: 0.8rem; font-weight: 400;
  cursor: pointer; white-space: nowrap;
  transition: background 0.2s, color 0.2s, border-color 0.2s;
}
.cat-btn:hover { border-color: var(--ife-sky); color: var(--ife-navy); }
.cat-btn[aria-checked="true"] {
  background: var(--ife-navy); color: white;
  border-color: var(--ife-navy); font-weight: 700;
}
.entry {
  margin: 0 0 var(--space-6); padding: 0 0 var(--space-4);
  border-bottom: 1px solid #E8ECF0;
  scroll-margin-top: var(--toc-height);
}
.entry:last-child { border-bottom: none; }
.entry-title {
  font-size: 1.25rem; font-weight: 700; color: var(--ife-navy);
  margin: 0 0 var(--space-2); line-height: 1.3;
}
.entry-title a { color: inherit; text-decoration: none; }
.entry-category-tag {
  display: inline-block; font-size: 0.7rem; font-weight: 700;
  letter-spacing: 0.05em; text-transform: uppercase;
  color: var(--ife-slate); background: var(--ife-off-white);
  padding: 2px 10px; border-radius: 9999px; margin: 0 0 var(--space-1);
}
.entry-content { color: var(--ife-charcoal); }
.entry-content p { margin: 0 0 var(--space-2); }
.entry-content strong { color: var(--ife-navy); }
.entry-content ul, .entry-content ol {
  margin: var(--space-1) 0 var(--space-2); padding-left: 1.5rem;
}
.entry-content li { margin: 0 0 6px; }
.entry-content a {
  color: var(--ife-sky); text-decoration: underline; text-underline-offset: 2px;
}
.entry-content a:hover { color: var(--ife-navy); }
.cross-ref {
  color: var(--ife-sky); text-decoration: underline;
  text-decoration-style: dotted; text-underline-offset: 2px; cursor: pointer;
}
.cross-ref:hover { color: var(--ife-navy); text-decoration-style: solid; }
.ext-icon {
  display: inline; margin-left: 3px; vertical-align: middle;
  opacity: 0.5; position: relative; top: -1px;
}
.search-overlay {
  display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); z-index: 200;
  justify-content: center; padding-top: 80px;
}
.search-overlay.active { display: flex; }
.search-box {
  background: white; border-radius: 12px; width: 90%;
  max-width: 640px; max-height: 70vh; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: 0 16px 48px rgba(0,0,0,0.2); align-self: flex-start;
}
.search-input-wrap {
  display: flex; align-items: center; padding: 16px 20px;
  border-bottom: 1px solid #E8ECF0; gap: 12px;
}
.search-input-wrap svg { flex-shrink: 0; color: var(--ife-slate); }
.search-input {
  flex: 1; border: none; outline: none; font-family: inherit;
  font-size: 1rem; color: var(--ife-charcoal);
}
.search-input::placeholder { color: var(--ife-gray); }
.search-close {
  background: none; border: none; font-size: 1.25rem;
  color: var(--ife-slate); cursor: pointer; padding: 4px 8px;
}
.search-results { overflow-y: auto; flex: 1; padding: 8px 0; }
.search-result {
  display: block; padding: 12px 20px; text-decoration: none;
  color: var(--ife-charcoal); cursor: pointer; border: none;
  background: none; width: 100%; text-align: left;
  font-family: inherit; font-size: 0.875rem;
  transition: background 0.1s;
}
.search-result:hover, .search-result:focus { background: var(--ife-off-white); }
.search-result-title { font-weight: 700; color: var(--ife-navy); font-size: 0.9rem; }
.search-result-part { font-size: 0.75rem; color: var(--ife-slate); margin-left: 8px; }
.search-result-snippet {
  font-size: 0.8rem; color: var(--ife-charcoal);
  margin: 4px 0 0; line-height: 1.4;
}
.search-result-snippet mark {
  background: #FFF3CD; color: inherit; padding: 0 2px; border-radius: 2px;
}
.search-empty {
  padding: 24px 20px; text-align: center;
  color: var(--ife-slate); font-size: 0.875rem;
}
.section-toc {
  margin: 0 0 var(--space-4);
  border: 1px solid #E8ECF0;
  border-radius: 8px;
  font-size: 0.85rem;
}
.section-toc summary {
  padding: 10px 16px;
  cursor: pointer;
  font-weight: 600;
  color: var(--ife-navy);
}
.section-toc-list {
  padding: 0 16px 12px 36px;
  margin: 0;
  columns: 2;
  column-gap: 24px;
}
.section-toc-list li { margin: 0 0 4px; }
.section-toc-list a {
  color: var(--ife-sky);
  text-decoration: none;
}
.section-toc-list a:hover {
  color: var(--ife-navy);
  text-decoration: underline;
}
.graphic-container {
  margin: var(--space-4) 0; overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid #E8ECF0; border-radius: 8px;
  background: white; padding: var(--space-2);
}
.pull-quote {
  border-left: 4px solid var(--ife-orange);
  margin: var(--space-4) 0; padding: var(--space-2) var(--space-3);
  background: var(--ife-off-white); border-radius: 0 4px 4px 0;
}
.pull-quote p {
  font-size: 1.125rem; font-weight: 400; color: var(--ife-navy);
  line-height: 1.5; margin: 0; font-style: italic;
}
.intro-content h2 { font-size: 1.5rem; margin: var(--space-6) 0 var(--space-2); color: var(--ife-navy); }
.intro-content h3 { font-size: 1.25rem; margin: var(--space-4) 0 var(--space-1); color: var(--ife-navy); }
.intro-content h4 { font-size: 1.125rem; margin: var(--space-3) 0 var(--space-1); color: var(--ife-navy); }
.intro-content p { margin: 0 0 var(--space-2); }
.intro-content a { color: var(--ife-sky); text-decoration: underline; text-underline-offset: 2px; }
.intro-content a:hover { color: var(--ife-navy); }
.intro-content ul, .intro-content ol { margin: var(--space-1) 0 var(--space-2); padding-left: 1.5rem; }
.intro-content li { margin: 0 0 6px; }
.feedback-cta {
  display: block; text-align: center; padding: var(--space-4);
  background: var(--ife-off-white); color: var(--ife-charcoal);
  font-size: 0.9rem; border-top: 1px solid #D0DCE5; margin-top: var(--space-8);
}
.feedback-cta a { color: var(--ife-sky); text-decoration: underline; }
.feedback-cta a:hover { color: var(--ife-navy); }
@media (max-width: 810px) {
  .page-runner { display: none; }
  .toc-bar-toggle { display: block; }
  .toc-tabs { display: none; flex-direction: column; padding-bottom: 8px; }
  .toc-tabs.open { display: flex; }
  .toc-tab {
    padding: 10px 0; border-bottom: none;
    border-left: 3px solid transparent; padding-left: 12px; font-size: 0.875rem;
  }
  .toc-tab[aria-selected="true"] { border-bottom: none; border-left-color: var(--ife-orange); }
  .toc-bar-inner { flex-direction: column; align-items: stretch; }
  .toc-search-btn { position: absolute; right: var(--space-4); top: 6px; }
  .cards-grid { grid-template-columns: 1fr; }
  .chapter-divider-inner { text-align: center; }
  .chapter-number { font-size: 3rem; }
}
@media (max-width: 600px) {
  :root { --content-padding: 20px; }
  .hero { padding: var(--space-4) var(--space-2) var(--space-3); }
  .hero-title { font-size: 1.5rem; }
  .category-filters { flex-direction: column; }
}
@media print {
  .page-runner { display: none !important; }
  .toc-bar, .search-overlay, #progress-bar, .skip-link,
  .toc-search-btn, .category-filters, .feedback-cta { display: none !important; }
  .part-view { display: block !important; }
  .hero { padding: var(--space-3); }
  .entry { break-inside: avoid; }
  .graphic-container { overflow: visible; max-width: 100%; }
  body { font-size: 11pt; }
}
"""


def generate_js(entry_map_json, part_titles_json):
    """Generate the JavaScript. All DOM content is from build-time trusted sources."""
    return f"""
(function() {{
  'use strict';

  var ENTRY_MAP = {entry_map_json};
  var PART_TITLES = {part_titles_json};

  var currentView = 'home';
  var views = document.querySelectorAll('.part-view');
  var tabs = document.querySelectorAll('.toc-tab');
  var searchOverlay = document.getElementById('search-overlay');
  var searchInput = document.getElementById('search-input');
  var searchResults = document.getElementById('search-results');
  var tocToggle = document.querySelector('.toc-bar-toggle');
  var tocTabs = document.querySelector('.toc-tabs');

  function showView(viewId, scrollToEntry) {{
    currentView = viewId;
    views.forEach(function(v) {{
      var isActive = v.id === 'view-' + viewId;
      v.classList.toggle('active', isActive);
      v.setAttribute('aria-hidden', String(!isActive));
    }});
    tabs.forEach(function(t) {{
      t.setAttribute('aria-selected', String(t.dataset.view === viewId));
    }});
    if (tocTabs) tocTabs.classList.remove('open');
    if (tocToggle) tocToggle.setAttribute('aria-expanded', 'false');
    var tocBar = document.querySelector('.toc-bar');
    if (tocBar) tocBar.classList.toggle('toc-minimal', viewId === 'home');

    if (scrollToEntry) {{
      setTimeout(function() {{
        var el = document.getElementById(scrollToEntry);
        if (el) {{
          el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
          el.focus({{ preventScroll: true }});
        }}
      }}, 50);
    }} else {{
      var activeView = document.getElementById('view-' + viewId);
      if (activeView) {{
        var target = activeView.querySelector('.content-well') || activeView;
        target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        target.setAttribute('tabindex', '-1');
        target.focus({{ preventScroll: true }});
      }} else {{
        window.scrollTo(0, 0);
      }}
    }}
  }}

  function navigateToHash() {{
    var hash = location.hash.replace('#', '');
    if (!hash || hash === 'home') {{ showView('home'); return; }}
    if (PART_TITLES[hash]) {{ showView(hash); return; }}
    var partId = ENTRY_MAP[hash];
    if (partId) {{ showView(partId, hash); return; }}
    var viewEl = document.getElementById('view-' + hash);
    if (viewEl) showView(hash);
  }}

  tabs.forEach(function(tab) {{
    tab.addEventListener('click', function(e) {{
      e.preventDefault();
      location.hash = tab.dataset.view;
    }});
    tab.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); tab.click(); }}
    }});
  }});

  if (tocToggle && tocTabs) {{
    tocToggle.addEventListener('click', function() {{
      var expanded = tocToggle.getAttribute('aria-expanded') === 'true';
      tocToggle.setAttribute('aria-expanded', String(!expanded));
      tocTabs.classList.toggle('open', !expanded);
    }});
  }}

  document.querySelectorAll('.section-card').forEach(function(card) {{
    card.addEventListener('click', function() {{
      var target = card.dataset.target;
      if (target) location.hash = target;
    }});
    card.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); card.click(); }}
    }});
  }});

  document.addEventListener('click', function(e) {{
    var ref = e.target.closest('.cross-ref');
    if (ref) {{ e.preventDefault(); var target = ref.dataset.target; if (target) location.hash = target; }}
  }});

  document.querySelectorAll('.category-filters').forEach(function(filterGroup) {{
    var buttons = filterGroup.querySelectorAll('.cat-btn');
    buttons.forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var category = btn.dataset.category;
        var partView = btn.closest('.part-view');
        if (!partView) return;
        buttons.forEach(function(b) {{ b.setAttribute('aria-checked', String(b === btn)); }});
        partView.querySelectorAll('.entry[data-category]').forEach(function(entry) {{
          entry.style.display = (category === 'all' || entry.dataset.category === category) ? '' : 'none';
        }});
      }});
    }});
  }});

  /* Search - uses textContent for safe text extraction, builds DOM nodes for results */
  var searchIndex = [];
  function buildSearchIndex() {{
    document.querySelectorAll('.entry').forEach(function(entry) {{
      var titleEl = entry.querySelector('.entry-title');
      var contentEl = entry.querySelector('.entry-content');
      if (!titleEl) return;
      searchIndex.push({{
        id: entry.id,
        title: titleEl.textContent.trim(),
        text: (contentEl ? contentEl.textContent : '').trim().substring(0, 500),
        partId: ENTRY_MAP[entry.id] || '',
        partTitle: PART_TITLES[ENTRY_MAP[entry.id]] || ''
      }});
    }});
  }}

  var searchTimeout;
  function doSearch(query) {{
    // Clear previous results using DOM methods
    while (searchResults.firstChild) searchResults.removeChild(searchResults.firstChild);

    if (!query || query.length < 2) {{
      var empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.textContent = 'Type at least 2 characters to search';
      searchResults.appendChild(empty);
      return;
    }}
    var q = query.toLowerCase();
    var results = [];
    searchIndex.forEach(function(item) {{
      var titleMatch = item.title.toLowerCase().indexOf(q) >= 0;
      var textMatch = item.text.toLowerCase().indexOf(q) >= 0;
      if (titleMatch || textMatch) {{
        var score = titleMatch ? 10 : 1;
        if (item.title.toLowerCase() === q) score = 100;
        results.push({{ item: item, score: score }});
      }}
    }});
    results.sort(function(a, b) {{ return b.score - a.score; }});
    results = results.slice(0, 15);

    if (results.length === 0) {{
      var noResult = document.createElement('div');
      noResult.className = 'search-empty';
      noResult.textContent = 'No results found for "' + query + '"';
      searchResults.appendChild(noResult);
      return;
    }}

    results.forEach(function(r) {{
      var btn = document.createElement('button');
      btn.className = 'search-result';
      btn.dataset.target = r.item.id;
      btn.dataset.part = r.item.partId;

      var header = document.createElement('div');
      var titleSpan = document.createElement('span');
      titleSpan.className = 'search-result-title';
      titleSpan.textContent = r.item.title;
      header.appendChild(titleSpan);
      var partSpan = document.createElement('span');
      partSpan.className = 'search-result-part';
      partSpan.textContent = r.item.partTitle;
      header.appendChild(partSpan);
      btn.appendChild(header);

      var idx = r.item.text.toLowerCase().indexOf(q);
      if (idx >= 0) {{
        var snippetDiv = document.createElement('div');
        snippetDiv.className = 'search-result-snippet';
        var start = Math.max(0, idx - 40);
        var end = Math.min(r.item.text.length, idx + q.length + 60);
        if (start > 0) snippetDiv.appendChild(document.createTextNode('...'));
        snippetDiv.appendChild(document.createTextNode(r.item.text.substring(start, idx)));
        var mark = document.createElement('mark');
        mark.textContent = r.item.text.substring(idx, idx + q.length);
        snippetDiv.appendChild(mark);
        snippetDiv.appendChild(document.createTextNode(r.item.text.substring(idx + q.length, end)));
        if (end < r.item.text.length) snippetDiv.appendChild(document.createTextNode('...'));
        btn.appendChild(snippetDiv);
      }}

      btn.addEventListener('click', function() {{
        closeSearch();
        location.hash = btn.dataset.target;
      }});
      searchResults.appendChild(btn);
    }});
  }}

  function openSearch() {{
    searchOverlay.classList.add('active');
    searchInput.value = '';
    while (searchResults.firstChild) searchResults.removeChild(searchResults.firstChild);
    var hint = document.createElement('div');
    hint.className = 'search-empty';
    hint.textContent = 'Type to search across all sections';
    searchResults.appendChild(hint);
    setTimeout(function() {{ searchInput.focus(); }}, 100);
  }}

  function closeSearch() {{
    searchOverlay.classList.remove('active');
    searchInput.value = '';
  }}

  window.openSearch = openSearch;
  window.closeSearch = closeSearch;

  if (searchOverlay) {{
    searchOverlay.addEventListener('click', function(e) {{
      if (e.target === searchOverlay) closeSearch();
    }});
  }}
  if (searchInput) {{
    searchInput.addEventListener('input', function() {{
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(function() {{ doSearch(searchInput.value.trim()); }}, 150);
    }});
    searchInput.addEventListener('keydown', function(e) {{
      if (e.key === 'Escape') closeSearch();
      if (e.key === 'ArrowDown') {{
        e.preventDefault();
        var first = searchResults.querySelector('.search-result');
        if (first) first.focus();
      }}
    }});
  }}
  if (searchResults) {{
    searchResults.addEventListener('keydown', function(e) {{
      var focused = document.activeElement;
      if (!focused || !focused.classList.contains('search-result')) return;
      if (e.key === 'ArrowDown') {{
        e.preventDefault();
        var next = focused.nextElementSibling;
        if (next && next.classList.contains('search-result')) next.focus();
      }} else if (e.key === 'ArrowUp') {{
        e.preventDefault();
        var prev = focused.previousElementSibling;
        if (prev && prev.classList.contains('search-result')) prev.focus();
        else searchInput.focus();
      }} else if (e.key === 'Escape') closeSearch();
    }});
  }}

  var searchBtn = document.querySelector('.toc-search-btn');
  if (searchBtn) {{ searchBtn.addEventListener('click', function(e) {{ e.preventDefault(); openSearch(); }}); }}

  var progressBar = document.getElementById('progress-bar');
  if (progressBar) {{
    window.addEventListener('scroll', function() {{
      var scrollTop = document.documentElement.scrollTop;
      var scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      progressBar.style.width = (scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0) + '%';
    }});
  }}

  window.addEventListener('hashchange', navigateToHash);
  buildSearchIndex();
  navigateToHash();
}})();
"""


def build_html(parsed, graphics, images):
    """Build the complete HTML file."""
    entry_map = build_entry_to_part_map(parsed)
    part_titles = {p['id']: p['title'] for p in parsed['parts']}
    part_titles['home'] = 'Home'
    part_titles['introduction'] = 'Introduction'

    entry_map_json = '{\n'
    for slug, part_id in sorted(entry_map.items()):
        entry_map_json += f'    "{slug}": "{part_id}",\n'
    entry_map_json += '  }'

    part_titles_json = '{\n'
    for pid, title in sorted(part_titles.items()):
        part_titles_json += f'    "{pid}": "{title}",\n'
    part_titles_json += '  }'

    css = generate_css()
    js = generate_js(entry_map_json, part_titles_json)

    graphic_css = ''
    graphic_js = ''
    for gname, gdata in graphics.items():
        graphic_css += f'\n/* Graphic: {gname} */\n{gdata["css"]}\n'
        if gdata.get('js'):
            graphic_js += f'\n// Graphic JS: {gname}\n{gdata["js"]}\n'

    hero_html = build_hero(parsed, images)
    toc_html = build_toc(parsed)
    home_view = build_home_view(parsed, images, graphics)
    intro_view = build_intro_view(parsed, graphics)
    part_views = []
    for part in parsed['parts']:
        part_views.append(build_part_view(part, images, graphics))

    search_html = build_search_overlay()
    feedback_html = build_feedback()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>2026 Guide for Chicago Housing Advocates | Impact for Equity</title>
  <meta name="description" content="A comprehensive reference guide to Chicago's housing policy landscape, covering institutions, funding, programs, ordinances, and advocacy resources.">
  <style>
{css}
{graphic_css}
  </style>
</head>
<body>
  <div class="page-runner" aria-hidden="true"></div>
  <a href="#main-content" class="skip-link">Skip to content</a>
  <div id="progress-bar" aria-hidden="true"></div>

  {hero_html}
  {toc_html}

  <main id="main-content" role="main">
    {home_view}
    {intro_view}
    {''.join(part_views)}
  </main>

  {search_html}
  {feedback_html}

  <script>
{js}
{graphic_js}
  </script>
</body>
</html>'''


def build_hero(parsed, images):
    """Build the hero section — compact version with cards visible above the fold."""
    fm = parsed['front_matter']
    authors_str = ' &middot; '.join(fm['authors'][:3]) if fm['authors'] else ''
    ack_str = html_escape(fm["acknowledgment"]) if fm["acknowledgment"] else ''

    logo_img = ''
    if images.get('logo'):
        logo_img = f'<img src="{images["logo"]}" alt="Impact for Equity" class="hero-logo">'

    search_bar = '''
    <div style="max-width:480px;margin:var(--space-2) auto 0;">
      <div style="display:flex;align-items:center;background:white;border-radius:9999px;padding:8px 16px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border:1px solid #D0DCE5;cursor:text;" onclick="openSearch()" role="button" tabindex="0" aria-label="Open search">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#67808E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <span style="margin-left:10px;color:#919191;font-size:0.875rem;">Search the guide...</span>
      </div>
    </div>'''

    # Compact byline: authors + acknowledgment on one small line
    byline = ''
    parts = []
    if authors_str:
        parts.append(authors_str)
    if ack_str:
        parts.append(ack_str)
    if parts:
        byline = f'<p style="font-size:0.75rem;color:var(--ife-slate);margin:var(--space-1) 0 0;line-height:1.4;">{" | ".join(parts)}</p>'

    return f'''
  <section class="hero" aria-label="Guide hero" style="padding:var(--space-4) var(--space-4) var(--space-3);">
    <div class="hero-inner">
      {logo_img}
      <h1 class="hero-title" style="margin-bottom:var(--space-1);">2026 Guide for Chicago<br>Housing Advocates</h1>
      {byline}
      {search_bar}
    </div>
  </section>'''


def build_toc(parsed):
    """Build the sticky TOC bar."""
    short_titles = {
        'institutions': 'Institutions',
        'funding': 'Funding',
        'programs': 'Programs',
        'ordinances': 'Ordinances',
        'legislative': 'Legislative',
        'resources': 'Resources',
        'glossary': 'Glossary',
    }
    tabs_html = '<li><button class="toc-tab" role="tab" data-view="home" aria-selected="true" tabindex="0">Home</button></li>'
    tabs_html += '<li><button class="toc-tab" role="tab" data-view="introduction" aria-selected="false" tabindex="0">Intro</button></li>'
    for part in parsed['parts']:
        label = short_titles.get(part['id'], part['title'])
        tabs_html += f'<li><button class="toc-tab" role="tab" data-view="{part["id"]}" aria-selected="false" tabindex="0">{label}</button></li>'

    return f'''
  <nav class="toc-bar" aria-label="Table of contents">
    <div class="toc-bar-inner">
      <button class="toc-bar-toggle" aria-expanded="false" aria-controls="toc-tabs-list">Contents</button>
      <ol class="toc-tabs" id="toc-tabs-list" role="tablist">
        {tabs_html}
      </ol>
      <button class="toc-search-btn" aria-label="Search the guide">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
      </button>
    </div>
  </nav>'''


def build_home_view(parsed, images, graphics):
    """Build the home view with cards and introduction."""
    card_descs = {
        'institutions': 'City departments, CHA, state agencies, and private organizations that shape housing policy.',
        'funding': 'City, state, and federal funding mechanisms for affordable housing.',
        'programs': 'Housing assistance programs for renters, homeowners, and homebuyers.',
        'ordinances': 'Key local ordinances and laws shaping housing policy.',
        'legislative': 'How city ordinances and budgets are passed.',
        'resources': 'External guides, data sources, research centers, and tools.',
        'glossary': 'Glossary of housing terms and select bibliography.',
    }

    cards_html = '''
        <div class="section-card" role="button" tabindex="0" data-target="introduction" aria-label="Go to Introduction">
          <div class="section-card-title">Introduction</div>
          <div class="section-card-desc">Overview, racial equity lens, the housing continuum, and area median income.</div>
        </div>'''
    for part in parsed['parts']:
        desc = card_descs.get(part['id'], '')
        cards_html += f'''
        <div class="section-card" role="button" tabindex="0" data-target="{part['id']}" aria-label="Go to Part {part['chapter_num']}: {part['title']}">
          <div class="section-card-num">Part {part['chapter_num']}</div>
          <div class="section-card-title">{part['title']}</div>
          <div class="section-card-desc">{desc}</div>
        </div>'''

    return f'''
    <article id="view-home" class="part-view active" role="tabpanel" aria-hidden="false">
      <div class="content-well">
        <div class="cards-grid">
          {cards_html}
        </div>
      </div>
    </article>'''


def insert_intro_graphics(html, graphics):
    """Insert HTML graphics into the introduction."""
    if 'housing_continuum.html' in graphics:
        g = graphics['housing_continuum.html']
        graphic_html = f'<div class="graphic-container {g["scope_class"]}">{g["html"]}</div>'
        html = re.sub(
            r'(<h2[^>]*id="the-housing-continuum-and-area-median-income"[^>]*>.*?</h2>)',
            r'\1\n' + graphic_html, html, flags=re.DOTALL)

    if 'income_limits.html' in graphics:
        g = graphics['income_limits.html']
        graphic_html = f'<div class="graphic-container {g["scope_class"]}">{g["html"]}</div>'
        html = re.sub(
            r'(affordable to a family making \$35,970.*?</p>)',
            r'\1\n' + graphic_html, html, flags=re.DOTALL)

    return html


def build_intro_view(parsed, graphics):
    """Build the Introduction as its own section view."""
    intro_html = ''
    if parsed['introduction']:
        intro_html = md_to_html(parsed['introduction'])
        intro_html = insert_intro_graphics(intro_html, graphics)

    # Build collapsible TOC from H2 headings in the introduction
    toc_items = ''
    h2_count = 0
    if parsed['introduction']:
        for line in parsed['introduction']:
            h2_match = re.match(r'^##\s+\*\*(.+?)\*\*', line.strip())
            if h2_match:
                title = h2_match.group(1).strip()
                heading_id = slugify(title)
                toc_items += f'<li><a href="#{heading_id}">{title}</a></li>\n'
                h2_count += 1

    section_toc = ''
    if h2_count > 0:
        section_toc = f'''
        <details class="section-toc">
          <summary>Table of Contents ({h2_count} sections)</summary>
          <ol class="section-toc-list">{toc_items}</ol>
        </details>'''

    return f'''
    <article id="view-introduction" class="part-view" role="tabpanel" aria-hidden="true">
      <div class="chapter-divider">
        <div class="chapter-divider-inner">
          <h2 class="chapter-title" id="part-introduction">Introduction</h2>
        </div>
      </div>
      <div class="content-well">
        {section_toc}
        <div class="intro-content">
          {intro_html}
        </div>
      </div>
    </article>'''


def build_part_view(part, images, graphics):
    """Build a Part view."""
    part_id = part['id']

    divider_html = f'''
    <div class="chapter-divider">
      <div class="chapter-divider-inner">
        <div class="chapter-number">{part['chapter_num']}</div>
        <h2 class="chapter-title" id="part-{part_id}">{part['title']}</h2>
      </div>
    </div>'''

    intro_prose = ''
    if part['intro_lines']:
        intro_prose = f'<div class="intro-content">{md_to_html(part["intro_lines"])}</div>'

    graphic_html = ''
    for gname, (gpart, _) in GRAPHIC_PLACEMENTS.items():
        if gpart == part_id and gpart != 'introduction' and gname in graphics:
            g = graphics[gname]
            graphic_html += f'<div class="graphic-container {g["scope_class"]}">{g["html"]}</div>\n'

    # Collapsible section TOC
    section_toc = ''
    if part['sections']:
        toc_items = ''
        for section in part['sections']:
            toc_items += f'<li><a href="#{section["id"]}">{section["title"]}</a></li>\n'
        section_toc = f'''
        <details class="section-toc">
          <summary>Table of Contents ({len(part["sections"])} entries)</summary>
          <ol class="section-toc-list">{toc_items}</ol>
        </details>'''

    filters_html = ''
    if part_id in CATEGORY_LABELS:
        btns = '<button class="cat-btn" role="radio" data-category="all" aria-checked="true">All</button>\n'
        for slug, label in CATEGORY_LABELS[part_id]:
            btns += f'<button class="cat-btn" role="radio" data-category="{slug}" aria-checked="false">{label}</button>\n'
        filters_html = f'<div class="category-filters" role="radiogroup" aria-label="Filter by category">{btns}</div>'

    entries_html = ''
    state_graphic_inserted = False
    for section in part['sections']:
        content_html = md_to_html(section['content_lines'])

        state_graphic = ''
        if (part_id == 'institutions' and section['category'] == 'state'
                and not state_graphic_inserted and 'state_of_illinois_chart.html' in graphics):
            g = graphics['state_of_illinois_chart.html']
            state_graphic = f'<div class="graphic-container {g["scope_class"]}">{g["html"]}</div>'
            state_graphic_inserted = True

        cat_tag = ''
        if part_id in CATEGORY_LABELS:
            cat_label = dict(CATEGORY_LABELS[part_id]).get(section['category'], section['category'])
            cat_tag = f'<span class="entry-category-tag">{cat_label}</span>'

        entries_html += f'''
      <div class="entry" id="{section['id']}" data-category="{section['category']}" tabindex="-1">
        {cat_tag}
        <h3 class="entry-title"><a href="#{section['id']}">{section['title']}</a></h3>
        {state_graphic}
        <div class="entry-content">
          {content_html}
        </div>
      </div>'''

    return f'''
    <article id="view-{part_id}" class="part-view" role="tabpanel" aria-hidden="true">
      {divider_html}
      <div class="content-well">
        {intro_prose}
        {graphic_html}
        {section_toc}
        {filters_html}
        {entries_html}
      </div>
    </article>'''


def build_search_overlay():
    """Build the search overlay."""
    return '''
  <div id="search-overlay" class="search-overlay" role="dialog" aria-label="Search the guide">
    <div class="search-box">
      <div class="search-input-wrap">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input type="text" id="search-input" class="search-input" placeholder="Search entries, programs, ordinances..." role="combobox" aria-expanded="true" aria-controls="search-results" autocomplete="off">
        <button class="search-close" onclick="closeSearch()" aria-label="Close search">&times;</button>
      </div>
      <div id="search-results" class="search-results" role="listbox"></div>
    </div>
  </div>'''


def build_feedback():
    """Build the feedback CTA."""
    return '''
  <div class="feedback-cta">
    <p>Questions or feedback? Email <a href="mailto:housingguide@impactforequity.org">housingguide@impactforequity.org</a></p>
    <p style="font-size:0.75rem;margin-top:8px;color:var(--ife-slate);">&copy; 2026 Impact for Equity. All rights reserved.</p>
  </div>'''


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Building 2026 Guide for Chicago Housing Advocates v2.0")
    print("=" * 60)

    print("\n[1/6] Parsing markdown...")
    with open(MD_FILE, 'r', encoding='utf-8') as f:
        md_text = f.read()
    # Clean up DOCX-inherited Unicode whitespace (NBSP, en/em space, ZWSP, BOM)
    md_text = re.sub(r'[\u00a0\u2002\u2003\u200b\ufeff]', ' ', md_text)
    parsed = parse_markdown(md_text)
    total_entries = sum(len(p['sections']) for p in parsed['parts'])
    print(f"  Parsed {len(parsed['parts'])} Parts with {total_entries} entries")

    # Content audit: verify expected entry counts per part
    expected_counts = {
        'institutions': 26, 'funding': 9, 'programs': 29, 'ordinances': 11,
        'legislative': 6, 'resources': 5, 'glossary': 6,  # 92 total
    }
    audit_ok = True
    for part in parsed['parts']:
        exp = expected_counts.get(part['id'])
        actual = len(part['sections'])
        if exp and actual != exp:
            print(f"  WARNING: {part['id']} has {actual} entries, expected {exp}")
            audit_ok = False
        else:
            print(f"  OK: {part['id']} = {actual} entries")
    if not audit_ok:
        print("  ** Content audit found mismatches — review warnings above **")

    print("\n[2/6] Extracting HTML graphics...")
    graphics = {}
    scope_classes = {
        'housing_continuum.html': 'g-continuum',
        'income_limits.html': 'g-income',
        'combined_housing_bodies.html': 'g-orgchart',
        'programs_by_department.html': 'g-programs',
        'legislative_process.html': 'g-legislative',
        'state_of_illinois_chart.html': 'g-state',
    }
    for gfile, scope_class in scope_classes.items():
        filepath = os.path.join(GRAPHICS_DIR, gfile)
        if os.path.exists(filepath):
            graphics[gfile] = extract_graphic(filepath, scope_class)
            print(f"  {gfile}: CSS={len(graphics[gfile]['css']):,}, HTML={len(graphics[gfile]['html']):,}")
        else:
            print(f"  WARNING: Not found: {filepath}")

    print("\n[3/6] Loading images...")
    image_data = {}
    image_data['logo'] = load_and_encode_image(LOGO_IMAGE)

    print("\n[4/6] Building cross-references...")
    xref_data = build_cross_ref_data(parsed)
    print(f"  {len(xref_data)} entry names indexed")

    print("\n[5/6] Generating HTML...")
    html = build_html(parsed, graphics, image_data)

    print("\n[6/6] Writing output...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_FILE)
    print(f"\n{'=' * 60}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Size:   {file_size:,} bytes ({file_size/1024:.0f} KB)")
    if file_size > 2 * 1024 * 1024:
        print("WARNING: File size exceeds 2 MB target!")
    else:
        print("OK - under 2 MB")
    print("=" * 60)


if __name__ == '__main__':
    main()
