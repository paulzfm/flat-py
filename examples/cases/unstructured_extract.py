import re

from unstructured.nlp.patterns import (
    EMAIL_ADDRESS_PATTERN,
)

from flat.py import list_of, lang, ensures
from flat.types import RFC_Email


def extract_email_address(text: str) -> list_of(RFC_Email):
    return re.findall(EMAIL_ADDRESS_PATTERN, text.lower())


def test_extract_email_address():
    text = "Im Rabn <Im.Rabn@npf.gov.nr>"
    assert extract_email_address(text) == ["im.rabn@npf.gov.nr"]

    valid_email_addresses = [
        'simple@example.com',
        'very.common@example.com',
        'FirstName.LastName@EasierReading.org',
        'x@example.com',
        'long.email-address-with-hyphens@and.subdomains.example.com',
        'user.name+tag+sorting@example.com',
        'name/surname@example.com',
        # 'admin@example',
        'example@s.example',
        # '" "@example.org',
        # '"john..doe"@example.org',
        'mailhost!username@example.org',
        # '"very.(),:;<>[]\".VERY.\"very@\\ \"very\".unusual"@strange.example.com',
        'user%example.com@example.org',
        'user-@example.org',
        # 'postmaster@[123.123.123.123]',
        # 'postmaster@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]',
        # '_test@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
    ]
    for email in valid_email_addresses:
        text = f'Valid {email}'
        assert len(extract_email_address(text)) == 1, f'test failed: {email}'


EmailText = lang('EmailText', """
start: "From <" RFC_Email ">" ", " "To <" RFC_Email ">";
""")


@ensures('len(_) == 2')
def extract_email_address_from_email_text(text: EmailText) -> list_of(RFC_Email):
    return extract_email_address(text)


def main():
    test_extract_email_address()
    # fuzz(extract_email_address_from_email_text, 10)
