"""common/grading_policies.py: Logic for grading policies"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GradingPolicy(ABC):
    """Interface for Grading Policies

    This abstract base class defines the interface for grading policies.
    Grading policies are used to adjust the total points and comments for a submission
    based on specific criteria.

    Methods:
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Adjusts the total points and comments based on the policy data.
    """

    @abstractmethod
    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data
    ) -> tuple[float, list[str]]:
        """
        Adjusts the total points and comments based on the policy data.

        Args:
            total_pts (float): The total points before applying the policy.
            all_comments (list[str]): The list of comments before applying the policy.
            policy_data (any): The data specific to the policy.

        Returns:
            tuple[float, list[str]]: The adjusted total points and comments.
        """


class LatePercentagePenaltyPolicy(GradingPolicy):
    """Apply a percentage penalty if the submission was late

    This class implements a grading policy that applies a percentage penalty to the total points
    if the submission was late. The penalty percentage is specified in the policy data.

    Methods:
        get_points_and_comments(total_pts: float, all_comments: list[str], policy_data) -> tuple[float, list[str]]:
            Applies the late penalty to the total points and adds a comment indicating the penalty.
    """

    def get_points_and_comments(
        self, total_pts: float, all_comments: list[str], policy_data: Any
    ) -> tuple[float, list[str]]:
        """
        Applies the late penalty to the total points and adds a comment indicating the penalty.

        Args:
            total_pts (float): The total points before applying the penalty.
            all_comments (list[str]): The list of comments before applying the penalty.
            policy_data: The percentage penalty to apply (e.g., 0.1 for 10%).

        Returns:
            tuple[float, list[str]]: The adjusted total points and comments.
        """
        if policy_data != 0:
            total_pts = round(total_pts * (1 - policy_data), 2)
            all_comments.insert(0, "(LATE)")

        return total_pts, all_comments
