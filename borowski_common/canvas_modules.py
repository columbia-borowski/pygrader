"""borowski_common/canvas_modules.py: canvas modules"""

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
