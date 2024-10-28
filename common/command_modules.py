"""common/command_modules.py: Base class for command modules and base modules

This module defines abstract base classes and concrete implementations for command modules.
These modules are used to extend argument parsers and execute commands based on parsed arguments.

Classes:
    CommandModule
        Abstract base class for command modules.
    CompositeCommandModule
        Abstract base class for composite command modules.
    CommandWithHWDetailsModule
        Command module with parser arguments for homework details.
    GradeModule
        Command module for grading.
    DumpGradesModule
        Command module for dumping grades.
    CheckStatusModule
        Command module for checking grading status.
    InspectModule
        Command module for inspecting submissions.
    StatsModule
        Command module for computing and displaying statistics.
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable

from common import printing as p
from common.assignments import get_assignment_manager


class CommandModule(ABC):
    """Abstract base class for command modules."""

    def __init__(self, name: str, parent_command_module: CommandModule = None):
        """
        Initializes the CommandModule.

        Args:
            name (str): The name of the command module.
            parent_command_module (CommandModule, optional): The parent command module. Defaults to None.
        """
        self.name = name
        self.parent_command_module = parent_command_module

    @abstractmethod
    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """

    @abstractmethod
    def run(self, parsed: Namespace):
        """
        Executes the command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """


class CompositeCommandModule(CommandModule):
    """Abstract base class for composite command modules."""

    def __init__(self, name: str, dest: str, modules: Iterable[CommandModule]):
        """
        Initializes the CompositeCommandModule.

        Args:
            name (str): The name of the composite command module.
            dest (str): The destination attribute for subcommands.
            modules (Iterable[CommandModule]): The subcommand modules.
        """
        super().__init__(name)
        self.dest = dest
        self.modules = modules

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with subcommand parsers.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        subparsers = parser.add_subparsers(required=True, dest=self.dest)
        self.modules_map = {}
        for module in self.modules:
            module.parent_command_module = self
            self.modules_map[module.name] = module
            subparser = subparsers.add_parser(module.name)
            module.extend_parser(subparser)

    def run(self, parsed: Namespace):
        """
        Executes the appropriate subcommand based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
        self.modules_map[getattr(parsed, self.dest)].run(parsed)


class CommandWithHWDetailsModule(CommandModule):
    """Command module with parser arguments for homework details."""

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with homework-related arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")

        hw_details_group = parser.add_mutually_exclusive_group()
        hw_details_group.add_argument(
            "submitter",
            type=str,
            nargs="?",
            help="the name of student/group to grade",
        )
        hw_details_group.add_argument(
            "-T",
            "--ta",
            type=str,
            nargs="?",
            help="grade all submissions for ta",
            dest="ta",
        )

        parser.add_argument(
            "-c",
            "--code",
            type=str,
            nargs="?",
            const="ALL",
            default="ALL",
            help="rubric item (e.g. A, B4) to grade; defaults to ALL",
        )


class GradeModule(CommandWithHWDetailsModule):
    """Command module for grading."""

    def __init__(self):
        """
        Initializes the GradeModule.
        """
        super().__init__("grade")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with grading-related arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        super().extend_parser(parser)

        command_group = parser.add_mutually_exclusive_group()
        command_group.add_argument(
            "-g",
            "--grade-only",
            action="store_true",
            help="grade without running any tests",
            dest="grade_only",
        )
        command_group.add_argument(
            "-t",
            "--test-only",
            action="store_true",
            help="run tests without grading",
            dest="test_only",
        )

        parser.add_argument(
            "-r",
            "--regrade",
            action="store_true",
            help="do not skip previously graded items",
            dest="regrade",
        )

    def run(self, parsed: Namespace):
        """
        Executes the grading command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
        env = vars(parsed)
        env["code"] = env["code"].upper()
        self._grade(env, get_assignment_manager(parsed.hw))

    def _grade(self, env, hw_manager):
        """
        Grades the submissions based on the environment and homework manager.

        Args:
            env (dict): The environment variables.
            hw_manager (HWManager): The homework manager.
        """
        if submitter := env["submitter"]:
            self._grade_submission(env, hw_manager, submitter)
            return

        submitters = hw_manager.get_submitters(env["ta"])
        total_graded_count = len(submitters)
        graded_count = 0
        for submitter in submitters:
            graded_count += 1
            if self._grade_submission(env, hw_manager, submitter, skip_if_graded=True):
                p.print_green(f"\nGraded {graded_count}/{total_graded_count}")

    def _grade_submission(
        self, env, hw_manager, submitter: str, skip_if_graded: bool = False
    ) -> bool:
        """
        Grades a single submission.

        Args:
            env (dict): The environment variables.
            hw_manager (HWManager): The homework manager.
            submitter (str): The name of the submitter.
            skip_if_graded (bool, optional): Whether to skip if already graded. Defaults to False.

        Returns:
            bool: False if the submission was already graded, True otherwise.
        """
        grader = hw_manager.get_submission_grader(env, submitter)
        if (
            not env["test_only"]
            and not env["regrade"]
            and skip_if_graded
            and grader.grades.status(env["code"])[0]
        ):
            return False

        grader.grade()
        grader.hw_tester.cleanup()
        return True


class DumpGradesModule(CommandWithHWDetailsModule):
    """Command module for dumping grades."""

    def __init__(self):
        """
        Initializes the DumpGradesModule.
        """
        super().__init__("dump")

    def run(self, parsed: Namespace):
        """
        Executes the dump grades command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        grades = hw_manager.get_grades(parsed.submitter, parsed.ta)
        grades.dump(parsed.code.upper())


class CheckStatusModule(CommandWithHWDetailsModule):
    """Command module for checking grading status."""

    def __init__(self):
        """
        Initializes the CheckStatusModule.
        """
        super().__init__("status")

    def run(self, parsed: Namespace):
        """
        Executes the check status command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        status = hw_manager.get_grading_status(
            parsed.code.upper(), parsed.submitter, parsed.ta
        )
        sys.exit(not status)


class InspectModule(CommandModule):
    """Command module for inspecting submissions."""

    def __init__(self):
        """
        Initializes the InspectModule.
        """
        super().__init__("inspect")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with inspection-related arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")
        parser.add_argument(
            "submitter",
            type=str,
            help="the name of student/group to grade",
        )

    def run(self, parsed: Namespace):
        """
        Executes the inspect command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        tester = hw_manager.get_hw_tester(parsed.submitter)

        # (pygrader)user@host:pwd $
        prompt = (
            f"{p.CGREEN}({p.CYELLOW}pygrader{p.CGREEN}){p.CEND}"
            f":{p.CBLUE}\\w{p.CCYAN} \\${p.CEND} "
        )

        p.print_red("[ ^D/exit when done ]")
        os.system(f"PROMPT_COMMAND='PS1=\"{prompt}\"; unset PROMPT_COMMAND' " f"bash")

        tester.cleanup()


class StatsModule(CommandWithHWDetailsModule):
    """Command module for computing and displaying statistics."""

    def __init__(self):
        """
        Initializes the StatsModule.
        """
        super().__init__("stats")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with statistics-related arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        super().extend_parser(parser)
        parser.add_argument(
            "-n",
            "--non-zero",
            action="store_true",
            help="compute non zero stats",
            dest="non_zero",
        )

    def run(self, parsed: Namespace):
        """
        Executes the stats command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        stats = hw_manager.get_grades(parsed.submitter, parsed.ta).stats(
            parsed.code, parsed.non_zero
        )
        p.print_stats(stats)
