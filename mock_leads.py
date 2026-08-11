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


def _apply_filters(text: str):
    t = (text or "").lower()

    wanted_states = {full for key, full in STATE_ALIASES.items() if key in t}
    wanted_sizes = {SIZE_WORDS[w] for w in SIZE_WORDS if re.search(rf"\b{re.escape(w)}\b", t)}

    # exclusions: "exclude X", "without X", "not X", "except X"
    excludes = [m.group(1).strip() for m in re.finditer(r"(?:exclude|without|except|not)\s+([a-z0-9 &]+)", t)]

    rows = []
    for name, phone, email, product, state, size in COMPANY_POOL:
        if wanted_states and state not in wanted_states:
            continue
        if wanted_sizes and size not in wanted_sizes:
            continue
        if any(x and x in name.lower() for x in excludes):
            continue
        rows.append([name, phone, email, product])
    return rows


def _to_markdown(rows):
    header = "| " + " | ".join(COLUMNS) + " |"
    sep = "|" + "|".join(["---"] * len(COLUMNS)) + "|"
    if not rows:
        return "\n".join([header, sep, "| No matching companies found for those filters | N/A | N/A | N/A |"])
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([header, sep, body])


def mock_answer(user_text: str) -> str:
    """Plain-language request -> filtered Markdown lead table. Never raises."""
    try:
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
