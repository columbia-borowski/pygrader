"""borowski_common/quizzes.py: Creates an html version of quiz file"""

from __future__ import annotations

import os

from borowski_common.canvas import Canvas
from borowski_common.constants import QUIZZES_ROOT, SEMESTER_CODE


class QuizDownloader:
    """
    A class to download a quiz from Canvas and create an HTML version of it.

    Attributes:
        canvas_quiz_id (int): The ID of the quiz on Canvas.
        quiz_dir (str): The directory where the quiz HTML file will be saved.

    Methods:
        download() -> str: Downloads the quiz from Canvas and creates an HTML file.
    """

    def __init__(self, canvas_quiz_id: int):
        """
        Initializes the QuizDownloader with the given Canvas quiz ID.

        Args:
            canvas_quiz_id (int): The ID of the quiz on Canvas.
        """
        self.canvas_quiz_id = canvas_quiz_id

        if not os.path.isdir(QUIZZES_ROOT):
            os.mkdir(QUIZZES_ROOT, 0o700)
        os.chmod(QUIZZES_ROOT, 0o711)

        self.quiz_dir = os.path.join(QUIZZES_ROOT, SEMESTER_CODE)
        if not os.path.isdir(self.quiz_dir):
            os.mkdir(self.quiz_dir, 0o700)
        os.chmod(self.quiz_dir, 0o711)

    def download(self) -> str:
        """
        Downloads the quiz from Canvas and creates an enhanced HTML file with styled quiz content.

        Returns:
            str: The path to the created HTML file.
        """
        quiz = Canvas().get_course().get_quiz(self.canvas_quiz_id)
        questions = quiz.get_questions()

        # Adding basic styling for the HTML content
        style = """
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 20px;
                color: #333;
                background-color: #f9f9f9;
            }
            h1 {
                font-size: 2em;
                color: #0056b3;
                margin-bottom: 20px;
            }
            h3 {
                font-size: 1.5em;
                color: #333;
                margin: 20px 0 10px;
            }
            h4 {
                font-size: 1.2em;
                color: #0056b3;
                margin: 10px 0;
            }
            ul {
                list-style-type: disc;
                margin-left: 20px;
            }
            li {
                margin: 5px 0;
            }
            hr {
                border: 0;
                height: 1px;
                background: #ddd;
                margin: 30px 0;
            }
            .question {
                padding: 15px;
                background: #fff;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-bottom: 20px;
            }
            .answer {
                padding: 10px;
                background: #f1f1f1;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        </style>
        """

        # Building HTML content with embedded styles
        content = f"<!DOCTYPE html><html><head>{style}<title>{quiz.title}</title></head><body>"
        content += f"<h1>{quiz.title}</h1><hr />"

        i = 1
        for question in questions:
            content += '<div class="question">'
            if question.question_type != "text_only_question":
                content += f"<h3>Question {i}</h3>"
                i += 1

            content += f"<p>{question.question_text}</p>"
            if question.question_type == "multiple_choice_question":
                content += "<ul>"
                for answer in question.answers:
                    content += f"<li>{answer['text']}</li>"
                content += "</ul>"

            if question.question_type != "text_only_question":
                content += '<div class="answer"><h4>Answer(s):</h4><ul>'
                for answer in question.answers:
                    if answer["weight"] > 0:
                        content += f"<li>{answer['text'] or answer['html']}</li>"

                content += "</ul></div>"

            content += "</div><hr />"

        content += "</body></html>"

        quiz_file = os.path.join(self.quiz_dir, f"{self.canvas_quiz_id}.html")
        with open(quiz_file, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(quiz_file, 0o644)

        return quiz_file
