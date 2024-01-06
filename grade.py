#!/usr/bin/env python3

"""grade.py: Grading driver"""

import argparse
import importlib
import os
import signal
import sys
from typing import Dict, List, Optional, Tuple

import common.printing as p
import common.utils as utils
from common.grades import Grades
from common.rubric import RubricItem

_, subdirs, _ = next(os.walk(os.path.dirname(os.path.realpath(__file__))))
assignments = []
for subdir in subdirs:
    if (
        subdir[0] != "."
        and subdir != "docs"
        and subdir != "common"
        and not subdir.endswith("_common")
    ):
        assignments.append(importlib.import_module(f"{subdir}.grader"))


def main():
    """Entry-point into the grader"""
    parser = argparse.ArgumentParser(description="pygrader: Python Grading Framework")

    parser.add_argument("hw", type=str, help="homework to grade")
    parser.add_argument(
        "submitter",
        type=str,
        nargs="?",
        default=None,
        help="the name of student/group to grade",
    )
    parser.add_argument(
        "-c",
        "--code",
        type=str,
        nargs="?",
        default="all",
        help=("rubric item (e.g. A, B4) to grade; " "defaults to all"),
    )

    grading_mode = parser.add_mutually_exclusive_group()
    grading_mode.add_argument(
        "-g",
        "--grade-only",
        action="store_true",
        help="grade without running any tests",
        dest="grade_only",
    )
    grading_mode.add_argument(
        "-t",
        "--test-only",
        action="store_true",
        help=("run tests without grading"),
        dest="test_only",
    )
    script_mode = parser.add_mutually_exclusive_group()
    script_mode.add_argument(
        "-r",
        "--regrade",
        action="store_true",
        help="do not skip previously graded items",
        dest="regrade",
    )
    script_mode.add_argument(
        "-d",
        "--dump-grades",
        action="store_true",
        help=("dump grades for this homework -- " "all if no submitter specified"),
        dest="dump_grades",
    )
    script_mode.add_argument(
        "-s",
        "--status",
        action="store_true",
        help=(
            "return grading status for this homework -- "
            "all if no submitter specified"
        ),
        dest="status",
    )
    script_mode.add_argument(
        "-i",
        "--inspect",
        action="store_true",
        help=("drop into shell to inspect submission"),
        dest="inspect",
    )

    args = parser.parse_args()
    env = {
        "regrade": args.regrade,
        "grade_only": args.grade_only,
        "test_only": args.test_only,
        "dump_grades": args.dump_grades,
        "status": args.status,
        "inspect": args.inspect,
    }

    rubric_code = args.code if args.code else "all"

    tester = Grader(args.hw, args.submitter, rubric_code, env)

    if args.dump_grades:
        tester.grades.dump(rubric_code.upper())
        sys.exit()

    if args.status:
        all_graded, _ = tester.grades.status(rubric_code.upper())
        sys.exit(not all_graded)  # If all graded, exit with 0 (success)

    if args.inspect:
        # (pygrader)user@host:pwd $
        prompt = (
            f"{p.CGREEN}({p.CYELLOW}pygrader{p.CGREEN}){p.CEND}"
            f":{p.CBLUE}\\w{p.CCYAN} \${p.CEND} "
        )
        p.print_red("[ ^D/exit when done ]")
        os.system(f"PROMPT_COMMAND='PS1=\"{prompt}\"; unset PROMPT_COMMAND' " f"bash")
        sys.exit()

    if not args.submitter:
        sys.exit("unspecified student/team")
    tester.grade()

    # TODO: add progress/percentage complete?
    p.print_magenta(f"\n[ Pretty-printing pts/comments for {args.submitter}... ]")
    _, _, s = tester.grades.get_submission_grades(args.submitter, rubric_code.upper())
    print(s)
    # clean up
    tester.hw_class.cleanup()


class Grader:
    """Represents the current hw grading session

    Attributes:
        hw_name: Homework name being graded (e.g. hw1)
        rubric_code: Rubric code being graded (based on AP/OS-style rubrics)
            This can be a table (A), or an item (A1).
        submitter: Team/uni of the submission
        hw_class: The object representing this homework (rubric, testers)
        env: Flags determining grader behavior (see main routine for argsparse)
        grades_file: Path to JSON file containing session grades
        grades: Maps (uni/team) -> (rubric item -> (pts, comments))
    """

    def __init__(
        self, hw_name: str, submitter: str, rubric_code: str, env: Dict[str, bool]
    ):
        self.hw_name = hw_name
        self.rubric_code = rubric_code
        self.submitter = submitter
        self.env = env
        self.hw_class = self._get_hw_class()
        self.hw_class.grader = self

        signal.signal(signal.SIGINT, self.hw_class.exit_handler)

        self.grades_file = os.path.join(self.hw_class.hw_workspace, "grades.json")
        self.grades = Grades(
            self.grades_file,
            self.hw_class.rubric,
            self.submitter,
            self.hw_class.grading_policy,
        )

    def _get_hw_class(self):
        for assignment in assignments:
            if self.hw_name.lower() in assignment.ALIASES:
                return assignment.GRADER(self.submitter)
        sys.exit(f"Unsupported assignment: {self.hw_name}")

    def print_headerline(self, rubric_item: RubricItem):
        header = "Grading {}".format(rubric_item.code)
        if rubric_item.deduct_from:
            header += " ({}p, deductive)".format(rubric_item.deduct_from)
        p.print_green(header)

    def print_subitems(self, rubric_item: RubricItem):
        for i, (pts, desc) in enumerate(rubric_item.subitems, 1):
            p.print_magenta("{}.{} ({}p): {}".format(rubric_item.code, i, pts, desc))

    def print_subitem_grade(self, code: str, warn: bool = False):
        if self.grades.is_graded(code):
            # We've graded this already. Let's show the current grade.
            awarded = self.grades[code]["award"]
            comments = self.grades[code]["comments"]
            p.print_green(
                f"[ ({code}) Previous Grade: awarded={awarded} "
                f"comments='{comments}']"
            )
        elif warn:
            p.print_yellow(f"[ {code} hasn't been graded yet ]")

    def prompt_grade(
        self,
        rubric_item: RubricItem,
        autogrades: Optional[List[Tuple[str, str]]] = None,
    ):
        """Prompts the TA for pts/comments"""

        if autogrades:
            if len(autogrades) != len(rubric_item.subitems):
                raise Exception("Autogrades don't align with rubric item!")

            for i, (a, c) in enumerate(autogrades, 1):
                subitem_code = f"{rubric_item.code}.{i}"
                self.grades[subitem_code]["award"] = a == "y"
                self.grades[subitem_code]["comments"] = c

        else:
            for i, (pts, desc) in enumerate(rubric_item.subitems, 1):
                subitem_code = f"{rubric_item.code}.{i}"
                p.print_magenta(f"{subitem_code} ({pts}p): {desc}")
                self.print_subitem_grade(subitem_code)
                while True:
                    try:
                        award = input(f"{p.CBLUE2}Apply? [y/n]: {p.CEND}")
                        award = award.strip().lower()
                        if award in ("y", "n"):
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

    def _check_valid_table(self, table_key: str):
        """Given a key (i.e A, C, N) check if its a valid rubric item"""

        keys = [*self.hw_class.rubric.keys()]
        if table_key not in keys:
            raise ValueError(f"{self.hw_name} does not have table {table_key}")

    def _check_valid_item(self, item_key: str):
        """Given a table item (i.e. A1, B2, D9) check if it is valid.

        Assumes the table is valid (use _check_valid_table() for validation on
        that).
        """
        keys = [*self.hw_class.rubric[item_key[0]].keys()]
        if item_key not in keys:
            raise ValueError(f"{self.hw_name} does not have " f"rubric item {item_key}")

    def grade(self):
        key = self.rubric_code
        p.print_intro(self.hw_class.submitter, self.hw_name, key)

        self.grades.enforce_grading_policy(self.hw_class)

        if key.lower() == "all":
            self.grade_all()
        elif key.isalpha():
            # e.g. A, B, C, ...
            table = key.upper()
            self._check_valid_table(table)
            self.grade_table(table)
        else:
            # e.g. A1, B4, ...
            table = key[0].upper()
            item = key.upper()
            self._check_valid_table(table)
            self._check_valid_item(item)
            rubric_item_obj = self.hw_class.rubric[table][item]
            self.grade_item(rubric_item_obj)

    def grade_all(self):
        for table in self.hw_class.rubric.keys():
            if table == "late_penalty":
                continue
            self.grade_table(table)

    def grade_table(self, table_key: str):
        table = self.hw_class.rubric[table_key]

        for item in table:
            self.grade_item(table[item])

    def grade_item(self, rubric_item: RubricItem, skip_if_graded: bool = True):
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
            dependancies = [
                dep_ri
                for dep_ri in rubric_item.depends_on
                if not dep_ri.has_test_ran(self.hw_class)
            ]
            if dependancies:
                p.print_yellow(f"[ Running {rubric_item.code}'s dependancies ]")
                for dependancy_rubric_item in dependancies:
                    self._grade_item(dependancy_rubric_item, skip_if_graded=False)

            def test_wrapper():
                nonlocal autogrades

                p.print_double()
                self.print_headerline(rubric_item)
                for i, (pts, desc) in enumerate(rubric_item.subitems, 1):
                    p.print_magenta(f"{rubric_item.code}.{i} ({pts}p): {desc}")
                p.print_double()

                test = rubric_item.get_test(self.hw_class)
                autogrades = test()
                return autogrades

            try:
                utils.run_and_prompt(test_wrapper)
            except Exception as e:
                p.print_red(f"\n\n[ Exception: {e} ]")
        else:
            self.print_headerline(rubric_item)

        # if -t is not provided, ask for grade. If -t is provided skip
        if not self.env["test_only"]:
            p.print_line()

            self.prompt_grade(rubric_item, autogrades)
        else:
            # Let the grader know if the subitems have been graded yet
            for i in range(1, len(rubric_item.subitems) + 1):
                code = f"{rubric_item.code}.{i}"
                self.print_subitem_grade(code, warn=True)


if __name__ == "__main__":
    main()
