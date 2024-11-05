"""common/rubric.py: classes to create a rubric from json file"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from common import printing as p

if TYPE_CHECKING:
    from common.grades import Grades
    from common.hw_base import HWTester


@dataclass
class RubricItem:
    """Representation of a rubric item.

    Attributes:
        code (str): The code of this item (e.g. B1).
        deduct_from (float): Points to deduct from the total score.
        subitems (list[tuple[float, str]]): List containing (pts, desc) for each subitem (e.g. B1.1, B1.2).
        depends_on (dict[str, list[RubricItem]]): Dictionary containing the dependencies for this item.
    """

    code: str
    deduct_from: float
    subitems: list[tuple[float, str]]
    depends_on: dict[str, list[RubricItem]]

    def get_test(self, hw_tester: HWTester, grades: Grades) -> Callable:
        """
        Retrieves the test function for this rubric item.

        Args:
            hw_tester (HWTester): The homework tester instance.
            grades (Grades): The grades instance.

        Returns:
            callable: The test function for this rubric item.
        """

        def test_wrapper():
            ungraded_dependencies = []
            for rubric_item in self.depends_on["is_graded"]:
                for i in range(1, len(rubric_item.subitems) + 1):
                    if not grades.is_graded(f"{rubric_item.code}.{i}"):
                        ungraded_dependencies.append(rubric_item)
                        break

            if ungraded_dependencies:
                codes = ", ".join(
                    rubric_item.code for rubric_item in ungraded_dependencies
                )
                p.print_yellow(
                    f"[ You shouldn't grade {self.code} because you haven't graded {codes}. Please be careful. ]"
                )
                return None

            test = getattr(hw_tester, "grade_" + self.code, hw_tester.default_grader)
            output = test()

            hw_tester.ran_rubric_tests.add(test)
            hw_tester.ran_rubric_item_codes.add(self.code)

            return output

        return test_wrapper

    def has_test_ran(self, hw_tester: HWTester) -> bool:
        """
        Checks if the test for this rubric item has already been run.

        Args:
            hw_tester (HWTester): The homework tester instance.

        Returns:
            bool: True if the test has been run, False otherwise.
        """
        return self.code in hw_tester.ran_rubric_item_codes


class Rubric:
    """Class to create a rubric from a JSON file."""

    def __init__(self, rubric_file: str):
        """
        Initializes the Rubric.

        Args:
            rubric_file (str): The path to the JSON file containing the rubric.
        """
        if not os.path.isfile(rubric_file):
            raise Exception("Rubric file not found.")

        with open(rubric_file, "r", encoding="utf-8") as f:
            rubric_json = json.load(f)

        self._rubric = {}
        for table_k, table_v in rubric_json.items():
            if table_k == "late_penalty":
                continue

            if table_k not in self._rubric:
                self._rubric[table_k] = {}

            for item in table_v:
                self._rubric[table_k][item] = self._create_rubric_item(table_v[item])

    def _create_rubric_item(self, item_dict: dict) -> RubricItem:
        """
        Creates a RubricItem from a dictionary.

        Args:
            item_dict (dict): The dictionary containing the rubric item data.

        Returns:
            RubricItem: The created RubricItem.
        """
        depends_on = item_dict.get("depends_on", {})
        return RubricItem(
            item_dict["name"],
            item_dict.get("deducting_from", None),
            list(
                zip(
                    item_dict["points_per_subitem"],
                    item_dict["desc_per_subitem"],
                )
            ),
            {
                "has_ran": self._create_dependencies_list(
                    depends_on.get("has_ran", [])
                ),
                "is_graded": self._create_dependencies_list(
                    depends_on.get("is_graded", [])
                ),
            },
        )

    def _create_dependencies_list(
        self, depends_on_codes: list[str]
    ) -> list[RubricItem]:
        """
        Creates a list of dependencies for a rubric item.

        Args:
            depends_on_codes (list[str]): The list of dependency codes.

        Returns:
            list[RubricItem]: The list of dependent RubricItems.
        """
        depends_on = []
        for key in depends_on_codes:
            if key == "ALL":
                for rubric_items in self._rubric.values():
                    for rubric_item in rubric_items.values():
                        depends_on.append(rubric_item)
            elif key.isalpha():
                if key not in self._rubric:
                    raise Exception(f"Rubric table {key} not found.")

                for rubric_item in self._rubric[key].values():
                    depends_on.append(rubric_item)
            else:
                table = key[0]
                if table not in self._rubric or key not in self._rubric[table]:
                    raise Exception(f"Rubric item {key} not found.")

                depends_on.append(self._rubric[table][key])

        return depends_on

    def keys(self):
        """
        Returns the keys of the rubric.

        Returns:
            dict_keys: The keys of the rubric.
        """
        return self._rubric.keys()

    def values(self):
        """
        Returns the values of the rubric.

        Returns:
            dict_values: The values of the rubric.
        """
        return self._rubric.values()

    def items(self):
        """
        Returns the items of the rubric.

        Returns:
            dict_items: The items of the rubric.
        """
        return self._rubric.items()

    def __getitem__(self, table_k) -> dict[str, RubricItem]:
        """
        Retrieves a table of rubric items by key.

        Args:
            table_k (str): The key of the table to retrieve.

        Returns:
            dict[str, RubricItem]: The table of rubric items.
        """
        return self._rubric[table_k]
