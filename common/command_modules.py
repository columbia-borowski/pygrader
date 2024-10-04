"""common/command_modules.py: Base class for command modules and base modules"""

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
        self.name = name
        self.parent_command_module = parent_command_module

    @abstractmethod
    def extend_parser(self, parser: ArgumentParser):
        pass

    @abstractmethod
    def run(self, parsed: Namespace):
        pass


class CompositeCommandModule(CommandModule):
    """Abstract base class for composite command modules."""

    def __init__(self, name: str, dest: str, modules: Iterable[CommandModule]):
        super().__init__(name)
        self.dest = dest
        self.modules = modules

    def extend_parser(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(required=True, dest=self.dest)
        self.modules_map = {}
        for module in self.modules:
            module.parent_command_module = self
            self.modules_map[module.name] = module
            subparser = subparsers.add_parser(module.name)
            module.extend_parser(subparser)

    def run(self, parsed: Namespace):
        self.modules_map[getattr(parsed, self.dest)].run(parsed)


class CommandWithHWDetailsModule(CommandModule):
    """Command module with parser arguments for hw details."""

    def extend_parser(self, parser: ArgumentParser):
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
            help=("grade all submissions for ta"),
            dest="ta",
        )

        parser.add_argument(
            "-c",
            "--code",
            type=str,
            nargs="?",
            const="ALL",
            default="ALL",
            help=("rubric item (e.g. A, B4) to grade; " "defaults to ALL"),
        )


class GradeModule(CommandWithHWDetailsModule):
    """Command module for grading."""

    def __init__(self):
        super().__init__("grade")

    def extend_parser(self, parser: ArgumentParser):
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
            help=("run tests without grading"),
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
        env = vars(parsed)
        env["code"] = env["code"].upper()

        self.env = env
        self.hw_name = env["hw"]
        self.rubric_code = env["code"]
        self.submitter = env["submitter"]
        self.ta = env["ta"]

        self.hw_manager = get_assignment_manager(parsed.hw)

        self._grade()

    def _grade(self):
        if self.submitter:
            self._grade_submission(self.submitter)
            return

        student_list = self.hw_manager.get_students(self.ta)
        total_graded_count = len(student_list)
        graded_count = 0
        for student in student_list:
            graded_count += 1
            if self._grade_submission(student, skip_if_graded=True):
                p.print_green(f"\nGraded {graded_count}/{total_graded_count}")

    def _grade_submission(self, submitter: str, skip_if_graded: bool = False) -> bool:
        """Returns false if the submission was already graded"""
        grader = self.hw_manager.get_submission_grader(self.env, submitter)
        if (
            not self.env["test_only"]
            and not self.env["regrade"]
            and skip_if_graded
            and grader.grades.status(self.env["code"])[0]
        ):
            return False

        grader.grade()
        grader.hw_tester.cleanup()
        return True


class DumpGradesModule(CommandWithHWDetailsModule):
    """Command module for dumping grades."""

    def __init__(self):
        super().__init__("dump")

    def run(self, parsed: Namespace):
        hw_manager = get_assignment_manager(parsed.hw)
        grades = hw_manager.get_grades(parsed.submitter, parsed.ta)
        grades.dump(parsed.code.upper())


class CheckStatusModule(CommandWithHWDetailsModule):
    """Command module for checking grading status."""

    def __init__(self):
        super().__init__("status")

    def run(self, parsed: Namespace):
        hw_manager = get_assignment_manager(parsed.hw)
        status = hw_manager.get_grading_status(
            parsed.code.upper(), parsed.submitter, parsed.ta
        )
        sys.exit(not status)


class InspectModule(CommandModule):
    """Command module for inspecting submissions."""

    def __init__(self):
        super().__init__("inspect")

    def extend_parser(self, parser: ArgumentParser):
        parser.add_argument("hw", type=str, help="homework to grade")
        parser.add_argument(
            "submitter",
            type=str,
            help="the name of student/group to grade",
        )

    def run(self, parsed: Namespace):
        hw_manager = get_assignment_manager(parsed.hw)
        tester = hw_manager.get_hw_tester(parsed.submitter)

        # (pygrader)user@host:pwd $
        prompt = (
            f"{p.CGREEN}({p.CYELLOW}pygrader{p.CGREEN}){p.CEND}"
            f":{p.CBLUE}\\w{p.CCYAN} \${p.CEND} "
        )

        p.print_red("[ ^D/exit when done ]")
        os.system(f"PROMPT_COMMAND='PS1=\"{prompt}\"; unset PROMPT_COMMAND' " f"bash")

        tester.cleanup()


class StatsModule(CommandWithHWDetailsModule):
    def __init__(self):
        super().__init__("stats")

    def extend_parser(self, parser: ArgumentParser):
        super().extend_parser(parser)
        parser.add_argument(
            "-n",
            "--non-zero",
            action="store_true",
            help=("compute non zero stats"),
            dest="non_zero",
        )

    def run(self, parsed: Namespace):
        hw_manager = get_assignment_manager(parsed.hw)
        stats = hw_manager.get_grades(parsed.submitter, parsed.ta).stats(
            parsed.code, parsed.non_zero
        )

        p.print_stats(stats)
