"""common/grader.py: runs hw tester tests and assigns grades"""

from __future__ import annotations

import signal
from collections.abc import Callable
from typing import TYPE_CHECKING

from common import printing as p
from common import utils as u
from common.grades import Grades
from common.rubric import RubricItem

if TYPE_CHECKING:
    from common.hw_base import HWTester


class Grader:
    """Represents the current hw grader

    Attributes:
        env (dict[str, bool | str]): Arguments and Flags determining grader behavior (see main routine for argsparse)
        hw_tester (HWTester): The HWTester object representing this homework (rubric, testers)
        grades (Grades): Maps (uni/team) -> (rubric item -> (pts, comments))
        rubric_code (str): Rubric code being graded (based on AP/OS-style rubrics). This can be a table (A), or an item (A1).
    """

    def __init__(self, env: dict[str, bool | str], hw_tester: HWTester, grades: Grades):
        """
        Initializes the Grader.

        Args:
            env (dict[str, bool | str]): Arguments and Flags determining grader behavior.
            hw_tester (HWTester): The HWTester object representing this homework.
            grades (Grades): The grades object mapping (uni/team) to (rubric item -> (pts, comments)).
        """
        self.env = env
        self.hw_tester = hw_tester
        self.grades = grades

        self.rubric_code = env["code"]
        self.hw_name = self.hw_tester.manager.hw_name

        self.hw_tester.grader = self
        signal.signal(signal.SIGINT, self.hw_tester.exit_handler)

        self.next_item_flag = False
        self.next_student_flag = False

    def grade(self):
        """
        Grades the homework based on the rubric code.

        This method handles the grading process, including printing intros, checking grading policies,
        and grading all items or specific items based on the rubric code.
        """
        key = self.rubric_code
        p.print_intro(self.hw_tester.submitter, self.hw_name, key)

        if not self.grades.are_grading_policies_applied():
            self.grades.save_grading_policies_data(
                self.hw_tester.get_grading_policy_data()
            )

        if key == "ALL":
            self._grade_all()
        elif key.isalpha():
            # e.g. A, B, C, ...
            self._check_valid_table(key)
            self._grade_table(key)
        else:
            # e.g. A1, B4, ...
            table = key[0]
            self._check_valid_table(table)
            self._check_valid_item(key)
            rubric_item_obj = self.hw_tester.manager.rubric[table][key]
            self._grade_item(rubric_item_obj)

        self.hw_tester.cleanup()

        p.print_magenta(
            f"\n[ Pretty-printing pts/comments for {self.hw_tester.submitter}... ]"
        )
        self.grades.dump(key)

    def _check_valid_table(self, table_key: str):
        """
        Checks if the given table key is valid.

        Args:
            table_key (str): The table key to check.

        Raises:
            ValueError: If the table key is not valid.
        """
        keys = [*self.hw_tester.manager.rubric.keys()]
        if table_key not in keys:
            raise ValueError(f"{self.hw_name} does not have table {table_key}")

    def _check_valid_item(self, item_key: str):
        """
        Checks if the given item key is valid.

        Args:
            item_key (str): The item key to check.

        Raises:
            ValueError: If the item key is not valid.
        """
        keys = [*self.hw_tester.manager.rubric[item_key[0]].keys()]
        if item_key not in keys:
            raise ValueError(f"{self.hw_name} does not have rubric item {item_key}")

    def _grade_all(self):
        """
        Grades all tables in the rubric.
        """
        for table in self.hw_tester.manager.rubric.keys():
            self._grade_table(table)
            if self.next_student_flag:
                return

    def _grade_table(self, table_key: str):
        """
        Grades all items in the specified table.

        Args:
            table_key (str): The table key to grade.
        """
        table = self.hw_tester.manager.rubric[table_key]

        for item in table:
            self._grade_item(table[item])
            if self.next_student_flag:
                return

    def _grade_item(self, rubric_item: RubricItem, skip_if_graded: bool = True):
        """
        Grades a single rubric item.

        Args:
            rubric_item (RubricItem): The rubric item to grade.
            skip_if_graded (bool, optional): Whether to skip if already graded. Defaults to True.
        """
        if (
            not self.env["test_only"]
            and not self.env["regrade"]
            and skip_if_graded
            and all(
                self.grades.is_graded(f"{rubric_item.code}.{si}")
                for si, _ in enumerate(rubric_item.subitems, 1)
            )
        ):
            p.print_yellow(f"[ {rubric_item.code} has been graded, skipping... ]")
            return

        # if --grade-only/-g is not provided, run tests else skip tests
        autogrades = None
        if not self.env["grade_only"]:
            dependencies = [
                dep_ri
                for dep_ri in rubric_item.depends_on["has_ran"]
                if not dep_ri.has_test_ran(self.hw_tester)
            ]
            if dependencies:
                p.print_yellow(f"[ Running {rubric_item.code}'s dependencies ]")
                for dependency_rubric_item in dependencies:
                    self._grade_item(dependency_rubric_item, skip_if_graded=False)

            def test_wrapper():
                nonlocal autogrades

                p.print_double()
                self._print_headerline(rubric_item)
                for i, (pts, desc) in enumerate(rubric_item.subitems, 1):
                    p.print_magenta(f"{rubric_item.code}.{i} ({pts}p): {desc}")
                p.print_double()

                test = rubric_item.get_test(self.hw_tester, self.grades)
                autogrades = test()
                return autogrades

            try:
                self._run_and_prompt(test_wrapper)
            except Exception as e:
                p.print_red(f"\n\n[ Exception: {e} ]")
        else:
            self._print_headerline(rubric_item)

        # if -t is not provided, ask for grade. If -t is provided skip
        if (
            not self.env["test_only"]
            and not self.next_item_flag
            and not self.next_student_flag
        ):
            p.print_line()

            self._prompt_grade(rubric_item, autogrades)
        else:
            # Let the grader know if the subitems have been graded yet
            for i in range(1, len(rubric_item.subitems) + 1):
                code = f"{rubric_item.code}.{i}"
                self._print_subitem_grade(code, warn=True)

        self.next_item_flag = False

    def _run_and_prompt(self, f: Callable):
        if self.env["autograde_only"]:
            f()
            return

        valid_options = ["a", "s", "ni"]
        if ns_available := not self.env["submitter"]:
            valid_options.append("ns")

        while True:
            out = f()
            if out is True or isinstance(out, list):
                break

            p.print_line()
            p.print_yellow("Run test again (a)")
            p.print_yellow("Open shell & run again (s)")
            p.print_yellow("Move to next rubric item (ni)")
            if ns_available:
                p.print_yellow("Move to next submission (ns)")
            p.print_yellow("Continue (enter)")

            while True:
                try:
                    usr_input = input(
                        f"{p.CBLUE2}Enter an action [{'|'.join(valid_options)}]: {p.CEND}"
                    )
                    if usr_input == "" or usr_input in valid_options:
                        break
                except EOFError as _:
                    print("^D")
                    continue

            if usr_input == "a":
                continue
            if usr_input == "s":
                u.open_shell()
                continue

            if ns_available and usr_input == "ns":
                self.next_student_flag = True
            if usr_input == "ni":
                self.next_item_flag = True

            break

    def _prompt_grade(
        self, rubric_item: RubricItem, autogrades: list[tuple[str, str]] | None = None
    ):
        """
        Prompts the TA for points and comments for each subitem in the rubric item.

        Args:
            rubric_item (RubricItem): The rubric item to grade.
            autogrades (list[tuple[str, str]] | None, optional): The autogrades for the rubric item. Defaults to None.
        """
        if autogrades:
            # if grade function returns True, assume everything is awarded
            if autogrades is True:
                for i, (_, _) in enumerate(rubric_item.subitems, 1):
                    subitem_code = f"{rubric_item.code}.{i}"
                    self.grades[subitem_code]["award"] = True
                    self.grades[subitem_code]["comments"] = ""
            else:
                if len(autogrades) != len(rubric_item.subitems):
                    raise Exception("Autogrades don't align with rubric item!")

                for i, (a, c) in enumerate(autogrades, 1):
                    subitem_code = f"{rubric_item.code}.{i}"
                    self.grades[subitem_code]["award"] = a == "y"
                    self.grades[subitem_code]["comments"] = c

        elif not self.env["autograde_only"]:
            for i, (pts, desc) in enumerate(rubric_item.subitems, 1):
                subitem_code = f"{rubric_item.code}.{i}"
                p.print_magenta(f"{subitem_code} ({pts}p): {desc}")
                if pts < 0:
                    p.print_red("[ DEDUCTIVE ITEM: enter 'n' if test case passed ]")

                self._print_subitem_grade(subitem_code)
                while True:
                    try:
                        award = input(f"{p.CBLUE2}Apply? [y/n]: {p.CEND}")
                        award = award.strip().lower()
                        if award in {"y", "n"}:
                            break
                    except EOFError:
                        print("^D")
                        continue
                while True:
                    try:
                        comments = input(f"{p.CBLUE2}Comments: {p.CEND}")
                        break
                    except EOFError:
                        print("^D")
                        continue

                self.grades[subitem_code]["award"] = award == "y"
                self.grades[subitem_code]["comments"] = comments.strip()

        self.grades.synchronize()

    def _print_headerline(self, rubric_item: RubricItem):
        """
        Prints the header line for the rubric item.

        Args:
            rubric_item (RubricItem): The rubric item to print the header for.
        """
        header = f"Grading {rubric_item.code}"
        if rubric_item.deduct_from:
            header += " ({rubric_item.deduct_from}p, deductive)"
        p.print_green(header)

    def _print_subitem_grade(self, code: str, warn: bool = False):
        """
        Prints the grade for a subitem.

        Args:
            code (str): The code of the subitem.
            warn (bool, optional): Whether to print a warning if the subitem hasn't been graded. Defaults to False.
        """
        if self.grades.is_graded(code):
            # Let's show the current grade.
            awarded = self.grades[code]["award"]
            comments = self.grades[code]["comments"]
            p.print_green(
                f"[ ({code}) Previous Grade: awarded={awarded} "
                f"comments='{comments}']"
            )
        elif warn:
            p.print_yellow(f"[ {code} hasn't been graded yet ]")
