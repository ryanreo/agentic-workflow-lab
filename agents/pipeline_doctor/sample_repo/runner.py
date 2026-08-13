"""Tiny test runner (no third-party dependencies)."""

import sys

from pipeline import apply_discount, apply_tax, process_order

CHECKS = [
    ("discount", apply_discount(100), 85.0),
    ("tax", apply_tax(100), 118.0),
    ("order", process_order([50, 30, 20]), 100.3),
]


def main():
    failures = 0
    for name, got, expected in CHECKS:
        if abs(got - expected) > 1e-9:
            print(f"FAIL: {name} expected={expected} got={got}")
            failures += 1
        else:
            print(f"PASS: {name}")
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
