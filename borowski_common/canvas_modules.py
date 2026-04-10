"""borowski_common/canvas_modules.py: canvas modules"""

from __future__ import annotations

import json
import statistics
import sys
from argparse import ArgumentParser, Namespace
from csv import DictReader
from io import StringIO
from math import ceil
from typing import Any

import requests

from borowski_common.canvas import Canvas
from borowski_common.constants import ACCOMMODATIONS_SHEET_ID
from borowski_common.quizzes import QuizDownloader
from common import printing as p
from common.assignments import get_assignment_manager
from common.command_modules import CommandModule, CommandWithHWDetailsModule


class UploadGradesModule(CommandWithHWDetailsModule):
    """
    A command module to upload grades.

    Methods:
        run(parsed: Namespace): Runs the upload grades command.
    """

    def __init__(self):
        super().__init__("upload")

    def run(self, parsed: Namespace):
        """
        Runs the upload grades command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        hw_manager = get_assignment_manager(parsed.hw)
        hw_manager.upload_grades(parsed.submitter, parsed.ta)


class ClassRankModule(CommandModule):
    """
    A command module to calculate and upload class ranks.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the class rank command.
    """

    def __init__(self):
        super().__init__("class-rank")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "class_rank_canvas_id",
            type=str,
            help="the canvas id of class rank assignment",
        )

    def run(self, parsed: Namespace):
        """
        Runs the class rank command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        canvas = Canvas()
        course = canvas.get_course()

        user_id_set = set()
        enrollments = []
        for enrollment_obj in course.get_enrollments(type=["StudentEnrollment"]):
            if enrollment_obj.user_id not in user_id_set:
                user_id_set.add(enrollment_obj.user_id)
                enrollments.append(get_enrollment_dict(enrollment_obj))

        enrollments.sort(key=lambda enrollment: enrollment["score"], reverse=True)

        class_rank_data = {enrollments[0]["user_id"]: get_grade_dict(1)}
        prev_score = enrollments[0]["score"]
        prev_rank = 1
        for rank, enrollment in enumerate(enrollments[1:], 2):
            if enrollment["score"] == prev_score:
                rank = prev_rank

            class_rank_data[enrollment["user_id"]] = get_grade_dict(rank)
            prev_score = enrollment["score"]
            prev_rank = rank

        canvas.upload_raw_grades(parsed.class_rank_canvas_id, class_rank_data)


class MidtermModule(CommandModule):
    """
    A command module to calculate and upload midterm grades.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the midterm command.
        _get_midterm_submissions(midterm): Retrieves midterm submissions.
        _get_midterm_grades_dict(submission, num: float): Creates a dictionary of midterm grades.
    """

    def __init__(self):
        super().__init__("midterm")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "midterm1_canvas_id",
            type=str,
            help="the canvas id of the midterm 1 assignment",
        )
        parser.add_argument(
            "midterm2_canvas_id",
            type=str,
            help="the canvas id of the midterm 2 assignment",
        )
        parser.add_argument(
            "higher_midterm_canvas_id",
            type=str,
            help="the canvas id of the midterm with higher score assignment",
        )
        parser.add_argument(
            "lower_midterm_canvas_id",
            type=str,
            help="the canvas id of the midterm with lower score assignment",
        )

    def run(self, parsed: Namespace):
        """
        Runs the midterm command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        canvas = Canvas()
        course = canvas.get_course()

        midterm1_submissions = self._get_midterm_submissions(
            course.get_assignment(parsed.midterm1_canvas_id)
        )
        midterm2_submissions = self._get_midterm_submissions(
            course.get_assignment(parsed.midterm2_canvas_id)
        )

        higher_midterm_grade_data = {}
        lower_midterm_grade_data = {}

        for user_id in midterm1_submissions:
            midterm1_submission = midterm1_submissions[user_id]
            midterm1_dict = self._get_midterm_grades_dict(midterm1_submission, 1)
            midterm2_submission = midterm2_submissions[user_id]
            midterm2_dict = self._get_midterm_grades_dict(midterm2_submission, 2)

            if midterm1_submission.excused:
                lower_midterm_grade_data[user_id] = higher_midterm_grade_data[
                    user_id
                ] = midterm2_dict
                continue

            if midterm2_submission.excused:
                lower_midterm_grade_data[user_id] = higher_midterm_grade_data[
                    user_id
                ] = midterm1_dict
                continue

            higher_midterm_grade_data[user_id] = midterm1_dict
            lower_midterm_grade_data[user_id] = midterm2_dict
            if int(midterm2_submission.grade) > int(midterm1_submission.grade):
                higher_midterm_grade_data[user_id] = midterm2_dict
                lower_midterm_grade_data[user_id] = midterm1_dict

        canvas.upload_raw_grades(
            parsed.higher_midterm_canvas_id, higher_midterm_grade_data
        )
        canvas.upload_raw_grades(
            parsed.lower_midterm_canvas_id, lower_midterm_grade_data
        )

    def _get_midterm_submissions(self, midterm: Any):
        """
        Retrieves midterm submissions.

        Args:
            midterm (Any): The midterm assignment object.

        Returns:
            dict: A dictionary of midterm submissions.
        """
        return {
            submission.user_id: submission for submission in midterm.get_submissions()
        }

    def _get_midterm_grades_dict(self, submission: Any, num: float):
        """
        Creates a dictionary of midterm grades.

        Args:
            submission (Any): The submission object.
            num (float): The midterm number.

        Returns:
            dict: A dictionary containing the midterm grades.
        """
        return {
            "posted_grade": submission.grade,
            "text_comment": f"Midterm {num}",
        }


class FinalGradesModule(CommandModule):
    """
    A command module to calculate and upload final grades.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the final grades command.
    """

    def __init__(self):
        super().__init__("final-grades")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "final_canvas_id",
            type=str,
            help="the canvas id of the final grade assignment",
        )
        parser.add_argument(
            "final_with_bonus_canvas_id",
            default=None,
            type=str,
            help="the canvas id of the final grade with bonus assignment",
        )

    def run(self, parsed: Namespace):
        """
        Runs the final grades command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        canvas = Canvas()
        course = canvas.get_course()

        final_data = {}
        final_with_bonus_data = {}

        enrollments = map(
            get_enrollment_dict, course.get_enrollments(type=["StudentEnrollment"])
        )
        for enrollment in enrollments:
            user_id = enrollment["user_id"]
            score = enrollment["score"]

            final_data[user_id] = get_grade_dict(score)
            final_with_bonus_data[user_id] = get_grade_dict(score + 1)

        canvas.upload_raw_grades(parsed.final_canvas_id, final_data)
        if parsed.final_with_bonus_canvas_id:
            canvas.upload_raw_grades(
                parsed.final_with_bonus_canvas_id, final_with_bonus_data
            )


class QuizExtensionsModule(CommandModule):
    """
    A command module to set quiz extensions for students.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the quiz extensions command.
        _get_approved_students() -> dict[str, set]: Retrieves the approved students for quiz extensions.
    """

    def __init__(self):
        super().__init__("quiz-extensions")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "canvas_id",
            type=str,
            help="the canvas id of the quiz",
        )

    def run(self, parsed: Namespace):
        """
        Runs the quiz extensions command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        course = Canvas().get_course()
        quiz = course.get_quiz(parsed.canvas_id)

        uni_to_user_id = {user.sis_user_id: str(user.id) for user in course.get_users()}

        quiz_extensions = []
        approved_students = self._get_approved_students()
        for student in approved_students:
            uni = student["UNI"]
            multiplier = float(student["Multiplier"])
            break_time = float(student["Break Time"] or 0)
            try:
                quiz_extensions.append(
                    {
                        "user_id": uni_to_user_id[uni],
                        "extra_time": int(ceil((multiplier - 1) * quiz.time_limit))
                        + break_time,
                    }
                )
            except Exception:
                p.print_red(f"[ Could not set extension for {uni} ]")
                continue

        quiz.set_extensions(quiz_extensions)

    def _get_approved_students(self) -> dict[str, set]:
        """
        Retrieves the approved students for quiz extensions.

        Returns:
            dict[str, set]: A dictionary of approved students.
        """
        try:
            csv_req = requests.get(
                f"https://docs.google.com/spreadsheet/ccc?key={ACCOMMODATIONS_SHEET_ID}&output=csv",
                timeout=10,
            )
            csv_req.raise_for_status()
            return DictReader(StringIO(csv_req.text))
        except requests.exceptions.HTTPError as err:
            sys.exit("Failed to get CSV: " + str(err))


class QuizRegradesModule(CommandModule):
    """
    A command module to regrade quiz submissions.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the quiz regrades command.
    """

    def __init__(self):
        super().__init__("regrade-quiz")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "canvas_id",
            type=str,
            help="the canvas id of the quiz",
        )
        parser.add_argument(
            "-q",
            "--question_id",
            type=int,
            help=("the question id in the quiz"),
            dest="question_id",
            required=True,
        )
        parser.add_argument(
            "-a",
            "--answers",
            type=str,
            nargs="+",
            help=("list of accepted answers"),
            dest="answers",
            required=True,
        )
        parser.add_argument(
            "-p",
            "--points",
            type=float,
            help=("the points to return"),
            dest="points",
            required=True,
        )

    def run(self, parsed: Namespace):
        course = Canvas().get_course()
        quiz = course.get_quiz(parsed.canvas_id)
        assignment = course.get_assignment(quiz.assignment_id)

        ids = {}
        for submission in assignment.get_submissions(include=["submission_history"]):
            user_id = submission.user_id
            for attempt in submission.submission_history:
                if "submission_data" not in attempt:
                    continue

                question = [
                    q
                    for q in attempt["submission_data"]
                    if q["question_id"] == parsed.question_id
                ][0]
                if question["text"] in parsed.answers:
                    if user_id not in ids:
                        ids[user_id] = []
                    ids[user_id].append(attempt["attempt"])

        question_id = str(parsed.question_id)
        for submission in quiz.get_submissions():
            for attempt in ids.get(submission.user_id, []):
                submission.update_score_and_comments(
                    quiz_submissions=[
                        {
                            "attempt": attempt,
                            "questions": {
                                question_id: {
                                    "score": parsed.points,
                                    "comment": "Regraded",
                                },
                            },
                        }
                    ]
                )


class DownloadQuizModule(CommandModule):
    """
    A command module to download quizzes.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the download quiz command.
    """

    def __init__(self):
        super().__init__("download-quiz")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument("canvas_quiz_id", type=int, help="Canvas quiz ID")

    def run(self, parsed: Namespace):
        """
        Runs the download quiz command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        quiz_downloader = QuizDownloader(parsed.canvas_quiz_id)
        quiz_downloader.download()


class MissingExamModule(CommandModule):
    """
    A command module to calculate missing exam score submissions based on average percentile across exams.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the missing exam command.
    """

    def __init__(self):
        super().__init__("missing-exam")

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "--dry-run",
            "-d",
            action="store_true",
            help="if set, do not upload grades",
        )
        parser.add_argument(
            "canvas_assignment_ids",
            type=str,
            nargs="+",
            help="the canvas id of the assignment",
        )

    def run(self, parsed: Namespace):
        """
        Runs the missing exam command, imputing missing scores by average percentile.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        canvas = Canvas()
        course = canvas.get_course()
        assignment_ids = parsed.canvas_assignment_ids
        assignment_scores = {assignment_id: {} for assignment_id in assignment_ids}
        excused_students = {}

        for assignment_id in assignment_ids:
            assignment = course.get_assignment(assignment_id)
            for submission in assignment.get_submissions():
                user_id = submission.user_id
                if submission.excused:
                    excused_students.setdefault(user_id, set()).add(assignment_id)
                elif submission.score is not None:
                    assignment_scores[assignment_id][user_id] = float(submission.score)

        percentiles = {}
        sorted_scores_list = {}
        for assignment_id, scores in assignment_scores.items():
            pairs = sorted(scores.items(), key=lambda x: x[1])
            sorted_scores_list[assignment_id] = [score for _, score in pairs]
            N = len(sorted_scores_list[assignment_id])
            percentiles[assignment_id] = {
                user_id: (rank - 1) / (N - 1)
                for rank, (user_id, _) in enumerate(pairs, start=1)
            }

        imputed_scores = {}
        for user_id, excused_assignment_ids in excused_students.items():
            avg_pct = statistics.mean(
                percentiles[assignment_id][user_id]
                for assignment_id in assignment_ids
                if assignment_id not in excused_assignment_ids
            )
            for assignment_id in excused_assignment_ids:
                scores_list = sorted_scores_list.get(assignment_id, [])
                N = len(scores_list)
                idx = max(0, min(int(round(avg_pct * (N - 1))), N - 1))
                imputed_scores.setdefault(user_id, {})[assignment_id] = scores_list[idx]

        final_scores = {}
        for user_id, scores in imputed_scores.items():
            for assignment_id, score in scores.items():
                final_scores.setdefault(assignment_id, {})[user_id] = get_grade_dict(
                    score,
                    "Computed from average percentile across taken exams and looked up score for missing exam",
                )

        if parsed.dry_run:
            print(json.dumps(final_scores, indent=2))
            sys.exit(0)

        for assignment_id, scores in final_scores.items():
            canvas.upload_raw_grades(assignment_id, scores)


class CurveScoresModule(CommandModule):
    """
    A command module to curve scores from a source assignment and write them to a target assignment.
    Uses a power curve (score/max)^p that flattens near the top, preserving ordering
    and ensuring scores never decrease or exceed the assignment max.
    """

    def __init__(self):
        super().__init__("curve")

    def extend_parser(self, parser: ArgumentParser):
        parser.add_argument(
            "source_canvas_id",
            type=str,
            help="canvas ID of the source assignment to read scores from",
        )
        parser.add_argument(
            "target_canvas_id",
            type=str,
            help="canvas ID of the target assignment to write curved scores to",
        )

        curve_group = parser.add_mutually_exclusive_group(required=True)
        curve_group.add_argument(
            "--target-mean",
            type=float,
            help="target mean score after curving",
        )
        curve_group.add_argument(
            "--target-median",
            type=float,
            help="target median score after curving",
        )

        parser.add_argument(
            "--boost",
            type=float,
            default=0,
            help="fraction (0 to 1) to pull all scores toward the max, applied after the power curve",
        )

        parser.add_argument(
            "--anchor-min",
            type=float,
            default=None,
            help="fixed score to map the lowest original score to",
        )
        parser.add_argument(
            "--anchor-max",
            type=float,
            default=None,
            help="fixed score to map the highest original score to",
        )

        parser.add_argument(
            "--preview",
            action="store_true",
            help="preview curved grade distribution and statistics without uploading",
        )

    def run(self, parsed: Namespace):
        canvas = Canvas()
        course = canvas.get_course()

        boost = parsed.boost
        anchor_min = parsed.anchor_min
        anchor_max = parsed.anchor_max
        has_anchors = anchor_min is not None or anchor_max is not None

        if has_anchors and boost > 0:
            p.print_red(
                "Error: --boost cannot be used with --anchor-min or --anchor-max."
            )
            sys.exit(1)

        if not 0 <= boost < 1:
            p.print_red("Error: --boost must be >= 0 and < 1.")
            sys.exit(1)

        assignment = course.get_assignment(parsed.source_canvas_id)
        max_points = float(assignment.points_possible)
        scores = {}
        for submission in assignment.get_submissions():
            if submission.score is not None and not submission.excused:
                scores[submission.user_id] = float(submission.score)

        if len(scores) < 2:
            p.print_red("Error: Not enough scored submissions to curve.")
            sys.exit(1)

        score_values = sorted(scores.values())
        current_mean = statistics.mean(score_values)
        current_median = statistics.median(score_values)

        if anchor_min is not None and anchor_min < 0:
            p.print_red("Error: --anchor-min must be >= 0.")
            sys.exit(1)
        if anchor_max is not None and anchor_max > max_points:
            p.print_red(
                f"Error: --anchor-max must be <= assignment max ({max_points:.2f})."
            )
            sys.exit(1)
        if (
            anchor_min is not None
            and anchor_max is not None
            and anchor_min > anchor_max
        ):
            p.print_red("Error: --anchor-min must be <= --anchor-max.")
            sys.exit(1)

        if parsed.target_mean is not None:
            stat_name = "mean"
            stat_fn = statistics.mean
            target_value = parsed.target_mean
            current_value = current_mean
        else:
            stat_name = "median"
            stat_fn = statistics.median
            target_value = parsed.target_median
            current_value = current_median

        if not has_anchors and target_value < current_value:
            p.print_red(
                f"Error: Cannot curve to target {stat_name} {target_value:.2f} "
                f"without decreasing scores."
            )
            p.print_red(
                f"Current mean: {current_mean:.2f}, current median: {current_median:.2f}"
            )
            sys.exit(1)

        if target_value > max_points:
            p.print_red(
                f"Error: Target {stat_name} {target_value:.2f} exceeds "
                f"assignment max of {max_points:.2f}."
            )
            sys.exit(1)

        exponent = self._find_exponent(
            score_values,
            max_points,
            target_value,
            stat_fn,
            boost,
            anchor_min,
            anchor_max,
        )
        if exponent is None:
            p.print_red(
                f"Error: Could not find a curve that achieves target "
                f"{stat_name} {target_value:.2f} without decreasing scores."
            )
            sys.exit(1)

        if has_anchors:
            curved_range = (
                max_points * (score_values[0] / max_points) ** exponent,
                max_points * (score_values[-1] / max_points) ** exponent,
            )
        else:
            curved_range = None

        curved_scores = {
            uid: self._apply_curve(
                score, max_points, exponent, boost, anchor_min, anchor_max, curved_range
            )
            for uid, score in scores.items()
        }
        curved_values = sorted(curved_scores.values())

        self._print_stats("Original Scores", score_values, max_points)
        self._print_stats("Curved Scores", curved_values, max_points)
        p.print_green(f"  Exponent: {exponent:.4f}")
        if boost > 0:
            p.print_green(f"  Boost:    {boost:.4f}")
        if anchor_min is not None:
            p.print_green(f"  Anchor Min: {anchor_min:.2f}")
        if anchor_max is not None:
            p.print_green(f"  Anchor Max: {anchor_max:.2f}")

        print()
        self._print_histogram("Original Distribution", score_values, max_points)
        print()
        self._print_histogram("Curved Distribution", curved_values, max_points)

        if parsed.preview:
            return

        print()
        grade_data = {
            uid: get_grade_dict(round(score, 2))
            for uid, score in curved_scores.items()
        }
        canvas.upload_raw_grades(parsed.target_canvas_id, grade_data)
        p.print_green(f"\nUploaded {len(grade_data)} curved scores.")

    @staticmethod
    def _apply_curve(
        score: float,
        max_points: float,
        exponent: float,
        boost: float = 0,
        anchor_min: float = None,
        anchor_max: float = None,
        curved_range: tuple[float, float] = None,
    ) -> float:
        if max_points == 0:
            return score
        curved = max_points * (score / max_points) ** exponent
        if anchor_min is not None or anchor_max is not None:
            src_min, src_max = curved_range
            dst_min = anchor_min if anchor_min is not None else src_min
            dst_max = anchor_max if anchor_max is not None else src_max
            if src_max == src_min:
                return (dst_min + dst_max) / 2
            curved = (
                dst_min + (curved - src_min) / (src_max - src_min) * (dst_max - dst_min)
            )
        else:
            curved = curved + boost * (max_points - curved)
        return curved

    @staticmethod
    def _find_exponent(
        values: list[float],
        max_points: float,
        target: float,
        stat_fn,
        boost: float = 0,
        anchor_min: float = None,
        anchor_max: float = None,
    ) -> float | None:
        has_anchors = anchor_min is not None or anchor_max is not None

        def curved_stat(exp):
            raw = [max_points * (v / max_points) ** exp for v in values]
            if has_anchors:
                src_min, src_max = min(raw), max(raw)
                dst_min = anchor_min if anchor_min is not None else src_min
                dst_max = anchor_max if anchor_max is not None else src_max
                if src_max == src_min:
                    return (dst_min + dst_max) / 2
                curved = [
                    dst_min
                    + (c - src_min) / (src_max - src_min) * (dst_max - dst_min)
                    for c in raw
                ]
            else:
                curved = [c + boost * (max_points - c) for c in raw]
            return stat_fn(curved)

        lo, hi = 0.01, 1.0
        # At exponent=1.0 scores are mostly unchanged; at exponent->0 all scores->max_points.
        stat_lo = curved_stat(lo)
        stat_hi = curved_stat(hi)

        if not (min(stat_lo, stat_hi) <= target <= max(stat_lo, stat_hi)):
            return None

        for _ in range(100):
            mid = (lo + hi) / 2
            stat_mid = curved_stat(mid)
            if abs(stat_mid - target) < 0.001:
                return mid
            if stat_mid > target:
                lo = mid
            else:
                hi = mid

        return (lo + hi) / 2

    @staticmethod
    def _print_stats(title: str, values: list[float], max_points: float):
        print(f"\n  {title}")
        print(f"    Count:    {len(values)}")
        print(f"    Mean:     {statistics.mean(values):.2f}")
        print(f"    Median:   {statistics.median(values):.2f}")
        print(f"    Std Dev:  {statistics.stdev(values):.2f}")
        print(f"    Min:      {min(values):.2f}")
        print(f"    Max:      {max(values):.2f}  (out of {max_points:.2f})")

    @staticmethod
    def _print_histogram(title: str, values: list[float], max_points: float):
        num_bins = 10
        bin_size = max_points / num_bins
        bins = []
        for i in range(num_bins):
            bins.append((i * bin_size, (i + 1) * bin_size))

        if not bins:
            return

        counts = []
        for low, high in bins:
            count = sum(1 for v in values if low <= v < high)
            counts.append(count)
        # Include scores exactly equal to max_points in the last bin
        counts[-1] += sum(1 for v in values if v == bins[-1][1])

        max_count = max(counts) if counts else 1
        bar_width = 40

        print(f"  {title}")
        for (low, high), count in zip(bins, counts):
            bar_len = int(count / max_count * bar_width) if max_count > 0 else 0
            bar = "#" * bar_len # pylint: disable=disallowed-name
            label = f"    {low:6.1f} - {high:6.1f}"
            print(f"{label} | {bar} ({count})")


def get_enrollment_dict(enrollment: Any):
    """
    Converts an enrollment object to a dictionary.

    Args:
        enrollment (Any): The enrollment object.

    Returns:
        dict: A dictionary containing the enrollment information.
    """
    return {
        "user_id": enrollment.user_id,
        "name": enrollment.user["name"],
        "score": float(enrollment.grades["current_score"]),
    }


def get_grade_dict(score: float, comment: str = ""):
    """
    Creates a dictionary of grades.

    Args:
        score (float): The grade score.
        comment (str, optional): The grade comment. Defaults to "".

    Returns:
        dict: A dictionary containing the grade information.
    """
    grade_dict = {"posted_grade": score}
    if comment:
        grade_dict["text_comment"] = comment

    return grade_dict
