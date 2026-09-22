#!/usr/bin/env python3
"""
Fail if an em dash appears in any tracked text file.

    python3 tools/check_no_em_dashes.py

A standing rule for this repository: no em dashes, anywhere, including code
comments and generated documents. This runs in CI because the rule is easy to
satisfy by hand and easy to forget. It was added after seventeen of them were
found sitting in the document builder, rendering into the .docx being emailed
to people.

The character is built with chr(8212) rather than written literally, so this
file can never trip its own check.
"""

import subprocess
import sys

EM_DASH = chr(8212)
BINARY = (".docx", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".ico", ".woff", ".woff2")


def tracked_text_files():
    listing = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split("\n")
    return [name for name in listing if name and not name.endswith(BINARY)]


def main():
    offenders = []
    for name in tracked_text_files():
        try:
            body = open(name, encoding="utf-8").read()
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError, PermissionError):
            continue
        count = body.count(EM_DASH)
        if count:
            lines = [
                i for i, line in enumerate(body.splitlines(), 1) if EM_DASH in line
            ]
            shown = ", ".join(str(n) for n in lines[:8])
            more = f" and {len(lines) - 8} more" if len(lines) > 8 else ""
            offenders.append(f"{name}: {count} on line(s) {shown}{more}")

    if offenders:
        print("em dashes found, which this repository does not use:")
        for line in offenders:
            print(f"  {line}")
        print("\nReplace with a comma, a colon, parentheses or a full stop.")
        return 1

    print(f"ok: no em dashes in {len(tracked_text_files())} tracked text files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
