"""common/grading_policies.py: Logic for grading policies"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.hw_base import BaseHWTester, HWTester


class GradingPolicy(ABC):
    """Interface for Grading Policies"""

    @abstractmethod
    def enforce_policy(self, hw_tester: HWTester):
        pass

    @abstractmethod
    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data
    ) -> tuple[float, list[str]]:
        pass


class LatePercentagePenaltyPolicy(GradingPolicy):
    """Apply a percentage penalty if the submission was late"""

    def __init__(self, percentage_penalty: float = 0.2):
        self.percentage_penalty = percentage_penalty

    def enforce_policy(self, hw_tester: BaseHWTester):
        return hw_tester.check_late_submission()

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data
    ) -> tuple[float, list[str]]:
        if policy_data:
            total_pts = round(total_pts * (1 - self.percentage_penalty), 2)
            all_comments.insert(0, "(LATE)")

        return total_pts, all_comments


class NullGradingPolicy(GradingPolicy):
    """Policy that does nothing"""

    def enforce_policy(self, _):
        return None

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], _
    ) -> tuple[float, list[str]]:
        return total_pts, all_comments


class CompositeGradingPolicy(GradingPolicy):
    """Composite that can hold and enforce multiple Grading Policies"""

    def __init__(self, grading_policies: list[GradingPolicy]):
        self.grading_policies = grading_policies

    def enforce_policy(self, hw_tester: HWTester):
        return {
            self._policy_key(grading_policy): grading_policy.enforce_policy(hw_tester)
            for grading_policy in self.grading_policies
        }

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data
    ) -> tuple[float, list[str]]:
        for grading_policy in self.grading_policies:
            if not (policy_key := self._policy_key(grading_policy)) in policy_data:
                continue

            total_pts, all_comments = grading_policy.get_points_and_comments(
                total_pts,
                all_comments,
                policy_data[policy_key],
            )

        return total_pts, all_comments

    def _policy_key(self, grading_policy: GradingPolicy) -> str:
        return type(grading_policy).__name__
