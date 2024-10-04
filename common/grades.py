"""common/grades.py: Logic for storing points/comments while grading"""

from __future__ import annotations

import json
import os
import statistics
import sys
from typing import TYPE_CHECKING, TypeAlias

from common import utils
from common.grading_policies import GradingPolicy
from common.rubric import Rubric

if TYPE_CHECKING:
    from common.hw_base import HWTester

# Probably better to just look at a grades.json
GradesDictType: TypeAlias = dict[str, dict[str, list[dict[str, dict[str, bool | str]]]]]


class Grades:
    """Represents the grades for the current hw

    Attributes:
        grades_file: the JSON file with grades
        rubric: the rubric object for a given hw
        submitter: The uni/team we're currently grading
        _grades: Maps submitter -> (is_late, (item -> (pts, comments)))
        grading_policy: Class which control grading adjustments for submissions
    """

    def __init__(
        self,
        grades_file: str,
        rubric: Rubric,
        name: str,
        grading_policy: GradingPolicy,
    ):
        self.grades_file = os.path.abspath(grades_file)
        self.rubric = rubric
        self.submitter = name
        self._grades = self._load_grades()
        self.grading_policy = grading_policy

        if self.submitter and self.submitter not in self._grades:
            # This is the first time grading the submission
            self._add_submission_entry()
        self.synchronize()

    def _load_grades(self) -> GradesDictType:
        """Returns a dictionary representation of the TA's grades thus far"""
        if not utils.file_exists(self.grades_file):
            # The TA hasn't started grading this hw yet
            return {}

        with open(self.grades_file, "r", encoding="utf-8") as f:
            grades = json.load(f)

        # Let's traverse over the rubric and make sure to adjust the dict if
        # anything has changed.
        defined_subitems = self._get_defined_rubric_subitems()
        for grade_info in grades.values():
            scores = grade_info["scores"]
            present_subitems = set(scores.keys())

            for code in defined_subitems.symmetric_difference(present_subitems):
                if code not in defined_subitems:
                    scores.pop(code)
                    continue

                assert code not in present_subitems
                scores[code] = {"award": None, "comments": None}

        return grades

    def _get_defined_rubric_subitems(self) -> set[str]:
        subitems = set()
        for table_code in sorted(self.rubric.keys()):
            for item_code in sorted(self.rubric[table_code].keys()):
                item = self.rubric[table_code][item_code]
                for subitem_code in range(1, len(item.subitems) + 1):
                    code = f"{item_code}.{subitem_code}"
                    if code in subitems:
                        sys.exit(f"Rubric subitem '{code}' defined twice!")

                    subitems.add(code)

        return subitems

    def _add_submission_entry(self):
        """Create a new entry for student/team with null fields"""
        self._grades[self.submitter] = {}
        rubric_scores = {}
        for table_code in sorted(self.rubric.keys()):
            for item_code in sorted(self.rubric[table_code].keys()):
                item = self.rubric[table_code][item_code]
                for subitem_code in range(1, len(item.subitems) + 1):
                    code = f"{item_code}.{subitem_code}"
                    # None means that it hasn't been graded yet
                    rubric_scores[code] = {"award": None, "comments": None}
        self._grades[self.submitter]["scores"] = rubric_scores

    def __getitem__(self, rubric_subitem) -> dict[str, bool | str]:
        """Wrapper around self._grades for convenience"""
        return self._grades[self.submitter]["scores"][rubric_subitem]

    def synchronize(self):
        """Write out the grades dictionary to the filesystem"""
        with open(self.grades_file, "w", encoding="utf-8") as f:
            # Indent for pretty printing :^)
            json.dump(self._grades, f, indent=4, sort_keys=True)
            os.fsync(f.fileno())

    def is_graded(self, code: str, name: str | None = None) -> bool:
        """Checks if a subitem has been graded yet"""
        if not name:
            name = self.submitter

        return self._grades[name]["scores"][code]["award"] is not None

    def enforce_grading_policy(self, hw_tester: HWTester):
        if "grading_policy" not in self._grades[self.submitter]:
            self._grades[self.submitter][
                "grading_policy"
            ] = self.grading_policy.enforce_policy(hw_tester)
            self.synchronize()

    def dump(self, rubric_code: str):
        student_list = self._grades if not self.submitter else [self.submitter]
        for name in student_list:
            _, _, s = self._get_submission_grades(name, rubric_code)
            print(s)

    def status(self, rubric_code: str) -> tuple[bool, int]:
        student_list = self._grades if not self.submitter else [self.submitter]
        all_graded = True
        graded_count = 0
        for name in student_list:
            is_graded, _, _ = self._get_submission_grades(name, rubric_code)
            if is_graded:
                graded_count += 1
            elif all_graded:
                all_graded = False

        return all_graded, graded_count

    def stats(self, rubric_code: str = "ALL", non_zero: bool = True):
        if self.submitter:
            raise ValueError("Cannot return stats for a single submission")

        grades_list = []
        for uni in self._grades:
            is_graded, pts, _ = self._get_submission_grades(uni, rubric_code)
            if is_graded and (not non_zero or pts > 0):
                grades_list.append(pts)

        return {
            "is_non_zero": non_zero,
            "count": len(grades_list),
            "avg": statistics.mean(grades_list),
            "median": statistics.median(grades_list),
            "std_dev": statistics.stdev(grades_list),
        }

    def _get_submission_grades(
        self, name: str | None = None, rubric_code: str | None = None
    ) -> tuple[bool, float, str]:
        """Returns (uni, pts, comments) in tsv format

        Returns:
            A tuple with two members: a bool indicating whether or not this
            submission was even graded yet and a float representing the total
            score of this submission. If it hasn't been graded yet, this float
            should be zero.

            NOTE: We only apply the late penalty if the TA requested ALL grades
            (such that rubric_code = 'ALL'.
        """
        if not name:
            name = self.submitter

        if not rubric_code:
            rubric_code = "ALL"

        total_pts = 0
        all_comments = []
        submission_scores = self._grades[name]["scores"]

        for _, rubric_item_mappings in self.rubric.items():
            for item_code, rubric_item in rubric_item_mappings.items():
                if rubric_code != "ALL" and not item_code.startswith(rubric_code):
                    continue

                if not all(
                    self.is_graded(f"{item_code}.{si}", name)
                    for si, _ in enumerate(rubric_item.subitems, 1)
                ):
                    return False, total_pts, f"{name}\tn/a\tn/a"

                if rubric_item.deduct_from:
                    # If a deductive item, we increment total_pts upfront
                    # and floor it at its current value (s.t. our subitems
                    # can't deduct us to below where we started).
                    floor_pts = total_pts
                    total_pts += rubric_item.deduct_from

                for i, (pts, _) in enumerate(rubric_item.subitems, 1):
                    code = f"{item_code}.{i}"
                    applied = submission_scores[code]["award"]
                    raw_pts = pts if applied else 0
                    total_pts += raw_pts
                    ta_comments = submission_scores[code]["comments"]
                    item_comments = ""

                    if (
                        (applied and pts < 0) or (not applied and pts > 0)
                    ) or ta_comments:
                        # 1. You applied a deductive rubric item
                        # 2. They lost an additive rubric item
                        # 3. You left a comment on a rubric item

                        # If a section only has one item, print A2 instead of
                        # A2.1 since that's how we stylize our rubrics.
                        pretty_code_name = (
                            item_code if len(rubric_item.subitems) == 1 else code
                        )
                        pretty_pts = pts if pts > 0 else abs(pts)
                        if (pts >= 0) == applied and ta_comments:
                            item_comments += f"({pretty_code_name})"
                        else:
                            item_comments += f"({pretty_code_name}: -{pretty_pts})"

                    if ta_comments:
                        item_comments += f" {ta_comments}"

                    if item_comments:
                        all_comments.append(item_comments)
                if rubric_item.deduct_from:
                    # Enforce the bounds on our deductive item (i.e. clamping
                    # total_pts to range [floor_pts, floor_pts + deduct_from]).
                    ceiled = min(floor_pts + rubric_item.deduct_from, total_pts)
                    total_pts = max(floor_pts, ceiled)

        # We assume that if the TA wants ALL submission grades, that they'll
        # also want to apply grading policies (they're about to finalize
        # grades). Otherwise, we just just dump raw grades for reference.
        if rubric_code == "ALL":
            total_pts, all_comments = self.grading_policy.get_points_and_comments(
                total_pts, all_comments, self._grades[name]["grading_policy"]
            )

        concatted_comments = "; ".join(all_comments)

        total_pts = max(total_pts, 0)

        return True, total_pts, f"{name}\t{total_pts}\t{concatted_comments}"
