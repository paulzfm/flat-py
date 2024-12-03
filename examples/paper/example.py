from flat.errors import Error
from flat.lib import select
from flat.py import lang, fuzz, ensures
from flat.py.utils import print_fuzz_report
from flat.types import RFC_Host as Host
from flat.types import RFC_URL as URL


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
start: "INSERT INTO hosts VALUES " "(" RFC_Host ")";
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


@ensures(lambda url, ret: ret == select(URL.xpath("..host"), url))
def get_hostname_oracle(url: URL) -> Host:
    return get_hostname(url)


def main():
    print('== SQL injection ==')
    malicious_url = "https://localhost'); DROP TABLE users --/"
    save_hostname(malicious_url)

    print('== Solution 1 ==')
    try:
        save_hostname_1(malicious_url)
    except Error as err:
        err.print()

    print('== Solution 2 ==')
    try:
        save_hostname_2(malicious_url)
    except Error as err:
        err.print()

    print('== Fuzz ==')
    report = fuzz(get_hostname_safe, 50)
    print_fuzz_report(report)

    report = fuzz(get_hostname_fixed, 50)
    print_fuzz_report(report)

    print('== Oracles ==')
    report = fuzz(get_hostname_oracle, 50)
    print_fuzz_report(report)
