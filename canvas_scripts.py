#!/usr/bin/env python3
"""canvas_scripts.py: scripts that deal with canvas"""

from borowski_common.canvas_modules import (
    ClassRankModule,
    DownloadQuizModule,
    FinalGradesModule,
    MidtermModule,
    QuizExtensionsModule,
    QuizRegradesModule,
    UploadGradesModule,
)
from common.loader import load_and_run_modules

if __name__ == "__main__":
    load_and_run_modules(
        (
            UploadGradesModule(),
            ClassRankModule(),
            MidtermModule(),
            FinalGradesModule(),
            QuizExtensionsModule(),
            QuizRegradesModule(),
            DownloadQuizModule(),
        )
    )
