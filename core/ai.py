"""Talks to Google Gemini (free allowance). Every function raises
RuntimeError with a plain message if anything goes wrong, so the app can fall
back to the offline way."""

import json
import urllib.error
import urllib.request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
# Tried in order. If Google retires one, the next is used.
MODELS = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-2.5-flash"]

SCHEMA = """{
  "name": "", "title": "", "email": "", "phone": "", "location": "", "links": [""],
  "summary": "",
  "skills": [""],
  "experience": [{"role": "", "company": "", "location": "", "start": "", "end": "", "bullets": [""]}],
  "education": [{"degree": "", "school": "", "location": "", "start": "", "end": "", "details": [""]}],
  "projects": [{"name": "", "tech": "", "date": "", "bullets": [""]}],
  "certifications": [""],
  "other": [{"heading": "", "items": [""]}]
}"""

PARSE_PROMPT = """Sort this CV into JSON with exactly this shape:
""" + SCHEMA + """

Rules:
- Copy the person's own words. Do not rewrite, improve or add anything.
- Put each job bullet point in "bullets" as its own string, without the bullet mark.
- In "skills", keep labelled groups whole, for example "Cloud: EC2, S3, Lambda".
- Use "" or [] for anything the CV does not have.
- Sections that do not fit (languages, interests, volunteering) go in "other".
- Reply with the JSON only.

CV:
"""

TAILOR_PROMPT = """You help a job seeker tailor their CV to one job, honestly.

Here is their CV as JSON:
{cv}

Here is the job description:
{job}

Return JSON with exactly this shape:
{{
  "cv": <the tailored CV, same shape as the input>,
  "changes": [{{"section": "", "what": "", "why": ""}}],
  "advice": ["short tips for gaps they cannot fix by rewording"]
}}

Strict rules, because a CV must be true:
- Never invent jobs, employers, dates, qualifications, skills, tools or numbers.
- Only use facts already in the CV. You may reword them, using the job's
  words where they honestly describe the same thing.
- Rewrite the summary in 2 to 3 sentences aimed at this job, using only true facts.
- Put the skills that the job asks for first. Do not add skills that are not
  already in the CV anywhere.
- Within each job and project, put the most relevant bullets first and make
  them clear and active (start with a verb, keep each under 30 words).
- Keep contact details exactly as they are.
- Use British English. Do not use dashes as punctuation in sentences.
- In "changes", list each real change in plain words, with a short reason.
- Reply with the JSON only.
"""


def call(prompt: str, key: str, model: str = "", base_url: str = GEMINI_URL, timeout: int = 90) -> dict:
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
    }).encode()
    names = [model] if model else []
    names += [m for m in MODELS if m not in names]
    reply = None
    for name in names:
        req = urllib.request.Request(
            f"{base_url}/models/{name}:generateContent", data=body,
            headers={"x-goog-api-key": key, "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                reply = json.loads(resp.read())
            break
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:200]
            if err.code == 404:
                continue
            if err.code == 429:
                raise RuntimeError("The free AI allowance is used up for now. It usually resets the next day.")
            if err.code in (400, 401, 403):
                raise RuntimeError(f"Google did not accept the request ({err.code}). Check your GEMINI_API_KEY. {detail}")
            raise RuntimeError(f"The AI service had a problem ({err.code}).")
        except Exception as err:
            raise RuntimeError(f"Could not reach the AI service: {err}")
    if reply is None:
        raise RuntimeError("No Gemini model could be found. Set TAILOR_GEMINI_MODEL in your .env file.")
    try:
        text = "".join(p.get("text", "") for p in reply["candidates"][0]["content"]["parts"])
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1])
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError("The AI reply was not in the expected format.")


def parse_cv(text: str, key: str, **kw) -> dict:
    return call(PARSE_PROMPT + text[:20000], key, **kw)


def tailor_cv(cv: dict, job: str, key: str, **kw) -> dict:
    return call(TAILOR_PROMPT.format(cv=json.dumps(cv, ensure_ascii=False), job=job[:12000]), key, **kw)
