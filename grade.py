#!/usr/bin/env python3
"""grade.py: Grading driver"""

from __future__ import annotations

import argparse
import os
import sys

from common import printing as p
from common.assignments import get_assignment_manager


def main():
    """Entry-point into the grader"""
    parser = argparse.ArgumentParser(description="pygrader: Python Grading Framework")

    parser.add_argument("hw", type=str, help="homework to grade")

    # either specify a student, a ta, or neither, but not both
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

    command_group = parser.add_mutually_exclusive_group()
    # grade mode
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
    command_group.add_argument(
        "-r",
        "--regrade",
        action="store_true",
        help="do not skip previously graded items",
        dest="regrade",
    )
    # script mode
    command_group.add_argument(
        "-d",
        "--dump-grades",
        action="store_true",
        help=("dump grades for this homework -- " "all if no submitter specified"),
        dest="dump_grades",
    )
    command_group.add_argument(
        "-s",
        "--status",
        action="store_true",
        help=(
            "return grading status for this homework -- "
            "all if no submitter specified"
        ),
        dest="status",
    )
    command_group.add_argument(
        "-i",
        "--inspect",
        action="store_true",
        help=("drop into shell to inspect submission"),
        dest="inspect",
    )

    args = parser.parse_args()
    env = vars(args)
    env["code"] = env["code"].upper()

    session = GradingSession(env)

    if args.dump_grades:
        session.dump_grades()
        sys.exit()

    if args.status:
        sys.exit(not session.grades_status())

    if args.inspect:
        session.inspect()
        sys.exit()

    session.grade()


class GradingSession:
    """Represents the current hw grading session
    Attributes:
        env: Arguments and Flags determining grader behavior (see main routine for argsparse)
        hw_name: Homework name being graded (e.g. hw1)
        rubric_code: Rubric code being graded (based on AP/OS-style rubrics)
            This can be a table (A), or an item (A1).
        submitter: Team/uni of the submission
        ta: the TA whose submissions are being graded
        hw_manager: The MANAGER object representing this homework
    """

    def __init__(self, env: dict[str, bool | str]):
        self.env = env
        self.hw_name = env["hw"]
        self.rubric_code = env["code"]
        self.submitter = env["submitter"]
        self.ta = env["ta"]

        self.hw_manager = get_assignment_manager(self.hw_name)

    def grade(self):
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

    def dump_grades(self):
        grades = self.hw_manager.get_grades(self.submitter, self.ta)
        grades.dump(self.rubric_code)

    def grades_status(self) -> bool:
        return self.hw_manager.get_grading_status(
            self.rubric_code, self.submitter, self.ta
        )

    def inspect(self):
        tester = self.hw_manager.get_hw_tester(self.submitter)
        # (pygrader)user@host:pwd $
        prompt = (
            f"{p.CGREEN}({p.CYELLOW}pygrader{p.CGREEN}){p.CEND}"
            f":{p.CBLUE}\\w{p.CCYAN} \${p.CEND} "
        )
        p.print_red("[ ^D/exit when done ]")
        os.system(f"PROMPT_COMMAND='PS1=\"{prompt}\"; unset PROMPT_COMMAND' " f"bash")
        tester.cleanup()


if __name__ == "__main__":
    main()
