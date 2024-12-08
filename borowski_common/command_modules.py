"""borowski_common/command_modules.py: Custom command modules"""

import json
import logging
import sys
from argparse import ArgumentParser, Namespace

from borowski_common.constants import MOSS_REPORT_URL
from common import printing as p
from common.assignments import get_assignment_manager
from common.command_modules import CommandModule, CompositeCommandModule

logger = logging.getLogger(__name__)


class RunMossModule(CommandModule):
    """
    A command module to run MOSS (Measure of Software Similarity) for plagiarism detection.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the MOSS command.
    """

    def __init__(self):
        super().__init__("moss")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")

    def run(self, parsed: Namespace):
        """
        Runs the MOSS command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        hw_manager.plagiarism_check()


class GetSubmissionInfoModule(CommandModule):
    """
    A command module to get submission information.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the get submission info command.
    """

    def __init__(self):
        super().__init__("submission-info")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

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
        Runs the get submission info command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        print(json.dumps(hw_manager.get_submission_data(parsed.submitter), indent=4))


class PlagiarismModule(CommandModule):
    """
    A command module to flag submissions for plagiarism.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the plagiarism command.
    """

    def __init__(self):
        super().__init__("plagiarism")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")
        parser.add_argument("matches", type=str, help="matches to flag", nargs="+")

    def run(self, parsed: Namespace):
        """
        Runs the plagiarism command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)

        if "moss" not in hw_manager.hw_info:
            p.print_red("[ MOSS has not been run yet]")
            sys.exit(1)

        for match in parsed.matches:
            if match not in hw_manager.hw_info["moss"]:
                p.print_yellow(f"[ Match {match} not found ]")
                continue

            for submitter in hw_manager.hw_info["moss"][match]:
                student_grades = hw_manager.get_grades(submitter)
                student_grades._grades[submitter]["grading_policies"][
                    "PlagiarismPolicy"
                ][match] = f"{MOSS_REPORT_URL}/{parsed.hw}/{match}"
                student_grades.synchronize()


class DeductionsModule(CompositeCommandModule):
    """
    A composite command module to manage deductions.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
    """

    def __init__(self):
        super().__init__(
            "deductions",
            "deduction-command",
            [DeductionsAddModule(), DeductionsGetModule(), DeductionsRemoveModule()],
        )

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")
        parser.add_argument(
            "submitter", type=str, help="the name of student/group to grade"
        )
        super().extend_parser(parser)


class DeductionsAddModule(CommandModule):
    """
    A command module to add deductions.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the add deductions command.
    """

    def __init__(self):
        super().__init__("add")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "-p",
            "--points",
            type=int,
            help=("the points you wanna add (use negative value for deduction)"),
            dest="points",
            required=True,
        )
        parser.add_argument(
            "-c",
            "--comment",
            type=str,
            help=("rubric item (e.g. A, B4) to grade; " "defaults to ALL"),
            dest="comment",
            required=True,
        )

    def run(self, parsed: Namespace):
        """
        Runs the add deductions command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        student_grades = hw_manager.get_grades(parsed.submitter)

        grading_policy = student_grades._grades[parsed.submitter]["grading_policies"]
        grading_policy["CustomDeductionsPolicy"].append(
            {"comment": parsed.comment, "deduction": parsed.points}
        )

        student_grades.synchronize()


class DeductionsGetModule(CommandModule):
    """
    A command module to get deductions.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the get deductions command.
    """

    def __init__(self):
        super().__init__("get")

    def extend_parser(self, _):
        """
        Extends the argument parser with additional arguments.
        """

    def run(self, parsed: Namespace):
        """
        Runs the get deductions command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        student_grades = hw_manager.get_grades(parsed.submitter)

        grading_policy = student_grades._grades[parsed.submitter]["grading_policies"]
        for i, entry in enumerate(grading_policy["CustomDeductionsPolicy"]):
            print(f"{i}: ({entry['deduction']}) {entry['comment']}")


class DeductionsRemoveModule(CommandModule):
    """
    A command module to remove deductions.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the remove deductions command.
    """

    def __init__(self):
        super().__init__("remove")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("index", type=int)

    def run(self, parsed: Namespace):
        """
        Runs the remove deductions command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        student_grades = hw_manager.get_grades(parsed.submitter)

        grading_policy = student_grades._grades[parsed.submitter]["grading_policies"]
        grading_policy["CustomDeductionsPolicy"].pop(parsed.index)

        student_grades.synchronize()
