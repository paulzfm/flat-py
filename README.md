# FLAT-PY: Formal Languages as Types, for Python

String is a universal representation of many types of data, e.g., email addresses, URLs, Unix file paths, HTML, and
JSON.
These types of data are conceptually different, but all have type `str` (in Python) or `java.lang.String` (in Java).
This can bring problems like "you promise me JSON and then sent XML"[^1] as shown in the following Python snippet:

```python
def send(json: str) -> None:
    ...

send('<error>404</error>')
```

FLAT-PY is a Python testing framework that aims to detect such format/syntax incompatibility issues and
avoid unexceptional failures and severe vulnerabilities caused by them.
We apply a syntax-aware type-directed approach, using the idea of regarding Formal Languages as Types (FLAT).
See our paper *FLAT: Formal Languages as Types* for more technical details.

## Features

FLAY-PY:

+ offers convenient annotations for users to define formal language types and attach them directly to Python code
+ comes with ready-to-use types for email addresses, URLs, and JSON
+ allows arbitrary Python expressions/functions as expressive semantic constraints
+ provides annotations to specify oracles/contracts in the pre-/post-condition style
+ integrates language-based test generation to fuzz your code with random inputs generated from language types

## Example

Consider an ad hoc parser that aims to extract the hostname part form the input `url`:

```python
def get_hostname(url: str) -> str:
    """Extract the hostname part."""
    start = url.find('://') + 3
    end = url.find('/', start)
    host = url[start:end]
    return host
```

We wish to save the extracted hostname in a database table named `hosts`:

```python
def save_hostname(url: str, db_cursor: MysqlCursor):
    sql_temp = "INSERT INTO hosts VALUES ('{host}')"
    hostname = get_hostname(url)
    sql_query = sql_temp.format(host=hostname)
    db_cursor.execute(sql_query)
```

### Issue: SQL Injection

The above code is **unsafe**: it suffers from SQL injection if we feed the following malicious input to `get_hostname`:

```python
malicious_url = "https://localhost'); DROP TABLE users --/"
```

The output `localhost'); DROP TABLE users --` is indeed not a legal hostname.
Using it to instantiate `sql_temp`, we obtain a SQL query that contains a dangerous `DROP TABLE` command:

```sql
INSERT INTO hosts VALUES ('localhost'); DROP TABLE users --')
```

### Solution: Language Types

Such an issue can be avoided if we force the `url` input to be a valid URL string but not any string.
In FLAT-PY, we achieve this by refining the type signature of the `get_hostname` function:

```python
from flat.types import URL, Host

def get_hostname(url: URL) -> Host:
    ...
```

The language types `URL`[^2] and `Host` restrict the set of valid strings for the input and the output respectively.
Feeding `malicious_url` to `get_hostname` now causes a type error:

```text
Type mismatch for argument 0 of method get_hostname
  expected type: URL
  actual value:  "https://localhost'); DROP TABLE users --/"
```

### Fuzz Testing

To better know if the code is functionally correct, meaning it behaves normally on valid URL inputs,
here we apply language-based fuzzing.
The idea is to rely on a backend language-based fuzzer to produce random input strings that match the syntax,
and test our functions against them.
FLAT-PY offers a `fuzz` function to enable such a functionality:

```python
from flat.py import fuzz

report = fuzz(get_hostname, 50)
```

FLAT-PY now produces 50 random URLs (with the help of a language-based fuzzer),
tests the target function `get_hostname`, and finally generates a test `report`.
One can display the result via a utility function:

```python
from flat.py.utils import print_fuzz_report

print_fuzz_report(report)
```

Note that the implementation of `get_hostname` is buggy:
it cannot handle URLs with empty paths correctly, e.g., `http://W`.

### Oracles

Apart from format validation/checking, functional correctness is also of great importance.
The contract that describes the required behaviors can be used as test oracles.
FLAT-PY offers `requires` and `ensures` decorators to specify pre-/post-conditions,
and a `select` function to extract a particular substring via an XPath:

```python
from flat.py import ensures
from flat.lib import select, xpath

@ensures(lambda url, ret: ret == select(xpath(URL, "..host"), url))
def get_hostname(url: URL) -> Host:
    ...
```

This post-condition states that the output value (bound to the last lambda parameter `ret`) equals to
the hostname extracted by `..host`: it refers to the (unique) node labeled with nonterminal symbol `host`,
which refers to the hostname part, in the derivation tree of `url`.

For the full example, see `examples/papers/hostname.py`.

## Installation

Python >= 3.11 is required. No other dependencies need be installed first.

We recommend setting up a virtual environment. In the project root folder:

```shell
python3 -m venv .venv
source .venv/bin/activate
```

In the environment `.venv`:

```shell
pip install .
```

## Usage

The basic usage is:

```shell
python -m flat.py FILE
```

where FILE is the input Python file path.
This will by default generate the instrumented version in `examples/out`.
Then run this instrumented version using `python` to execute the actual runtime checks:

```shell
python -m flat.py examples/out/FILE
```

## Case Studies

The case studies mentioned in Section 7??? of the paper are included in `examples/paper`.
The subfolder `logs` includes the output logs that match the paper results.
To check these files yourself, follow the instructions shown in "Usage".

[^1]: Lyrics from the song "You Give REST a Bad Name" (https://dylanbeattie.net/songs/bad_name.html).
[^2]: Here we only consider a simplified version of URLs with no IP addresses, queries, and fragments.