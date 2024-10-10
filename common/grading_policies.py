"""common/grading_policies.py: Logic for grading policies"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.hw_base import BaseHWTester, HWTester


class GradingPolicy(ABC):
    """Interface for Grading Policies"""

    @abstractmethod
    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data
    ) -> tuple[float, list[str]]:
        pass


class LatePercentagePenaltyPolicy(GradingPolicy):
    """Apply a percentage penalty if the submission was late"""

    def __init__(self, percentage_penalty: float = 0.2):
        self.percentage_penalty = percentage_penalty

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data
    ) -> tuple[float, list[str]]:
        if policy_data:
            total_pts = round(total_pts * (1 - self.percentage_penalty), 2)
            all_comments.insert(0, "(LATE)")

        return total_pts, all_comments


class NullGradingPolicy(GradingPolicy):
    """Policy that does nothing"""

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], _
    ) -> tuple[float, list[str]]:
        return total_pts, all_comments
