"""
contacts.py

Pure-Python contact extraction from scraped page markdown. Kept separate from
workflow.py so it can be imported and tested without the agent framework.

Precision over recall, on purpose: a wrong number is worse than "N/A".
"""

import re

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

# Mailboxes a sales team actually wants, and ones that are real but wrong for
# lead outreach. Real footers list e.g. whistleblower@ or secshare@ (shareholder
# services) before the general enquiry address, and the profiler agent only sees
# the first few emails, so order matters.
_GENERAL = ("info", "enquiry", "enquiries", "inquiry", "inquiries", "sales", "contact",
            "marketing", "hello", "office", "mail", "admin", "support")
_SPECIALIST = ("whistleblower", "secshare", "secretarial", "investor", "investors",
               "careers", "career", "hr", "jobs", "privacy", "legal", "compliance",
               "grievance", "abuse", "webmaster", "noreply", "no-reply", "donotreply")


def _email_rank(email: str) -> int:
    local = email.split("@", 1)[0].lower()
    if local in _GENERAL:
        return 0
    if local in _SPECIALIST:
        return 2
    return 1


def extract_contacts(md: str):
    """Pull emails + phones from scraped markdown. Returns (emails, phones), each
    at most 3 long, de-duplicated.

    Emails are ordered general-purpose first (info@, enquiry@, sales@...), then
    personal/other addresses, then specialist mailboxes (whistleblower@, hr@...).

    Phones must carry a '+' or come from a tel: link, so a CAS number, date or
    timestamp is never surfaced as a phone number.
    """
    md = md or ""

    raw_emails = re.findall(r"mailto:([\w.+-]+@[\w-]+\.[\w.-]+)", md)
    raw_emails += re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", md)
    emails, seen_emails = [], set()
    for e in raw_emails:
        e = e.rstrip(".")  # "write to info@x.com." -> "info@x.com"
        key = e.lower()
        if key in seen_emails or key.endswith(_IMAGE_SUFFIXES):
            continue
        seen_emails.add(key)
        emails.append(e)

    raw_phones = re.findall(r"tel:(\+?[\d\s\-()]{8,}\d)", md)
    raw_phones += re.findall(r"\+\d[\d\s\-()]{7,}\d", md)  # must start with + = real phone
    phones, seen_digits = [], set()
    for p in raw_phones:
        p = p.strip()
        digits = re.sub(r"\D", "", p)
        # De-dupe on digits so "tel:+917942722349" and "+91 79 42722349" count once.
        if not (10 <= len(digits) <= 13) or digits in seen_digits:
            continue
        seen_digits.add(digits)
        phones.append(p)

    emails.sort(key=_email_rank)  # stable: page order is kept within a rank
    return emails[:3], phones[:3]
