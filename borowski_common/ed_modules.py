"""borowski_common/command_modules.py: Custom command modules"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta

import requests
import websockets
from jinja2 import Environment, FileSystemLoader, select_autoescape

from borowski_common.constants import (
    ED_COURSE_ID,
    ED_HEADERS,
    NYZ_TZ,
    PYGRADER_ROOT,
)
from common.assignments import get_assignment_manager
from common.command_modules import CommandModule

logger = logging.getLogger(__name__)


class RegradeRequestModule(CommandModule):
    """
    A command module to handle regrade requests on Ed.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the regrade request command.
        _connect_to_websocket(hw: str, round_robin: bool, index: int, category: str): Connects to the Ed websocket.
        _get_user_info(): Retrieves user information from Ed.
    """

    def __init__(self):
        super().__init__("regrades")

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
                    "wss://us.edstem.org/api/stream", extra_headers=ED_HEADERS
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
                                ta_uni = self.hw_manager.get_ta_for_regrade_request(
                                    self.ed_id_to_ed_user[poster_id]["sourced_id"],
                                    response["data"]["thread"]["document"],
                                )

                                if ta_uni:
                                    ta_id = self.uni_to_ed_id_map[ta_uni]
                                    ta_name = self.ed_id_to_ed_user[ta_id]["name"]

                                    logger.info(
                                        "Assigned thread %d to %s", thread_id, ta_name
                                    )

                                    comment_content = (
                                        f'<mention id="{ta_id}">{ta_name}</mention>'
                                    )
                                else:
                                    logger.error(
                                        "Could not find TA for thread %d", thread_id
                                    )

                                    comment_content = (
                                        "Could not find TA for this submission"
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


class GradesPostModule(CommandModule):
    """
    A command module to post grades on Ed.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the post grades command.
    """

    def __init__(self):
        super().__init__("grades-post")

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

        response = requests.post(
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
        response.raise_for_status()


class LecturePostsModule(CommandModule):
    """
    A command module to schedule lecture posts on Ed.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the post grades command.
    """

    def __init__(self):
        super().__init__("lecture-posts")
        self.weekday_map = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4}

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "-w",
            "--weekdays",
            required=True,
            dest="weekdays",
            type=str,
            nargs="+",
            choices=self.weekday_map.keys(),
            help="weekdays to post lectures (e.g. M, T, W, R, F)",
        )
        parser.add_argument(
            "-t",
            "--time",
            required=True,
            dest="time",
            type=str,
            help="time to post lectures (e.g. 09:00 AM)",
        )
        parser.add_argument(
            "-s",
            "--start-date",
            required=True,
            dest="start_date",
            type=str,
            help="start date for lecture posts (e.g. 2021-09-01)",
        )
        parser.add_argument(
            "-e",
            "--end-date",
            required=True,
            dest="end_date",
            type=str,
            help="end date for lecture posts (e.g. 2021-12-31)",
        )

    def run(self, parsed: Namespace):
        """
        Runs the command to schedule lecture posts on Ed.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        start_date = datetime.strptime(parsed.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(parsed.end_date, "%Y-%m-%d")

        for date in self._get_dates(parsed.weekdays, start_date, end_date):
            date = NYZ_TZ.localize(
                datetime.strptime(
                    f"{date.strftime('%Y-%m-%d')} {parsed.time}", "%Y-%m-%d %I:%M %p"
                )
            )

            thread_response = requests.post(
                f"https://us.edstem.org/api/courses/{ED_COURSE_ID}/thread_drafts",
                headers=ED_HEADERS,
                json={
                    "thread_draft": {
                        "course_id": ED_COURSE_ID,
                        "type": "announcement",
                        "title": f"{date.strftime('%m/%d')} Lecture Questions Thread",
                        "content": "<document version=\"2.0\"><paragraph>Hello, this will be a place for you to ask questions during today's lecture!</paragraph><paragraph>The process is simple, have a question? Post it here and you'll get a reply from the TA who is currently sitting in on your lecture.</paragraph></document>",
                        "category": "Lectures",
                        "subcategory": "",
                        "subsubcategory": "",
                        "is_pinned": True,
                        "is_private": False,
                        "is_anonymous": False,
                        "is_megathread": True,
                        "anonymous_comments": False,
                    }
                },
                timeout=10,
            )
            thread_id = thread_response.json()["thread_draft"]["id"]

            requests.patch(
                f"https://us.edstem.org/api/thread_drafts/{thread_id}/schedule",
                params={
                    "send_emails": "1",
                    "scheduled_time": date.isoformat(timespec="milliseconds"),
                },
                headers=ED_HEADERS,
                timeout=10,
            )

    def _get_dates(self, chosen_days, start_date, end_date):
        chosen_weekdays = {self.weekday_map[day] for day in chosen_days}

        current_date = max(start_date, datetime.today())
        while current_date <= end_date:
            if current_date.weekday() in chosen_weekdays:
                yield current_date

            current_date += timedelta(days=1)
