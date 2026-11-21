"""Checks how well a CV matches a job description, and lists the gaps.

The score is worked out the same way every time, without AI, so you can trust
that a higher score really means a better match:

    Must have skills found       55 points
    Nice to have skills found    20 points
    Other key words found        15 points
    Years of experience          10 points
"""

import re
from collections import Counter
from datetime import date

from core.reader import RANGE, cv_to_text
from core.skills import CATEGORY, find_skills

NICE_WORDS = re.compile(r"\b(nice to have|desirable|preferred|bonus|a plus|advantage|ideally|"
                        r"would be great|beneficial|not essential|bonus points)\b", re.I)
MUST_HEAD = re.compile(r"\b(requirements|required|essential|must have|you will have|you'll have|"
                       r"what you need|what we're looking for|about you|skills and experience|"
                       r"qualifications|responsibilities|the role|key skills)\b", re.I)
NICE_HEAD = re.compile(r"\b(nice to have|desirable|preferred|bonus|nice-to-have|good to have)\b", re.I)
PERKS = re.compile(r"\b(we offer|benefits|holiday|pension|salary|perks|bonus scheme|"
                   r"training budget|days off|annual leave|cycle to work|discount)\b", re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs)", re.I)

STOP = set("""a about above after again all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has
have having he her here hers him his how i if in into is it its itself just me more most my no nor not
now of off on once only or other our ours out over own same she should so some such than that the
their them then there these they this those through to too under until up very was we were what when
where which while who whom why will with would you your yours role team work working job company
candidate candidates join us looking opportunity ability strong excellent good great experience
including within across using based new well able ensure help support including day days year years
skills skill knowledge understanding environment business key etc e.g ie per must please apply salary
benefits holiday pension we're you'll you're it's will ideal successful responsibilities requirements
required desirable essential plus bonus hybrid remote office onsite write help look looks
things parts boring happen clear friendly learn want need make like get keep run running""".split())


def stem(word: str) -> str:
    """Cut common word endings so "scripting" matches "scripts"."""
    w = word.lower()
    for end in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "ed", "es", "s"):
        if w.endswith(end) and len(w) - len(end) >= 4:
            return w[: -len(end)]
    return w


def _job_lines(jd: str):
    """Split the job description into lines, each marked must or nice."""
    out = []
    mode = "must"
    for raw in re.split(r"\n|(?<=[.!?])\s+(?=[A-Z])", jd):
        line = raw.strip()
        if not line:
            continue
        short = len(line) < 60 and not line.endswith(".")
        if short and NICE_HEAD.search(line):
            mode = "nice"
            continue
        if short and MUST_HEAD.search(line):
            mode = "must"
            continue
        if PERKS.search(line):
            continue   # what they offer you, not what they want from you
        out.append((line, "nice" if (mode == "nice" or NICE_WORDS.search(line)) else "must"))
    return out


def job_skills(jd: str) -> dict:
    """Skills the job asks for: {name: "must" or "nice"}."""
    kinds = {}
    for line, kind in _job_lines(jd):
        for name in find_skills(line):
            if kinds.get(name) != "must":
                kinds[name] = kind
    return kinds


def keywords(text: str, n: int = 15) -> list:
    """Other words the job repeats that are not in the skills list."""
    text = "\n".join(line for line, _ in _job_lines(text))
    words = re.findall(r"[A-Za-z][A-Za-z+#.-]{3,}", text)
    known = {w.lower() for w in find_skills(text)}
    count = Counter(w.lower().strip(".-") for w in words)
    out = [w for w, c in count.most_common(80)
           if w not in STOP and w not in known and c >= 2 and not w.isdigit()]
    return out[:n]


def years_wanted(jd: str):
    vals = [int(m.group(1)) for m in YEARS.finditer(jd) if 0 < int(m.group(1)) <= 20]
    return max(vals) if vals else None


def _to_date(s: str, end=False):
    s = (s or "").strip().lower()
    if not s:
        return None
    if s in ("present", "current", "now", "today"):
        return date.today()
    m = re.search(r"(\d{4})", s)
    if not m:
        return None
    year = int(m.group(1))
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    month = next((i + 1 for i, mo in enumerate(months) if mo in s), None)
    if month is None:
        m2 = re.match(r"(\d{1,2})/\d{4}", s)
        month = int(m2.group(1)) if m2 else (12 if end else 1)
    return date(year, max(1, min(12, month)), 1)


def years_on_cv(cv: dict) -> float:
    """Rough total years of work, with overlapping jobs counted once."""
    spans = []
    for e in cv.get("experience", []):
        a, b = _to_date(e.get("start")), _to_date(e.get("end"), end=True)
        if a and b and b >= a:
            spans.append((a, b))
    spans.sort()
    total, cur = 0, None
    for a, b in spans:
        if cur and a <= cur[1]:
            cur = (cur[0], max(cur[1], b))
        else:
            if cur:
                total += (cur[1] - cur[0]).days
            cur = (a, b)
    if cur:
        total += (cur[1] - cur[0]).days
    return round(total / 365.25, 1)


def check(cv: dict, jd: str) -> dict:
    """Score the CV against the job and list what is missing."""
    text = cv_to_text(cv)
    have = find_skills(text)
    want = job_skills(jd)
    must = [s for s, k in want.items() if k == "must"]
    nice = [s for s, k in want.items() if k == "nice"]
    must_hit = [s for s in must if s in have]
    nice_hit = [s for s in nice if s in have]

    kw = keywords(jd)
    cv_stems = {stem(w) for w in re.findall(r"[A-Za-z][A-Za-z+#.-]{2,}", text)}
    kw_hit = [w for w in kw if stem(w) in cv_stems]

    need_years = years_wanted(jd)
    got_years = years_on_cv(cv)

    pts_must = 55 * (len(must_hit) / len(must)) if must else 55
    pts_nice = 20 * (len(nice_hit) / len(nice)) if nice else 20
    pts_kw = 15 * (len(kw_hit) / len(kw)) if kw else 15
    pts_years = 10 if not need_years else 10 * min(1.0, got_years / need_years)
    total = int(round(pts_must + pts_nice + pts_kw + pts_years))

    if total >= 75:
        verdict, advice = "Strong match", "You meet most of what they ask for. Worth applying."
    elif total >= 55:
        verdict, advice = "Good match with gaps", "You meet a lot of it. Apply, and cover the gaps below where you honestly can."
    elif total >= 35:
        verdict, advice = "Partial match", "You meet some of it. Apply if the gaps are things you can show or learn quickly."
    else:
        verdict, advice = "Weak match", "This role asks for a lot you have not shown yet. Look at the gaps before applying."

    # Skills listed on the CV but never shown in a job or project bullet
    bullets = " ".join(b for e in cv.get("experience", []) + cv.get("projects", []) for b in e.get("bullets", []))
    in_bullets = find_skills(bullets)
    unproven = [s for s in must_hit + nice_hit if s not in in_bullets and CATEGORY.get(s) != "Qualifications"]

    gaps = []
    for s in must:
        if s not in have:
            gaps.append({"skill": s, "level": "must", "category": CATEGORY.get(s, ""),
                         "tip": _tip(s, True)})
    for s in nice:
        if s not in have:
            gaps.append({"skill": s, "level": "nice", "category": CATEGORY.get(s, ""),
                         "tip": _tip(s, False)})

    return {
        "score": total,
        "verdict": verdict,
        "advice": advice,
        "parts": {
            "must": {"points": round(pts_must), "of": 55, "found": must_hit, "wanted": must},
            "nice": {"points": round(pts_nice), "of": 20, "found": nice_hit, "wanted": nice},
            "keywords": {"points": round(pts_kw), "of": 15, "found": kw_hit, "wanted": kw},
            "years": {"points": round(pts_years), "of": 10, "wanted": need_years, "have": got_years},
        },
        "gaps": gaps,
        "missing_keywords": [w for w in kw if w not in kw_hit],
        "unproven": unproven,
        "years_short": bool(need_years and got_years < need_years),
    }


def _tip(skill: str, must: bool) -> str:
    cat = CATEGORY.get(skill, "")
    if cat == "Ways of working":
        return (f"Most people have some {skill.lower()}. Show it with a short example in one of "
                f"your job bullets, rather than just listing the word.")
    if cat == "Qualifications":
        return (f"If you have {skill}, add it clearly. If not, say in your cover letter if you are "
                f"working towards it.")
    start = f"If you have used {skill}, even a little, add it with a real example of what you did."
    if must:
        return start + " If not, a short course or a small project you can show would help."
    return start + " It is a nice to have, so it is fine to apply without it."
