"""borowski_common/command_modules.py: Custom command modules"""

import asyncio
import json
import logging
import os
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta

import requests
import websockets
from jinja2 import Environment, FileSystemLoader, select_autoescape

from borowski_common.constants import (
    ED_COURSE_ID,
    ED_HEADERS,
    MOSS_REPORT_URL,
    NYZ_TZ,
    PYGRADER_ROOT,
)
from common import printing as p
from common.assignments import get_assignment_manager
from common.command_modules import (
    CommandModule,
    CommandWithHWDetailsModule,
    CompositeCommandModule,
)

logger = logging.getLogger(__name__)


class UploadGradesModule(CommandWithHWDetailsModule):
    """
    A command module to upload grades.

    Methods:
        run(parsed: Namespace): Runs the upload grades command.
    """

    def __init__(self):
        super().__init__("upload")

    def run(self, parsed: Namespace):
        """
        Runs the upload grades command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        hw_manager.upload_grades(parsed.submitter, parsed.ta)


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


class EdRegradeRequestModule(CommandModule):
    """
    A command module to handle regrade requests on Ed.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the regrade request command.
        _connect_to_websocket(hw: str, round_robin: bool, index: int, category: str): Connects to the Ed websocket.
        _get_user_info(): Retrieves user information from Ed.
        _get_ta_tag_comment(thread_id, submitter, content): Generates a TA tag comment.
        _get_uni_from_post(content): Extracts the UNI from a post.
    """

    def __init__(self):
        super().__init__("ed-regrades")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")
        parser.add_argument(
            "-r",
            "--round-robin",
            type=int,
            nargs="?",
            const=0,
            default=-1,
            help=("specify if round robin allocation starting at index"),
            dest="round_robin",
        )
        parser.add_argument(
            "-c",
            "--category",
            type=str,
            nargs="?",
            const="Regrade Requests",
            default="Regrade Requests",
            help=("post category name to tag"),
            dest="category",
        )

    def run(self, parsed: Namespace):
        """
        Runs the regrade request command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        logging.basicConfig(
            filename=os.path.join(PYGRADER_ROOT, "regrade.log"),
            format="%(asctime)s %(levelname)-8s %(message)s",
            level=logging.INFO,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        asyncio.get_event_loop().run_until_complete(
            self._connect_to_websocket(
                parsed.hw, parsed.round_robin >= 0, parsed.round_robin, parsed.category
            )
        )

    async def _connect_to_websocket(
        self, hw: str, round_robin: bool, index: int, category: str
    ):
        """
        Connects to the Ed websocket.

        Args:
            hw (str): The homework assignment.
            round_robin (bool): Whether to use round-robin allocation.
            index (int): The starting index for round-robin allocation.
            category (str): The category to filter threads.
        """
        self._get_user_info()

        current_ta = index - 1

        self.hw_manager = None if round_robin else get_assignment_manager(hw)
        while True:
            try:
                async with websockets.connect(
                    "wss://us.edstem.org/api/stream", additional_headers=ED_HEADERS
                ) as websocket:
                    logger.info("Connected to Web Socket")
                    await websocket.send(
                        json.dumps(
                            {"id": 0, "type": "course.subscribe", "oid": ED_COURSE_ID}
                        )
                    )
                    while True:
                        response = json.loads(await websocket.recv())
                        if (
                            response["type"] == "thread.new"
                            and response["data"]["thread"]["category"] == category
                        ):
                            thread_id = response["data"]["thread"]["id"]
                            poster_id = response["data"]["thread"]["user_id"]
                            if poster_id not in self.ed_id_to_ed_user:
                                self._get_user_info()

                            if round_robin:
                                current_ta = (current_ta + 1) % len(self.ed_ta_list)
                                ta_id = self.ed_ta_list[current_ta]["id"]
                                ta_name = self.ed_ta_list[current_ta]["name"]

                                logger.info(
                                    "Assigned thread %d to %s", thread_id, ta_name
                                )
                                comment_content = (
                                    f'<mention id="{ta_id}">{ta_name}</mention>'
                                )
                            else:
                                comment_content = self._get_ta_tag_comment(
                                    thread_id,
                                    self.ed_id_to_ed_user[poster_id]["sourced_id"],
                                    response["data"]["thread"]["document"],
                                )

                            response = requests.post(
                                f"https://us.edstem.org/api/threads/{thread_id}/comments",
                                timeout=10,
                                json={
                                    "comment": {
                                        "type": "comment",
                                        "content": f'<document version="2.0"><paragraph>{comment_content}</paragraph></document>',
                                        "is_private": True,
                                        "is_anonymous": False,
                                    }
                                },
                                headers=ED_HEADERS,
                            )
            except websockets.ConnectionClosed as e:
                logger.error("Connection Closed: %s", e)
            except Exception as e:
                logger.error("An error occurred: %s", e)

    def _get_user_info(self):
        """
        Retrieves user information from Ed.
        """
        response = requests.get(
            f"https://us.edstem.org/api/courses/{ED_COURSE_ID}/admin",
            timeout=10,
            headers=ED_HEADERS,
        )
        ed_users = response.json()["users"]

        self.ed_id_to_ed_user = {user["id"]: user for user in ed_users}
        self.uni_to_ed_id_map = {user["sourced_id"]: user["id"] for user in ed_users}

        self.ed_ta_list = sorted(
            (
                user
                for user in ed_users
                if user["role"] != "student" and user["name"] != "Brian Borowski"
            ),
            key=lambda u: u["name"],
        )

    def _get_ta_tag_comment(self, thread_id: str, submitter: str, content: str):
        """
        Generates a TA tag comment.

        Args:
            thread_id (str): The thread ID.
            submitter (str): The submitter's identifier.
            content (str): The content of the post.

        Returns:
            str: The TA tag comment.
        """
        try:
            ta_uni = self.hw_manager.get_submission_data(submitter)["ta"]["uni"]
        except KeyError:
            try:
                submitter = self._get_uni_from_post(content)
                ta_uni = self.hw_manager.get_submission_data(submitter)["ta"]["uni"]
            except KeyError:
                logger.error("Could not find TA for thread %d", thread_id)
                return "Could not find TA for this submission"

        ta_id = self.uni_to_ed_id_map[ta_uni]
        ta_name = self.ed_id_to_ed_user[ta_id]["name"]

        logger.info("Assigned thread %d to %s", thread_id, ta_name)

        return f'<mention id="{ta_id}">{ta_name}</mention>'

    def _get_uni_from_post(self, content: str):
        """
        Extracts the UNI from a post.

        Args:
            content (str): The content of the post.

        Returns:
            str: The extracted UNI.
        """
        for line in content.lower().splitlines():
            if "uni:" in line:
                return line.split("uni:")[1].strip()
        return None


class EdGradesPostModule(CommandModule):
    """
    A command module to post grades on Ed.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the post grades command.
    """

    def __init__(self):
        super().__init__("ed-grades-post")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("hw", type=str, help="homework to grade")

    def run(self, parsed: Namespace):
        """
        Runs the post grades command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        stats = hw_manager.get_grades().stats(non_zero=True)

        now = datetime.now(NYZ_TZ).replace(hour=23, minute=55, second=0, microsecond=0)
        regrade_deadline = (now + timedelta(days=3)).strftime("%A, %B %d at %I:%M %p")

        env = Environment(
            loader=FileSystemLoader(PYGRADER_ROOT), autoescape=select_autoescape()
        )

        template = env.get_template(f"templates/{parsed.hw}-grades-post.xml.j2")
        content = template.render(
            hw_name=parsed.hw,
            stats=stats,
            regrade_deadline=regrade_deadline,
        ).replace("\n", "")

        requests.post(
            f"https://us.edstem.org/api/courses/{ED_COURSE_ID}/threads",
            headers=ED_HEADERS,
            timeout=10,
            json={
                "thread": {
                    "type": "post",
                    "title": f"{hw_manager.hw_name.upper()} Grades Released",
                    "category": "Announcements",
                    "subcategory": "",
                    "subsubcategory": "",
                    "content": content,
                    "is_pinned": True,
                    "is_private": True,
                    "is_anonymous": False,
                    "is_megathread": False,
                    "anonymous_comments": False,
                }
            },
        )
