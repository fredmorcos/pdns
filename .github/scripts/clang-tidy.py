#!/usr/bin/env python3

"""Clang-tidy to Github Actions annotations converter.

Convert the YAML file produced by clang-tidy-diff containing warnings and
suggested fixes to Github Actions annotations.

"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml


def create_argument_parser():
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert clang-tidy output to Github Actions"
    )
    parser.add_argument(
        "--fixes-file",
        type=str,
        required=True,
        help="Path to the clang-tidy fixes YAML",
    )
    # parser.add_argument(
    #     "--prefix-dir",
    #     type=str,
    #     required=True,
    #     help="Project subdirectory",
    # )
    return parser.parse_args()


def get_line_from_offset(file_contents, offset):
    """Calculate line number from byte offset in source file."""
    return file_contents[:offset].count("\n") + 1


def load_fixes_file(filename):
    """Load the clang-tidy YAML fixes file."""
    with open(filename, encoding="utf_8") as file:
        return yaml.safe_load(file)


def load_file(filename):
    """Load the entire contents of a file."""
    with open(filename, encoding="utf-8") as file:
        contents = file.read()
        return contents


def load_compdb(fixes_filename):
    """Load the compilation database next to the fixes file."""
    fixes_path = Path(fixes_filename)
    compdb_filename = os.path.join(fixes_path.parent, "compile_commands.json")
    with open(compdb_filename, encoding="utf_8") as file:
        return json.load(file)


def index_compdb(compdb):
    """Index the compilation database."""
    result = set()
    for item in compdb:
        filename = os.path.join(item["directory"], item["file"])
        result.add(filename)
    return result


def main():
    """Start the script."""
    args = create_argument_parser()

    compdb = load_compdb(args.fixes_file)
    compdb = index_compdb(compdb)

    fixes = load_fixes_file(args.fixes_file)
    fixes = fixes["Diagnostics"]
    have_warnings = False
    for fix in fixes:
        name = fix["DiagnosticName"]
        level = fix["Level"]
        directory = fix["BuildDirectory"]
        diagnostic = fix["DiagnosticMessage"]
        offset = diagnostic["FileOffset"]
        filename = diagnostic["FilePath"]
        message = diagnostic["Message"]

        if filename == "":
            print(f"Meta error message from `{directory}`: {message}")
            continue

        full_filename = filename
        full_filename = Path(full_filename)
        full_filename = (
            full_filename.as_posix()
            if full_filename.is_absolute()
            else os.path.join(directory, filename)
        )

        if full_filename not in compdb:
            print(
                f"Skipping `{full_filename}`"
                " because it is not found"
                " in the compilation database"
            )
            continue

        try:
            file_contents = load_file(full_filename)
        except OSError:
            # Skip in case the file can't be found. This is usually one of
            # those "too many errors emitted, stopping now" clang messages.
            print(f"Skipping `{full_filename}` because it is not found")
            continue

        line = get_line_from_offset(file_contents, offset)

        annotation = "".join(
            [
                f"::warning file={full_filename},line={line}",
                f"::{message} ({name} - Level={level})",
            ]
        )
        print(annotation)

        # User-friendly printout
        print(f"{level}: {full_filename}:{line}: {message} ({name})")

        have_warnings = True

    return 1 if have_warnings else 0


if __name__ == "__main__":
    sys.exit(main())
