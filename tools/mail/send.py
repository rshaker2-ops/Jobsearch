#!/usr/bin/env python3
"""
Send today's queued HTML email, then file it away.

    python3 tools/mail/send.py [--dry-run] [--date YYYY-MM-DD] [--config PATH]

Looks for outbox/<today>.html, where today is the current date in
America/New_York rather than UTC, so a run scheduled near midnight UTC still
picks the file a person would call "today". Anything sitting in
outbox/<today>.files/ is attached. Sends it as an HTML email through
smtp.gmail.com:465, then git mv's the HTML and its attachment directory into
sent/, commits and pushes.

Credentials come from the environment, never from the config file or the repo:

    GMAIL_USER          the full Gmail address to authenticate as
    GMAIL_APP_PASSWORD  a Google app password, not the account password

Exit codes:
    0  sent (or dry run completed)
    1  configuration or credential problem
    2  no file queued for today
    3  already sent (a file of that name exists in sent/)
    4  delivery or git failure
"""

import argparse
import mimetypes
import os
import smtplib
import ssl
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

REPO = Path(__file__).resolve().parents[2]
OUTBOX = REPO / "outbox"
SENT = REPO / "sent"
TZ_NAME = "America/New_York"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

# Anything sitting in outbox/<date>.files/ is attached to that day's email.
# The directory travels with the HTML into sent/ when the send succeeds.
ATTACH_SUFFIX = ".files"

# Gmail refuses a message over 25MB. Stop well short, because base64 encoding
# inflates attachments by about a third and headers add more on top.
ATTACH_WARN_BYTES = 15 * 1024 * 1024
ATTACH_MAX_BYTES = 20 * 1024 * 1024

# mimetypes does not know the Office formats on every system, and getting these
# wrong makes Word refuse to open the attachment.
MIME_OVERRIDES = {
    ".docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".xlsx": ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".pptx": ("application", "vnd.openxmlformats-officedocument.presentationml.presentation"),
    ".doc": ("application", "msword"),
    ".xls": ("application", "vnd.ms-excel"),
    ".ppt": ("application", "vnd.ms-powerpoint"),
}


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def read_config(path):
    """
    Read the flat subset of YAML this tool uses: "key: value" pairs and
    "- item" lists nested one level under a key. Written by hand because the
    sender is standard library only and there is no YAML parser in it.
    """
    cfg = {}
    current_list = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.strip().startswith("#") else ""
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if current_list is None:
                raise ValueError(f"list item with no key above it: {raw!r}")
            current_list.append(_unquote(line.lstrip()[2:].strip()))
            continue
        if ":" not in line:
            raise ValueError(f"cannot parse line: {raw!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            cfg[key] = current_list = []
        else:
            cfg[key] = _unquote(value)
            current_list = None
    return cfg


def _unquote(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def today_local():
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(TZ_NAME))
        except Exception:
            # tzdata missing on a slim image. Fall through to UTC and say so.
            print(f"warning: no {TZ_NAME} tz data available, using UTC", file=sys.stderr)
    return datetime.utcnow()


def git(*args, check=True):
    result = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def guess_mime(path):
    suffix = path.suffix.lower()
    if suffix in MIME_OVERRIDES:
        return MIME_OVERRIDES[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and "/" in guessed:
        maintype, _, subtype = guessed.partition("/")
        return maintype, subtype
    return "application", "octet-stream"


def collect_attachments(directory):
    """
    Every file directly inside outbox/<date>.files/, sorted by name so the
    order in the mail is predictable. Subdirectories and dotfiles are skipped.
    """
    if not directory.is_dir():
        return []
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )


def html_to_text(html):
    """
    Crude plain-text alternative so the message is not HTML only, which scores
    badly with spam filters. Good enough for the simple documents this sends.
    """
    import html as html_mod
    import re

    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "  - ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Send today's queued HTML email.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do everything except send, move, commit and push",
    )
    parser.add_argument(
        "--date",
        help="override the date to send, as YYYY-MM-DD (for testing)",
    )
    parser.add_argument(
        "--config",
        default=str(REPO / "send_config.yaml"),
        help="path to send_config.yaml",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"error: no config file at {config_path}", file=sys.stderr)
        return 1
    try:
        cfg = read_config(config_path)
    except ValueError as exc:
        print(f"error: {config_path} is malformed: {exc}", file=sys.stderr)
        return 1

    recipients = cfg.get("recipients") or []
    sender = cfg.get("sender")
    subject_template = cfg.get("subject", "Update, {date}")
    if not recipients:
        print(f"error: no recipients listed in {config_path}", file=sys.stderr)
        return 1
    if not sender:
        print(f"error: no sender address in {config_path}", file=sys.stderr)
        return 1

    now = today_local()
    stamp = args.date or now.strftime("%Y-%m-%d")
    try:
        parsed = datetime.strptime(stamp, "%Y-%m-%d")
    except ValueError:
        print(f"error: --date must look like YYYY-MM-DD, got {stamp!r}", file=sys.stderr)
        return 1
    date_long = f"{parsed.day} {parsed.strftime('%B %Y')}"

    queued = OUTBOX / f"{stamp}.html"
    delivered = SENT / f"{stamp}.html"
    queued_files = OUTBOX / f"{stamp}{ATTACH_SUFFIX}"
    delivered_files = SENT / f"{stamp}{ATTACH_SUFFIX}"

    # Refuse to send the same day twice. This is the guard that makes a manual
    # workflow_dispatch safe to press after a scheduled run has already gone.
    if delivered.exists():
        print(
            f"error: {delivered.relative_to(REPO)} already exists, so "
            f"{stamp} has been sent. Nothing to do.",
            file=sys.stderr,
        )
        return 3

    if not queued.is_file():
        print(
            f"error: nothing queued for {stamp}.\n"
            f"       Expected {queued.relative_to(REPO)} and it is not there.\n"
            f"       Write that file, commit it, then run this again.",
            file=sys.stderr,
        )
        return 2

    html = queued.read_text(encoding="utf-8")
    if not html.strip():
        print(f"error: {queued.relative_to(REPO)} is empty", file=sys.stderr)
        return 2

    subject = subject_template.format(date=stamp, date_long=date_long)

    message = EmailMessage()
    message["From"] = formataddr(("Bob Shaker", sender))
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message.set_content(html_to_text(html))
    message.add_alternative(html, subtype="html")

    attachments = collect_attachments(queued_files)
    total_bytes = sum(a.stat().st_size for a in attachments)
    if total_bytes > ATTACH_MAX_BYTES:
        print(
            f"error: attachments total {total_bytes / 1048576:.1f}MB, over the "
            f"{ATTACH_MAX_BYTES / 1048576:.0f}MB limit this sender allows. "
            f"Gmail rejects anything past 25MB once encoded. Remove or shrink "
            f"files in {queued_files.relative_to(REPO)}.",
            file=sys.stderr,
        )
        return 1
    for item in attachments:
        maintype, subtype = guess_mime(item)
        message.add_attachment(
            item.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=item.name,
        )

    print(f"date      {stamp} ({TZ_NAME})")
    print(f"file      {queued.relative_to(REPO)} ({len(html)} bytes)")
    print(f"subject   {subject}")
    print(f"from      {sender}")
    print(f"to        {', '.join(recipients)}")
    if attachments:
        print(f"attached  {len(attachments)} file(s), {total_bytes / 1024:.0f} KB total")
        for item in attachments:
            maintype, subtype = guess_mime(item)
            print(f"          {item.name}  ({item.stat().st_size / 1024:.0f} KB, {maintype}/{subtype})")
        if total_bytes > ATTACH_WARN_BYTES:
            print(
                f"warning: {total_bytes / 1048576:.1f}MB of attachments is close to "
                f"the limit Gmail will accept.",
                file=sys.stderr,
            )
    else:
        print(f"attached  nothing ({queued_files.relative_to(REPO)} is absent or empty)")

    if args.dry_run:
        print("\ndry run: not sending, not moving, not committing.")
        return 0

    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not password:
        missing = [
            name
            for name, value in (("GMAIL_USER", user), ("GMAIL_APP_PASSWORD", password))
            if not value
        ]
        print(
            f"error: missing environment variable(s): {', '.join(missing)}.\n"
            f"       Set them as repository secrets, or export them locally.",
            file=sys.stderr,
        )
        return 1

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=60) as smtp:
            smtp.login(user, password)
            smtp.send_message(message, from_addr=sender, to_addrs=recipients)
    except smtplib.SMTPAuthenticationError:
        print(
            "error: Gmail rejected the login. GMAIL_APP_PASSWORD must be a "
            "Google app password (16 characters, no spaces), not the account "
            "password, and 2-Step Verification must be on for the account.",
            file=sys.stderr,
        )
        return 4
    except Exception as exc:
        print(f"error: delivery failed: {exc}", file=sys.stderr)
        return 4

    print(f"\nsent to {len(recipients)} recipient(s).")

    # Delivery succeeded. From here a failure must not look like a failed send,
    # so git problems are reported loudly but the mail is already gone.
    try:
        SENT.mkdir(exist_ok=True)
        git("mv", str(queued.relative_to(REPO)), str(delivered.relative_to(REPO)))
        if attachments:
            git(
                "mv",
                str(queued_files.relative_to(REPO)),
                str(delivered_files.relative_to(REPO)),
            )
        git("config", "user.name", os.environ.get("GIT_AUTHOR_NAME", "github-actions[bot]"))
        git(
            "config",
            "user.email",
            os.environ.get(
                "GIT_AUTHOR_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com"
            ),
        )
        git("commit", "-m", f"Sent {stamp}")
        git("push")
    except RuntimeError as exc:
        print(
            f"error: the email WAS SENT but filing it failed: {exc}\n"
            f"       Move {queued.relative_to(REPO)} to sent/ by hand, or the "
            f"next run for this date will refuse rather than send twice.",
            file=sys.stderr,
        )
        return 4

    print(f"moved to {delivered.relative_to(REPO)}, committed and pushed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
