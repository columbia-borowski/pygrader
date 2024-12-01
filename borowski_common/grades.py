"""borowski_common/grades.py: grades for Borowski courses"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from borowski_common import utils as u
from borowski_common.canvas import CanvasGrades
from common.grades import Grades
from common.grading_policies import GradingPolicy
from common.rubric import Rubric


class BorowskiGrades(Grades, CanvasGrades):
    """
    Represents the grades for the current Borowski homework.

    Attributes:
        canvas_assignment_id (str): The Canvas assignment ID.
    """

    def __init__(
        self,
        grades_file: str,
        rubric: Rubric,
        name: str,
        grading_policies: Iterable[GradingPolicy],
        canvas_assignment_id: str,
        submissions: dict[str, Any],
    ):
        """
        Initializes the BorowskiGrades object.

        Args:
            grades_file (str): The path to the JSON file with grades.
            rubric (Rubric): The rubric object for a given homework.
            name (str): The name of the submitter (uni/team).
            grading_policies (Iterable[GradingPolicy]): The grading policies to apply.
            canvas_assignment_id (str): The Canvas assignment ID.
            submissions (dict[str, Any]): The submissions data.
        """
        super().__init__(grades_file, rubric, name, grading_policies)
        self.canvas_assignment_id = canvas_assignment_id

        for submission_id in set(self._grades.keys()).difference(
            set(submissions.keys())
        ):
            self._grades.pop(submission_id, None)
        self.synchronize()

    def get_canvas_assignment_id(self) -> str:
        """
        Returns the Canvas assignment ID.

        Returns:
            str: The Canvas assignment ID.
        """
        return self.canvas_assignment_id

    def get_canvas_grades_dict(self) -> dict[str, dict[str, float | str]]:
        """
        Returns the grades dictionary formatted for Canvas.

        Returns:
            dict[str, dict[str, float | str]]: A dictionary where keys are submitter IDs and values are dictionaries
            containing the posted grade and text comment.
        """
        grades_dict = {}

        submitters = self._grades if not self.submitter else [self.submitter]
        for submitter in submitters:
            _, total_pts, all_comments = self._get_submission_grades(submitter, "ALL")
            concatted_comments = "<br />".join(
                (u.html_escape(comment) for comment in all_comments)
            )
            grades_dict[submitter] = {
                "posted_grade": total_pts,
                "text_comment": concatted_comments,
            }

        return grades_dict
