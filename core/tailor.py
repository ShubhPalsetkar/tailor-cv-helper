"""Tailors a CV to a job.

Offline (no key): puts the skills the job wants first, moves the most
relevant bullets to the top of each job, puts the most relevant projects
first, and lists suggestions. It does not change your words.

With Gemini: also rewrites the summary and bullets using the job's language.

Either way, an honesty check runs at the end. Any skill, number or job that
was not in your original CV is taken out or flagged for you to check.
"""

import copy
import re

from core import ai
from core.matcher import check, job_skills, keywords, stem
from core.reader import cv_to_text, empty_cv
from core.skills import find_skills


def normalise(cv: dict) -> dict:
    """Make sure every field exists and has the right type."""
    base = empty_cv()
    out = {}
    for k, v in base.items():
        val = cv.get(k, v) if isinstance(cv, dict) else v
        if isinstance(v, str):
            out[k] = str(val or "").strip()
        else:
            out[k] = list(val) if isinstance(val, list) else []
    out["links"] = [str(x).strip() for x in out["links"] if str(x).strip()]
    out["skills"] = [str(x).strip() for x in out["skills"] if str(x).strip()]
    out["certifications"] = [str(x).strip() for x in out["certifications"] if str(x).strip()]

    def entries(items, fields, listkey):
        clean = []
        for e in items:
            if not isinstance(e, dict):
                continue
            row = {f: str(e.get(f, "") or "").strip() for f in fields}
            row[listkey] = [str(b).strip() for b in (e.get(listkey) or []) if str(b).strip()]
            if any(row.values()):
                clean.append(row)
        return clean

    out["experience"] = entries(out["experience"], ["role", "company", "location", "start", "end"], "bullets")
    out["education"] = entries(out["education"], ["degree", "school", "location", "start", "end"], "details")
    out["projects"] = entries(out["projects"], ["name", "tech", "date"], "bullets")
    out["other"] = entries(out["other"], ["heading"], "items")
    return out


def _relevance(text: str, wanted: dict, kw_stems: set) -> float:
    found = find_skills(text)
    score = sum(2 if wanted.get(s) == "must" else 1 for s in found if s in wanted)
    score += 0.5 * len({stem(w) for w in re.findall(r"[A-Za-z]{4,}", text)} & kw_stems)
    return score


def offline(cv: dict, job: str) -> dict:
    cv = normalise(cv)
    out = copy.deepcopy(cv)
    wanted = job_skills(job)
    kw_stems = {stem(w) for w in keywords(job)}
    changes = []

    order = list(wanted)
    def skill_rank(s):
        hits = [order.index(k) for k in find_skills(s) if k in wanted]
        return (0, min(hits)) if hits else (1, 0)
    new_skills = sorted(out["skills"], key=skill_rank)
    if new_skills != out["skills"]:
        out["skills"] = new_skills
        moved = [s for s in new_skills if skill_rank(s)[0] == 0]
        changes.append({"section": "Skills", "what": "Moved the skills this job asks for to the front: "
                        + ", ".join(moved[:6]), "why": "Recruiters skim the first few skills."})

    for e in out["experience"]:
        ranked = sorted(e["bullets"], key=lambda b: -_relevance(b, wanted, kw_stems))
        if ranked != e["bullets"]:
            e["bullets"] = ranked
            changes.append({"section": "Experience", "what": f"Reordered the points under {e['role'] or 'a job'} "
                            "so the most relevant come first.", "why": "The first point under each job gets read most."})

    ranked = sorted(out["projects"], key=lambda p: -_relevance(
        " ".join([p["name"], p["tech"], *p["bullets"]]), wanted, kw_stems))
    if ranked != out["projects"]:
        out["projects"] = ranked
        changes.append({"section": "Projects", "what": "Put your most relevant project first.",
                        "why": "It shows the skills this job wants straight away."})

    result = check(cv, job)
    advice = []
    for g in result["gaps"][:6]:
        advice.append(f"{g['skill']} ({'must have' if g['level'] == 'must' else 'nice to have'}): {g['tip']}")
    for s in result["unproven"][:4]:
        advice.append(f"{s} is in your skills list but not in any job or project point. "
                      f"Add an example of when you used it.")
    if result["missing_keywords"]:
        advice.append("The job also uses these words a lot: " + ", ".join(result["missing_keywords"][:6])
                      + ". Use them where they honestly describe what you did.")
    advice.append("Rewrite your summary so the first sentence says what this job is looking for, "
                  "in your own true words. (Add a free Gemini key and Tailor can draft this for you.)")
    return {"cv": out, "changes": changes, "advice": advice, "flags": [], "used_ai": False}


def with_ai(cv: dict, job: str, key: str, **kw) -> dict:
    cv = normalise(cv)
    reply = ai.tailor_cv(cv, job, key, **kw)
    new = normalise(reply.get("cv") or {})
    changes = [c for c in reply.get("changes", []) if isinstance(c, dict)]
    advice = [str(a) for a in reply.get("advice", []) if str(a).strip()]
    new, flags = honesty_check(cv, new)
    if not new["experience"] and cv["experience"]:
        raise RuntimeError("The AI reply left out your jobs, so it was not used.")
    return {"cv": new, "changes": changes, "advice": advice, "flags": flags, "used_ai": True}


def honesty_check(original: dict, new: dict):
    """Undo or flag anything the AI added that was not in the original CV."""
    flags = []
    src = cv_to_text(original)
    src_low = src.lower()
    src_skills = set(find_skills(src))

    # Contact details stay exactly as they were.
    for k in ("name", "email", "phone", "location", "links"):
        new[k] = copy.deepcopy(original[k])

    # No new skills.
    kept = []
    for s in new["skills"]:
        added = [k for k in find_skills(s) if k not in src_skills]
        if s.lower() in src_low or not added:
            kept.append(s)
        else:
            flags.append(f"Removed \"{s}\" from your skills: it was not in your original CV. "
                         "Only add it back if it is true.")
    new["skills"] = kept

    # No new jobs, schools or dates.
    def same_entries(orig, items, keyname, label):
        out = []
        for e in items:
            match = next((o for o in orig if o[keyname] and (o[keyname].lower() in e[keyname].lower()
                          or e[keyname].lower() in o[keyname].lower())), None)
            if match is None:
                flags.append(f"Removed a {label} the AI added that was not in your CV: {e[keyname] or 'untitled'}.")
                continue
            for f in ("start", "end", "company", "school"):
                if f in match:
                    e[f] = match[f]
            out.append(e)
        return out
    new["experience"] = same_entries(original["experience"], new["experience"], "role", "job")
    new["education"] = same_entries(original["education"], new["education"], "degree", "qualification")
    new["certifications"] = [c for c in new["certifications"] if c.lower() in src_low] or original["certifications"]

    # Numbers that were not in the CV before.
    src_numbers = set(re.findall(r"\d+(?:\.\d+)?", src))
    texts = [("Summary", new["summary"])]
    texts += [(e["role"], b) for e in new["experience"] for b in e["bullets"]]
    texts += [(p["name"], b) for p in new["projects"] for b in p["bullets"]]
    for where, t in texts:
        for n in set(re.findall(r"\d+(?:\.\d+)?", t)) - src_numbers:
            flags.append(f"Check the number {n} in \"{t[:70]}\" ({where}). It was not in your original CV.")
    return new, flags
