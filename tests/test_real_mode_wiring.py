"""Real-mode wiring, offline: dummy keys, and Firecrawl replaced by a fake. Runs in a
subprocess because workflow.py reads DEMO_MODE at import time."""
import os
import subprocess
import sys
import textwrap

SNIPPET = textwrap.dedent('''
    import workflow as w

    assert w.DEMO_MODE == "real"
    assert w.agent_db is None  # Postgres is optional
    assert len(w.agent_team_coordinator.members) == 3
    assert [m.name for m in w.agent_team_coordinator.members] == [
        "Chemical Analyst", "Lead Finder", "Corporate Profiler"]

    class R:  # minimal stand-in for a Firecrawl search/scrape result
        def __init__(self, **kw): self.__dict__.update(kw)

    class FakeFC:
        def search(self, q, limit):
            self.q = q
            return R(web=[
                R(url="https://www.indiamart.com/x", title="Directory"),
                R(url="https://report.example/market.pdf", title="Report"),
                R(url="https://a-resins.example", title="A Resins "),
                {"url": "https://b-resins.example", "title": "B Resins"},
                R(url="https://c-resins.example", title=None),
                R(url="https://d-resins.example", title="D Resins"),
            ])
        def scrape(self, url, **kw):
            assert kw["only_main_content"] is False  # footer is where contacts live
            return R(markdown="Mail sales@a-resins.example or tel:+91 98765 43210. CAS 27253-31-2")

    w._fc = FakeFC()
    lines = w.find_companies("unsaturated polyester resin Gujarat").splitlines()
    assert lines == [
        "A Resins | https://a-resins.example",
        "B Resins | https://b-resins.example",
        "https://c-resins.example | https://c-resins.example",
    ], lines  # junk dropped, capped at 3, missing title falls back to the URL
    assert "manufacturer" in w._fc.q

    out = w.scrape_contacts("https://a-resins.example")
    assert "sales@a-resins.example" in out and "+91 98765 43210" in out and "27253" not in out, out

    class Boom:
        def search(self, *a, **k): raise RuntimeError("quota")
        def scrape(self, *a, **k): raise RuntimeError("timeout")
    w._fc = Boom()
    assert w.find_companies("x").startswith("search failed")
    assert w.scrape_contacts("https://x").startswith("scrape failed")
    print("OK")
''')


def test_real_mode_tools_and_team_wiring():
    env = {**os.environ, "DEMO_MODE": "real", "GROQ_API_KEY": "dummy",
           "FIRECRAWL_API_KEY": "dummy", "POSTGRES_URL": ""}
    r = subprocess.run([sys.executable, "-c", SNIPPET], env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK"), r.stdout + r.stderr
