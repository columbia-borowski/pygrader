"""
common/assignments.py

This module provides functions to manage and setup assignments based on their names.
It dynamically imports assignment modules and retrieves their manager and setup classes.

Functions:
    get_assignment_manager(hw_name: str) -> HWManager
        Retrieves the manager class for the specified assignment.

    get_assignment_setup(hw_name: str) -> HWSetup
        Retrieves the setup class for the specified assignment.

    _get_assignment_module(hw_name: str)
        Dynamically imports and returns the assignment module based on the assignment name.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.hw_base import HWManager, HWSetup


def get_assignment_manager(hw_name: str) -> HWManager:
    """
    Retrieves the manager class for the specified assignment.

    Args:
        hw_name (str): The name of the assignment.

    Returns:
        HWManager: The manager class for the specified assignment.
    """
    return _get_assignment_module(hw_name).MANAGER()


def get_assignment_setup(hw_name: str) -> HWSetup:
    """
    Retrieves the setup class for the specified assignment.

    Args:
        hw_name (str): The name of the assignment.

    Returns:
        HWSetup: The setup class for the specified assignment.
    """
    return _get_assignment_module(hw_name).SETUP()


def _get_assignment_module(hw_name: str):
    """
    Dynamically imports and returns the assignment module based on the assignment name.

    Args:
        hw_name (str): The name of the assignment.

    Returns:
        module: The imported assignment module.

    Raises:
        SystemExit: If the assignment module is not found.
    """
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

    for assignment in ASSIGNMENTS:
        if hw_name in assignment.ALIASES:
            return assignment

    sys.exit(f"Unsupported assignment: {hw_name}")
