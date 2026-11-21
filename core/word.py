"""Builds the CV as a Word (.docx) file in one of four styles.

All four keep to one column with real text and standard headings, so the
software many employers use to read CVs can read them properly.
"""

import io

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: F401  (kept for custom styles)
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

COLOURS = {"navy": "1F3A5F", "teal": "0F6B63", "burgundy": "7A1F3D", "charcoal": "333333", "black": "000000"}

STYLES = {
    "classic": {"label": "Classic", "about": "Traditional and safe for any job.",
                "font": "Cambria", "size": 11, "name_size": 20, "margins": 2.0, "align": "center",
                "heading": "caps_rule", "colour": "black"},
    "modern": {"label": "Modern", "about": "Clean, with a touch of colour.",
               "font": "Calibri", "size": 11, "name_size": 24, "margins": 1.8, "align": "left",
               "heading": "colour", "colour": "teal"},
    "compact": {"label": "Compact", "about": "Fits more on one page.",
                "font": "Arial", "size": 9.5, "name_size": 16, "margins": 1.3, "align": "left",
                "heading": "caps_rule", "colour": "charcoal"},
    "executive": {"label": "Executive", "about": "Elegant, for senior or client facing roles.",
                  "font": "Garamond", "size": 11.5, "name_size": 22, "margins": 2.2, "align": "center",
                  "heading": "centred", "colour": "navy"},
}


def _border(paragraph, where="bottom", colour="000000", size=6):
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    el = OxmlElement(f"w:{where}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), "1")
    el.set(qn("w:color"), colour)
    borders.append(el)


def _font(run, name, size=None, bold=None, colour=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if colour:
        run.font.color.rgb = RGBColor.from_string(colour)


def is_group(skill: str) -> bool:
    """A labelled skill group such as "Cloud / AWS: EC2, S3, Lambda"."""
    label = skill.split(":", 1)[0]
    return ":" in skill and len(label) < 40 and len(skill) > 30


def dates(start: str, end: str) -> str:
    start, end = (start or "").strip(), (end or "").strip()
    if start and end:
        return f"{start} to {end}"
    return start or end


def build(cv: dict, style: str = "modern", colour: str = "", order: str = "experience_first") -> bytes:
    st = STYLES.get(style, STYLES["modern"])
    accent = COLOURS.get(colour or st["colour"], COLOURS[st["colour"]])
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)   # A4
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(st["margins"]))
    width = sec.page_width - sec.left_margin - sec.right_margin

    normal = doc.styles["Normal"]
    normal.font.name = st["font"]
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), st["font"])
    normal.font.size = Pt(st["size"])
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.05 if style == "compact" else 1.12
    bullet_style = doc.styles["List Bullet"]
    bullet_style.font.name = st["font"]
    bullet_style.font.size = Pt(st["size"])
    gap = 3 if style == "compact" else 6
    centred = st["align"] == "center"

    def para(text="", size=None, bold=False, colour=None, align=None, after=0, before=0, italic=False):
        p = doc.add_paragraph()
        if text:
            _font(p.add_run(text), st["font"], size or st["size"], bold, colour, italic)
        if align == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.space_before = Pt(before)
        return p

    # Name and contact
    name = para(cv.get("name") or "Your Name", st["name_size"], True,
                accent if style in ("modern", "executive") else None, st["align"])
    if style == "executive":
        name.runs[0].font.small_caps = True
    if cv.get("title"):
        para(cv["title"], st["size"] + 1.5, False, accent if style != "classic" else None, st["align"],
             italic=style == "executive")
    contact = [x for x in [cv.get("location"), cv.get("phone"), cv.get("email"), *cv.get("links", [])] if x]
    if contact:
        p = para("  |  ".join(contact), st["size"] - 1, align=st["align"], after=gap)
        if style == "modern":
            _border(p, "bottom", accent, 12)

    def heading(title):
        p = para(before=gap * 2 if style != "compact" else gap + 2, after=gap / 2 + 1)
        p.paragraph_format.keep_with_next = True   # never leave a heading alone at the foot of a page
        text = title.upper() if st["heading"] in ("caps_rule", "centred") else title
        _font(p.add_run(text), st["font"], st["size"] + (1.5 if style != "compact" else 1), True,
              accent if style != "classic" else None)
        if st["heading"] == "caps_rule":
            _border(p, "bottom", "000000" if style == "classic" else accent, 6)
        if st["heading"] == "centred":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _border(p, "top", accent, 4)
            _border(p, "bottom", accent, 4)
        if st["heading"] == "colour":
            p.runs[0].font.all_caps = False
        return p

    def line_with_date(left_bold, left_rest, right):
        p = para(before=gap)
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        p.paragraph_format.keep_with_next = True
        _font(p.add_run(left_bold), st["font"], st["size"], True)
        if left_rest:
            _font(p.add_run(left_rest), st["font"], st["size"], False)
        if right:
            _font(p.add_run("\t" + right), st["font"], st["size"] - 0.5, False, None, True)
        return p

    def bullets(items):
        for b in items:
            p = doc.add_paragraph(style="List Bullet")
            _font(p.add_run(b), st["font"], st["size"])
            p.paragraph_format.space_after = Pt(1)

    def summary():
        if cv.get("summary"):
            heading("Profile")
            para(cv["summary"], after=0)

    def skills():
        if cv.get("skills"):
            heading("Key skills")
            groups = [s for s in cv["skills"] if is_group(s)]
            plain = [s for s in cv["skills"] if not is_group(s)]
            if plain:
                para("  •  ".join(plain), align="center" if centred and len(plain) <= 14 and style != "compact" else None,
                     after=3 if groups else 0)
            for g in groups:   # "Cloud / AWS: EC2, S3, Lambda" with the label in bold
                label, items = g.split(":", 1)
                p = para(after=1)
                _font(p.add_run(label.strip() + ": "), st["font"], st["size"], True)
                _font(p.add_run(items.strip()), st["font"], st["size"])

    def experience():
        if cv.get("experience"):
            heading("Experience")
            for e in cv["experience"]:
                rest = "".join(x for x in [f", {e['company']}" if e.get("company") else "",
                                           f", {e['location']}" if e.get("location") else ""])
                line_with_date(e.get("role") or e.get("company") or "", rest, dates(e.get("start"), e.get("end")))
                bullets(e.get("bullets", []))

    def projects():
        if cv.get("projects"):
            heading("Projects")
            for pj in cv["projects"]:
                p = line_with_date(pj.get("name", ""), "", pj.get("date", ""))
                if pj.get("tech"):
                    t = para(after=1)
                    t.paragraph_format.keep_with_next = True
                    _font(t.add_run(pj["tech"]), st["font"], st["size"] - 0.5, False, None, True)
                bullets(pj.get("bullets", []))

    def education():
        if cv.get("education"):
            heading("Education")
            for e in cv["education"]:
                rest = "".join(x for x in [f", {e['school']}" if e.get("school") else "",
                                           f", {e['location']}" if e.get("location") else ""])
                line_with_date(e.get("degree") or e.get("school") or "", rest, dates(e.get("start"), e.get("end")))
                bullets(e.get("details", []))

    def certs():
        if cv.get("certifications"):
            heading("Certifications")
            bullets(cv["certifications"])

    def other():
        for o in cv.get("other", []):
            if o.get("items"):
                heading(o.get("heading") or "Other")
                bullets(o["items"])

    parts = [summary, skills, experience, projects, education, certs, other]
    if order == "education_first":
        parts = [summary, skills, education, projects, experience, certs, other]
    for part in parts:
        part()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
