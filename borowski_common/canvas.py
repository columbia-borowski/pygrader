"""borowski_common/canvas.py: tools that interact with canvas"""

from __future__ import annotations

from abc import ABC, abstractmethod

from canvasapi import Canvas as CanvasAPI

from borowski_common.constants import API_KEY, API_URL, COURSE_ID
from common import printing as p


class CanvasGrades(ABC):
    """
    Interface that allows uploading grades to Canvas.

    Methods:
        get_canvas_assignment_id() -> str:
            Returns the Canvas assignment ID.
        get_canvas_grades_dict() -> dict[str, dict[str, float | str]]:
            Returns a dictionary of grades formatted for Canvas.
    """

    @abstractmethod
    def get_canvas_assignment_id(self) -> str:
        """
        Returns the Canvas assignment ID.

        Returns:
            str: The Canvas assignment ID.
        """

    @abstractmethod
    def get_canvas_grades_dict(self) -> dict[str, dict[str, float | str]]:
        """
        Returns a dictionary of grades formatted for Canvas.

        Returns:
            dict[str, dict[str, float | str]]: A dictionary where keys are student identifiers and values are dictionaries
            containing the grades and comments.
        """


class Canvas:
    """
    Wrapper for canvasapi to interact with Canvas LMS.

    Attributes:
        canvas (CanvasAPI): An instance of the Canvas API.
        _course (Course | None): The course object.
        tas (dict): A dictionary mapping TA login IDs to TA objects.
        uni_to_user_id_map (dict): A dictionary mapping UNI to user IDs.

    Methods:
        get_course() -> Course:
            Retrieves the course object.
        get_tas() -> dict[str, dict]:
            Retrieves a dictionary of TAs.
        upload_grades(canvas_grades: CanvasGrades, uni_keys: bool = True) -> int:
            Uploads grades to Canvas.
        upload_raw_grades(assignment_id: str, grade_data: dict) -> int:
            Uploads raw grades to Canvas.
        _change_uni_keys_to_user_id(grade_data: dict) -> dict:
            Converts UNI keys to user ID keys in the grade data.
    """

    def __init__(self):
        """
        Initializes the Canvas object.
        """
        self.canvas = CanvasAPI(API_URL, API_KEY)
        self._course = None

        self.tas = {}
        self.uni_to_user_id_map = {}

    def get_course(self):
        """
        Retrieves the course object.

        Returns:
            Course: The course object.
        """
        if not self._course:
            self._course = self.canvas.get_course(COURSE_ID)
        return self._course

    def get_tas(self) -> dict[str, dict]:
        """
        Retrieves a dictionary of TAs.

        Returns:
            dict[str, dict]: A dictionary mapping TA login IDs to TA objects.
        """
        if not self.tas:
            self.tas = {
                ta.login_id: ta
                for ta in self.get_course().get_users(enrollment_type=["ta"])
            }
        return self.tas

    def upload_grades(self, canvas_grades: CanvasGrades, uni_keys: bool = True) -> int:
        """
        Uploads grades to Canvas.

        Args:
            canvas_grades (CanvasGrades): An instance of CanvasGrades containing the grades to upload.
            uni_keys (bool): Whether to use UNI keys. Defaults to True.

        Returns:
            int: The number of grades uploaded.
        """
        grade_data = canvas_grades.get_canvas_grades_dict()
        if uni_keys:
            grade_data = self._change_uni_keys_to_user_id(grade_data)

        return self.upload_raw_grades(
            canvas_grades.get_canvas_assignment_id(), grade_data
        )

    def upload_raw_grades(self, assignment_id: str, grade_data: dict) -> int:
        """
        Uploads raw grades to Canvas.

        Args:
            assignment_id (str): The Canvas assignment ID.
            grade_data (dict): A dictionary containing the grades to upload.

        Returns:
            int: The number of grades uploaded.
        """
        assignment = self.get_course().get_assignment(assignment_id)
        assignment.submissions_bulk_update(grade_data=grade_data)

        return len(grade_data)

    def _change_uni_keys_to_user_id(self, grade_data: dict) -> dict:
        """
        Converts UNI keys to user ID keys in the grade data.

        Args:
            grade_data (dict): A dictionary containing the grades with UNI keys.

        Returns:
            dict: A dictionary containing the grades with user ID keys.
        """
        if not self.uni_to_user_id_map:
            self.uni_to_user_id_map = {
                user.login_id: str(user.id) for user in self.get_course().get_users()
            }

        new_data = {}
        for uni, grade in grade_data.items():
            try:
                new_data[self.uni_to_user_id_map[uni]] = grade
            except Exception:
                p.print_red(f"[ Can not get user for UNI: {uni} ]")

        return new_data
