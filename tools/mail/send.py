#!/usr/bin/env python3
"""
Send today's queued HTML email, then file it away.

    python3 tools/mail/send.py [--dry-run] [--date YYYY-MM-DD] [--config PATH]
    python3 tools/mail/send.py --check-auth
    python3 tools/mail/send.py --to you@example.com

Looks for outbox/<today>.html, where today is the current date in
America/New_York rather than UTC, so a run scheduled near midnight UTC still
picks the file a person would call "today". Anything sitting in
outbox/<today>.files/ is attached. Sends it as an HTML email through
smtp.gmail.com:465, then git mv's the HTML and its attachment directory into
sent/, commits and pushes.

Credentials come from the environment, never from the config file or the repo:

    GMAIL_USER          the full Gmail address to authenticate as
    GMAIL_APP_PASSWORD  a Google app password, not the account password

Two layouts. A single broadcast, outbox/<date>.html with an optional
outbox/<date>.files/, goes to everyone in send_config.yaml with every
attachment. A per-recipient send, outbox/<date>/ holding <address>.html and
an optional <address>.files/ per person, sends each address its own body and
its own attachments and nothing belonging to anyone else. Use the second
whenever the content differs by reader, which is most of the time: a shared
send puts every recipient's address on one To: line and hands each of them
everybody else's documents.

--to replaces the recipient list for one run, so a real send can be tested
against a single inbox without mailing everybody on the list.

--check-auth logs in to Gmail and disconnects without sending anything and
without needing a queued file. It is the only way to prove the credentials
work before a real send, because --dry-run returns before it reads them.

Exit codes:
    0  sent (or dry run / auth check completed)
    1  configuration or credential problem
    2  no file queued for today
    3  already sent (a file of that name exists in sent/)
    4  delivery or git failure
"""

import argparse
import mimetypes
import os
import re
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

# A directory at outbox/<date>/ means one message per recipient rather than one
# message to everybody. Added 24 Sep after a broadcast sent all four candidates
# each other's documents and put all four addresses on a single To: line.
ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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


def credentials():
    """The two secrets, or a message naming whichever is missing."""
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    missing = [
        name
        for name, value in (("GMAIL_USER", user), ("GMAIL_APP_PASSWORD", password))
        if not value
    ]
    if missing:
        return None, None, (
            f"missing environment variable(s): {', '.join(missing)}.\n"
            f"       Set them as repository secrets, or export them locally."
        )
    return user, password, None


def check_auth():
    """
    Log in and hang up. Nothing is sent, nothing is read from the outbox, and
    no file has to be queued. This exists because --dry-run returns before it
    ever looks at the credentials, so it cannot tell you whether they work.
    """
    user, password, problem = credentials()
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    print(f"host      {SMTP_HOST}:{SMTP_PORT}")
    print(f"user      {user}")
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=60) as smtp:
            smtp.login(user, password)
    except smtplib.SMTPAuthenticationError as exc:
        print(
            f"error: Gmail rejected the login ({exc.smtp_code}).\n"
            f"       GMAIL_APP_PASSWORD must be a Google app password, 16\n"
            f"       characters, not the account password, and 2-Step\n"
            f"       Verification must be on for {user}.\n"
            f"       If this is a Workspace account, an administrator may have\n"
            f"       disabled app passwords entirely.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"error: could not reach {SMTP_HOST}: {exc}", file=sys.stderr)
        return 1
    print("\nauthenticated. The credentials work. Nothing was sent.")
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def build_message(sender, recipients, subject, html, attachments):
    """One message. Attachments are already collected and size-checked."""
    message = EmailMessage()
    message["From"] = formataddr(("Bob Shaker", sender))
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message.set_content(html_to_text(html))
    message.add_alternative(html, subtype="html")
    for item in attachments:
        maintype, subtype = guess_mime(item)
        message.add_attachment(item.read_bytes(), maintype=maintype,
                               subtype=subtype, filename=item.name)
    return message


def deliver(messages, user, password, sender):
    """Open one connection and send every message through it."""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=60) as smtp:
        smtp.login(user, password)
        for message, to_addrs in messages:
            smtp.send_message(message, from_addr=sender, to_addrs=to_addrs)


def per_recipient_jobs(directory):
    """
    outbox/<date>/ holding <address>.html and an optional <address>.files/.
    Returns [(address, html_path, [attachments])], sorted, or None if the
    directory is not present.
    """
    if not directory.is_dir():
        return None
    jobs = []
    for html in sorted(directory.glob("*.html")):
        address = html.stem
        if not ADDRESS.match(address):
            raise ValueError(
                f"{html.name} is not named after an email address. In a "
                f"per-recipient send every file must be <address>.html."
            )
        jobs.append((address, html, collect_attachments(directory / f"{address}{ATTACH_SUFFIX}")))
    if not jobs:
        raise ValueError(f"{directory} exists but holds no <address>.html files")
    return jobs


def main():
    parser = argparse.ArgumentParser(description="Send today's queued HTML email.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do everything except send, move, commit and push",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="log in to Gmail and disconnect, sending nothing. Proves the "
             "credentials work without needing anything queued.",
    )
    parser.add_argument(
        "--date",
        help="override the date to send, as YYYY-MM-DD (for testing)",
    )
    parser.add_argument(
        "--to",
        action="append",
        metavar="ADDRESS",
        help="send to this address instead of the configured recipients. "
             "Repeatable. Use it to test a real send against one inbox.",
    )
    parser.add_argument(
        "--config",
        default=str(REPO / "send_config.yaml"),
        help="path to send_config.yaml",
    )
    args = parser.parse_args()

    if args.check_auth:
        return check_auth()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"error: no config file at {config_path}", file=sys.stderr)
        return 1
    try:
        cfg = read_config(config_path)
    except ValueError as exc:
        print(f"error: {config_path} is malformed: {exc}", file=sys.stderr)
        return 1

    recipients = args.to or cfg.get("recipients") or []
    sender = cfg.get("sender")
    subject_template = cfg.get("subject", "Update, {date}")
    if not recipients:
        print(f"error: no recipients listed in {config_path}", file=sys.stderr)
        return 1
    if args.to:
        print("note      overriding the configured recipients with --to")
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
    queued_dir = OUTBOX / stamp
    delivered_dir = SENT / stamp

    # Refuse to send the same day twice. This is the guard that makes a manual
    # workflow_dispatch safe to press after a scheduled run has already gone.
    if delivered.exists() or delivered_dir.exists():
        already = delivered if delivered.exists() else delivered_dir
        print(
            f"error: {already.relative_to(REPO)} already exists, so "
            f"{stamp} has been sent. Nothing to do.",
            file=sys.stderr,
        )
        return 3

    if queued.is_file() and queued_dir.is_dir():
        print(
            f"error: both {queued.relative_to(REPO)} and "
            f"{queued_dir.relative_to(REPO)}/ exist for {stamp}. Keep one. "
            f"The directory is the per-recipient layout and the file is the "
            f"broadcast layout, and sending both would mail people twice.",
            file=sys.stderr,
        )
        return 2

    subject = subject_template.format(date=stamp, date_long=date_long)

    try:
        jobs = per_recipient_jobs(queued_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if jobs is not None:
        # One message per recipient. Nobody receives anybody else's body or
        # attachments, and nobody sees anybody else's address.
        mode = "per recipient"
        plan = []
        for address, html_path, attachments in jobs:
            html = html_path.read_text(encoding="utf-8")
            if not html.strip():
                print(f"error: {html_path.relative_to(REPO)} is empty", file=sys.stderr)
                return 2
            plan.append(([address], html, attachments, html_path))
        moves = [(queued_dir, delivered_dir)]
    else:
        if not queued.is_file():
            print(
                f"error: nothing queued for {stamp}.\n"
                f"       Expected {queued.relative_to(REPO)}, or a directory at\n"
                f"       {queued_dir.relative_to(REPO)}/ holding one <address>.html per person.\n"
                f"       Write one of those, commit it, then run this again.",
                file=sys.stderr,
            )
            return 2
        html = queued.read_text(encoding="utf-8")
        if not html.strip():
            print(f"error: {queued.relative_to(REPO)} is empty", file=sys.stderr)
            return 2
        mode = "broadcast"
        attachments = collect_attachments(queued_files)
        plan = [(list(recipients), html, attachments, queued)]
        moves = [(queued, delivered)]
        if attachments:
            moves.append((queued_files, delivered_files))

    if args.to:
        # Every message in the plan is redirected, so a per-recipient run under
        # --to lands one message per candidate in the same test inbox.
        plan = [(list(args.to), html, att, src) for (_, html, att, src) in plan]

    # Gmail's size limit is per message, so this is checked per message rather
    # than across the run. Four people receiving 6MB each is fine; one person
    # receiving 24MB is not.
    for addrs, _, attachments, src in plan:
        size = sum(a.stat().st_size for a in attachments)
        if size > ATTACH_MAX_BYTES:
            print(
                f"error: attachments for {', '.join(addrs)} total "
                f"{size / 1048576:.1f}MB, over the "
                f"{ATTACH_MAX_BYTES / 1048576:.0f}MB limit this sender allows "
                f"({src.relative_to(REPO)}).",
                file=sys.stderr,
            )
            return 1

    print(f"date      {stamp} ({TZ_NAME})")
    print(f"mode      {mode}, {len(plan)} message(s)")
    print(f"subject   {subject}")
    print(f"from      {sender}")
    for addrs, html, attachments, src in plan:
        print(f"\n  to      {', '.join(addrs)}")
        print(f"  body    {src.relative_to(REPO)} ({len(html)} bytes)")
        if attachments:
            for item in attachments:
                maintype, subtype = guess_mime(item)
                print(f"  attach  {item.name}  ({item.stat().st_size / 1024:.0f} KB, {maintype}/{subtype})")
        else:
            print("  attach  nothing")
        size = sum(a.stat().st_size for a in attachments)
        if size > ATTACH_WARN_BYTES:
            print(
                f"\nwarning: {size / 1048576:.1f}MB of attachments for "
                f"{', '.join(addrs)}.",
                file=sys.stderr,
            )
    print()

    if args.dry_run:
        print("dry run: not sending, not moving, not committing.")
        return 0

    user, password, problem = credentials()
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    messages = [
        (build_message(sender, addrs, subject, html, att), addrs)
        for addrs, html, att, _ in plan
    ]
    try:
        deliver(messages, user, password, sender)
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

    print(f"\nsent {len(plan)} message(s).")

    # Delivery succeeded. From here a failure must not look like a failed send,
    # so git problems are reported loudly but the mail is already gone.
    try:
        SENT.mkdir(exist_ok=True)
        for src, dst in moves:
            git("mv", str(src.relative_to(REPO)), str(dst.relative_to(REPO)))
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
            f"       Move the queued paths for {stamp} into sent/ by hand, or "
            f"the next run for this date will refuse rather than send twice.",
            file=sys.stderr,
        )
        return 4

    print("filed into sent/, committed and pushed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
