"""borowski_common/late_days.py: Late Days logic"""

from __future__ import annotations

import json

from filelock import FileLock

from borowski_common.canvas import CanvasGrades
from borowski_common.constants import (
    LATE_DAYS_ASSIGNMENT_ID,
    LATE_DAYS_FILE,
    TOTAL_LATE_DAYS,
)


class LateDays(CanvasGrades):
    """
    A class to manage late days for homework assignments.

    Attributes:
        late_days_file (str): The path to the file storing late days information.
        lock (FileLock): A file lock to ensure thread-safe access to the late days file.
        class_late_days (dict): A dictionary storing late days information for the class.
        hw_name (str): The name of the homework assignment.
        submitters (list[str]): A list of submitters' identifiers.
    """

    def __init__(self, hw_name: str, submitters: str | list[str] | None = None):
        """
        Initializes the LateDays class with the homework name and submitters.

        Args:
            hw_name (str): The name of the homework assignment.
            submitters (str | list[str] | None): The submitters' identifiers. Defaults to None.
        """
        self.late_days_file = LATE_DAYS_FILE

        self.lock = FileLock(self.late_days_file + ".lock", timeout=3)

        self.class_late_days = self._load_class()
        self.hw_name = hw_name

        if not submitters:
            submitters = []
        self.submitters = [submitters] if isinstance(submitters, str) else submitters

    def _load_class(self) -> dict:
        """
        Loads the class late days information from the file.

        Returns:
            dict: A dictionary containing the class late days information.
        """
        try:
            with self.lock:
                with open(self.late_days_file, "r", encoding="utf-8") as f:
                    class_late_days = dict(json.load(f))
        except FileNotFoundError:
            class_late_days = {}
        return class_late_days

    def has_late_days(self, days_late: int) -> bool:
        """
        Checks if all submitters have enough late days.

        Args:
            days_late (int): The number of late days to check.

        Returns:
            bool: True if all submitters have enough late days, False otherwise.

        Raises:
            Exception: If no submitter is provided.
        """
        if not self.submitters:
            raise Exception("No submitter provided")

        return all(
            self._student_has_late_days(uni, days_late) for uni in self.submitters
        )

    def _student_has_late_days(self, uni: str, days_late: int) -> bool:
        """
        Checks if a student has enough late days.

        Args:
            uni (str): The student's identifier.
            days_late (int): The number of late days to check.

        Returns:
            bool: True if the student has enough late days, False otherwise.
        """
        student_late_days = self._try_to_get_student(uni)
        late_sum = sum(student_late_days.values())

        if self.hw_name not in student_late_days.keys():
            late_sum += days_late

        return late_sum <= TOTAL_LATE_DAYS

    def update_late_days(self, days_late: int):
        """
        Updates the late days for all submitters.

        Args:
            days_late (int): The number of late days to update.

        Raises:
            Exception: If no submitter is provided.
        """
        if not self.submitters:
            raise Exception("No submitter provided")

        for uni in self.submitters:
            student_late_days = self._try_to_get_student(uni)
            if self.hw_name not in student_late_days.keys():
                student_late_days[self.hw_name] = days_late

        self._synchronize()

    def _try_to_get_student(self, uni: str):
        """
        Retrieves the late days information for a student, initializing if not present.

        Args:
            uni (str): The student's identifier.

        Returns:
            dict: The student's late days information.
        """
        if uni not in self.class_late_days.keys():
            self.class_late_days[uni] = {}
        return self.class_late_days[uni]

    def _synchronize(self):
        """
        Synchronizes the class late days information to the file.
        """
        with self.lock:
            with open(self.late_days_file, "w", encoding="utf-8") as f:
                json.dump(self.class_late_days, f, indent=4)

    def dump(self, _):
        """
        Prints the late days information for the class or specified submitters.
        """
        hw_numbers = sorted(
            set(
                hw
                for days_dict in self.class_late_days.values()
                for hw in days_dict.keys()
            )
        )

        late_days_dict = self.class_late_days
        if self.submitters:
            late_days_dict = {
                uni: late_days_dict.get(uni, {}) for uni in self.submitters
            }

        print("UNI\t{}\ttotal\n".format("\t".join(hw_numbers)))
        for uni, days_dict in late_days_dict.items():
            days_list = [days_dict.get(hw, 0) for hw in hw_numbers]
            days_list.append(sum(grade for grade in days_list))
            days_list_str = map(lambda days: str(days) if days != 0 else "", days_list)
            print("{}\t{}".format(uni, "\t".join(days_list_str)))

    def get_canvas_assignment_id(self) -> str:
        """
        Retrieves the Canvas assignment ID for late days.

        Returns:
            str: The Canvas assignment ID.
        """
        return LATE_DAYS_ASSIGNMENT_ID

    def get_canvas_grades_dict(self) -> dict:
        """
        Retrieves the Canvas grades dictionary for late days.

        Returns:
            dict: A dictionary containing the Canvas grades for late days.
        """
        submitters = self.class_late_days if not self.submitters else self.submitters
        return {
            submitter: {
                "posted_grade": sum(self.class_late_days.get(submitter, {}).values())
            }
            for submitter in submitters
        }
