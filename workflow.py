import os
import re
from dotenv import load_dotenv

# --- INITIALIZE ENV CONFIGS ---
load_dotenv()

# =========================================================================
# DEMO MODE SWITCH  --  flip this in ONE line to survive a dead wifi.
#   DEMO_MODE=mock  -> instant, offline (pure-Python filter in mock_leads.py,
#                      called directly by main.py — no server, no network)
#   DEMO_MODE=real  -> Groq cloud LLM + Firecrawl (search + footer scrape)
# Set it in .env. Default is "mock" because that is the reliable demo path.
# =========================================================================
DEMO_MODE = os.getenv("DEMO_MODE", "mock").strip().lower()

GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1")

if DEMO_MODE == "real":
    SERVER_URL = GROQ_URL
    # gpt-oss tool-calls cleanly on Groq (Llama models emit a malformed
    # tool-call format Groq rejects). Override via MODEL_ID.
    MODEL_ID = os.getenv("MODEL_ID", "openai/gpt-oss-120b")
    API_KEY = os.getenv("GROQ_API_KEY", "")
else:
    DEMO_MODE = "mock"
    SERVER_URL = "none (offline)"  # mock mode calls mock_leads.mock_answer directly
    MODEL_ID = "mock-model"
    API_KEY = "mock"

POSTGRES_URL = os.getenv("POSTGRES_URL")

# --- OPTIONAL LANGSMITH TRACING (off by default; a dead endpoint can slow or
#     break every agent step if wifi drops, so we never let it touch the run). ---
if os.getenv("ENABLE_TRACING", "false").strip().lower() == "true" and os.getenv("LANGSMITH_API_KEY"):
    try:
        from openinference.instrumentation.agno import AgnoInstrumentor
        from opentelemetry import trace as trace_api
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        endpoint = "https://api.smith.langchain.com/otel/v1/traces"
        headers = {
            "x-api-key": os.getenv("LANGSMITH_API_KEY"),
            "Langsmith-Project": os.getenv("LANGSMITH_PROJECT", "chemical_lead_generation"),
        }
        if not isinstance(trace_api.get_tracer_provider(), TracerProvider):
            tracer_provider = TracerProvider()
            tracer_provider.add_span_processor(
                SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
            )
            trace_api.set_tracer_provider(tracer_provider=tracer_provider)
            AgnoInstrumentor().instrument()
    except Exception as _trace_err:  # never let tracing kill the demo
        print(f"[tracing disabled] {_trace_err}")

# --- AGNO ECOSYSTEM IMPORTS ---
from agno.agent import Agent
from agno.team import Team
from agno.models.openai import OpenAIChat
from agno.db.postgres import PostgresDb

# --- STORAGE DATABASE BACKEND LAYER ---
# Postgres is optional: with no POSTGRES_URL the app runs without saved-session history
# (PostgresDb raises at construction if given no URL, which would stop the app starting).
agent_db = (
    PostgresDb(db_url=POSTGRES_URL, session_table="chemical_agent_sessions")
    if POSTGRES_URL
    else None
)

TABLE_HEADER = "| Company Name | Contact Number | Email ID | Product Made |"

# =========================================================================
# REAL-MODE TOOLS (Firecrawl search + footer scrape).
# We use the raw Firecrawl client, not agno's FirecrawlTools, because the
# stock tool can't disable onlyMainContent (which strips the footer where the
# contact details live). We also regex-extract inside the tool, so each call
# returns ~50 tokens instead of a 25K-char page -> cheap on Groq's free tier.
# DuckDuckGo was dropped: the ddgs library is rate-limited/blocked ("No results").
# =========================================================================

# Search hits that are directories / aggregators / market-reports, not real makers.
_JUNK = ("indiamart", "justdial", "tradeindia", "exportersindia", "gujaratdirectory",
         "facebook", "linkedin", "youtube", "wikipedia", "alibaba", "made-in-china",
         "zauba", "thomasnet", "marketsandmarkets", "fortunebusinessinsights",
         "mordorintelligence", "grandviewresearch", "researchandmarkets",
         "globenewswire", "statista", ".pdf")


def _extract_contacts(md: str):
    """Pull emails + phones from scraped markdown. High precision on purpose:
    phones must carry a '+' or a tel: link so we never surface a CAS number,
    date or timestamp as a phone (a wrong number on stage is worse than N/A)."""
    md = md or ""
    emails = re.findall(r"mailto:([\w.+-]+@[\w-]+\.[\w.-]+)", md)
    emails += re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", md)
    emails = [e for e in dict.fromkeys(emails)
              if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"))]
    phones = re.findall(r"tel:(\+?[\d\s\-()]{8,}\d)", md)
    phones += re.findall(r"\+\d[\d\s\-()]{7,}\d", md)  # must start with + = real phone
    phones = [p.strip() for p in dict.fromkeys(phones) if 10 <= len(re.sub(r"\D", "", p)) <= 13]
    return emails[:3], phones[:3]


if DEMO_MODE == "real":
    from firecrawl import Firecrawl
    _fc = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))

    def find_companies(query: str) -> str:
        """Search the web for real manufacturers. Pass the downstream PRODUCT plus any
        location the user gave, e.g. 'unsaturated polyester resin manufacturer Gujarat'.
        Returns up to 5 lines of 'Company Name | https://website'. Never invent companies."""
        try:
            res = _fc.search(f"{query} manufacturer supplier company", limit=10)
        except Exception as e:
            return f"search failed: {e}"
        items = getattr(res, "web", None) or getattr(res, "data", None) or []
        out = []
        for r in items:
            url = getattr(r, "url", None) or (r.get("url") if isinstance(r, dict) else None)
            title = getattr(r, "title", None) or (r.get("title") if isinstance(r, dict) else None) or url
            if not url or any(d in url.lower() for d in _JUNK):
                continue
            out.append(f"{title.strip()} | {url}")
            if len(out) >= 3:   # 3 keeps a live run ~60-90s; raise if you want more rows
                break
        return "\n".join(out) if out else "No companies found."

    def scrape_contacts(url: str) -> str:
        """Scrape a company's homepage INCLUDING its footer and return the contact
        details found. Returns 'emails: [...] | phones: [...]' (either may be empty)."""
        try:
            doc = _fc.scrape(url, formats=["markdown"], only_main_content=False, timeout=30000)
            md = getattr(doc, "markdown", "") or ""
        except Exception as e:
            return f"scrape failed: {e}"
        emails, phones = _extract_contacts(md)
        return f"emails: {emails or 'none'} | phones: {phones or 'none'}"


# --- MODEL LAYER (60s per-call timeout guards against a frozen server) ---
llm = OpenAIChat(id=MODEL_ID, base_url=SERVER_URL, api_key=API_KEY or "x", timeout=60.0)


# =========================================================================
# MULTI-AGENT PIPELINE (real mode). Contact Hunter dropped — footer-first
# scraping covers contacts in one shot, no repair loop needed.
# =========================================================================

chemical_analyst = Agent(
    name="Chemical Analyst",
    role="Supply Chain & Chemistry Expert",
    model=llm,
    instructions=[
        "Analyze the user's chemical / raw-material request.",
        "Manufacturers advertise what they SELL, not what they BUY. If the user names a raw "
        "material (e.g. Maleic Anhydride), deduce the downstream finished PRODUCT that buyers "
        "make from it (e.g. Unsaturated Polyester Resins, Alkyd Resins).",
        "State ONLY the downstream product name(s), plus any location the user mentioned. "
        "Do not name companies.",
    ],
    markdown=True,
)

lead_finder = Agent(
    name="Lead Finder",
    role="B2B Market Researcher",
    model=llm,
    tools=[find_companies] if DEMO_MODE == "real" else [],
    instructions=[
        "Call find_companies ONCE with the downstream product plus any location "
        "(e.g. 'unsaturated polyester resin Gujarat').",
        "Return the raw 'Company Name | URL' lines exactly as the tool gives them. "
        "Never add companies the tool did not return.",
    ],
    markdown=True,
)

corporate_profiler = Agent(
    name="Corporate Profiler",
    role="Footer Contact Extraction",
    model=llm,
    tools=[scrape_contacts] if DEMO_MODE == "real" else [],
    instructions=[
        "For EACH company URL from the Lead Finder, call scrape_contacts(url) to read its footer.",
        "Pick the single best email and phone from what the tool returns. If the tool returns "
        "'none' or fails for a field, use 'N/A' — NEVER invent a number or email.",
        "Compile the final answer as EXACTLY this Markdown table and nothing else:",
        TABLE_HEADER,
        "One row per company: Company Name, Contact Number, Email ID, Product Made "
        "(the downstream product from the Analyst).",
    ],
    markdown=True,
)

# =========================================================================
# TEAM COORDINATOR
#   real -> analyst -> lead_finder -> profiler produce the live table.
#   mock -> no members; the single LLM call hits the mock server, which
#           returns the filter-aware table directly.
# =========================================================================

_REAL_INSTRUCTIONS = [
    "Run a lead-discovery pipeline for chemical/industrial companies.",
    "STEP 1: Ask the Chemical Analyst for the downstream product(s) + any location.",
    "STEP 2: Ask the Lead Finder to find real companies + URLs for that product.",
    "STEP 3: Ask the Corporate Profiler to scrape each URL's footer and build the table.",
    "If the user said to exclude a company, drop it. If they gave a location, keep it in the search.",
    "Return ONLY the final Markdown table with columns: " + TABLE_HEADER,
    "Use 'N/A' for genuinely missing contact fields. NEVER fabricate contact details.",
]

_MOCK_INSTRUCTIONS = [
    "Return ONLY the Markdown table content from the model response, verbatim.",
    "Do not add any conversational text before or after the table.",
]

agent_team_coordinator = Team(
    name="Team Coordinator",
    role="Orchestrator",
    members=[chemical_analyst, lead_finder, corporate_profiler] if DEMO_MODE == "real" else [],
    model=llm,
    db=agent_db,
    instructions=_REAL_INSTRUCTIONS if DEMO_MODE == "real" else _MOCK_INSTRUCTIONS,
    markdown=True,
    max_iterations=12,
    retries=1,
)

if __name__ == "__main__":
    # self-checks that don't need the network
    assert _extract_contacts("mailto:a@b.com tel:+91 99251 22752") == (["a@b.com"], ["+91 99251 22752"])
    # CAS number / date / timestamp must NOT be read as phones:
    assert _extract_contacts("CAS 27253-31-2 on 2026-02-26 id 1719416109703") == ([], [])
    n = len(agent_team_coordinator.members or [])
    assert (n == 3) if DEMO_MODE == "real" else (n == 0), "members not wired for mode"
    print(f"OK  DEMO_MODE={DEMO_MODE}  MODEL_ID={MODEL_ID}  members={n}")
