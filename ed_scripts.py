#!/usr/bin/env python3
"""ed_scripts.py: scripts that deal with Ed"""

from borowski_common.ed_modules import GradesPostModule, RegradeRequestModule
from common.loader import load_and_run_modules

if __name__ == "__main__":
    load_and_run_modules((GradesPostModule(), RegradeRequestModule()))
