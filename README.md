# Tailor · CV helper

Add your CV, paste a job advert, and Tailor will:

* **Check your match** with a score out of 100 and a plain verdict
* **Show your gaps**: must haves you are missing, nice to haves, skills you
  list but never show in action, and words the advert keeps using
* **Tailor your CV** to the job, and tell you exactly what it changed
* **Let you pick a style** (Classic, Modern, Compact, Executive), a colour and
  the section order
* **Download it as a Word file** (.docx)

No CV yet? Fill in the form and Tailor builds one for you.

## Run it

You need Python 3.10 or newer (free from https://www.python.org/downloads/).

| Your computer | What to do |
|---|---|
| Windows | Double click `run.bat` |
| Mac or Linux | Open a terminal in this folder and type `./run.sh` |

The first run takes about a minute to set up. Then your browser opens at
http://localhost:5080. Press Ctrl+C in the black window to stop it.

Or by hand:
```
python -m venv .venv
.venv\Scripts\activate          (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python app.py
```

## Use it

1. **Your CV:** upload a Word, PDF or text file, or fill in the form.
   Check every section after uploading and fix anything that landed in the
   wrong place. Press **Try a sample** to see it working first.
2. **The job:** paste the whole advert.
3. Press **Check my match** to see your score and gaps, or **Tailor my CV**
   to get a version aimed at this job.
4. In **CV and download**, pick a style and colour, then **Download as Word**.
   Press **Edit this version in the form** if you want to change anything first.

## With or without AI

| | Without a key | With a free Gemini key |
|---|---|---|
| Reading your CV | Rule based, so check it | AI sorts it more reliably |
| Match score and gaps | Yes | Yes (same score either way) |
| Tailoring | Reorders skills, points and projects. Your words stay the same | Also rewrites your profile and points using the advert's language |
| Gap advice | General tips | Specific advice |

The match score never uses AI, so it is worked out the same way every time
and you can compare jobs fairly.

To turn on AI (about two minutes):

1. Go to https://aistudio.google.com/apikey, sign in and press **Create API key**.
2. Copy `.env.example`, name the copy `.env`, paste the key after `GEMINI_API_KEY=`.
3. Start Tailor again.

With AI on, your CV and the advert are sent to Google. On the free allowance
Google may use them to improve its products. Untick **Use AI** on the page to
keep everything on your computer.

## Honesty check

A CV must be true. Whatever the AI writes, Tailor checks it against your
original CV and:

* removes any skill that was not in your CV
* removes any job or qualification you did not have, and keeps your real
  dates and employers
* flags any number that was not in your CV (for example "4 stores") so you can
  check it
* keeps your contact details exactly as they were

Lines the AI reworded are highlighted in yellow in the preview.

## How the match score works

| Part | Points |
|---|---|
| Must have skills found | 55 |
| Nice to have skills found | 20 |
| Other words the advert repeats | 15 |
| Years of experience | 10 |

75 and over is a strong match, 55 to 74 is good with gaps, 35 to 54 is a
partial match, under 35 is weak. Skills under headings like "Nice to have" or
"Desirable" count as nice to have, and perks like "training budget" are
ignored. Years counts all the jobs on your CV.

Tailor knows about 250 skills across tech, data, business, retail and
qualifications. To add more, edit `core/skills.py`.

## Put it on a website

Tailor works on phones, tablets and computers. To let other people use it, it
has to run on a server (your laptop only serves you). It saves nothing about
visitors: each CV is used to work out the results and then forgotten.

**What is set up for you**

* `Dockerfile`: packages Tailor as a container, which most hosts accept.
* When `HOST` is not your own computer, Tailor runs a proper web server
  (Waitress) instead of the test one.
* Each visitor gets 15 AI uses a day (change it with
  `AI_USES_PER_VISITOR_PER_DAY`), so one person cannot use up the free
  allowance for everyone. After that it carries on without AI.

**Try the container on your computer**
```
docker build -t tailor .
docker run -p 8080:8080 -e GEMINI_API_KEY=your-key tailor
```
Then open http://localhost:8080

**On AWS App Runner** (one simple choice)

1. Push the image to Amazon ECR.
2. In App Runner, create a service from that image, port 8080.
3. Store `GEMINI_API_KEY` in Secrets Manager and add it as an environment variable.
4. App Runner gives you a web address with HTTPS.

**On the AI Transformers site**, either link to that address or show it
inside a page:
```html
<iframe src="https://your-tailor-address" style="width:100%;height:1400px;border:0"
        title="Tailor CV helper"></iframe>
```

**Before going public**

* CVs are personal data, so the site needs a privacy notice saying what
  happens to them.
* On Google's free allowance, Google may use what is sent to improve its
  products. For a public site, use a paid Gemini plan (which does not), or
  leave the key out so AI is off.

## Make an executable

```
pip install -r requirements-build.txt
python build_exe.py
```
Gives `dist/Tailor.exe` on Windows (build it on Windows) or `dist/Tailor` on
Mac and Linux. No Python needed to run it. Put your `.env` file next to it to
turn on AI.

## What is in the folder

| File | What it does |
|---|---|
| `app.py` | The web app |
| `core/reader.py` | Reads Word, PDF and text CVs into sections |
| `core/skills.py` | The skills list |
| `core/matcher.py` | Match score and gaps |
| `core/tailor.py` | Tailoring and the honesty check |
| `core/ai.py` | Talks to Google Gemini |
| `core/word.py` | Builds the Word file in four styles |
| `templates/index.html` | The web page |
| `samples/` | A made up CV and job advert to try |

## Good to know

* Scanned PDFs (photos of paper) have no text to read. Use the Word version.
* Old `.doc` files need saving as `.docx` first.
* All four styles use one column and normal headings, so the systems many
  employers use to read CVs can read them.
* On a phone, the preview shows the whole page small. Pinch to zoom in.
  The Word file opens in the Word app, or saves to your Files or Downloads.
* Tailor suggests, you decide. Read every line before you send it.
