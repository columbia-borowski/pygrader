"""borowski_common/test_runner.py: Service to run tests"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from borowski_common import utils as u
from common import printing as p


@dataclass
class TestCase:
    """Representation of a test case.

    Attributes:
        cmd (str): The command to run the test case.
        stdin (str | None): The standard input for the test case. Defaults to None.
        expected_stdout (str | None): The expected standard output. Defaults to None.
        expected_stderr (str | None): The expected standard error. Defaults to None.
        expected_return_code (int | None): The expected return code. Defaults to None.
    """

    cmd: str
    stdin: str | None = None
    expected_stdout: str | None = None
    expected_stderr: str | None = None
    expected_return_code: int | None = None

    @classmethod
    def get_cases_list_from_file(cls, json_file_path: str) -> dict[str, list[TestCase]]:
        """
        Reads test cases from a JSON file and returns them as a dictionary.

        Args:
            json_file_path (str): The path to the JSON file containing test cases.

        Returns:
            dict[str, list[TestCase]]: A dictionary where keys are item codes and values are lists of TestCase objects.
        """
        with open(json_file_path, encoding="utf-8") as cases:
            cases_json = json.load(cases)
            return {
                item_code: [cls(**test_case) for test_case in test_cases]
                for item_code, test_cases in cases_json.items()
            }


class TestRunner(ABC):
    """Abstract class that handles compiling and running programs.

    Attributes:
        test_cases (dict[str, list[TestCase]]): The test cases to run.
        setup_function (callable): The function to set up the environment.
        check_manually_on_fail (bool): Whether to check manually on failure. Defaults to False.
        disable_comments (bool): Whether to disable comments. Defaults to False.
        allowed_formatting_errors_count (int): The allowed number of formatting errors. Defaults to 0.
        timeout (int): The timeout for each test case. Defaults to 1.
        run_on_shell (bool): Whether to run the command on the shell. Defaults to False.
        redirect_stderr_to_stdout (bool): Whether to redirect stderr to stdout. Defaults to False.
        diff_use_pager (bool): Whether to use a pager for the diff. Defaults to True.
    """

    def __init__(
        self,
        test_cases: dict[str, list[TestCase]],
        setup_function: callable,
        check_manually_on_fail: bool = False,
        disable_comments: bool = False,
        allowed_formatting_errors_count: int = 0,
        timeout: int = 1,
        run_on_shell: bool = False,
        redirect_stderr_to_stdout: bool = False,
        diff_use_pager: bool = True,
    ):
        self.test_cases = test_cases
        self.setup_function = setup_function
        self.check_manually_on_fail = check_manually_on_fail
        self.disable_comments = disable_comments
        self.allowed_formatting_errors_count = allowed_formatting_errors_count
        self.timeout = timeout
        self.run_on_shell = run_on_shell
        self.redirect_stderr_to_stdout = redirect_stderr_to_stdout
        self.diff_use_pager = diff_use_pager

        self.is_compiled = None

        self.needed_check_manually_on_fail = False
        self.items_with_formatting_errors = []

    def run_tests(
        self,
        item_code: str,
        check_manually_on_fail: bool | None = None,
        disable_comments: bool | None = None,
        timeout: int | None = None,
        run_on_shell: bool | None = None,
        redirect_stderr_to_stdout: bool | None = None,
        diff_use_pager: bool | None = None,
    ) -> list[tuple[str, str]] | None:
        """
        Runs all test cases for a given item code.

        Args:
            item_code (str): The item code for which to run the test cases.
            check_manually_on_fail (bool | None): Whether to check manually on failure. Defaults to None.
            disable_comments (bool | None): Whether to disable comments. Defaults to None.
            timeout (int | None): The timeout for each test case. Defaults to None.
            run_on_shell (bool | None): Whether to run the command on the shell. Defaults to None.
            redirect_stderr_to_stdout (bool | None): Whether to redirect stderr to stdout. Defaults to None.
            diff_use_pager (bool | None): Whether to use a pager for the diff. Defaults to None.

        Returns:
            list[tuple[str, str]] | None: A list of tuples where each tuple contains:
                - "y" if the test passed, "n" if it failed.
                - An empty string if the test passed, or the error message if it failed.
        """
        if self.is_compiled is None:
            self.is_compiled = self.setup_function()

        if check_manually_on_fail is None:
            check_manually_on_fail = self.check_manually_on_fail

        if redirect_stderr_to_stdout is None:
            redirect_stderr_to_stdout = self.redirect_stderr_to_stdout

        if diff_use_pager is None:
            diff_use_pager = self.diff_use_pager

        if run_on_shell is None:
            run_on_shell = self.run_on_shell

        if timeout is None:
            timeout = self.timeout

        if disable_comments is None:
            disable_comments = self.disable_comments

        test_cases = self.test_cases[item_code]
        grades = [
            self.run_test(
                test_case,
                f"{item_code}.{i}",
                check_manually_on_fail,
                disable_comments,
                len(test_cases) > 1,
                timeout,
                run_on_shell,
                redirect_stderr_to_stdout,
                diff_use_pager,
            )
            for i, test_case in enumerate(test_cases, 1)
        ]

        if any(grade is None for grade in grades):
            p.print_yellow("[ Manual Check Required ]")
            return None

        return grades

    def run_test(
        self,
        test_case: TestCase,
        subitem_code: str,
        check_manually_on_fail: bool,
        disable_comments: bool,
        show_header: bool,
        timeout: int,
        run_on_shell: bool,
        redirect_stderr_to_stdout: bool,
        diff_use_pager: bool,
    ) -> tuple[str, str] | None:
        """
        Runs a single test case.

        Args:
            test_case (TestCase): The test case to run.
            subitem_code (str): The subitem code for the test case.
            check_manually_on_fail (bool): Whether to check manually on failure.
            disable_comments (bool): Whether to disable comments.
            show_header (bool): Whether to show the header.
            timeout (int): The timeout for the test case.
            run_on_shell (bool): Whether to run the command on the shell.
            redirect_stderr_to_stdout (bool): Whether to redirect stderr to stdout.
            diff_use_pager (bool): Whether to use a pager for the diff.

        Returns:
            tuple[str, str] | None: A tuple containing:
                - "y" if the test passed, "n" if it failed.
                - An empty string if the test passed, or the error message if it failed.
        """
        if show_header:
            p.print_cyan(f"[ Running {subitem_code} ]")

        if not self.is_compiled:
            p.print_red("[ Compilation Failed ]")
            return "n", "Compilation Failed"

        received_stdout, received_stderr, received_return_code = u.run_cmd_with_timeout(
            self.proccess_cmd(test_case),
            stdin=test_case.stdin,
            timeout=timeout,
            run_on_shell=run_on_shell,
            redirect_stderr_to_stdout=redirect_stderr_to_stdout,
        )

        if received_return_code == 124:  # timeout return_code
            p.print_red("[ Time Limit Exceeded ]")
            return "n", "Time Limit Exceeded"

        expected_return_code = test_case.expected_return_code
        expected_stdout = test_case.expected_stdout
        expected_stderr = test_case.expected_stderr

        autochecks_needed = (
            expected_return_code is not None
            or expected_stdout is not None
            or expected_stderr is not None
        )

        comments = []
        awarded = (
            self._check_return_code(
                expected_return_code, received_return_code, comments
            )
            and self._check_stream(
                "stdout",
                expected_stdout,
                received_stdout,
                subitem_code,
                comments,
                diff_use_pager,
            )
            and self._check_stream(
                "stderr",
                expected_stderr,
                received_stderr,
                subitem_code,
                comments,
                diff_use_pager,
            )
        )

        if not autochecks_needed or (check_manually_on_fail and not awarded):
            self.needed_check_manually_on_fail = True
            return None

        comments_string = ""
        if not disable_comments:
            comments_string = ", ".join(comments)

        return ("y" if awarded else "n", comments_string)

    def _check_return_code(
        self,
        expected_return_code: int | None,
        received_return_code: int,
        comments: list[str],
    ):
        """
        Checks if the received return code matches the expected return code.

        Args:
            expected_return_code (int | None): The expected return code.
            received_return_code (int): The received return code.
            comments (list[str]): The list of comments to append messages to.

        Returns:
            bool: True if the return codes match, False otherwise.
        """
        if expected_return_code is None:
            return True

        if expected_return_code != received_return_code:
            message = f"Incorrect Return Code: Expected {expected_return_code} but got {received_return_code}"
            comments.append(message)
            p.print_red(f"[ {message} ]")

            return False

        p.print_green("[ Return code is correct ]")

        return True

    def _check_stream(
        self,
        stream: str,
        expected: str | None,
        received: str | None,
        subitem_code: str,
        comments: list[str],
        diff_use_pager: bool,
    ):
        """
        Checks if the received stream matches the expected stream.

        Args:
            stream (str): The name of the stream (stdout or stderr).
            expected (str | None): The expected stream output.
            received (str | None): The received stream output.
            subitem_code (str): The subitem code for the test case.
            comments (list[str]): The list of comments to append messages to.
            diff_use_pager (bool): Whether to use a pager for the diff.


        Returns:
            bool: True if the streams match, False otherwise.
        """
        if expected is None:
            return True

        if not self.check_stream_correctness(stream, expected, received):
            message = f"{stream} is incorrect"
            comments.append(message)
            p.print_red(f"[ {message} ]")
            u.diff(
                expected,
                received,
                f"Expected {stream}",
                f"Received {stream}",
                use_pager=diff_use_pager,
            )
            return False

        if not self.check_stream_exact_match(stream, expected, received):
            self.items_with_formatting_errors.append(subitem_code)
            p.print_yellow(f"{stream} is correct but formatting is incorrect")
            u.diff(
                expected,
                received,
                f"Expected {stream}",
                f"Received {stream}",
                use_pager=diff_use_pager,
            )
        else:
            p.print_green(f"[ {stream} is correct ]")

        return True

    @abstractmethod
    def check_stream_correctness(
        self, stream: str, expected: str, received: str
    ) -> bool:
        """
        Abstract method to check the correctness of a stream.

        Args:
            stream (str): The name of the stream (stdout or stderr).
            expected (str): The expected stream output.
            received (str): The received stream output.

        Returns:
            bool: True if the streams match, False otherwise.
        """

    @abstractmethod
    def check_stream_exact_match(
        self, stream: str, expected: str, received: str
    ) -> bool:
        """
        Abstract method to check the exact match of a stream.

        Args:
            stream (str): The name of the stream (stdout or stderr).
            expected (str): The expected stream output.
            received (str): The received stream output.

        Returns:
            bool: True if the streams match exactly, False otherwise.
        """

    def get_formatting_status(
        self, deductive: bool = True
    ) -> list[tuple[str, str]] | None:
        """
        Gets the formatting status of the test cases.

        Args:
            deductive (bool): Whether the formatting errors are deductive. Defaults to True.

        Returns:
            list[tuple[str, str]] | None: A list of tuples where each tuple contains:
                - "y" if the formatting was correct, "n" if it was incorrect.
                - An empty string if the formatting was correct, or the error message if it was incorrect.
        """
        if self.needed_check_manually_on_fail:
            p.print_yellow("[ Do manual check for spacing and formatting errors ]")
            return None

        if (
            len(self.items_with_formatting_errors)
            <= self.allowed_formatting_errors_count
        ):
            p.print_green("[ Spacing and formatting was correct ]")
            return [("n" if deductive else "y", "")]

        p.print_red("[ There were errors in spacing and formatting ]")
        return [
            (
                "y" if deductive else "n",
                f"Errors in spacing and formatting in: {', '.join(self.items_with_formatting_errors)}",
            )
        ]

    def proccess_cmd(self, test_case: TestCase):
        """
        Processes the command for a test case.

        Args:
            test_case (TestCase): The test case to process.

        Returns:
            str: The command to run the test case.
        """
        return test_case.cmd


class WhitespaceTestRunner(TestRunner):
    """Class that runs tests and compares streams by stripping all whitespace."""

    def check_stream_correctness(self, _, expected: str, received: str) -> bool:
        """
        Checks the correctness of a stream by stripping all whitespace.

        Args:
            expected (str): The expected stream output.
            received (str): The received stream output.

        Returns:
            bool: True if the streams match after stripping whitespace, False otherwise.
        """
        stripped_expected = expected.replace(" ", "").replace("\n", "")
        stripped_received = received.replace(" ", "").replace("\n", "")

        return stripped_expected == stripped_received

    def check_stream_exact_match(self, _, expected: str, received: str) -> bool:
        """
        Checks the exact match of a stream.

        Args:
            expected (str): The expected stream output.
            received (str): The received stream output.

        Returns:
            bool: True if the streams match exactly, False otherwise.
        """
        return expected == received
