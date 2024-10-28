"""common/rubric.py: classes to create a rubric from json file"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.hw_base import HWTester


@dataclass
class RubricItem:
    """Representation of a rubric item.

    Attributes:
        code (str): The code of this item (e.g. B1).
        deduct_from (float): Points to deduct from the total score.
        subitems (list[tuple[float, str]]): List containing (pts, desc) for each subitem (e.g. B1.1, B1.2).
        depends_on (list[RubricItem]): List of other rubric items this item depends on.
    """

    code: str
    deduct_from: float
    subitems: list[tuple[float, str]]
    depends_on: list[RubricItem]

    def get_test(self, hw_tester: HWTester) -> callable:
        """
        Retrieves the test function for this rubric item.

        Args:
            hw_tester (HWTester): The homework tester instance.

        Returns:
            callable: The test function for this rubric item.
        """

        def test_wrapper():
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
        return RubricItem(
            item_dict["name"],
            item_dict.get("deducting_from", None),
            list(
                zip(
                    item_dict["points_per_subitem"],
                    item_dict["desc_per_subitem"],
                )
            ),
            self._create_dependancies_list(item_dict.get("depends_on", [])),
        )

    def _create_dependancies_list(
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
