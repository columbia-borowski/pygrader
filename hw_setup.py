#!/usr/bin/env python3
"""hw_setup.py: Prepares grading environment"""

import argparse

from common import printing as p
from common.assignments import get_assignment_setup


def main():
    """Prompts for homework deadline and prepares submissions for grading"""
    parser = argparse.ArgumentParser()
    parser.add_argument("hw", type=str, help="the assignment to setup (e.g. hw1)")
    parsed, _ = parser.parse_known_args()

    hw_setup = get_assignment_setup(parsed.hw)

    hw_setup.extend_parser(parser)
    parsed = parser.parse_args()

    hw_setup.run(parsed)

    p.print_green(f"Ready to grade {parsed.hw}!")


if __name__ == "__main__":
    main()
