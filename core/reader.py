"""Reads a CV from a Word file, a PDF or plain text, and sorts it into
sections: contact details, summary, skills, experience, education, projects,
certifications and anything else.

Reading CVs without AI is guesswork, because everyone lays theirs out
differently. So the result always goes into a form you can check and fix.
With a Gemini key, the AI does this sorting instead, which is more reliable.
"""

import io
import re

HEADINGS = {
    "summary": ["summary", "profile", "personal profile", "professional summary", "about me",
                "personal statement", "career summary", "objective", "career objective", "overview"],
    "skills": ["skills", "key skills", "technical skills", "core skills", "skills and tools",
               "core competencies", "competencies", "technologies", "tools", "technical expertise",
               "skills & tools", "key skills & tools", "tech stack"],
    "experience": ["experience", "work experience", "professional experience", "employment",
                   "employment history", "work history", "career history", "relevant experience"],
    "education": ["education", "education and training", "academic background", "qualifications",
                  "education & training"],
    "projects": ["projects", "personal projects", "key projects", "portfolio", "selected projects"],
    "certifications": ["certifications", "certificates", "certification", "licences", "licenses",
                       "courses", "training", "certifications & training"],
}
_HEAD = {h: k for k, hs in HEADINGS.items() for h in hs}

MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE = rf"(?:{MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
RANGE = re.compile(rf"({DATE})\s*(?:-|–|—|to)\s*({DATE}|present|current|now|today)", re.I)
# Bullet marks, including the odd symbols Word puts in PDFs (\uf0b7 and similar)
BULLET = re.compile(r"^\s*(?:[•\-\*▪●◦‣·►➢✓❖\uf000-\uf0ff]|o(?=\s)|\d+[.)])\s+")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?\d[\d\s()-]{8,}\d)")
LINK = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[\w-]+\.(?:dev|io|me|com|co\.uk|org))/?[\w/.-]*", re.I)


def empty_cv() -> dict:
    return {"name": "", "title": "", "email": "", "phone": "", "location": "", "links": [],
            "summary": "", "skills": [], "experience": [], "education": [], "projects": [],
            "certifications": [], "other": []}


def text_from_file(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(data))
        def para_text(p):
            # Keep Word's tabs, because many CVs put the dates after a tab.
            out = []
            for t in p.iter():
                if t.tag.endswith("}t"):
                    out.append(t.text or "")
                elif t.tag.endswith("}tab") and t.getparent().tag.endswith("}r"):
                    out.append("\t")
            return "".join(out)

        lines = []
        for block in doc.element.body.iterchildren():
            tag = block.tag.split("}")[-1]
            if tag == "p":
                lines.append(para_text(block))
            elif tag == "tbl":   # CVs laid out in tables
                for row in block.iter():
                    if row.tag.endswith("}p"):
                        lines.append(para_text(row))
        # Word list bullets are formatting, not characters, so mark them.
        out = []
        paras = {p._p: p for p in doc.paragraphs}
        for block, line in zip(doc.element.body.iterchildren(), lines):
            p = paras.get(block)
            if p is not None and p.style is not None and "list" in (p.style.name or "").lower() and line.strip():
                line = "• " + line
            out.append(line)
        out += lines[len(out):]
        return "\n".join(out)
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".doc"):
        raise ValueError("Old .doc files cannot be read. Open it in Word and save it as .docx first.")
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("That file could not be read.")


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace(" ", " ")).strip()


HEAD_WORDS = [  # checked in this order, for headings like "Reliability & Infrastructure Projects"
    ("projects", r"\bprojects?\b|\bportfolio\b"),
    ("certifications", r"\bcertificat|\blicen[cs]es\b|\bcourses\b"),
    ("experience", r"\bexperience\b|\bemployment\b|\bwork history\b|\bcareer history\b"),
    ("education", r"\beducation\b|\bqualifications\b|\bacademic"),
    ("skills", r"\bskills\b|\bstrengths\b|\bcompetenc|\bexpertise\b|\btech(nical)? stack\b|\btools\b"),
    ("summary", r"\bsummary\b|\bprofile\b|\bobjective\b|\babout me\b|\bpersonal statement\b"),
]


def _heading(line: str):
    t = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    if not t or len(t) > 45 or len(t.split()) > 6:
        return None
    if t in _HEAD:
        return _HEAD[t]
    # Only treat it as a heading if it looks like one: capitals or title case, no full stop.
    looks = line.strip().isupper() or line.strip().istitle() or len(t.split()) <= 3
    if not looks or line.strip().endswith("."):
        return None
    for key, rx in HEAD_WORDS:
        if re.search(rx, t):
            return key
    return None


def _split_skills(lines):
    skills = []
    for line in lines:
        line = _clean(BULLET.sub("", line))
        if ":" in line and len(line.split(":", 1)[0]) < 40 and len(line) > 45:
            # A labelled group such as "Cloud / AWS: EC2, S3, Lambda" stays as one line.
            skills.append(line)
            continue
        if ":" in line and len(line.split(":", 1)[0]) < 30:
            line = line.split(":", 1)[1]
        # split on commas and similar, but not inside brackets: "AWS (EC2, S3)"
        for part in re.split(r"[,;|•·](?![^()]*\))|\s{2,}|\s/\s", line):
            part = part.strip(" .-")
            if 1 < len(part) <= 60:
                skills.append(part)
    seen, out = set(), []
    for s in skills:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


ROLE_WORDS = re.compile(r"\b(engineer|intern|manager|analyst|developer|assistant|supervisor|lead|leader|"
                        r"consultant|officer|associate|specialist|administrator|technician|architect|designer|"
                        r"executive|director|coordinator|co-ordinator|apprentice|trainee|advisor|adviser|head|"
                        r"scientist|researcher|tester|support|operator|representative|clerk|teacher|nurse|"
                        r"volunteer|founder|owner|freelance|contractor|programmer|administrator)\b", re.I)
DEGREE_WORDS = re.compile(r"\b(msc|bsc|btech|mtech|ba|ma|beng|meng|mba|phd|bachelor|master|masters|degree|diploma|"
                          r"hnd|hnc|a[- ]levels?|gcses?|btec|certificate|foundation|nvq|level \d|honours|hons)\b", re.I)
SINGLE_DATE = re.compile(rf"^(?:(?:earned|issued|completed|since|from)\s+)?({DATE}|present)$", re.I)


def _split_date(raw: str):
    """Split "Text<TAB>Sept 2024 - Sept 2025" or "Text 2024" into (text, start, end)."""
    parts = raw.split("\t")
    left = _clean(parts[0])
    right = _clean(" ".join(parts[1:])) if len(parts) > 1 else ""
    for chunk in ([right] if right else []) + [left]:
        m = RANGE.search(chunk)
        if m:
            rest = _clean(RANGE.sub("", chunk)).strip(" |,–—-")
            text = left if chunk is right else rest
            return text, m.group(1).strip(), m.group(2).strip().title()
    if right and SINGLE_DATE.match(right.split("|")[0].strip()):
        return left, "", SINGLE_DATE.match(right.split("|")[0].strip()).group(1).title()
    m = re.search(rf"\s({DATE})$", left)
    if m and not right:
        return _clean(left[:m.start()]).strip(" |,–—-"), "", m.group(1).title()
    return _clean(left + (" " + right if right else "")), "", ""


def _assign(parts, keyword, first_key, second_key, e):
    """Put the job title (or qualification) and the employer (or school) in
    the right boxes, whichever order the CV writes them in."""
    if len(parts) >= 2 and not keyword.search(parts[0]) and keyword.search(parts[1]):
        parts[0], parts[1] = parts[1], parts[0]
    e[first_key] = parts[0] if parts else ""
    e[second_key] = parts[1] if len(parts) > 1 else ""
    e["location"] = parts[2] if len(parts) > 2 else ""


def _entries(lines, kind):
    """Split experience, education or project lines into entries. A new entry
    starts at a non bullet line that follows bullets, or at a line with dates."""
    entries, cur = [], None

    def new():
        return ({"role": "", "company": "", "location": "", "start": "", "end": "", "bullets": []}
                if kind == "experience" else
                {"degree": "", "school": "", "location": "", "start": "", "end": "", "details": []}
                if kind == "education" else {"name": "", "tech": "", "date": "", "bullets": []})

    header_lines = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        is_bullet = bool(BULLET.match(raw))
        text = BULLET.sub("", line)
        # A line that starts in lower case straight after a point is the rest
        # of that point, wrapped onto a new line (common in PDFs).
        items = (cur.get("bullets") if cur and "bullets" in cur else cur.get("details") if cur else None)
        if not is_bullet and items and line[:1].islower() and not RANGE.search(line):
            items[-1] = items[-1] + " " + line
            continue
        if is_bullet and cur is not None:
            (cur.get("bullets") if "bullets" in cur else cur["details"]).append(text)
            continue
        text_part, d_start, d_end = _split_date(raw) if not is_bullet else (line, "", "")
        has_date = bool(d_start or d_end)
        if cur is None or (cur and (cur.get("bullets") or cur.get("details"))) or \
                (has_date and (cur.get("start") or cur.get("end") or cur.get("date"))):
            if cur is not None:
                entries.append(cur)
            cur = new()
            header_lines = []
        if is_bullet:
            (cur.get("bullets") if "bullets" in cur else cur["details"]).append(text)
            continue
        if kind == "projects":
            if has_date:
                cur["date"] = " to ".join(x for x in (d_start, d_end) if x)
            if not cur["name"]:
                name, _, tools = text_part.partition(" | ")   # "Name | tools used"
                cur["name"] = name.strip()
                if tools:
                    cur["tech"] = tools.strip()
            elif not cur["tech"]:
                cur["tech"] = text_part          # the tools line under the project name
            else:
                cur["bullets"].append(text_part)
            continue
        if has_date:
            cur["start"], cur["end"] = d_start, d_end
        if not text_part:
            continue
        header_lines.append(text_part)
        parts = [p.strip() for p in re.split(r"\s[|–—-]\s|\s{2,}|,\s(?=[A-Z])|\sat\s", " | ".join(header_lines)) if p.strip()]
        if kind == "experience":
            _assign(parts, ROLE_WORDS, "role", "company", cur)
        else:
            _assign(parts, DEGREE_WORDS, "degree", "school", cur)
    if cur is not None:
        entries.append(cur)
    return [e for e in entries if any(v for v in e.values())]


def parse_text(text: str) -> dict:
    """Sort CV text into sections without AI."""
    cv = empty_cv()
    text = text.replace("\r", "")
    text = re.sub(r"(\S)-\n([a-z])", r"\1-\2", text)   # words and links split over two lines
    lines = text.split("\n")
    sections = {"top": []}
    current = "top"
    other_title = None
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        key = _heading(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        # Upper case short lines we do not know are their own "other" section
        if line.isupper() and len(line) < 35 and current != "top" and len(line.split()) <= 4:
            other_title = line.title()
            current = f"other:{other_title}"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw)

    top = [_clean(l) for l in sections["top"]]
    joined = " | ".join(top)
    if m := EMAIL.search(joined):
        cv["email"] = m.group(0)
    if m := PHONE.search(joined):
        cv["phone"] = _clean(m.group(0))
    cv["links"] = sorted({m.group(0).rstrip("/.") for m in LINK.finditer(joined)
                          if "@" not in m.group(0) and m.group(0) not in cv["email"]})
    for i, line in enumerate(top):
        is_contact = bool(EMAIL.search(line) or PHONE.search(line) or LINK.search(line))
        parts = [p.strip() for p in re.split(r"\s*[|•·]\s*", line) if p.strip()]
        if i == 0 and not is_contact:
            cv["name"] = line.title() if line.isupper() else line
            continue
        if is_contact:
            for p in parts:
                if EMAIL.search(p) or LINK.fullmatch(p) or (PHONE.search(p) and len(PHONE.sub("", p).strip()) < 3):
                    continue
                if not cv["location"] and len(p) < 40:
                    cv["location"] = p
        elif not cv["title"]:
            cv["title"] = line if len(line) <= 140 else parts[0]   # keep the whole headline
        elif not cv["location"] and len(line) < 40:
            cv["location"] = line

    cv["summary"] = " ".join(_clean(BULLET.sub("", l)) for l in sections.get("summary", []))
    cv["skills"] = _split_skills(sections.get("skills", []))
    cv["experience"] = _entries(sections.get("experience", []), "experience")
    cv["education"] = _entries(sections.get("education", []), "education")
    cv["projects"] = _entries(sections.get("projects", []), "projects")
    certs, can_merge = [], False
    for raw in sections.get("certifications", []):
        if not _clean(raw):
            continue
        text = BULLET.sub("", raw.strip())
        if "\t" in text:
            name, when = [_clean(x) for x in text.split("\t", 1)]
            certs.append(f"{name} ({when})" if when else name)
            can_merge = True
        elif certs and can_merge and len(text) < 50 and not re.search(r"certified|practitioner|associate\b|professional\b", text, re.I):
            certs[-1] += f", {_clean(text)}"    # the issuer, such as "Amazon Web Services"
            can_merge = False
        else:
            certs.append(_clean(text))
            can_merge = False
    cv["certifications"] = certs
    for key, val in sections.items():
        if key.startswith("other:") and val:
            cv["other"].append({"heading": key.split(":", 1)[1],
                                "items": [_clean(BULLET.sub("", l)) for l in val if _clean(l)]})
    return cv


def cv_to_text(cv: dict) -> str:
    """The whole CV as plain text, used for matching."""
    parts = [cv.get("name", ""), cv.get("title", ""), cv.get("summary", ""), ", ".join(cv.get("skills", []))]
    for e in cv.get("experience", []):
        parts += [e.get("role", ""), e.get("company", "")] + e.get("bullets", [])
    for e in cv.get("education", []):
        parts += [e.get("degree", ""), e.get("school", "")] + e.get("details", [])
    for p in cv.get("projects", []):
        parts += [p.get("name", ""), p.get("tech", ""), p.get("date", "")] + p.get("bullets", [])
    parts += cv.get("certifications", [])
    for o in cv.get("other", []):
        parts += [o.get("heading", "")] + o.get("items", [])
    return "\n".join(x for x in parts if x)
