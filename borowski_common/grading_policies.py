"""borowski_common/grading_policies.py: Custom grading policies"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from math import ceil
from typing import Any

from borowski_common.constants import NYZ_TZ
from borowski_common.late_days import LateDays
from common import printing as p
from common.grading_policies import GradingPolicy

SECONDS_IN_24_HOURS = 86_400
OK = 0
TOO_LATE = 1
NO_LATE_DAYS = 2
GOOD_JOB_PHRASES = ["Good job", "Great work", "Nice job", "Well done", "Awesome"]


class GoodJobPolicy(GradingPolicy):
    """
    A grading policy that adds a "Good Job" comment if the total points are high.

    Methods:
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Adds a "Good Job" comment and the TA's name to the comments if the total points are high.
    """

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data: Any
    ) -> tuple[float, list[str]]:
        """
        Adds a "Good Job" comment and the TA's name to the comments if the total points are high.

        Args:
            total_pts (float): The total points awarded.
            all_comments (list[str]): The list of comments.
            policy_data (Any): Additional data for the policy, including TA and student names.

        Returns:
            tuple[float, list[str]]: The updated total points and comments.
        """
        new_comments = [*all_comments]

        if total_pts >= 93:
            new_comment = random.choice(GOOD_JOB_PHRASES)
            if "student_names" in policy_data:
                first_names = [
                    name.split(" ")[0] for name in policy_data["student_names"]
                ]
                new_comment += (
                    f", {self._list_of_items_to_grammatical_text(first_names)}"
                )
            new_comments.append(f"{new_comment}!")

        if "ta_name" in policy_data:
            ta_name = policy_data["ta_name"]
            new_comments.append(f"Graded by {ta_name}")

        return total_pts, new_comments

    def _list_of_items_to_grammatical_text(self, items):
        """
        Converts a list of items to a grammatical text.

        Args:
            items (list): The list of items.

        Returns:
            str: The grammatical text.
        """
        if not items:
            return ""
        ln = len(items)
        if ln == 1:
            return items[0]
        if ln == 2:
            return " and ".join(items)
        return f"{', '.join(items[:-1])}, and {items[-1]}"


class PlagiarismPolicy(GradingPolicy):
    """
    A grading policy that sets the total points to zero and adds a plagiarism comment if plagiarism is detected.

    Methods:
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Sets the total points to zero and adds a plagiarism comment if plagiarism is detected.
    """

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data: Any
    ) -> tuple[float, list[str]]:
        """
        Sets the total points to zero and adds a plagiarism comment if plagiarism is detected.

        Args:
            total_pts (float): The total points awarded.
            all_comments (list[str]): The list of comments.
            policy_data (Any): Additional data for the policy, including plagiarism matches.

        Returns:
            tuple[float, list[str]]: The updated total points and comments.
        """
        if policy_data:
            total_pts = 0
            matches = ", ".join(policy_data.values())
            all_comments = [
                f"Your submission has been flagged for plagiarism. If you wish to escalate the matter to the deans, please make a private post on Ed. Otherwise, no further action is required. You may view your report(s) here: {matches}",
                *all_comments,
            ]
        return total_pts, all_comments


class LateDaysPolicy(GradingPolicy):
    """
    A grading policy that handles late submissions based on allowed late days.

    Methods:
        get_late_status(deadline_str: str, submission_str: str, late_days: LateDays, late_days_allowed: int = 2):
            Determines the late status of a submission.
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Adjusts the total points and comments based on the late status.
    """

    @staticmethod
    def get_late_status(
        deadline_str: str,
        submission_str: str,
        late_days: LateDays,
        late_days_allowed: int = 2,
    ):
        """
        Determines the late status of a submission.

        Args:
            deadline_str (str): The deadline as a string.
            submission_str (str): The submission time as a string.
            late_days (LateDays): The LateDays instance to check available late days.
            late_days_allowed (int): The number of allowed late days. Defaults to 2.

        Returns:
            int: The late status (OK, TOO_LATE, or NO_LATE_DAYS).
        """
        seconds_late = int(_get_seconds_late(deadline_str, submission_str))
        if seconds_late <= 0:
            return OK

        days_late = ceil(seconds_late / SECONDS_IN_24_HOURS)
        if days_late > late_days_allowed:
            p.print_red("[ SUBMITTED PAST HARD DEADLINE ]")
            late_status = TOO_LATE
        elif not late_days.has_late_days(days_late):
            p.print_red("[ SUBMITTER HAS NO LATE DAYS ]")
            late_status = NO_LATE_DAYS
        else:
            late_days.update_late_days(days_late)
            late_status = OK

        return late_status

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data: Any
    ) -> tuple[float, list[str]]:
        """
        Adjusts the total points and comments based on the late status.

        Args:
            total_pts (float): The total points awarded.
            all_comments (list[str]): The list of comments.
            policy_data (Any): The late status.

        Returns:
            tuple[float, list[str]]: The updated total points and comments.
        """
        if policy_data != OK:
            all_comments = [self._get_late_comment(policy_data)]
            total_pts = 0

        return total_pts, all_comments

    def _get_late_comment(self, late_status: int) -> str:
        """
        Returns a comment based on the late status.

        Args:
            late_status (int): The late status.

        Returns:
            str: The comment.
        """
        if late_status == TOO_LATE:
            return "Submitted past hard deadline"
        if late_status == NO_LATE_DAYS:
            return "Not enough late days"
        raise Exception("Late day error: this really shouldn't happen.")


class EarlyAndLatePolicy(GradingPolicy):
    """
    A grading policy that handles early and late submissions.

    Methods:
        get_late_status(deadline_str: str, submission_str: str, late_days_allowed: int = 2):
            Determines the late status of a submission.
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Adjusts the total points and comments based on the late status.
    """

    @staticmethod
    def get_late_status(
        deadline_str: str, submission_str: str, late_days_allowed: int = 2
    ):
        """
        Determines the late status of a submission.

        Args:
            deadline_str (str): The deadline as a string.
            submission_str (str): The submission time as a string.
            late_days_allowed (int): The number of allowed late days. Defaults to 2.

        Returns:
            int: The late status (positive for early, negative for late, None for too late).
        """
        time_after_deadline = _get_seconds_late(deadline_str, submission_str)
        time_before_deadline = -time_after_deadline

        if time_before_deadline >= SECONDS_IN_24_HOURS:
            return 2

        if 0 <= time_before_deadline < SECONDS_IN_24_HOURS:
            return 0

        days_late = ceil(time_after_deadline / SECONDS_IN_24_HOURS)
        return -days_late if days_late <= late_days_allowed else None

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data: Any
    ) -> tuple[float, list[str]]:
        """
        Adjusts the total points and comments based on the late status.

        Args:
            total_pts (float): The total points awarded.
            all_comments (list[str]): The list of comments.
            policy_data (Any): The late status.

        Returns:
            tuple[float, list[str]]: The updated total points and comments.
        """
        if policy_data is None:
            total_pts = 0
            all_comments = [self._get_deadline_comment(policy_data)]
        elif policy_data != 0:
            total_pts += policy_data
            all_comments = [self._get_deadline_comment(policy_data), *all_comments]

        return total_pts, all_comments

    def _get_deadline_comment(self, late_status: int) -> str:
        """
        Returns a comment based on the late status.

        Args:
            late_status (int): The late status.

        Returns:
            str: The comment.
        """
        if late_status is None:
            return "Submitted past hard deadline"
        if late_status == 2:
            return "(+2) Early deadline"
        if late_status == 0:
            return "Standard deadline"
        if late_status == -1:
            return "(-1) Late deadline"
        if late_status == -2:
            return "(-2) Hard deadline"

        return f"({late_status}) Custom deadline"


class CustomDeductionsPolicy(GradingPolicy):
    """
    A grading policy that applies custom deductions to the total points.

    Methods:
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Applies custom deductions to the total points and adds comments.
    """

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data: Any
    ) -> tuple[float, list[str]]:
        """
        Applies custom deductions to the total points and adds comments.

        Args:
            total_pts (float): The total points awarded.
            all_comments (list[str]): The list of comments.
            policy_data (Any): A list of dictionaries containing deductions and comments.

        Returns:
            tuple[float, list[str]]: The updated total points and comments.
        """
        comments = []

        for data in policy_data:
            deduction = data["deduction"]
            comment = data["comment"]

            total_pts += deduction
            comments.append(f"({deduction}) {comment}")

        return max(0, total_pts), [*comments, *all_comments]


def _get_seconds_late(deadline_str: str, submission_str: str):
    """
    Calculates the number of seconds a submission is late.

    Args:
        deadline_str (str): The deadline as a string.
        submission_str (str): The submission time as a string.

    Returns:
        float: The number of seconds the submission is late.
    """
    submission = datetime.fromisoformat(submission_str).astimezone(NYZ_TZ)
    deadline = (datetime.fromisoformat(deadline_str) + timedelta(minutes=5)).astimezone(
        NYZ_TZ
    )

    seconds_late = (submission - deadline).total_seconds()
    if deadline.dst() != submission.dst():
        seconds_late -= 3600

    return seconds_late
