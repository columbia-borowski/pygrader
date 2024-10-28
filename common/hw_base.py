"""common/hw_base.py: Base class for all HW managers and testers"""

from __future__ import annotations

import getpass
import os
import sys
from abc import ABC, abstractmethod
from argparse import REMAINDER, ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Any

from common import printing as p
from common import submissions as subs
from common import utils as u
from common.command_modules import CommandModule
from common.grader import Grader
from common.grades import Grades
from common.grading_policies import LatePercentagePenaltyPolicy
from common.rubric import Rubric


class HWManager(ABC):
    """Abstract base class for homework managers.

    Attributes:
        hw_name (str): The name of the homework.
        hw_tester_class (type[HWTester]): The class of the homework tester.
        scripts_dir (str): The directory containing the scripts for the homework.
        rubric (Rubric): The rubric for the homework.
        workspace_dir (str | None): The workspace directory for the homework.
    """

    def __init__(self, hw_name: str, rubric_name: str, hw_tester_class: type[HWTester]):
        """
        Initializes the HWManager.

        Args:
            hw_name (str): The name of the homework.
            rubric_name (str): The name of the rubric file.
            hw_tester_class (type[HWTester]): The class of the homework tester.
        """
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
        """
        Retrieves the grader for the specified submission.

        Args:
            env (dict[str, bool | str]): The environment variables.
            submitter (str | None): The name of the submitter.

        Returns:
            Grader: The grader for the specified submission.
        """

    @abstractmethod
    def get_grading_status(
        self, rubric_code: str, submitter: str | None = None, ta: str | None = None
    ) -> bool:
        """
        Retrieves the grading status for the specified rubric code.

        Args:
            rubric_code (str): The rubric code.
            submitter (str | None, optional): The name of the submitter. Defaults to None.
            ta (str | None, optional): The name of the TA. Defaults to None.

        Returns:
            bool: True if the grading is complete, False otherwise.
        """

    @abstractmethod
    def get_grades(self, submitter: str | None = None, ta: str | None = None) -> Grades:
        """
        Retrieves the grades for the specified submitter or TA.

        Args:
            submitter (str | None, optional): The name of the submitter. Defaults to None.
            ta (str | None, optional): The name of the TA. Defaults to None.

        Returns:
            Grades: The grades for the specified submitter or TA.
        """

    def get_hw_tester(self, submitter: str) -> HWTester:
        """
        Retrieves the homework tester for the specified submitter.

        Args:
            submitter (str): The name of the submitter.

        Returns:
            HWTester: The homework tester for the specified submitter.
        """
        return self.hw_tester_class(submitter, self)

    @abstractmethod
    def get_submitters(self, ta: str | None = None) -> list[str]:
        """
        Retrieves the list of submitters for the specified TA.

        Args:
            ta (str | None, optional): The name of the TA. Defaults to None.

        Returns:
            list[str]: The list of submitters.
        """


class HWSetup(CommandModule):
    """Alias for command module for homework setup."""

    def __init__(self):
        """
        Initializes the HWSetup.
        """
        super().__init__("hw_setup")


class HWTester:
    """Base class for homework testers.

    Attributes:
        submitter (str): The name of the submitter.
        manager (HWManager): The homework manager.
        grader (Grader | None): The grader.
        submission_dir (str | None): The directory containing the submission.
        ran_rubric_item_codes (set): The set of rubric item codes that have been run.
        ran_rubric_tests (set): The set of rubric tests that have been run.
    """

    def __init__(
        self, submitter: str, manager: HWManager, grader: Grader | None = None
    ):
        """
        Initializes the HWTester.

        Args:
            submitter (str): The name of the submitter.
            manager (HWManager): The homework manager.
            grader (Grader | None, optional): The grader. Defaults to None.
        """
        self.submitter = submitter
        self.manager = manager
        self.grader = grader

        self.submission_dir = None  # Populated in subclasses.

        self.ran_rubric_item_codes = set()
        self.ran_rubric_tests = set()

    @abstractmethod
    def get_grading_policy_data(self) -> dict[str, Any]:
        """
        Retrieves the grading policy data.

        Returns:
            dict[str, Any]: The grading policy data.
        """

    def do_cd(self, path):
        """
        Changes directory relative to the self.submission_dir.

        Args:
            path (str): The path to change to.
        """
        part_dir = os.path.join(self.submission_dir, path)
        u.is_dir(part_dir)
        os.chdir(part_dir)

    def default_grader(self):
        """
        Generic grade function.
        """
        p.print_red("[ Opening shell, ^D/exit when done. ]")
        os.system("bash")

    def exit_handler(self, _signal, _frame):
        """
        Handler for SIGINT.

        Note: this serves as a template for how the subclasses should do it.
        The subclass is free to override this function with more hw-specific
        logic.
        """
        p.print_cyan("\n[ Exiting generic grader... ]")
        self.cleanup()
        sys.exit()

    def cleanup(self):
        """
        Performs cleanup (kills stray processes, removes mods, etc.).
        """


class BaseHWManager(HWManager):
    """Base class for homework managers."""

    def __init__(
        self,
        hw_name: str,
        rubric_name: str,
        hw_tester_class: type[BaseHWTester],
    ):
        """
        Initializes the BaseHWManager.

        Args:
            hw_name (str): The name of the homework.
            rubric_name (str): The name of the rubric file.
            hw_tester_class (type[BaseHWTester]): The class of the homework tester.
        """
        super().__init__(hw_name, rubric_name, hw_tester_class)

        self.workspace_dir = os.path.join(
            Path.home(), ".grade", os.getenv("TA", default=""), hw_name
        )

        self.grades_file = os.path.join(self.workspace_dir, "grades.json")
        self.grading_policies = (LatePercentagePenaltyPolicy(),)

    def get_submission_grader(
        self, env: dict[str, bool | str], submitter: str | None
    ) -> Grader:
        """
        Retrieves the grader for the specified submission.

        Args:
            env (dict[str, bool | str]): The environment variables.
            submitter (str | None): The name of the submitter.

        Returns:
            Grader: The grader for the specified submission.
        """
        hw_tester = self.get_hw_tester(submitter)
        grades = self.get_grades(submitter)
        return Grader(env, hw_tester, grades)

    def get_grades(self, submitter: str | None = None, ta: str | None = None) -> Grades:
        """
        Retrieves the grades for the specified submitter or TA.

        Args:
            submitter (str | None, optional): The name of the submitter. Defaults to None.
            ta (str | None, optional): The name of the TA. Defaults to None.

        Returns:
            Grades: The grades for the specified submitter or TA.
        """
        if ta:
            u.exit_with_not_supported_msg()

        return Grades(self.grades_file, self.rubric, submitter, self.grading_policies)

    def get_grading_status(
        self, rubric_code: str, submitter: str | None = None, ta: str | None = None
    ) -> bool:
        """
        Retrieves the grading status for the specified rubric code.

        Args:
            rubric_code (str): The rubric code.
            submitter (str | None, optional): The name of the submitter. Defaults to None.
            ta (str | None, optional): The name of the TA. Defaults to None.

        Returns:
            bool: True if the grading is complete, False otherwise.
        """
        if ta:
            u.exit_with_not_supported_msg()

        grades = self.get_grades(submitter)
        graded, _ = grades.status(rubric_code)
        return graded

    def get_submitters(self, _: str | None = None) -> list[str]:
        """
        Retrieves the list of submitters.

        Returns:
            list[str]: The list of submitters.
        """
        return []


class BaseHWSetup(HWSetup):
    """Base class for homework setup."""

    def __init__(self):
        """
        Initializes the BaseHWSetup.
        """
        super().__init__()
        self.DEADLINE = None

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "...",
            type=str,
            nargs=REMAINDER,
            help="any arguments for assignment setup script",
        )

    def run(self, parsed: Namespace):
        """
        Executes the setup command based on parsed arguments.

        Args:
            parsed (Namespace): The parsed arguments.
        """
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
        """
        Reads in a deadline and stores it.
        """
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
    """Base class for homework testers."""

    def get_grading_policy_data(self):
        """
        Grabs the latest commit timestamp to compare against the deadline.

        Returns:
            dict[str, Any]: The grading policy data.
        """
        proc = u.cmd_popen("git log -n 1 --format='%aI'")
        iso_timestamp, _ = proc.communicate()

        is_late = subs.check_late(
            os.path.join(self.manager.workspace_dir, "deadline.txt"),
            iso_timestamp.strip("\n"),
        )
        return {"LatePercentagePenaltyPolicy": 0.2 if is_late else 0}


def directory(start_dir: str) -> callable:
    """
    Decorator function that cd's into `start_dir` before the test.

    If start_dir is 'root', we cd into the root of the submission_dir.
    For example:
        @directory("part1")
        def test_B1(self):
            ...
    This will cd into submission_dir/part1 before calling test_B1().

    Args:
        start_dir (str): The directory to change to.

    Returns:
        callable: The decorator function.
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
