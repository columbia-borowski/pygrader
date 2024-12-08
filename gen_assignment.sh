#!/bin/bash

if [ "$#" -lt 1 ]; then
	echo "Usage: $0 <assignment name>" >&2
	exit 1
fi

cd "$(dirname "$0")"

ASS="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
if [ -d "$ASS" ]; then
	read -p "Overwrite '$ASS'? [y/N]: " RESP
	if [ "$RESP" == y ] || [ "$RESP" == Y ]; then
		rm -rf "$ASS"
	else
		exit 1
	fi
fi

mkdir "$ASS" || exit
cp rubric.json.in "$ASS/rubric.json"
cp grader.py.in "$ASS/grader.py"
sed -i '' "s/ASSIGNMENT/$ASS/g" "$ASS/grader.py"
