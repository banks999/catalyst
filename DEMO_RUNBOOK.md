# Demo Runbook — Catalyst

**Bottom line: demo in MOCK mode. It's instant, offline-proof, and the filters work live.**
Real mode (Groq cloud + Firecrawl) genuinely works — real companies, real contacts — but it's
slow (~1–2.5 min/query) and rate-limit-fragile on the free tier, so use it as a ONE-query
"it's really live" showcase, not your main flow. Details in §5.

---

## 1. Start it (MOCK mode — your demo)

**One command, one terminal** in this folder:
```
streamlit run main.py
```
Opens http://localhost:8501. The sidebar shows a **🟡 MOCK MODE** badge — that's what you want.
No server to start, no internet needed — mock mode filters an in-app company list in pure
Python (`mock_leads.py`), so it cannot hang or lose connection.

Prereq (optional): Postgres on 5432 powers the "Saved Sessions" sidebar. If it's down the
sidebar shows a small "Could not load saved sessions" note — the chat + tables still work fine.

---

## 2. Flip mock ⇄ real in 10 seconds

Edit **one line** in `.env`:
```
DEMO_MODE=mock     # instant, offline demo (default)
DEMO_MODE=real     # live Groq LLM + Firecrawl (real companies + footer contacts)
```
Save, then **restart Streamlit** (Ctrl+C, re-run). The badge turns 🟢 green in real mode.
Mock needs **nothing external**; real needs **internet + the Groq/Firecrawl keys** (already in `.env`).

---

## 3. Confirmed demo queries (MOCK mode) — all instant (~2-3s)

Type these into the chat. Each returns a styled table + a **Download .xlsx** button.
The point to make on stage: **plain-language filters change the table live.**

1. **`companies that buy maleic anhydride near Gujarat`**
   → 3 companies, all in Gujarat. (Shows: location filter + the "buy → downstream product" story.)

2. **`unsaturated polyester resin makers, exclude Bhansali`**
   → full list (8) shrinks to 7 with **Bhansali removed**. (Shows: exclusion filter.)

3. **`large industrial solvent manufacturers`**
   → only the 3 **large** companies. (Shows: company-size filter.)

Great combo to show the feature back-to-back:
- First type `resin manufacturers` (full list),
- then `resin manufacturers near Gujarat` (list shrinks to Gujarat),
- then `resin manufacturers near Gujarat, exclude Josh` (shrinks again, 3 → 2).
The audience watches the table react to plain English. That's the pitch.

**Filters the mock understands:** location (Gujarat, Maharashtra, Uttar Pradesh and their
cities/industrial zones — Mumbai, Pune, Ahmedabad, Noida, GIDC, MIDC…), size (large/medium/small, MSME), and exclusions
(`exclude X`, `without X`, `not X`). It does NOT filter by product keyword — keep product
words in the sentence for flavor, but the filtering is location/size/exclude.

---

## 4. Things to AVOID typing live (mock mode)

- Don't expect product-name filtering ("only ethanol") to shrink the list — mock filters on
  location/size/exclude only. Non-matching filters just return the fuller list; nothing breaks.
- Unknown locations (e.g. Kerala, Hyderabad) are silently ignored, not rejected — `small companies
  in Kerala` returns the small companies from anywhere. A genuinely empty combo (e.g. `large
  companies in Gujarat, exclude Styrenix`) shows a friendly "No matching
  companies found" row — intended, not an error, but avoid it on stage.

---

## 5. Showing the REAL pipeline (Groq) — the "it's genuinely live" moment

Real mode uses **Groq cloud (`gpt-oss-120b`) + Firecrawl** for live web search and footer
scraping. Prereqs: internet up; the Groq + Firecrawl keys in `.env` (already there).
Set `DEMO_MODE=real`, restart Streamlit.

> **Free-tier daily token cap (important).** Each Groq model has its own ~200K tokens/day
> budget, and the `gpt-oss` reasoning models burn it fast (a few multi-agent runs can exhaust
> a day). If you see "Rate limit reached … tokens per day", the app now shows a calm
> "quota used up — switch to mock" message. To get a **fresh** quota, change `MODEL_ID` in
> `.env` to another model and restart:
> `openai/gpt-oss-120b` (current) → `openai/gpt-oss-20b` → `llama-3.1-8b-instant`
> (`8b-instant` has the biggest daily budget but rougher tables). **Do NOT rehearse real mode
> repeatedly** — every run spends the same daily quota you need for the live moment.

**It produces real data.** Confirmed example — `companies that buy maleic anhydride near Gujarat`
returned real firms with real contacts and correct chemistry:
```
| Amura Polymers   | +919925122752 | amurapolymerspvtltd@gmail.com | Unsaturated Polyester Resin |
| Crest Resins     | +91 9879233188| enquiry@crestresins.com       | Unsaturated Polyester Resin |
| Josh Resins      | +91-7942722349| N/A                           | Polyester Resin             |
```
Missing contacts come back as `N/A` (honest — the app highlights them), never invented.

**But treat it as a showcase, not your main flow:**
- **Slow:** ~1–2.5 minutes per query (live search + 3 footer scrapes + 3-agent pipeline).
  Narrate the architecture while it runs — don't stand in silence.
- **Free-tier fragile:** back-to-back queries can hit Groq's rate limit and return **empty**
  or stall. The app handles this gracefully (calm message, no crash) — but you get no table.
- **Do this:** run **ONE** real query, ideally the maleic-anhydride one above, on a **fresh
  quota** (don't hammer real mode during rehearsal — every run spends the same free quota).
  Then switch back to mock (`DEMO_MODE=mock`) for the rest of the demo.

**Golden path for the talk:** open in mock, show the live filters (§3), tell the multi-agent
story, then say "and here it is hitting the real web" → flip to real, run the one query, let it
work for ~2 min while you talk, reveal the real table + Excel export. Best of both.

---

## 6. Crash-proofing already in place

- No raw stack traces on screen — failures show a calm message; technical detail hides in a
  collapsed expander.
- Empty/failed model response → friendly fallback text, no crash.
- Bad/missing table → export is skipped with a note, never an error.
- LangSmith tracing is OFF by default so a dropped wifi can't slow or break runs.
- Per-call 60s model timeout; real-mode delegation is bounded (max_iterations=12).
