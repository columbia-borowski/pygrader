"""common/loader.py: Load command modules"""

from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Iterable

from common.command_modules import (
    CheckStatusModule,
    CommandModule,
    CompositeCommandModule,
    DumpGradesModule,
    GradeModule,
    InspectModule,
    StatsModule,
)


def load_and_run_pygrader(custom_modules: Iterable[CommandModule] | None = None):
    """Load and run the pygrader framework with the provided custom modules."""
    modules = [
        GradeModule(),
        DumpGradesModule(),
        CheckStatusModule(),
        InspectModule(),
        StatsModule(),
    ]
    if custom_modules:
        modules.extend(custom_modules)

    load_and_run_modules(modules, description="pygrader: Python Grading Framework")


def load_and_run_modules(modules: Iterable[CommandModule], **kwargs):
    main_module = CompositeCommandModule("main", "command", modules)

    parser = ArgumentParser(**kwargs)
    main_module.extend_parser(parser)

    parsed = parser.parse_args()
    main_module.run(parsed)
