from flat.lib import select, xpath
from flat.py import lang, ensures, fuzz
from flat.py.utils import ExpectError, print_fuzz_report
from flat.types import Host, URL


def get_hostname(url: str) -> str:
    """Extract the hostname part."""
    start = url.find('://') + 3
    end = url.find('/', start)
    host = url[start:end]
    return host


def save_hostname(url: str):
    sql_temp = "INSERT INTO hosts VALUES ('{host}')"
    hostname = get_hostname(url)
    sql_query = sql_temp.format(host=hostname)
    print(f'[SQL] {sql_query}')


def get_hostname_safe(url: URL) -> Host:
    return get_hostname(url)


def save_hostname_1(url: str):
    sql_temp = "INSERT INTO hosts VALUES ('{host}')"
    hostname = get_hostname_safe(url)
    sql_query = sql_temp.format(host=hostname)
    print(f'[SQL] {sql_query}')


SafeSQL = lang('SafeSQL', """
start: "INSERT INTO hosts VALUES " "(" Host ")";
""")


def save_hostname_2(url: str):
    sql_temp = "INSERT INTO hosts VALUES ('{host}')"
    hostname = get_hostname(url)
    sql_query: SafeSQL = sql_temp.format(host=hostname)
    print(f'[SQL] {sql_query}')


def get_hostname_fixed(url: URL) -> Host:
    """Extract the hostname part."""
    start = url.find('://') + 3
    end = url.find('/', start)
    if end == -1:  # fixed code
        end = len(url)  # fixed code
    host = url[start:end]
    return host


@ensures(lambda url, ret: ret == select(xpath(URL, "..host"), url))
def get_hostname_oracle(url: URL) -> Host:
    return get_hostname_fixed(url)


def main():
    print('== 2.1 Detecting SQL Injection ==')
    malicious_url = "https://localhost'); DROP TABLE users --/"
    save_hostname(malicious_url)

    print('* Solution 1')
    with ExpectError():
        save_hostname_1(malicious_url)

    print('* Solution 2')
    with ExpectError():
        save_hostname_2(malicious_url)

    print('== 2.2 Language-Based Test Generation ==')
    report = fuzz(get_hostname_safe, 50)
    print_fuzz_report(report)

    print('* Failing input shown in the paper')
    with ExpectError():
        get_hostname_safe('http://W')

    assert get_hostname_fixed('http://W') == 'W'
    print('* The fixed version solves this failing input and can pass other random inputs:')
    report = fuzz(get_hostname_fixed, 50)
    print_fuzz_report(report)

    print('== 2.3 Oracles ==')
    print('* The fixed version meets the functional contract:')
    report = fuzz(get_hostname_oracle, 50)
    print_fuzz_report(report)
