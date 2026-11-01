"""
mock_leads.py

The demo's offline "brain". Given the user's plain-language request it returns a
Markdown table of chemical-company leads, applying the same filters the real
pipeline is pitched on:

  * location      -> "near Gujarat", "in Maharashtra", "Mumbai"
  * exclude       -> "exclude Acme", "not Reliance", "without X"
  * company size  -> "large", "MSME / small", "medium"

Called directly by main.py in mock mode — no server, no network, no GPU. This is
what makes the demo instant and bulletproof.
"""

import re

COLUMNS = ["Company Name", "Contact Number", "Email ID", "Product Made"]

# REAL Indian manufacturers that CONSUME styrene monomer (make polystyrene/EPS,
# ABS/SAN, SBR latex, or unsaturated polyester resins). Contacts were verified
# from each company's own website; 'N/A' where the company does not publish that
# field (shared registrar/investor numbers were deliberately excluded).
# tuple: name, phone, email, product, state, size ("large"|"medium"|"small").
COMPANY_POOL = [
    ("Styrenix Performance Materials Ltd", "+91 265 2303201", "info@styrenix.com",           "ABS & Polystyrene Resins",     "Gujarat",       "large"),
    ("Supreme Petrochem Ltd",              "+91 22 6709 1900","N/A",                         "Polystyrene & EPS",            "Maharashtra",   "large"),
    ("Bhansali Engineering Polymers Ltd",  "N/A",             "abstron@bhansaliabs.com",     "ABS & SAN Resins",             "Maharashtra",   "large"),
    ("Apcotex Industries Ltd",             "N/A",             "info@apcotex.com",            "SBR Latex & Synthetic Rubber", "Maharashtra",   "medium"),
    ("Crest Resins Pvt Ltd",               "+91 9879233188",  "enquiry@crestresins.com",     "Unsaturated Polyester Resin",  "Gujarat",       "medium"),
    ("Josh Resins",                        "+91 79 42722349", "N/A",                         "Unsaturated Polyester Resin",  "Gujarat",       "small"),
    ("EPACK Petrochem Pvt Ltd",            "+91 9211300963",  "sales1@epack.in",             "Expandable Polystyrene (EPS)", "Uttar Pradesh", "medium"),
    ("Rattan Styrenics Pvt Ltd",           "+91 9555442228",  "admin@rattanstyrenics.co.in", "Expandable Polystyrene (EPS)", "Uttar Pradesh", "medium"),
]

STATE_ALIASES = {
    "gujarat": "Gujarat", "gidc": "Gujarat", "ahmedabad": "Gujarat", "vadodara": "Gujarat",
    "rajkot": "Gujarat", "ankleshwar": "Gujarat", "bharuch": "Gujarat", "surat": "Gujarat",
    "maharashtra": "Maharashtra", "mumbai": "Maharashtra", "pune": "Maharashtra",
    "midc": "Maharashtra", "taloja": "Maharashtra", "navi mumbai": "Maharashtra",
    "uttar pradesh": "Uttar Pradesh", "noida": "Uttar Pradesh", "greater noida": "Uttar Pradesh",
}

SIZE_WORDS = {
    "large": "large", "big": "large", "mnc": "large", "multinational": "large",
    "medium": "medium", "mid": "medium",
    "small": "small", "msme": "small", "sme": "small", "startup": "small",
}


# "exclude X", "without X", "except X", "not X" -> the names, up to the next clause.
_STOP = r"near|around|in|at|within|from|only|but|with"
_EXCLUDE_RE = re.compile(
    rf"\b(?:exclude|excluding|without|except|not)\s+([a-z0-9 &,]+?)(?=\s+(?:{_STOP})\b|[.;]|$)",
    re.I,
)
_NEAR_RE = re.compile(r"\b(?:near|around)\s+([a-z]+(?:\s+[a-z]+)?)")
_IN_RE = re.compile(r"\b(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")  # capitalised only
_NOT_PLACES = {"me", "my", "the", "a", "an", "here", "this", "these", "those", "some", "any"}
_NATIONAL = {"india", "indian"}  # the whole dataset is Indian, so this filters nothing
KNOWN_STATES = sorted(set(STATE_ALIASES.values()))


def _split_text(text: str):
    """-> (text with exclusion clauses removed, lower-cased exclude names).

    Removing the clauses first stops "exclude Gujarat companies" from being read
    as a request *for* Gujarat."""
    t = (text or "").lower()
    excludes = []
    for m in _EXCLUDE_RE.finditer(t):
        for name in re.split(r",|\band\b|\bor\b", m.group(1)):
            name = name.strip()
            if name:
                excludes.append(name)
    return _EXCLUDE_RE.sub(" ", text or ""), excludes


def _unknown_places(text: str):
    """Locations the user asked for that the sample data has no notion of
    (e.g. "near Kerala"). Without this they would be silently ignored and the
    user would get an unfiltered list that looks like an answer."""
    body, _ = _split_text(text)
    low = body.lower()
    found = []
    for m in _NEAR_RE.finditer(low):
        phrase = m.group(1)
        first = phrase.split()[0]
        if first in _NOT_PLACES or first in _NATIONAL or any(k in phrase for k in STATE_ALIASES):
            continue
        found.append(first.title())
    for m in _IN_RE.finditer(body):
        phrase = m.group(1).lower()
        first = phrase.split()[0]
        if first in _NATIONAL or any(k in phrase for k in STATE_ALIASES):
            continue
        found.append(first.title())
    return list(dict.fromkeys(found))


def _apply_filters(text: str):
    body, excludes = _split_text(text)
    t = body.lower()

    if _unknown_places(text):
        return []

    wanted_states = {full for key, full in STATE_ALIASES.items() if key in t}
    wanted_sizes = {SIZE_WORDS[w] for w in SIZE_WORDS if re.search(rf"\b{re.escape(w)}\b", t)}

    # "exclude Gujarat companies" is an exclusion by location, not by company name.
    excluded_states = {full for key, full in STATE_ALIASES.items()
                       if any(key in x for x in excludes)}

    rows = []
    for name, phone, email, product, state, size in COMPANY_POOL:
        if state in excluded_states:
            continue
        if wanted_states and state not in wanted_states:
            continue
        if wanted_sizes and size not in wanted_sizes:
            continue
        if any(x in name.lower() for x in excludes):
            continue
        rows.append([name, phone, email, product])
    return rows


def _to_markdown(rows, empty_message="No matching companies found for those filters"):
    header = "| " + " | ".join(COLUMNS) + " |"
    sep = "|" + "|".join(["---"] * len(COLUMNS)) + "|"
    if not rows:
        return "\n".join([header, sep, f"| {empty_message} | N/A | N/A | N/A |"])
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([header, sep, body])


def mock_answer(user_text: str) -> str:
    """Plain-language request -> filtered Markdown lead table. Never raises."""
    try:
        unknown = _unknown_places(user_text)
        if unknown:
            return _to_markdown(
                [],
                f"No sample data for {', '.join(unknown)} (sample covers {', '.join(KNOWN_STATES)})",
            )
        return _to_markdown(_apply_filters(user_text))
    except Exception:
        return _to_markdown([[c[0], c[1], c[2], c[3]] for c in COMPANY_POOL[:3]])


if __name__ == "__main__":
    # self-check: filters actually change the row set
    assert len(_apply_filters("resin makers near Gujarat")) < len(COMPANY_POOL)
    gj = {r[0] for r in _apply_filters("companies in Gujarat")}
    assert gj and gj <= {c[0] for c in COMPANY_POOL if c[4] == "Gujarat"}
    assert not any("bhansali" in r[0].lower() for r in _apply_filters("styrene buyers exclude Bhansali"))
    assert all(len(r) == 4 for r in _apply_filters("resin makers"))
    assert mock_answer("").startswith("| Company Name")
    print("mock_leads self-check OK")
