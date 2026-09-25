#!/usr/bin/env python3
"""
Tests for the scheduled email sender.

    python3 tools/mail/test_send.py

Standard library only, matching the sender. Nothing here touches the network
or the real outbox: the SMTP class and the git helper are both replaced, and
every fixture is created and removed inside a temporary date that no real
email will ever use.

This runs on every pull request. The sender only executes on a schedule, so
without this a change that breaks it merges green and the failure shows up as
an email that never arrives.
"""

import hashlib
import io
import os
import shutil
import sys
import types
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import send  # noqa: E402

FIXTURE_DATE = "2099-01-01"  # far enough out that it can never collide


def minimal_docx():
    """A real, openable .docx, built here so the test needs no sample files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Default Extension="xml" ContentType='
            '"application/xml"/><Override PartName="/word/document.xml" ContentType='
            '"application/vnd.openxmlformats-officedocument.wordprocessingml.document.'
            'main+xml"/></Types>',
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.'
            'org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Fixture</w:t>'
            "</w:r></w:p></w:body></w:document>",
        )
    return buffer.getvalue()


class SenderTestCase(unittest.TestCase):
    def setUp(self):
        self.html = REPO / "outbox" / f"{FIXTURE_DATE}.html"
        self.files = REPO / "outbox" / f"{FIXTURE_DATE}.files"
        self.delivered = REPO / "sent" / f"{FIXTURE_DATE}.html"
        self.html.write_text(
            "<!doctype html><html><body><p>Fixture <b>body</b>.</p>"
            "<ul><li>one</li></ul></body></html>",
            encoding="utf-8",
        )
        self.captured = {}
        self.moves = []
        self._real_smtp = send.smtplib
        self._real_git = send.git
        send.smtplib = types.SimpleNamespace(
            SMTP_SSL=self._fake_smtp(), SMTPAuthenticationError=Exception
        )
        send.git = self._fake_git
        os.environ["GMAIL_USER"] = "fixture@gmail.com"
        os.environ["GMAIL_APP_PASSWORD"] = "fixture-password"

    def tearDown(self):
        send.smtplib = self._real_smtp
        send.git = self._real_git
        for path in (self.html, self.delivered):
            if path.exists():
                path.unlink()
        for path in (self.files, REPO / "sent" / f"{FIXTURE_DATE}.files"):
            if path.exists():
                shutil.rmtree(path)

    def _fake_smtp(self):
        captured = self.captured

        class FakeSMTP:
            def __init__(self, host, port, context=None, timeout=None):
                captured["host"], captured["port"] = host, port
                captured["tls"] = context is not None

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def login(self, user, password):
                captured["login"] = (user, password)

            def send_message(self, message, from_addr=None, to_addrs=None):
                captured["message"] = message
                captured["to"] = to_addrs
                captured.setdefault("sent", []).append((message, to_addrs))

        return FakeSMTP

    def _fake_git(self, *args, **kwargs):
        if args and args[0] == "mv":
            self.moves.append((args[1], args[2]))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def _run(self, *extra):
        sys.argv = ["send.py", "--date", FIXTURE_DATE, *extra]
        return send.main()

    def _attach(self, name, payload):
        self.files.mkdir(exist_ok=True)
        (self.files / name).write_bytes(payload)

    # -- the happy path ----------------------------------------------------

    def test_sends_body_only_when_nothing_is_attached(self):
        self.assertEqual(self._run(), 0)
        message = self.captured["message"]
        self.assertEqual(message.get_content_type(), "multipart/alternative")
        parts = [p.get_content_type() for p in message.walk() if not p.is_multipart()]
        self.assertEqual(parts, ["text/plain", "text/html"])

    def test_reaches_gmail_over_tls_with_every_recipient(self):
        self._run()
        self.assertEqual(self.captured["host"], "smtp.gmail.com")
        self.assertEqual(self.captured["port"], 465)
        self.assertTrue(self.captured["tls"])
        self.assertEqual(self.captured["login"][0], "fixture@gmail.com")
        self.assertGreaterEqual(len(self.captured["to"]), 1)

    def test_plain_text_alternative_is_not_empty(self):
        self._run()
        plain = [
            p for p in self.captured["message"].walk()
            if p.get_content_type() == "text/plain"
        ][0]
        self.assertIn("Fixture", plain.get_content())

    # -- attachments -------------------------------------------------------

    def test_attachments_arrive_byte_identical_and_still_open(self):
        payload = minimal_docx()
        self._attach("Report.docx", payload)
        self.assertEqual(self._run(), 0)
        message = self.captured["message"]
        self.assertEqual(message.get_content_type(), "multipart/mixed")
        attached = [
            p for p in message.walk() if p.get_content_disposition() == "attachment"
        ]
        self.assertEqual(len(attached), 1)
        got = attached[0].get_payload(decode=True)
        self.assertEqual(hashlib.sha256(got).digest(), hashlib.sha256(payload).digest())
        archive = zipfile.ZipFile(io.BytesIO(got))
        self.assertIsNone(archive.testzip())
        self.assertIn("word/document.xml", archive.namelist())

    def test_docx_keeps_the_office_mime_type(self):
        self._attach("Report.docx", minimal_docx())
        self._run()
        attached = [
            p for p in self.captured["message"].walk()
            if p.get_content_disposition() == "attachment"
        ][0]
        self.assertEqual(
            attached.get_content_type(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_attachments_are_ordered_by_name(self):
        for name in ("Charlie.docx", "alpha.docx", "Bravo.docx"):
            self._attach(name, minimal_docx())
        self._run()
        names = [
            p.get_filename() for p in self.captured["message"].walk()
            if p.get_content_disposition() == "attachment"
        ]
        self.assertEqual(names, ["alpha.docx", "Bravo.docx", "Charlie.docx"])

    def test_dotfiles_and_subdirectories_are_skipped(self):
        self._attach("Real.docx", minimal_docx())
        self._attach(".DS_Store", b"junk")
        (self.files / "nested").mkdir()
        self._run()
        names = [
            p.get_filename() for p in self.captured["message"].walk()
            if p.get_content_disposition() == "attachment"
        ]
        self.assertEqual(names, ["Real.docx"])

    def test_oversize_attachments_fail_before_connecting(self):
        self._attach("huge.bin", b"x" * (send.ATTACH_MAX_BYTES + 1))
        self.assertEqual(self._run(), 1)
        self.assertNotIn("message", self.captured)

    # -- filing ------------------------------------------------------------

    def test_html_moves_to_sent(self):
        self._run()
        self.assertIn(
            (f"outbox/{FIXTURE_DATE}.html", f"sent/{FIXTURE_DATE}.html"), self.moves
        )

    def test_attachment_directory_follows_its_email(self):
        self._attach("Report.docx", minimal_docx())
        self._run()
        self.assertIn(
            (f"outbox/{FIXTURE_DATE}.files", f"sent/{FIXTURE_DATE}.files"), self.moves
        )

    # -- the refusals ------------------------------------------------------

    def test_missing_file_exits_two(self):
        self.html.unlink()
        self.assertEqual(self._run(), 2)
        self.assertNotIn("message", self.captured)

    def test_empty_file_exits_two(self):
        self.html.write_text("   \n", encoding="utf-8")
        self.assertEqual(self._run(), 2)

    def test_already_sent_exits_three_and_sends_nothing(self):
        self.delivered.write_text("already gone", encoding="utf-8")
        self.assertEqual(self._run(), 3)
        self.assertNotIn("message", self.captured)

    def test_missing_credentials_exits_one_before_connecting(self):
        del os.environ["GMAIL_APP_PASSWORD"]
        self.assertEqual(self._run(), 1)
        self.assertNotIn("host", self.captured)

    def test_dry_run_sends_nothing_and_files_nothing(self):
        self._attach("Report.docx", minimal_docx())
        self.assertEqual(self._run("--dry-run"), 0)
        self.assertNotIn("message", self.captured)
        self.assertEqual(self.moves, [])

    def test_check_auth_without_credentials_exits_one(self):
        del os.environ["GMAIL_USER"]
        sys.argv = ["send.py", "--check-auth"]
        self.assertEqual(send.main(), 1)
        self.assertNotIn("host", self.captured)

    def test_check_auth_connects_but_sends_nothing(self):
        sys.argv = ["send.py", "--check-auth"]
        self.assertEqual(send.main(), 0)
        self.assertEqual(self.captured["host"], "smtp.gmail.com")
        self.assertNotIn("message", self.captured)


class PerRecipientTestCase(unittest.TestCase):
    """
    outbox/<date>/ holding one <address>.html per person.

    These are the tests that would have caught the 24 September send, where a
    single broadcast put four candidates on one To: line and gave each of them
    the other three people's documents.
    """

    ADDRESSES = ("alpha@example.com", "beta@example.com", "gamma@example.com")

    def setUp(self):
        self.dir = REPO / "outbox" / FIXTURE_DATE
        self.dir.mkdir(parents=True, exist_ok=True)
        for address in self.ADDRESSES:
            (self.dir / f"{address}.html").write_text(
                f"<!doctype html><html><body><p>Private note for {address}.</p>"
                f"</body></html>",
                encoding="utf-8",
            )
            files = self.dir / f"{address}.files"
            files.mkdir(exist_ok=True)
            (files / f"{address.split('@')[0]}.docx").write_bytes(minimal_docx())
        self.captured = {}
        self.moves = []
        self._real_smtp = send.smtplib
        self._real_git = send.git
        send.smtplib = types.SimpleNamespace(
            SMTP_SSL=SenderTestCase._fake_smtp(self), SMTPAuthenticationError=Exception
        )
        send.git = self._fake_git
        os.environ["GMAIL_USER"] = "fixture@gmail.com"
        os.environ["GMAIL_APP_PASSWORD"] = "fixture-password"

    def tearDown(self):
        send.smtplib = self._real_smtp
        send.git = self._real_git
        for path in (self.dir, REPO / "sent" / FIXTURE_DATE):
            if path.exists():
                shutil.rmtree(path)
        stray = REPO / "outbox" / f"{FIXTURE_DATE}.html"
        if stray.exists():
            stray.unlink()

    def _fake_git(self, *args, **kwargs):
        if args and args[0] == "mv":
            self.moves.append((args[1], args[2]))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def _run(self, *extra):
        sys.argv = ["send.py", "--date", FIXTURE_DATE, *extra]
        return send.main()

    def _sent(self):
        return self.captured.get("sent", [])

    # -- isolation, which is the whole point -------------------------------

    def test_one_message_per_address_and_no_shared_to_line(self):
        self.assertEqual(self._run(), 0)
        sent = self._sent()
        self.assertEqual(len(sent), len(self.ADDRESSES))
        for message, to_addrs in sent:
            self.assertEqual(len(to_addrs), 1)
            self.assertEqual(message["To"], to_addrs[0])
        self.assertEqual(
            sorted(to[0] for _, to in sent), sorted(self.ADDRESSES)
        )

    def test_nobody_receives_anybody_elses_body(self):
        self._run()
        for message, to_addrs in self._sent():
            mine = to_addrs[0]
            body = "".join(
                part.get_content()
                for part in message.walk()
                if part.get_content_type() == "text/html"
            )
            self.assertIn(mine, body)
            for other in self.ADDRESSES:
                if other != mine:
                    self.assertNotIn(other, body)

    def test_nobody_receives_anybody_elses_attachment(self):
        self._run()
        for message, to_addrs in self._sent():
            names = [
                part.get_filename()
                for part in message.walk()
                if part.get_content_disposition() == "attachment"
            ]
            self.assertEqual(names, [f"{to_addrs[0].split('@')[0]}.docx"])

    def test_configured_recipient_list_is_ignored(self):
        """The directory decides who is written to, not send_config.yaml."""
        self._run()
        addresses = {to[0] for _, to in self._sent()}
        configured = set(send.read_config(REPO / "send_config.yaml")["recipients"])
        self.assertFalse(addresses & configured)

    # -- filing ------------------------------------------------------------

    def test_the_whole_directory_moves_to_sent(self):
        self._run()
        self.assertEqual(
            self.moves, [(f"outbox/{FIXTURE_DATE}", f"sent/{FIXTURE_DATE}")]
        )

    def test_already_sent_directory_exits_three_and_sends_nothing(self):
        (REPO / "sent" / FIXTURE_DATE).mkdir(parents=True, exist_ok=True)
        self.assertEqual(self._run(), 3)
        self.assertEqual(self._sent(), [])

    # -- refusals ----------------------------------------------------------

    def test_a_file_not_named_after_an_address_exits_two(self):
        (self.dir / "summary.html").write_text("<p>oops</p>", encoding="utf-8")
        self.assertEqual(self._run(), 2)
        self.assertEqual(self._sent(), [])

    def test_a_directory_with_no_html_exits_two(self):
        for html in self.dir.glob("*.html"):
            html.unlink()
        self.assertEqual(self._run(), 2)
        self.assertEqual(self._sent(), [])

    def test_an_empty_body_exits_two_before_sending_anyone(self):
        (self.dir / f"{self.ADDRESSES[0]}.html").write_text("   ", encoding="utf-8")
        self.assertEqual(self._run(), 2)
        self.assertEqual(self._sent(), [])

    def test_both_layouts_at_once_exits_two(self):
        (REPO / "outbox" / f"{FIXTURE_DATE}.html").write_text(
            "<p>broadcast</p>", encoding="utf-8"
        )
        self.assertEqual(self._run(), 2)
        self.assertEqual(self._sent(), [])

    # -- overrides ---------------------------------------------------------

    def test_to_redirects_every_message_without_merging_them(self):
        self.assertEqual(self._run("--to", "test@example.com"), 0)
        sent = self._sent()
        self.assertEqual(len(sent), len(self.ADDRESSES))
        for _, to_addrs in sent:
            self.assertEqual(to_addrs, ["test@example.com"])
        names = sorted(
            part.get_filename()
            for message, _ in sent
            for part in message.walk()
            if part.get_content_disposition() == "attachment"
        )
        self.assertEqual(
            names, sorted(f"{a.split('@')[0]}.docx" for a in self.ADDRESSES)
        )

    def test_dry_run_sends_nothing_and_files_nothing(self):
        self.assertEqual(self._run("--dry-run"), 0)
        self.assertEqual(self._sent(), [])
        self.assertEqual(self.moves, [])
        self.assertTrue(self.dir.is_dir())


class ConfigTestCase(unittest.TestCase):
    def test_reads_the_real_config(self):
        cfg = send.read_config(REPO / "send_config.yaml")
        self.assertTrue(cfg.get("sender"))
        self.assertTrue(cfg.get("recipients"))
        self.assertIsInstance(cfg["recipients"], list)

    def test_rejects_a_list_item_with_no_key(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
            handle.write("- orphan\n")
            path = Path(handle.name)
        with self.assertRaises(ValueError):
            send.read_config(path)
        path.unlink()

    def test_strips_quotes_and_comments(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
            handle.write('# leading comment\nsender: "quoted@example.com"  # trailing\n')
            path = Path(handle.name)
        self.assertEqual(send.read_config(path)["sender"], "quoted@example.com")
        path.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
