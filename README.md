# Catalyst

A multi-agent system that turns a plain-English request for a chemical into a verified,
export-ready list of companies likely to buy it.

Type `companies that buy maleic anhydride near Gujarat` and three cooperating agents
reason from the raw material to its downstream products, search the live web for real
manufacturers of those products, scrape their sites for contact details, and return a
table you can download as Excel.

Built as an undergraduate product-development project. The pipeline is real and works
against the live web — see [Limitations](#limitations) for an honest account of what it
does and doesn't do.

---

## How it works

The core insight the pipeline is built around: **manufacturers advertise what they sell,
not what they buy.** You cannot search the web for "companies that buy maleic anhydride"
and get useful results. So the system reasons one step down the supply chain first.

```
User: "companies that buy maleic anhydride near Gujarat"
   │
   ▼
┌──────────────────────┐
│  Chemical Analyst    │  Maleic anhydride → unsaturated polyester resins,
│                      │  alkyd resins. Emits product names only.
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Lead Finder         │  Firecrawl web search for real manufacturers of
│                      │  those products. Filters out directories and
│                      │  market-report spam. Returns Name | URL.
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  Corporate Profiler  │  Scrapes each site *including the footer*, where
│                      │  contact details actually live. Extracts phone
│                      │  and email. Emits the final Markdown table.
└──────────┬───────────┘
           ▼
   Streamlit table  →  styled .xlsx export
```

A `Team` coordinator orchestrates the three agents, applies user filters (location,
company size, exclusions), and persists sessions to Postgres.

---

## Engineering decisions worth noting

**Custom Firecrawl tools instead of the framework's built-ins.** The stock `FirecrawlTools`
wrapper cannot disable `onlyMainContent`, which strips the page footer — precisely where
company phone numbers and emails live. The tools here call the Firecrawl client directly
with `only_main_content=False`.

**Extraction happens inside the tool, not in the model's context.** Each `scrape_contacts`
call regex-extracts emails and phones and returns roughly 50 tokens instead of handing a
25,000-character page to the LLM. This is what makes the pipeline viable on a free-tier
token budget.

**A phone regex that refuses to guess.** Chemical pages are full of CAS numbers, dates and
timestamps that a naive `\d{10}` pattern happily reports as phone numbers. Numbers here
must carry a `+` prefix or a `tel:` link to qualify. A wrong number is worse than no
number, so unmatched fields return `N/A` rather than a plausible-looking fabrication.

**Missing data is never invented.** Every agent is instructed to emit `N/A` for fields it
cannot verify, and the UI highlights them. The system's honesty about gaps is a feature,
not an oversight.

**Two execution modes.** `mock` runs fully offline against an in-app company list with real
Python filtering — no network, no keys, instant. `real` runs the live pipeline. The mode is
a single line in `.env`, which means the app can be demonstrated on a dead network without
touching the code path that matters.

**Degrades instead of crashing.** Per-call 60s model timeout, bounded orchestration
(`max_iterations=12`), tracing disabled by default so an unreachable telemetry endpoint
cannot stall a run, and no raw stack traces in the UI — failures surface as a calm message
with technical detail tucked into a collapsed expander.

---

## Stack

| Layer | Choice |
|---|---|
| Agent framework | [Agno](https://github.com/agno-agi/agno) — `Agent`, `Team` |
| Model | `openai/gpt-oss-120b` via Groq's OpenAI-compatible API |
| Search + scraping | Firecrawl |
| UI | Streamlit |
| Session store | Postgres (`PostgresDb`) |
| Export | pandas + openpyxl, with styled headers |
| Tracing (optional) | OpenInference + OpenTelemetry → LangSmith |

---

## Running it

```bash
git clone https://github.com/banks999/catalyst.git
cd catalyst

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Windows: copy .env.example .env
streamlit run main.py
```

Opens at `http://localhost:8501`.

**Mock mode is the default and needs no API keys.** For the live pipeline, set
`DEMO_MODE=real` in `.env`, add a Groq key and a Firecrawl key, and restart.

Postgres is optional — without it the chat and tables still work, you just lose saved
session history.

Run the built-in self-checks without touching the network:

```bash
python workflow.py
```

---

## Limitations

Stated plainly, because they shaped the design:

- **Real mode takes 1–2.5 minutes per query.** Live search plus three page scrapes plus a
  three-agent pipeline is not fast. It replaces a task that takes a person hours, so the
  tradeoff is deliberate — but it is not an interactive experience.
- **Free-tier token budgets are tight.** Groq's free tier allocates a per-model daily token
  budget that a handful of multi-agent runs will exhaust. The app detects the rate-limit
  response and returns a clear message rather than failing opaquely.
- **Contact data is scraped, so it decays.** Published B2B contact details go stale at
  roughly 20–25% a year. This returns what a company publishes today; it does not verify
  that anyone answers.
- **Mock mode filters on location, size and exclusions only** — not on product keywords.
- **Buyer identification is inference, not evidence.** The pipeline reasons that a company
  making unsaturated polyester resin must buy maleic anhydride. That is sound chemistry,
  but it is not proof of a purchase. Customs and shipment records would be evidence;
  this is a well-reasoned shortlist.

---

## Repository layout

```
main.py           Streamlit UI, Markdown-table parsing, styled Excel export,
                  session sidebar and history rebuilding
workflow.py       Mode switch, Firecrawl tools, the three agents, Team coordinator
mock_leads.py     Offline mode — pure-Python filtering over a company list
DEMO_RUNBOOK.md   Operating notes: demo paths, failure modes, recovery
requirements.txt  Pinned dependencies (Python 3.11)
```

---

## License

MIT
