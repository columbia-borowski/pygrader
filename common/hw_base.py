"""common/hw_base.py: Base class for all HW managers and testers"""

from __future__ import annotations

import getpass
import os
import sys
from abc import ABC, abstractmethod
from argparse import REMAINDER, ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path

from common import printing as p
from common import submissions as subs
from common import utils as u
from common.command_modules import CommandModule
from common.grader import Grader
from common.grades import Grades
from common.grading_policies import LatePercentagePenaltyPolicy
from common.rubric import Rubric


class HWManager(ABC):
    def __init__(self, hw_name: str, rubric_name: str, hw_tester_class: type[HWTester]):
        self.hw_name = hw_name
        self.hw_tester_class = hw_tester_class

        # Find grader root relative to hw_manager.py: root/common/hw_manager.py
        pygrader_root = Path(__file__).resolve().parent.parent
        self.scripts_dir = os.path.join(pygrader_root, self.hw_name)
        # Here we assume the rubric file is in the scripts dir.
        self.rubric = Rubric(os.path.join(self.scripts_dir, rubric_name))

        self.workspace_dir = None

    @abstractmethod
    def get_submission_grader(
        self, env: dict[str, bool | str], submitter: str | None
    ) -> Grader:
        pass

    @abstractmethod
    def get_grading_status(
        self, rubric_code: str, submitter: str | None = None, ta: str | None = None
    ) -> bool:
        pass

    @abstractmethod
    def get_grades(self, submitter: str | None = None, ta: str | None = None) -> Grades:
        pass

    def get_hw_tester(self, submitter) -> HWTester:
        return self.hw_tester_class(submitter, self)

    @abstractmethod
    def get_students(self, ta: str | None = None) -> list[str]:
        pass


class HWSetup(CommandModule):
    """alias for command module"""

    def __init__(self):
        super().__init__("hw_setup")


class HWTester:
    def __init__(
        self, submitter: str, manager: HWManager, grader: Grader | None = None
    ):
        self.submitter = submitter
        self.manager = manager
        self.grader = grader

        self.submission_dir = None  # Populated in subclasses.

        self.ran_rubric_item_codes = set()
        self.ran_rubric_tests = set()

    def do_cd(self, path):
        """Changes directory relative to the self.submission_dir.

        For example, if you had the following:
            hw3  <---- self.submission_dir
            \_ part1
               \_ part1-sub

        and you wanted to cd into part1-sub, you would run
        `do_cd(os.path.join('part1', 'part1-sub'))`.
        """
        part_dir = os.path.join(self.submission_dir, path)
        u.is_dir(part_dir)
        os.chdir(part_dir)

    def default_grader(self):
        """Generic grade function."""
        p.print_red("[ Opening shell, ^D/exit when done. ]")
        os.system("bash")

    def exit_handler(self, _signal, _frame):
        """Handler for SIGINT

        Note: this serves as a template for how the subclasses should do it.
        The subclass is free to override this function with more hw-specific
        logic.
        """
        p.print_cyan("\n[ Exiting generic grader... ]")
        self.cleanup()
        sys.exit()

    def cleanup(self):
        """Performs cleanup (kills stray processes, removes mods, etc.)."""


class BaseHWManager(HWManager):
    def __init__(
        self,
        hw_name: str,
        rubric_name: str,
        hw_tester_class: type[BaseHWTester],
    ):
        super().__init__(hw_name, rubric_name, hw_tester_class)

        self.workspace_dir = os.path.join(
            Path.home(), ".grade", os.getenv("TA", default=""), hw_name
        )

        self.grades_file = os.path.join(self.workspace_dir, "grades.json")
        self.grading_policy = LatePercentagePenaltyPolicy()

    def get_submission_grader(
        self, env: dict[str, bool | str], submitter: str | None
    ) -> Grader:
        hw_tester = self.get_hw_tester(submitter)
        grades = self.get_grades(submitter)
        return Grader(env, hw_tester, grades)

    def get_grades(self, submitter: str | None = None, ta: str | None = None) -> Grades:
        if ta:
            u.exit_with_not_supported_msg()

        return Grades(self.grades_file, self.rubric, submitter, self.grading_policy)

    def get_grading_status(
        self, rubric_code: str, submitter: str | None = None, ta: str | None = None
    ) -> bool:
        if ta:
            u.exit_with_not_supported_msg()

        grades = self.get_grades(submitter)
        graded, _ = grades.status(rubric_code)
        return graded

    def get_students(self, _: str | None = None) -> list[str]:
        return []


class BaseHWSetup(HWSetup):
    def __init__(self):
        super().__init__()
        self.DEADLINE = None

    def extend_parser(self, parser: ArgumentParser):
        parser.add_argument(
            "...",
            type=str,
            nargs=REMAINDER,
            help="any arguments for assignment setup script",
        )

    def run(self, parsed: Namespace):
        run_dir = os.getcwd()
        tas = []

        ta_file = os.path.join(Path.home(), "tas.txt")
        if os.path.exists(ta_file):
            with open(os.path.join(Path.home(), "tas.txt"), "r", encoding="utf-8") as f:
                tas = f.read().splitlines()

        tas.append(getpass.getuser())

        for ta in tas:
            print(f"==={ta.rstrip()}===")
            os.chdir(run_dir)
            root = os.path.join(
                Path.home(), ".grade", ta if ta != getpass.getuser() else ""
            )
            u.create_dir(root)

            pygrader_dir = Path(__file__).resolve().parent.parent
            hw_dir = os.path.join(pygrader_dir, parsed.hw)
            if not os.path.isdir(hw_dir):
                sys.exit(f"Unsupported assignment: {parsed.hw}")

            os.chdir(root)

            if os.path.isdir(parsed.hw) and not u.prompt_overwrite(
                parsed.hw, parsed.hw
            ):
                continue
            u.create_dir(parsed.hw)
            os.chdir(parsed.hw)

            setup_script = os.path.join(hw_dir, "setup")
            if os.path.isfile(setup_script):
                if os.system(f"{setup_script} {' '.join(getattr(parsed, '...'))}"):
                    sys.exit("Setup failed.")

            self._record_deadline()

    def _record_deadline(self):
        """Reads in a deadline and stores it"""
        if os.path.exists("deadline.txt"):
            return
        if not self.DEADLINE:
            p.print_magenta("[ Recording assignment deadline... ]")
            while True:
                try:
                    raw_deadline = input("Soft deadline (MM/DD/YY HH:MM AM/PM): ")
                    # Let's make sure it actually parses
                    _ = datetime.strptime(raw_deadline, "%m/%d/%y %I:%M %p")
                    self.DEADLINE = raw_deadline
                    break
                except ValueError as _:
                    print("Incorrect format!")

        # Write the deadline to ~.grade/hwN/deadline.txt
        with open("deadline.txt", "w", encoding="utf-8") as d:
            d.write(self.DEADLINE)


class BaseHWTester(HWTester):
    def check_late_submission(self):
        """Grabs the latest commit timestamp to compare against the deadline"""
        proc = u.cmd_popen("git log -n 1 --format='%aI'")
        iso_timestamp, _ = proc.communicate()

        return subs.check_late(
            os.path.join(self.manager.workspace_dir, "deadline.txt"),
            iso_timestamp.strip("\n"),
        )


def directory(start_dir: str) -> callable:
    """Decorator function that cd's into `start_dir` before the test.

    If start_dir is 'root', we cd into the root of the submission_dir.
    For example:
        @directory("part1")
        def test_B1(self):
            ...
    This will cd into submission_dir/part1 before calling test_B1().
    """

    # This is definitely overkill, but for ultimate correctness (and
    # for the sake of making the decorator usage sleek), let's allow
    # users to just use '/'. We can correct it here.
    start_dir = os.path.join(*start_dir.split("/"))

    def function_wrapper(test_func):
        def cd_then_test(hw_instance):
            try:
                hw_instance.do_cd("" if start_dir == "root" else start_dir)
            except ValueError:
                p.print_red("[ Couldn't cd into tester's @directory, opening shell.. ]")
                os.system("bash")
            return test_func(hw_instance)

        return cd_then_test

    return function_wrapper
