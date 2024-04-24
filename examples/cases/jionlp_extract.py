import re

from jionlp.rule.rule_pattern import EMAIL_PATTERN

from flat.py import list_of
from flat.types import RFC_Email


def _extract_base(pattern, text, with_offset=False):
    """ 正则抽取器的基础函数

    Args:
        pattern(re.compile): 正则表达式对象
        text(str): 字符串文本
        with_offset(bool): 是否携带 offset （抽取内容字段在文本中的位置信息）

    Returns:
        list: 返回结果

    """
    if with_offset:
        results = [{'text': item.group(1),
                    'offset': (item.span()[0] - 1, item.span()[1] - 1)}
                   for item in pattern.finditer(text)]
    else:
        results = [item.group(1) for item in pattern.finditer(text)]

    return results


def extract_email(text: str) -> list_of(RFC_Email):
    """ 提取文本中的 E-mail

    Args:
        text(str): 字符串文本
        detail(bool): 是否携带 offset （E-mail 在文本中的位置信息）

    Returns:
        list: email列表

    """
    email_pattern = re.compile(EMAIL_PATTERN)

    text = ''.join(['龥', text, '龥'])
    results = _extract_base(email_pattern, text, with_offset=False)
    return results


def test_extract_email_address():
    text = "Im Rabn <im.rabn@npf.gov.nr>"
    assert extract_email(text) == ["im.rabn@npf.gov.nr"]

    valid_email_addresses = [
        'simple@example.com',
        'very.common@example.com',
        'FirstName.LastName@EasierReading.org',
        'x@example.com',
        'long.email-address-with-hyphens@and.subdomains.example.com',
        # 'user.name+tag+sorting@example.com',
        # 'name/surname@example.com',
        # 'admin@example',
        # 'example@s.example',
        # '" "@example.org',
        # '"john..doe"@example.org',
        # 'mailhost!username@example.org',
        # '"very.(),:;<>[]\".VERY.\"very@\\ \"very\".unusual"@strange.example.com',
        'user%example.com@example.org',
        'user-@example.org',
        # 'postmaster@[123.123.123.123]',
        # 'postmaster@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]',
        # '_test@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
    ]
    for email in valid_email_addresses:
        text = f'Valid {email}'
        assert len(extract_email(text)) == 1, f'test failed: {email}'


def main():
    test_extract_email_address()
