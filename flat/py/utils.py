import time
from io import TextIOWrapper
from typing import TypeVar, Callable, Tuple

from flat.py import FuzzReport

T = TypeVar('T')


def classify(f: Callable[[T], bool], xs: list[T]) -> Tuple[list[T], list[T]]:
    passed = []
    failed = []
    for x in xs:
        if f(x):
            passed.append(x)
        else:
            failed.append(x)

    return passed, failed


def print_fuzz_report(report: FuzzReport) -> None:
    print(f'--> Fuzz {report.target}')
    passed = 0
    for (args, r) in report.records:
        if r == 'OK':
            passed += 1
        else:
            print(f'[{r}] {args}')
    print(f'Summary: {passed}/{len(report.records)} passed, '
          f'execution time: producing {report.producer_time} s, checking {report.checker_time} s\n')


def log_fuzz_report(report: FuzzReport, to: TextIOWrapper) -> None:
    to.write(f'Fuzz {report.target}\n')
    passed = 0
    for (args, r) in report.records:
        to.write(f'[{r}] {args}\n')
        if r == 'OK':
            passed += 1
    to.write(f'Summary: {passed}/{len(report.records)} passed, '
             f'execution time: producing {report.producer_time} s, checking {report.checker_time} s\n')
    to.flush()


def measure_overhead(report: FuzzReport, original: Callable) -> Tuple[float, float]:
    total_time = 0.0
    for (inp, _) in report.records:
        try:
            t = time.process_time()
            original(*inp)
            total_time += (time.process_time() - t)
        except Exception:
            pass
        except SystemExit:
            pass
    return total_time, report.checker_time - total_time
