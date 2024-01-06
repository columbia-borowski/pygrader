"""common/printing.py: Colored output helpers"""

CEND = "\33[0m"
CBOLD = "\33[1m"
CITALIC = "\33[3m"
CURL = "\33[4m"
CBLINK = "\33[5m"
CBLINK2 = "\33[6m"
CSELECTED = "\33[7m"

CBLACK = "\33[30m"
CRED = "\33[31m"
CGREEN = "\33[32m"
CYELLOW = "\33[33m"
CBLUE = "\33[34m"
CVIOLET = "\33[35m"
CBEIGE = "\33[36m"
CWHITE = "\33[37m"
CORANGE = "\33[38;5;208m"


CBLACKBG = "\33[40m"
CREDBG = "\33[41m"
CGREENBG = "\33[42m"
CYELLOWBG = "\33[43m"
CBLUEBG = "\33[44m"
CVIOLETBG = "\33[45m"
CBEIGEBG = "\33[46m"
CWHITEBG = "\33[47m"

CGREY = "\33[90m"
CRED2 = "\33[91m"
CGREEN2 = "\33[92m"
CYELLOW2 = "\33[93m"
CBLUE2 = "\33[94m"
CVIOLET2 = "\33[95m"
CCYAN = "\33[96m"
CGRAYL = "\33[97m"

CGREYBG = "\33[100m"
CREDBG2 = "\33[101m"
CGREENBG2 = "\33[102m"
CYELLOWBG2 = "\33[103m"
CBLUEBG2 = "\33[104m"
CVIOLETBG2 = "\33[105m"
CBEIGEBG2 = "\33[106m"
CWHITEBG2 = "\33[107m"


def print_red(s):
    """Prints s in red"""
    print(f"{CRED2}{s}{CEND}")


def print_orange(s):
    """Prints s in red"""
    print(f"{CORANGE}{s}{CEND}")


def print_green(s):
    """Prints s in green"""
    print(f"{CGREEN2}{s}{CEND}")


def print_yellow(s):
    """Prints s in yellow"""
    print(f"{CYELLOW2}{s}{CEND}")


def print_magenta(s):
    """Prints s in magenta"""
    print(f"{CVIOLET2}{s}{CEND}")


def print_purple(s):
    """Prints s in purple"""
    print(f"{CVIOLET}{s}{CEND}")


def print_cyan(s):
    """Prints s in cyan"""
    print(f"{CCYAN}{s}{CEND}")


def print_light_gray(s):
    """Prints s in light gray"""
    print(f"{CGRAYL}{s}{CEND}")


def print_line():
    print_cyan("-" * 85)


def print_double():
    print_cyan("=" * 85)


def print_intro(submitter, hw, code):
    print_double()
    print(
        f"{CCYAN}Name:{CEND} {CVIOLET2}{submitter}{CEND}  {CCYAN}HW:{CEND} "
        f"{CVIOLET2}{hw}{CEND}  {CCYAN}Rubric Code:{CEND} "
        f"{CVIOLET2}{code}{CEND}"
    )
    print_double()


def print_between_cyan_line(msg):
    print_line()
    print_cyan(msg)
    print_line()


def print_outro(table_item):
    print_line()
    print_green(f"End test of {table_item}")
    print_double()
