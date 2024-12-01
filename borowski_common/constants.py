"""borowski_common/constants.py: Environment variables"""

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pytz import timezone

load_dotenv(find_dotenv())

# Paths
PYGRADER_ROOT = Path(os.path.abspath(__file__)).parent.parent
GRADES_ROOT = os.path.join(PYGRADER_ROOT, "grades")
MOSS_ROOT = os.path.join(PYGRADER_ROOT, "moss")
QUIZZES_ROOT = os.path.join(PYGRADER_ROOT, "quizzes")

# Course Info
SEMESTER_CODE = os.environ.get("SEMESTER_CODE")

# Late Days
LATE_DAYS_FILE = (
    os.path.join(GRADES_ROOT, os.environ.get("LATE_DAYS_FILE"))
    if os.environ.get("LATE_DAYS_FILE")
    else None
)
TOTAL_LATE_DAYS = int(os.environ.get("TOTAL_LATE_DAYS", "0"))

# Canvas
API_URL = os.environ.get("API_URL")
API_KEY = os.environ.get("API_KEY")
COURSE_ID = os.environ.get("COURSE_ID")
LATE_DAYS_ASSIGNMENT_ID = os.environ.get("LATE_DAYS_ASSIGNMENT_ID", "")

# ED
ED_API_KEY = os.environ.get("ED_API_KEY", "")
ED_COURSE_ID = int(os.environ.get("ED_COURSE_ID"))
ED_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "Authorization": f"Bearer {ED_API_KEY}",
}

# MOSS
MOSS_USERID = os.environ.get("MOSS_USERID", "")
MOSS_REPORT_URL = os.environ.get("MOSS_REPORT_URL", "")

# ODS/CARDS
ACCOMMODATIONS_SHEET_ID = os.environ.get("ACCOMMODATIONS_SHEET_ID")

# Timezone
NYZ_TZ = timezone("America/New_York")
