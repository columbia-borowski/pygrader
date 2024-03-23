"""common/loader.py: Load command modules"""

from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Iterable

from common.command_modules import (
    CheckStatusModule,
    CommandModule,
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
    parser = ArgumentParser(**kwargs)
    subparsers = parser.add_subparsers(required=True, dest="command")

    modules_map = {}
    for module in modules:
        modules_map[module.name] = module
        subparser = subparsers.add_parser(module.name)
        module.extend_parser(subparser)

    args = parser.parse_args()
    modules_map[args.command].run(args)
