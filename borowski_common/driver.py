"""borowski_common/driver.py: Grading driver"""

from __future__ import annotations

from collections.abc import Iterable

from borowski_common.command_modules import (
    DeductionsModule,
    GetSubmissionInfoModule,
    PlagiarismModule,
    RunMossModule,
)
from common.command_modules import CommandModule
from common.loader import load_and_run_pygrader


def run_borowski_pygrader(modules: Iterable[CommandModule] | None = None):
    """
    Runs the Borowski pygrader framework with a set of custom command modules.

    This function initializes and runs the pygrader framework with the following modules:
    - UploadGradesModule: Uploads grades to the system.
    - RunMossModule: Runs MOSS (Measure of Software Similarity) for plagiarism detection.
    - GetSubmissionInfoModule: Retrieves submission information.
    - PlagiarismModule: Flags submissions for plagiarism.
    - DeductionsModule: Manages deductions for submissions.
    - EdRegradeRequestModule: Handles regrade requests.
    - EdGradesPostModule: Posts grades to Ed.

    The function uses the `load_and_run_pygrader` function to load and run these modules.
    """
    if not modules:
        modules = []

    load_and_run_pygrader(
        [
            RunMossModule(),
            GetSubmissionInfoModule(),
            PlagiarismModule(),
            DeductionsModule(),
            *modules,
        ]
    )
