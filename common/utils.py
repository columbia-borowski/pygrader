"""common/utils.py: Grading helper functions"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable

from common import printing as p

KEDR_START = "sudo kedr start {}"
INSMOD = "sudo insmod {}"
RMMOD = "sudo rmmod {}"
KEDR_STOP = "sudo kedr stop {}"
DMESG = "sudo dmesg"
DMESG_C = "sudo dmesg -C"
MAKE = "make clean > /dev/null 2>&1 ; make {}"

# This template will extract all text in [start, end]
SED_BETWEEN = "sed -n '/{0}/,/{1}/p' {2}"

# This template will extract all text in [start, EOF)
SED_TO_END = "sed -n '/{0}/,$p' {1}"


def cmd_popen(cmd: str):
    """Uses subprocess.Popen to run a command, returns the object."""
    return subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        universal_newlines=True,
    )


def cmd_communicate(process, exclude: list[str]) -> tuple[str, str]:
    out, err = process.communicate()
    out = "".join(ch for ch in out if ch not in set(exclude))
    err = "".join(ch for ch in err if ch not in set(exclude))
    return out, err


def run_cmd(cmd: str, silent: bool = False, shell: bool = True, **kwargs) -> int:
    """Runs cmd and returns the status code."""
    return subprocess.run(cmd, shell=shell, capture_output=silent, **kwargs).returncode


def is_dir(path: str):
    """Checks if path is a directory"""
    if not os.path.isdir(path):
        raise ValueError(f"{path} is not a directory")


def create_dir(name):
    """Wrapper around mkdir"""
    if not os.path.isdir(name):
        access = 0o700
        try:
            os.mkdir(name, access)
        except OSError:
            sys.exit(f"Creation of the directory {name} failed")
        else:
            print(f"Successfully created the directory {name}")


def file_exists(fname: str) -> bool:
    """Checks if fname is a file"""
    return os.path.isfile(fname)


def dir_exists(dir_path: str) -> bool:
    """Checks if dir_path exists (and is a directory)."""
    return os.path.isdir(dir_path)


def prompt_overwrite(dir_name: str, dir_path: str) -> bool:
    while True:
        try:
            res = input(f"{dir_name} is already set up. Overwrite? [y/n]: ")
        except EOFError:
            print("^D")
        if res == "n":
            return False
        if res == "y":
            break

    shutil.rmtree(dir_path)
    return True


def prompt_file_name(file_list: list[str] | None = None) -> str:
    """Prompts the user for a file to open"""
    ls_output = os.listdir() if not file_list else file_list

    for i, file in enumerate(ls_output):
        p.print_yellow(f"({i + 1}) {file}")

    while True:
        try:
            select = int(input("Enter choice number or Ctrl-D: "))
        except ValueError:
            continue

        if 0 < select <= len(ls_output):
            return ls_output[select - 1]


def get_file(fname: str) -> str:
    """Checks if fname is in pwd. If not, prompts grader with choices"""
    if file_exists(fname):
        return fname

    p.print_red("_" * 85)
    p.print_red(f"Couldn't find {fname}! Did the student name it something else?")
    try:
        submission_name = prompt_file_name()
    except EOFError as e:
        raise Exception(f"Couldn't get {fname}") from e

    p.print_red("‾" * 85)
    return submission_name


def concat_files(outfile: str, file_types: list[str]) -> str:
    """Concats all relevant files in the cwd into 1 file called `outfile`."""
    if file_exists(outfile):
        return outfile
    file_header = "=" * 80 + "\n{}\n" + "=" * 80 + "\n"
    with open(outfile, "w+", encoding="utf-8") as o:
        for fname in os.listdir():
            if fname != outfile and fname[-2:] in file_types:
                o.write(file_header.format(fname))
                with open(fname, "r", encoding="utf-8") as src:
                    shutil.copyfileobj(src, o)
    return outfile


def remove_file(fname: str):
    if file_exists(fname):
        os.remove(fname)
    else:
        p.print_red(f"[ OPPS - {fname} does not exist ]")


def extract_between(
    fname: str, start: str, end: str | None = None, capture: bool = False
):
    """Prints the text in fname that's in between start and end"""
    if not end:
        sed_command = SED_TO_END.format(start, fname)
    else:
        sed_command = SED_BETWEEN.format(start, end, fname)
    return subprocess.run(
        sed_command, shell=True, capture_output=capture, universal_newlines=True
    )


def extract_function(file_name: str, funct_name: str, index: int = 0) -> str:
    if not file_exists(file_name):
        return ""
    stack = []
    started = False
    funct = ""
    block_comment_count = 0
    count = 0
    with open(file_name, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            if "/*" in line:
                block_comment_count += 1
            if "*/" in line:
                block_comment_count -= 1

            if block_comment_count > 0 or (not funct_name in line and not started):
                continue

            is_prototype = "{" not in line and ";" in line
            is_line_comment = "//" in line
            if funct_name in line and not is_prototype and not is_line_comment:
                if count == index:
                    started = True
                count += 1

            funct += line
            if "{" in line:
                stack.append("{")

            if "}" in line:
                stack.pop()
                if not stack:
                    break

    return funct


def grep_file(fname: str, pattern: str, padding: int = 0) -> int:
    """Greps fname for pattern and returns the status code

    NOTE: Grep output is dumped to the shell."""
    fname = get_file(fname)
    padding_opt = "" if not padding else f"-C {padding}"
    cmd = f"grep --color=always -n {padding_opt} -E '{pattern}' {fname} "
    return subprocess.run(cmd, shell=True).returncode


def grep_string(words: str, pattern: str, padding: int = 0) -> int:
    """Greps fname for pattern and returns the status code

    NOTE: Grep output is dumped to the shell."""
    padding_opt = "" if not padding else f"-C {padding}"
    cmd = f"echo {shlex.quote(words)} | grep --color=always {padding_opt} -E '^|{pattern}'"
    return subprocess.run(cmd, shell=True).returncode


def inspect_string(
    s: str, pattern: str | None = None, use_pager: bool = True, lang: str | None = None
):
    if not lang:
        lang = "txt"

    bat_str = f"bat --color=always -l {lang}"
    grep_str = (
        f"GREP_COLORS='ms=01;91;107' grep --color=always "
        f"-E '^|{pattern}' {'| less -R' if use_pager else ''}"
    )
    if pattern:
        cmd = f"{bat_str} | {grep_str}"
    else:
        cmd = f"{bat_str} {'--paging=never' if not use_pager else ''}"

    bat = cmd_popen(cmd)
    print(bat.communicate(input=s)[0])


def grep_includes(fname: str, pattern: str) -> set[str]:
    # file_check = get_file(fname)
    # https://linuxhint.com/run-grep-python/
    found_set = set()
    with open(fname, "r", encoding="utf-8") as file_open:
        for line in file_open:
            line = line[0 : len(line) - 1 :]
            if re.search(pattern, line):
                # https://www.geeksforgeeks.org/pattern-matching-python-reg ex/
                guard = re.search(r"(?<=#include\s<).*(?=>)", line)
                if not guard:
                    guard = re.search(r'(?<=#include\s").*(?=")', line)

                if guard:
                    guard = guard.group()
                    found_set.add(guard)
    return found_set


def inspect_file(fname: str, pattern: str | None = None, use_pager: bool = True):
    """Displays 'fname', w/ optional pattern highlighted, optionally in less"""
    name = get_file(fname)
    bat_str = f"bat --color=always {name}"
    grep_str = (
        f"GREP_COLORS='ms=01;91;107' grep --color=always "
        f"-E '^|{pattern}' {'| less -R' if use_pager else ''}"
    )
    if pattern:
        cmd = f"{bat_str} | {grep_str}"
    else:
        cmd = f"bat {name} {'--paging=never' if not use_pager else ''}"
    subprocess.run(cmd, shell=True)


def inspect_directory(
    files: list[str], pattern: str | None = None, banner_fn: Callable = None
):
    """Prompt the user for which file to inspect with optional pattern.

    Args:
        files: list of files in the current directory
            (as reported by os.listdir(os.getcwd())).
        pattern: Optional pattern to highlight in the files.
        banner_fn: Optional function to call before presenting choices
            (used to print some sort of banner).
    """
    while True:
        if banner_fn:
            banner_fn()
        for i, file in enumerate(files):
            p.print_yellow(f"({i + 1}) {file}")
        p.print_yellow(f"({len(files) + 1}) " f"{p.CVIOLET2}exit{p.CEND}")
        try:
            choice = int(input(f"{p.CBLUE2}Choice: {p.CEND}"))
        except (ValueError, EOFError):
            continue

        if 0 < choice <= len(files):
            inspect_file(files[choice - 1], pattern)
        elif choice == len(files) + 1:
            break
        else:
            continue


def compile_code(makefile_target: str = "", silent: bool = False):
    """Compiles the current directory (either with Make or manually)"""
    ls_output = os.listdir()
    if "Makefile" not in ls_output and "makefile" not in ls_output:
        # Let's let the grader figure it out
        os.system("bash")
    if not silent:
        p.print_cyan("[ Compiling... ]")
    silent_str = " > /dev/null 2>&1" if silent else ""
    ret = subprocess.call(MAKE.format(makefile_target) + silent_str, shell=True)

    # if ret != 0:
    #     p.print_red("[ OOPS ]")
    # else:
    #     p.print_green("[ OK ]")

    return ret


def insert_mod(mod: str, kedr: bool = True):
    """Calls insmod with mod and optionally attaches KEDR"""
    if subprocess.call(DMESG_C.split()) != 0:
        pass

    if kedr:
        p.print_cyan(f"[ Starting KEDR for {mod} ]")
        if subprocess.call(KEDR_START.format(mod).split()) != 0:
            p.print_red("[ OOPS ]")
        else:
            p.print_green("[ OK ]")

    p.print_cyan(f"[ Inserting module {mod} ]")
    if subprocess.call(INSMOD.format(mod).split()) != 0:
        p.print_red("[ OOPS ]")
    else:
        p.print_green("[ OK ]")


def remove_mod_silent(mod: str, kedr: bool = True):
    subprocess.run(
        RMMOD.format(mod).split(), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )
    if kedr:
        subprocess.run(
            KEDR_STOP.format(mod).split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )


def remove_mod(mod: str, dmesg: bool = True, kedr: bool = True):
    """Performs module removal

    Calls rmmod with mod, optionally detaches KEDR, and optionally dumps the
    kernel log buffer using dmesg
    """
    p.print_cyan(f"[ Removing module {mod} ]")
    if subprocess.call(RMMOD.format(mod).split()) != 0:
        p.print_red("[ OOPS ]")
    else:
        p.print_green("[ OK ]")

    if kedr:
        p.print_cyan(f"[ Stopping KEDR for {mod} ]")
        if subprocess.call(KEDR_STOP.format(mod).split()) != 0:
            p.print_red("[ OOPS ]")
        else:
            p.print_green("[ OK ]")
    if dmesg:
        p.print_cyan("[ Dumping kernel log buffer... ]")
        os.system(DMESG)


def compare_values(
    observed: int, expected: int, desc: str, silent: bool = False
) -> bool:
    """Compares two values and (optionally) prints comparison results.

    Args:
        observed: Value observed
        expected: Expected value
        desc: The name of what we're comparing
        silent: Whether or not to print results.

    Returns:
        bool representing whether or not the values were the same.
    """
    if observed == expected:
        if not silent:
            p.print_green(f"[ OK: Got {observed}/{expected} {desc} ]")

        return True

    if not silent:
        p.print_red(f"[ FAIL: Got {observed}/{expected} {desc} ]")

    return False


def prompt_continue(ptext: str = "[ Press enter to continue... ]"):
    input(f"{p.CCYAN}{ptext}{p.CEND}")


def tabs_to_spaces(text: str) -> str:
    """Converts tabs to spaces"""
    return text.expandtabs(4)


def exit_with_not_supported_msg():
    p.print_red("[ Not Supported ]")
    sys.exit(1)


def open_shell():
    # (pygrader)user@host:pwd $
    prompt = (
        f"{p.CGREEN}({p.CYELLOW}pygrader{p.CGREEN}){p.CEND}"
        f":{p.CBLUE}\\w{p.CCYAN} \\${p.CEND} "
    )

    p.print_red("[ ^D/exit when done ]")
    os.system(f"PROMPT_COMMAND='PS1=\"{prompt}\"; unset PROMPT_COMMAND' " f"bash")
