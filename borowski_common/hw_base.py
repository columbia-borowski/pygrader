"""borowski_common/hw_base.py: Base class for all Borowski HW managers and testers"""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
from abc import abstractmethod
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from pathlib import Path
from typing import Any

from borowski_common import utils as u
from borowski_common.canvas import Canvas
from borowski_common.constants import GRADES_ROOT
from borowski_common.moss import MossRunner
from common import printing as p
from common.command_modules import CommandModule, CompositeCommandModule
from common.grader import Grader
from common.hw_base import HWManager, HWTester


class BorowskiHWManager(HWManager):
    """
    Manages the homework assignments for Borowski courses.

    Attributes:
        hw_name (str): The name of the homework assignment.
        hw_tester_class (type[BorowskiHWTester]): The class of the homework tester.
        rubric_name (str): The name of the rubric file.
        language (str): The programming language of the submissions.
        submitted_files (set[str]): The set of submitted files.
        workspace_dir (str): The directory for the current homework assignment.
        hw_info (dict): Information about the homework assignment.
        _ta_submission_mapping (dict): A dictionary mapping TAs to their students.
        _submissions (dict): A dictionary of submissions.
        moss_files (set[str]): The set of files to be checked for plagiarism.
    """

    def __init__(
        self,
        hw_name: str,
        hw_tester_class: type[BorowskiHWTester],
        rubric_name: str = "rubric.json",
        language: str = "java",
        submitted_files: set[str] | None = None,
    ):
        """
        Initializes the BorowskiHWManager.

        Args:
            hw_name (str): The name of the homework assignment.
            hw_tester_class (type[BorowskiHWTester]): The class of the homework tester.
            rubric_name (str): The name of the rubric file. Defaults to "rubric.json".
            language (str): The programming language of the submissions. Defaults to "java".
            submitted_files (set[str] | None): The set of submitted files. Defaults to None.
        """
        super().__init__(hw_name, rubric_name, hw_tester_class)
        self.submitted_files = submitted_files or set()
        self.language = language

        self.workspace_dir = os.path.join(GRADES_ROOT, self.hw_name)
        if not os.path.isdir(self.workspace_dir):
            sys.exit("Please run hw_setup.py before grading")

        self.hw_info = self._get_hw_info()

        self._ta_submission_mapping = {}
        self._submissions = {}

        self.moss_files = self.submitted_files

    def _get_hw_info(self) -> dict:
        """
        Loads the homework information from the hw_info.json file.

        Returns:
            dict: The homework information.
        """
        with open(
            os.path.join(self.workspace_dir, "hw_info.json"), "r", encoding="utf-8"
        ) as hw_info_file:
            return json.load(hw_info_file)

    def get_submission_grader(
        self, env: dict[str, bool | str], submitter: str | None
    ) -> Grader:
        """
        Retrieves the grader for the specified submission.

        Args:
            env (dict[str, bool | str]): The environment variables.
            submitter (str | None): The submitter's identifier.

        Returns:
            Grader: The grader for the specified submission.
        """
        hw_tester = self.get_hw_tester(submitter)
        grades = self.get_grades(submitter)
        return Grader(env, hw_tester, grades)

    def get_grading_status(
        self, rubric_code: str, submitter: str | None = None, ta: str | None = None
    ) -> bool:
        """
        Retrieves the grading status for the specified rubric code.

        Args:
            rubric_code (str): The rubric code.
            submitter (str | None): The submitter's identifier. Defaults to None.
            ta (str | None): The TA's identifier. Defaults to None.

        Returns:
            bool: True if the grading is complete, False otherwise.
        """
        if submitter:
            grades = self.get_grades(submitter)
            graded, _ = grades.status(rubric_code)
            return graded

        if ta:
            grades = self.get_grades(ta=ta)
            total = len(self.get_submitters(ta))
            _, graded_count = grades.status(rubric_code)
            s = f"{ta}\t{graded_count}/{total}"

            if graded_count == total:
                p.print_green(s)
            elif graded_count == 0:
                p.print_red(s)
            else:
                p.print_light_gray(s)

            return total == graded_count

        return all(
            tuple(
                self.get_grading_status(rubric_code, ta=ta)
                for ta in self._get_ta_submission_mapping()
            )
        )

    def upload_grades(self, submitter: str | None, ta: str | None):
        """
        Uploads the grades to Canvas.

        Args:
            submitter (str | None): The submitter's identifier. Defaults to None.
            ta (str | None): The TA's identifier. Defaults to None.
        """
        p.print_between_cyan_line(f"Updating grades for {self.hw_name}")

        grades = self.get_grades(submitter, ta)
        count = Canvas().upload_grades(grades)

        if not submitter:
            p.print_stats(grades.stats())
        p.print_green(f"[ Updated grades for {count} students! ]")

    def plagiarism_check(self):
        """
        Runs the plagiarism check using MOSS (Measure of Software Similarity).
        """
        moss_runner = MossRunner(self.hw_name, self.language, self.moss_files)

        templates_dir = f"{self.scripts_dir}/templates"
        if os.path.isdir(templates_dir):
            moss_runner.add_template_dir(templates_dir)

        for submitter in self.get_submitters():
            moss_runner.add_student(submitter, self.get_submission_dir(submitter))

        self.hw_info["moss"] = moss_runner.run()
        self._synchornize_hw_info()

    def get_submission_dir(self, submitter: str):
        """
        Retrieves the submission directory for the specified submitter.

        Args:
            submitter (str): The submitter's identifier.

        Returns:
            str: The submission directory.
        """
        return os.path.join(self.workspace_dir, "submissions", submitter)

    def _synchornize_hw_info(self):
        """
        Synchronizes the homework information to the hw_info.json file.
        """
        with open(
            os.path.join(self.workspace_dir, "hw_info.json"), "w", encoding="utf-8"
        ) as hw_info_file:
            json.dump(self.hw_info, hw_info_file, indent=4, sort_keys=True)

    @abstractmethod
    def get_grades(self, submitter: str | None = None, ta: str | None = None):
        """
        Abstract method to retrieve the grades for the specified submitter or TA.

        Args:
            submitter (str | None): The submitter's identifier. Defaults to None.
            ta (str | None): The TA's identifier. Defaults to None.
        """

    def _create_class_grades_file(self):
        """
        Creates the class grades file by combining the TA grades files.
        """
        class_grades = {}
        for ta in self._get_ta_submission_mapping():
            with open(self._get_ta_grades_path(ta), "r", encoding="utf-8") as tf:
                class_grades.update(json.load(tf))

        with open(self._get_class_grades_path(), "w", encoding="utf-8") as cf:
            json.dump(class_grades, cf, indent=4, sort_keys=True)

    def _get_class_grades_path(self) -> str:
        """
        Retrieves the path to the class grades file.

        Returns:
            str: The path to the class grades file.
        """
        return os.path.join(self.workspace_dir, "class_grades.json")

    def _get_ta_grades_path(self, ta: str) -> str:
        """
        Retrieves the path to the TA grades file.

        Args:
            ta (str): The TA's identifier.

        Returns:
            str: The path to the TA grades file.
        """
        return os.path.join(self.workspace_dir, "grades", f"{ta}.json")

    def get_submitters(self, ta: str | None = None) -> list[str]:
        """
        Retrieves the list of submitters.

        Args:
            ta (str | None): The TA's identifier. Defaults to None.

        Returns:
            list[str]: The list of submitters.
        """
        return (
            self._get_submissions().keys()
            if not ta
            else self._get_ta_submission_mapping()[ta].keys()
        )

    def _get_ta_submission_mapping(self) -> dict[str, dict[str, Any]]:
        """
        Retrieves the mapping of TAs to their students.

        Returns:
            dict[str, dict[str, Any]]: The mapping of TAs to their students.
        """
        if not self._ta_submission_mapping:
            ta_submission_mapping = {}
            for student_uni, submission in self._get_submissions().items():
                ta = submission["ta"]["uni"]
                if ta not in ta_submission_mapping:
                    ta_submission_mapping[ta] = {}
                ta_submission_mapping[ta][student_uni] = submission

            self._ta_submission_mapping = dict(sorted(ta_submission_mapping.items()))

        return self._ta_submission_mapping

    def get_submission_data(self, submitter: str):
        """
        Retrieves the submission data for the specified submitter.

        Args:
            submitter (str): The submitter's identifier.

        Returns:
            dict: The submission data.
        """
        return self._get_submissions()[submitter]

    def _get_submissions(self) -> dict:
        """
        Retrieves the submissions data.

        Returns:
            dict: The submissions data.
        """
        if not self._submissions:
            with open(
                os.path.join(self.workspace_dir, "submissions.json"),
                "r",
                encoding="utf-8",
            ) as submissions_file:
                self._submissions = json.load(submissions_file)

        return self._submissions


class BorowskiHWSetup(CompositeCommandModule):
    """
    A composite command module to set up the homework environment.

    Methods:
        __init__(modules: os.Iterable[CommandModule]): Initializes the BorowskiHWSetup.
    """

    def __init__(self, modules: os.Iterable[CommandModule]):
        """
        Initializes the BorowskiHWSetup.

        Args:
            modules (os.Iterable[CommandModule]): The command modules to include in the setup.
        """
        super().__init__("hw-setup", "command", modules)


class BorowskiHWSetupSubcommand(CommandModule):
    """
    A command module to handle the setup of homework submissions.

    Attributes:
        canvas (Canvas): An instance of the Canvas class.

    Methods:
        extend_parser(parser: ArgumentParser): Extends the argument parser with additional arguments.
        run(parsed: Namespace): Runs the setup command.
        init_setup(parsed: Namespace): Initializes the setup process.
        setup_submission(submission, login_id: str, silent=True): Sets up a submission.
        download_submission(submission, silent: bool = True): Downloads a submission.
        setup_dummy_submission(login_id: str): Sets up a dummy submission.
    """

    def __init__(self, name: str, parent_command_module: CommandModule = None):
        """
        Initializes the BorowskiHWSetupSubcommand.

        Args:
            name (str): The name of the subcommand.
            parent_command_module (CommandModule, optional): The parent command module. Defaults to None.
        """
        super().__init__(name, parent_command_module)
        self.canvas = Canvas()

    def extend_parser(self, parser: ArgumentParser):
        """
        Extends the argument parser with additional arguments.

        Args:
            parser (ArgumentParser): The argument parser to extend.
        """
        parser.add_argument(
            "canvas_id",
            type=str,
            help="the canvas id of the assignment",
            nargs="?",
        )

    def run(self, parsed: Namespace):
        """
        Runs the setup command.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """
        self.ta = getattr(parsed, "ta", None)
        self.exclude_ta_unis = set(getattr(parsed, "exclude_ta_unis", None) or [])

        self._setup_dirs(parsed.hw, parsed.canvas_id)

        self.tas = self.canvas.get_tas()
        self._setup_mapping_files()

        self.init_setup(parsed)

        self._update_mapping_files()

    @abstractmethod
    def init_setup(self, parsed: Namespace):
        """
        Initializes the setup process.

        Args:
            parsed (Namespace): The parsed command-line arguments.
        """

    def _setup_dirs(self, hw_name: str, canvas_id: str):
        """
        Sets up the directories for the homework assignment.

        Args:
            hw_name (str): The name of the homework assignment.
            canvas_id (str): The Canvas assignment ID.
        """
        if not os.path.isdir(GRADES_ROOT):
            u.create_dir(GRADES_ROOT)

        self.grade_hwN_dir = os.path.join(GRADES_ROOT, hw_name)
        self.submissions_dir = os.path.join(self.grade_hwN_dir, "submissions")

        if os.path.isdir(self.grade_hwN_dir):
            with open(
                os.path.join(self.grade_hwN_dir, "hw_info.json"), "r", encoding="utf-8"
            ) as pygrader_hw_info:
                hw_info = json.load(pygrader_hw_info)
                if canvas_id and hw_info["id"] != canvas_id:
                    sys.exit(
                        "Assignment id does not match. Please run hw_setup.py again."
                    )

                self.assignment = self.canvas.get_course().get_assignment(hw_info["id"])
            return

        if not canvas_id:
            sys.exit("Please provide a canvas assignment id")

        self.assignment = self.canvas.get_course().get_assignment(canvas_id)

        u.create_dir(self.grade_hwN_dir)
        u.create_dir(os.path.join(self.grade_hwN_dir, "grades"))

        u.create_dir(self.submissions_dir)

        hw_info = {
            "id": str(self.assignment.id),
            "due_at": self.assignment.due_at.replace("Z", "+00:00"),
            "name": self.assignment.name,
        }
        with open(
            os.path.join(self.grade_hwN_dir, "hw_info.json"), "w", encoding="utf-8"
        ) as pygrader_hw_info:
            json.dump(hw_info, pygrader_hw_info, indent=4, sort_keys=True)

    def _setup_mapping_files(self):
        """
        Sets up the mapping files for the homework assignment.
        """
        self.submissions = {}
        self.submissions_mapping_json = os.path.join(
            self.grade_hwN_dir, "submissions.json"
        )
        if os.path.isfile(self.submissions_mapping_json):
            with open(
                self.submissions_mapping_json, "r", encoding="utf-8"
            ) as submissions_f:
                self.submissions = json.load(submissions_f)

        self.ta_count_mapping = {ta: 0 for ta in self.tas}
        for submission in self.submissions.values():
            ta = submission["ta"]["uni"]
            if ta not in self.ta_count_mapping:
                self.ta_count_mapping[ta] = 0
            self.ta_count_mapping[ta] += 1

    @abstractmethod
    def setup_submission(self, submission: Any, login_id: str, silent=True):
        """
        Sets up a submission.

        Args:
            submission (Any): The submission object.
            login_id (str): The login ID of the submitter.
            silent (bool): Whether to suppress output. Defaults to True.
        """

    def _get_ta_for_submission(self):
        """
        Retrieves the TA for the submission.

        Returns:
            dict: The TA information.
        """
        if self.ta is not None:
            if self.ta not in self.ta_count_mapping:
                self.ta_count_mapping[self.ta] = 0
            return {"uni": self.ta, "name": self.tas[self.ta].name}

        min_assignments = min(self.ta_count_mapping.values())
        ta_uni = random.choice(
            [
                ta
                for ta, count in self.ta_count_mapping.items()
                if count == min_assignments and ta not in self.exclude_ta_unis
            ]
        )
        return {"uni": ta_uni, "name": self.tas[ta_uni].name}

    def _remove_grades_for_submission(self, login_id: str, ta: str):
        """
        Removes the grades for the specified submission.

        Args:
            login_id (str): The login ID of the submitter.
            ta (str): The TA's identifier.
        """
        ta_grades_file_path = os.path.join(self.grade_hwN_dir, "grades", f"{ta}.json")
        if os.path.exists(ta_grades_file_path):
            ta_grades = {}
            with open(ta_grades_file_path, "r", encoding="utf-8") as ta_grades_f:
                ta_grades = json.load(ta_grades_f)

            ta_grades.pop(login_id, None)
            with open(ta_grades_file_path, "w", encoding="utf-8") as ta_grades_f:
                json.dump(ta_grades, ta_grades_f, indent=4, sort_keys=True)

    @abstractmethod
    def download_submission(self, submission: Any, silent: bool = True):
        """
        Downloads a submission.

        Args:
            submission (Any): The submission object.
            silent (bool): Whether to suppress output. Defaults to True.
        """

    @abstractmethod
    def setup_dummy_submission(self, login_id: str):
        """
        Sets up a dummy submission.

        Args:
            login_id (str): The login ID of the submitter.
        """

    def _update_mapping_files(self):
        """
        Updates the mapping files for the homework assignment.
        """
        with open(
            self.submissions_mapping_json, "w", encoding="utf-8"
        ) as submissions_f:
            json.dump(self.submissions, submissions_f, indent=4, sort_keys=True)


class BorowskiHWTester(HWTester):
    """
    A class to test homework submissions for Borowski courses.

    Attributes:
        submission_dir (str): The directory of the submission.
        hidden_files (set): A set of hidden files.
        copied_files (set): A set of copied files.
        submission_data (dict): The data of the submission.

    Methods:
        get_grading_policy_data() -> dict[str, Any]:
            Abstract method to get grading policy data.
        copy_files_from_dir(dir_path: str):
            Copies files from the specified directory.
        copy_files(files: dict):
            Copies the specified files.
        check_file_structure(rubric_item_code: str) -> bool | None:
            Checks the file structure of the submission.
        exit_handler(_signal, _frame):
            Handles the exit signal.
    """

    def __init__(self, submitter: str, manager: BorowskiHWManager):
        """
        Initializes the BorowskiHWTester.

        Args:
            submitter (str): The submitter's identifier.
            manager (BorowskiHWManager): The homework manager.
        """
        super().__init__(submitter, manager)

        self.submission_dir = manager.get_submission_dir(self.submitter)
        if not os.path.isdir(self.submission_dir):
            sys.exit("Submission not found")

        os.chdir(self.submission_dir)

        self.hidden_files = set()
        self.copied_files = set()

        self.submission_data = manager.get_submission_data(self.submitter)

    def check_file_structure(
        self, rubric_item_code: str
    ) -> bool | list[tuple[str, str]] | None:
        """
        Checks the file structure of the submission.

        Args:
            rubric_item_code (str): The rubric item code.

        Returns:
            bool | list[tuple[str, str]] | None: True if the file structure is correct, a list of deductions if fixed automatically, or None.
        """
        if self.grader.grades.is_graded(rubric_item_code):
            p.print_yellow(
                "[ File structure has already been graded. Please be careful. ]"
            )
            return None

        if rubric_item_code.split(".")[0] in self.ran_rubric_item_codes:
            self._print_file_structure()
            return None

        self._print_file_structure()
        res = self._try_to_fix_structure()

        if res is None:
            p.print_red("[ Incorrect File Structure: please fix and deduct ]")
        elif res is False:
            p.print_red("[ Incorrect File Structure but fixed automatically ]")
            self._print_file_structure()
        else:
            p.print_green("[ Correct File Structure ]")

        return [("n", "")] if res is False else res

    def _print_file_structure(self):
        """
        Prints the file structure of the submission.
        """
        # -a for all files
        # -C for colorized output
        # -I to ignore most non-binary files
        ignored_files = "|".join([".git", "__MACOSX", *self.hidden_files])
        u.run_cmd(f"tree -a -C -I '{ignored_files}'")

    def _try_to_fix_structure(self) -> bool | None:
        """
        Tries to fix the file structure of the submission if needed.

        Returns:
            bool | None: True if the file structure is correct, False if fixed automatically, or None.
        """
        required_files = self.manager.submitted_files
        missing_files = set(required_files)
        all_files_in_dir = set(
            str(path) for path in Path(".").rglob("*") if path.is_file()
        ).difference(self.hidden_files)

        file_name_to_paths = defaultdict(list)
        for file in all_files_in_dir:
            file_name = os.path.basename(file)
            file_name_to_paths[file_name].append(file)
            missing_files.discard(file)

        if all_files_in_dir == required_files:
            return True

        fixes = {}
        for missing_file in missing_files:
            file_name = os.path.basename(missing_file)
            if len(file_name_to_paths.get(file_name, [])) != 1 or os.path.isdir(
                missing_file
            ):
                return None

            fixes[file_name_to_paths[file_name][0]] = missing_file

        for wrong_path, correct_path in fixes.items():
            os.makedirs(os.path.dirname(correct_path) or ".", exist_ok=True)
            shutil.copy(wrong_path, correct_path)

        for file in all_files_in_dir.difference(required_files):
            os.remove(file)

        for dirpath, dirnames, filenames in os.walk(".", topdown=False):
            if not dirnames and not filenames:
                os.rmdir(dirpath)

        return False

    @abstractmethod
    def get_grading_policy_data(self) -> dict[str, Any]:
        """
        Abstract method to get grading policy data.

        Returns:
            dict[str, Any]: The grading policy data.
        """

    def copy_files_from_dir(self, dir_path: str):
        """
        Copies files from the specified directory.

        Args:
            dir_path (str): The path of the directory to copy files from.
        """
        self.copy_files(
            {
                str(path): str(path.relative_to(dir_path))
                for path in Path(dir_path).rglob("*")
                if path.is_file()
            }
        )

    def copy_files(self, files: dict):
        """
        Copies the specified files.

        Args:
            files (dict): A dictionary where keys are source file paths and values are destination file paths.
        """
        submission_dir_mtime = os.path.getmtime(self.submission_dir)
        for src_fpath, dst_fpath in files.items():
            os.makedirs(os.path.dirname(dst_fpath) or ".", exist_ok=True)
            shutil.copy(src_fpath, dst_fpath)

        os.utime(
            self.submission_dir,
            (os.path.getatime(self.submission_dir), submission_dir_mtime),
        )

        self.copied_files = self.copied_files.union(set(files.values()))
        self.hidden_files = self.hidden_files.union(self.copied_files)

    def exit_handler(self, _signal, _frame):
        """
        Handles the exit signal.
        """
        p.print_cyan(f"\n[ Exiting {self.manager.hw_name} grader... ]")
        self.cleanup()
        sys.exit()
