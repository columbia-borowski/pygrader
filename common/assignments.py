import importlib
import os
import sys
from pathlib import Path

from common.hw_base import HWManager, HWSetup

_, subdirs, _ = next(os.walk(os.path.dirname(Path(__file__).resolve().parent)))
ASSIGNMENTS = []
for subdir in subdirs:
    if (
        subdir[0] != "."
        and subdir != "docs"
        and subdir != "common"
        and not subdir.endswith("_common")
    ):
        try:
            ASSIGNMENTS.append(importlib.import_module(f"{subdir}.grader"))
        except ModuleNotFoundError:
            continue


def get_assignment_manager(hw_name: str) -> HWManager:
    return _get_assignment_module(hw_name).MANAGER()


def get_assignment_setup(hw_name: str) -> HWSetup:
    return _get_assignment_module(hw_name).SETUP()


def _get_assignment_module(hw_name: str):
    for assignment in ASSIGNMENTS:
        if hw_name in assignment.ALIASES:
            return assignment

    sys.exit(f"Unsupported assignment: {hw_name}")
