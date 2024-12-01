"""borowski_common/utils.py: Grading helper functions"""

from __future__ import annotations

import os
import shlex
import subprocess

from common.utils import *

HTML_ESCAPES = {'"': "&quot;", "'": "&#39;", "<": "&lt;", ">": "&gt;"}


def run_cmd_with_timeout(
    cmd: str,
    stdin: str | None = None,
    timeout: int | None = None,
    run_on_shell: bool = False,
    redirect_stderr_to_stdout: bool = False,
) -> tuple[str, str, int]:
    stdout = subprocess.PIPE
    stderr = subprocess.PIPE
    if redirect_stderr_to_stdout:
        stderr = subprocess.STDOUT

    if run_on_shell:
        stdout = None
        stderr = None

    with subprocess.Popen(
        cmd,
        shell=True,
        executable="/bin/bash",
        stdin=subprocess.PIPE if not run_on_shell else None,
        stdout=stdout,
        stderr=stderr,
        close_fds=True,
        universal_newlines=True,
    ) as process:
        try:
            stdout_data, stderr_data = process.communicate(input=stdin, timeout=timeout)
            return (
                stdout_data if stdout_data else "",
                stderr_data if stderr_data else "",
                process.returncode,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            return "", "", 124


def prompt_yn(prompt: str, default_y: bool = False) -> bool:
    """Prompt the user for a yes or no answer"""
    prompt = f"{prompt} [Y/n] " if default_y else f"{prompt} [y/N] "
    while True:
        answer = input(prompt).lower()
        if not answer:
            return default_y
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter y or n.")


def print_with_bat(text: str = "", language: str = "c", file=None):
    """Prints text with bat syntax highlighting"""
    if file:
        subprocess.call(f"bat {file} -l c --paging never --color=always --", shell=True)
    else:
        subprocess.call(
            f" echo {shlex.quote(text)} | bat -l {language} -n --color=always",
            shell=True,
        )


# pylint: disable=undefined-variable


def grep_and_prompt(file: str, pattern: str, padding: int = 0):
    """Grep a file and prompt the user to view it"""
    grep_file(file, pattern=pattern, padding=padding)
    if prompt_yn("View file?"):
        inspect_file(file, pattern=pattern)


def diff(
    expected_output: str | None = None,
    received_output: str | None = None,
    expected_label="Expected",
    received_label="Received",
):
    if not expected_output:
        expected_output = ""

    if not received_output:
        received_output = ""

    with open(expected_label, "w", encoding="utf-8") as expected_file:
        expected_file.write(expected_output)

    with open(received_label, "w", encoding="utf-8") as received_file:
        received_file.write(received_output)

    run_cmd(f"delta -s --hunk-header-style omit '{expected_label}' '{received_label}'")

    os.remove(expected_label)
    os.remove(received_label)


def grep_string_multiple(
    words: str, patterns_dict: dict[str, list[str]], padding: int = 0
):
    """Greps string for patterns

    NOTE: Grep output is dumped to the shell."""
    padding_opt = "" if not padding else f"-C {padding}"
    cmd = f"echo {shlex.quote(words)}"
    for color, patterns in patterns_dict.items():
        for pattern in patterns:
            cmd += f" | GREP_COLORS='mt={color}' grep --color=always {padding_opt} -E '^|{pattern}'"

    subprocess.run(cmd, shell=True)


def html_escape(htmlstring):
    htmlstring = htmlstring.replace("&", "&amp;")
    for seq, esc in HTML_ESCAPES.items():
        htmlstring = htmlstring.replace(seq, esc)
    return htmlstring
