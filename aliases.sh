#!/bin/bash

function check-grades() {
    /bin/vim "$PYGRADER_ROOT/grades/$HW/grades/$1.json"
}

function grade() {
    $PYGRADER_ROOT/grade.py grade "$HW" -T "$1" -c $2
}

function inspect() {
    $PYGRADER_ROOT/grade.py inspect "$HW" "$1"
}

function prettygrades() {
    $PYGRADER_ROOT/grade.py dump $HW -T "$@"
}

function stats() {
    $PYGRADER_ROOT/grade.py stats $HW "$@"
}

function progress() {
    $PYGRADER_ROOT/grade.py status "$HW" -T "$@"
}

function regrade() {
    $PYGRADER_ROOT/grade.py grade -r "$HW" "$1" -c $2
}

function regrade-ta() {
    $PYGRADER_ROOT/grade.py grade -r "$HW" -T "$1" -c $2
}

function run-moss() {
    $PYGRADER_ROOT/grade.py moss "$HW"
}

function submission-info() {
    $PYGRADER_ROOT/grade.py submission-info "$HW" "$1"
}

function flag-for-plagiarism() {
    $PYGRADER_ROOT/grade.py plagiarism "$HW" "$@"
}

function deductions() {
    $PYGRADER_ROOT/grade.py deductions "$HW" "$@"
}

function upload-grades() {
    $PYGRADER_ROOT/canvas_scripts.py upload "$HW" "$@"
}

function upload-late-days() {
    $PYGRADER_ROOT/canvas_scripts.py upload late_days "$@"
}
