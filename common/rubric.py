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
        code: The code of this item (e.g. B1)
        subitems: List containing (pts, desc) for each subitem (e.g. B1.1, B1.2)
        tester: Callback function to grade this item.
    """

    code: str
    deduct_from: float
    subitems: list[tuple[float, str]]
    depends_on: list[RubricItem]

    def get_test(self, hw_tester: HWTester) -> callable:
        def test_wrapper():
            test = getattr(hw_tester, "grade_" + self.code, hw_tester.default_grader)
            output = test()

            hw_tester.ran_rubric_tests.add(test)
            hw_tester.ran_rubric_item_codes.add(self.code)

            return output

        return test_wrapper

    def has_test_ran(self, hw_tester: HWTester) -> bool:
        return self.code in hw_tester.ran_rubric_item_codes


class Rubric:
    def __init__(self, rubric_file: str):
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

    def _create_rubric_item(self, item_dict: dict):
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

    def _create_dependancies_list(self, depends_on_codes: list[str]):
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
        return self._rubric.keys()

    def values(self):
        return self._rubric.values()

    def items(self):
        return self._rubric.items()

    def __getitem__(self, table_k) -> dict[str, RubricItem]:
        """Wrapper around self._rubric for convenience"""
        return self._rubric[table_k]
