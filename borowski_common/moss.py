"""borowski_common/moss.py: Service to run moss on submissions"""

from __future__ import annotations

import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor

import requests
import shortuuid
from bs4 import BeautifulSoup
from mosspy import Moss

from borowski_common import utils as u
from borowski_common.constants import (
    MOSS_ROOT,
    MOSS_USERID,
    PYGRADER_ROOT,
    SEMESTER_CODE,
)
from common import printing as p


class MossRunner:
    """
    A class to run MOSS (Measure of Software Similarity) on student submissions.

    Attributes:
        hw_name (str): The name of the homework assignment.
        moss (Moss): An instance of the Moss class for running MOSS.
        submitted_files (list[str]): A list of submitted files to be checked for similarity.
        hwN_dir (str): The directory for the current homework assignment.
        semester_dir (str): The directory for the current semester.
    """

    def __init__(
        self,
        hw_name: str,
        language: str,
        submitted_files: list[str],
    ):
        """
        Initializes the MossRunner with the homework name, language, and submitted files.

        Args:
            hw_name (str): The name of the homework assignment.
            language (str): The programming language of the submissions.
            submitted_files (list[str]): A list of submitted files to be checked for similarity.
        """
        self.hw_name = hw_name
        self.moss = Moss(MOSS_USERID, language)
        self.submitted_files = submitted_files

        if not os.path.isdir(MOSS_ROOT):
            os.mkdir(MOSS_ROOT, 0o700)
        os.chmod(MOSS_ROOT, 0o711)

        self.hwN_dir = os.path.join(MOSS_ROOT, hw_name)
        if not os.path.isdir(self.hwN_dir):
            os.mkdir(self.hwN_dir, 0o700)

        self.semester_dir = os.path.join(self.hwN_dir, SEMESTER_CODE)
        if os.path.isdir(self.semester_dir) and not u.prompt_overwrite(
            SEMESTER_CODE, self.semester_dir
        ):
            p.print_red(f"[ Setup incomplete. {SEMESTER_CODE} already exists. ]")
            return

        os.mkdir(self.semester_dir, 0o700)

    def add_template_dir(self, templates_dir: str):
        """
        Adds template files to the MOSS base files.

        Args:
            templates_dir (str): The directory containing template files.
        """
        for root, _, filenames in os.walk(templates_dir):
            for filename in filenames:
                self.moss.addBaseFile(os.path.join(root, filename), filename)

    def add_student(self, student: str, submission_dir: str):
        """
        Adds a student's submission to the MOSS files.

        Args:
            student (str): The student's identifier.
            submission_dir (str): The directory containing the student's submission files.
        """
        student_dir = os.path.join(self.semester_dir, student)
        os.mkdir(student_dir, 0o700)

        for file in self.submitted_files:
            full_path = os.path.join(submission_dir, file)

            if not os.path.isfile(full_path):
                p.print_red(f"[ File not found: {full_path} ]")
                continue

            if os.path.getsize(full_path) <= 0:
                p.print_yellow(f"[ Empty file: {full_path} ]")
                continue

            dest_path = os.path.join(student_dir, file)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy(full_path, dest_path)

    def run(self) -> str:
        """
        Runs MOSS on the added files and downloads the report.

        Returns:
            str: The path to the downloaded report.
        """
        p.print_between_cyan_line("Uploading to MOSS")

        os.chdir(self.hwN_dir)
        for file in self.submitted_files:
            self.moss.addFilesByWildcard(f"**/{file}")

        url = self.moss.send().strip("/")
        if url == "" or "Error:" in url:
            p.print_red(f"[ {url if url else 'Unknown Error'} ]")
            return {}

        p.print_green(f"[ Report URL: {url} ]")
        p.print_cyan("[ Downloading Report ]")

        os.chdir(MOSS_ROOT)
        report_download_path = os.path.join("reports", SEMESTER_CODE, self.hw_name)
        if os.path.exists(report_download_path):
            shutil.rmtree(report_download_path)
        self._create_directories(report_download_path)

        return ReportDownloader(url, report_download_path).download()

    def _create_directories(self, path):
        """
        Creates directories for the given path.

        Args:
            path (str): The path for which to create directories.
        """
        directories = path.split(os.sep)
        current_path = ""
        for directory in directories:
            current_path = os.path.join(current_path, directory)
            if not os.path.exists(current_path):
                os.mkdir(current_path)
                os.chmod(current_path, 0o711)


class ReportDownloader:
    """
    A class to download MOSS reports.

    Attributes:
        report_url (str): The URL of the MOSS report.
        download_path (str): The path to download the report to.
    """

    def __init__(self, report_url, download_path):
        """
        Initializes the ReportDownloader with the report URL and download path.

        Args:
            report_url (str): The URL of the MOSS report.
            download_path (str): The path to download the report to.
        """
        self.report_url = report_url
        self.download_path = download_path

    def download(self):
        """
        Downloads the MOSS report and returns the manifest.

        Returns:
            dict: A manifest of the downloaded report.
        """
        bitmaps_path = os.path.join(self.download_path, "bitmaps")
        shutil.copytree(
            os.path.join(PYGRADER_ROOT, "misc/moss_bitmaps"),
            bitmaps_path,
        )
        os.chmod(bitmaps_path, 0o711)
        for file in os.listdir(bitmaps_path):
            os.chmod(os.path.join(bitmaps_path, file), 0o644)

        main_page_req = requests.get(self.report_url, allow_redirects=True, timeout=10)
        main_page_path = os.path.join(self.download_path, "index.html")

        matches = set()
        manifest = {}
        with open(main_page_path, "w", encoding="utf-8") as main_page:
            html_content = main_page_req.text
            html_content = re.sub(
                rf"{self.report_url}/match(\d+)\.html", r"match\1", html_content
            )

            soup = BeautifulSoup(html_content, features="lxml")
            table = soup.find("table")

            filtered_rows = []
            for row in table.find_all("tr")[1:]:
                columns = row.find_all("td")
                file1, file2 = columns[0].text.strip(), columns[1].text.strip()
                if SEMESTER_CODE in file1 or SEMESTER_CODE in file2:
                    match_name = row.find("a")["href"]
                    match_id = shortuuid.uuid()
                    matches.add((match_name, match_id))

                    for a in row.find_all("a"):
                        a["href"] = match_id
                    filtered_rows.append(row)

                    manifest[match_id] = []
                    if SEMESTER_CODE in file1:
                        manifest[match_id].append(file1.split("/")[1])
                    if SEMESTER_CODE in file2:
                        manifest[match_id].append(file2.split("/")[1])

            filtered_table = "<table>"
            filtered_table += str(table.find("tr"))
            for row in filtered_rows:
                filtered_table += str(row)
            filtered_table += "</table>"

            soup.find("table").replace_with(
                BeautifulSoup(filtered_table, "html.parser")
            )

            main_page.write(soup.prettify())

        os.chmod(main_page_path, 0o644)

        pages = []
        for match_name, match_id in matches:
            match_path = os.path.join(self.download_path, match_id)

            os.mkdir(match_path)
            os.chmod(match_path, 0o711)

            pages.extend(
                (
                    (f"{match_name}.html", match_path, "index.html"),
                    (f"{match_name}-top.html", match_path),
                    (f"{match_name}-0.html", match_path),
                    (f"{match_name}-1.html", match_path),
                )
            )

        with ThreadPoolExecutor() as executor:
            executor.map(lambda args: self._download_page(*args), pages)

        return manifest

    def _download_page(
        self,
        file_name: str,
        match_path: str,
        download_file_name: str | None = None,
    ):
        """
        Downloads a single page of the MOSS report.

        Args:
            file_name (str): The name of the file to download.
            match_path (str): The path to save the downloaded file.
            download_file_name (str | None): The name to save the downloaded file as. Defaults to None.
        """
        download_path = os.path.join(match_path, download_file_name or file_name)
        req = requests.get(
            f"{self.report_url}/{file_name}", allow_redirects=True, timeout=10
        )
        with open(download_path, "wb") as file:
            content = req.content.replace(
                bytes(f"{self.report_url}/", "utf-8"), b""
            ).replace(
                bytes("http://moss.stanford.edu/bitmaps/", "utf-8"), b"../bitmaps/"
            )

            file.write(content)
        os.chmod(download_path, 0o644)
