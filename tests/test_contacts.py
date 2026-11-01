from contacts import extract_contacts


def test_mailto_and_tel_link():
    assert extract_contacts("mailto:a@b.com tel:+91 99251 22752") == (["a@b.com"], ["+91 99251 22752"])


def test_cas_numbers_dates_and_timestamps_are_not_phones():
    assert extract_contacts("CAS 27253-31-2 on 2026-02-26 id 1719416109703") == ([], [])


def test_bare_digits_without_plus_are_not_phones():
    assert extract_contacts("Call 9879233188 today")[1] == []


def test_plus_prefixed_number_is_a_phone():
    assert extract_contacts("Phone: +91 79 42722349")[1] == ["+91 79 42722349"]


def test_trailing_sentence_period_is_stripped_from_email():
    assert extract_contacts("write to info@x.com. thanks")[0] == ["info@x.com"]


def test_emails_dedupe_case_insensitively():
    emails = extract_contacts("Info@X.com info@x.com mailto:info@x.com")[0]
    assert len(emails) == 1 and emails[0].lower() == "info@x.com"


def test_same_phone_in_two_formats_counts_once():
    assert len(extract_contacts("tel:+917942722349 and +91 79 42722349")[1]) == 1


def test_image_filenames_are_not_emails():
    assert extract_contacts("logo@2x.png banner@3x.jpg")[0] == []


def test_results_capped_at_three():
    emails, phones = extract_contacts(
        " ".join(f"u{i}@x.com +91 98765 4321{i}" for i in range(6))
    )
    assert len(emails) == 3 and len(phones) == 3


def test_empty_and_none_input():
    assert extract_contacts("") == ([], [])
    assert extract_contacts(None) == ([], [])


# --- excerpts of real company footers (scraped 2026-11-01) -------------------
CREST_FOOTER = """
- [Whistleblower](mailto:whistleblower@crestresins.com)
###### Get in Touch
- [+91 9879233188](tel:+919879233188)
- [enquiry@crestresins.com](mailto:enquiry@crestresins.com)
- 605/A, 6th Floor, Tower D, Times Square Grand Office, Ahmedabad, Gujarat - 380059
"""

STYRENIX_FOOTER = """
**Styrenix Performance Materials Limited**
CIN: L25200GJ1973PLC002436
9th Floor, "Shiva", Sarabhai Complex, Vadiwadi, Vadodara-390023, Gujarat.
- **Email Us**
secshare@styrenix.com
- **Call us today**
+91 265 2303201/2
- **Styrenix Performance Materials(Thailand) Limited**
Company Registration No.:0215547000670
- **Email Us**
info@styrenix.com
- **Call us today**
+66 38 910 700
"""


def test_real_crest_footer_prefers_enquiry_over_whistleblower():
    emails, phones = extract_contacts(CREST_FOOTER)
    assert emails == ["enquiry@crestresins.com", "whistleblower@crestresins.com"]
    assert phones == ["+919879233188"]  # tel: link and visible text are one number


def test_real_styrenix_footer():
    emails, phones = extract_contacts(STYRENIX_FOOTER)
    assert emails[0] == "info@styrenix.com"          # not the shareholder-services box
    assert phones[0] == "+91 265 2303201"            # registration no. / CIN are not phones
    assert not any("0215547000670" in p or "25200" in p for p in phones)


def test_ranking_is_stable_within_a_rank():
    assert extract_contacts("zed@x.com amy@x.com")[0] == ["zed@x.com", "amy@x.com"]
