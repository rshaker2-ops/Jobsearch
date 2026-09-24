# Jobsearch

Working repository for an active job search across several people. Candidate
folders (`Bob/`, `Edan/`, `Robbie/`, and others) hold resumes and role analysis.
`tools/sweep/` holds the twice-weekly role sweep. The rest of this file covers
the scheduled email sender.

## Scheduled email sender

Sends queued HTML every Monday and Thursday, then files it away so it can
never go out twice. Two layouts, and the one you queue decides which you get.

```
outbox/YYYY-MM-DD/              per recipient: one message each (preferred)
    someone@example.com.html        that person's body
    someone@example.com.files/      that person's attachments, theirs only
outbox/YYYY-MM-DD.html          broadcast: one message to everyone in the config
outbox/YYYY-MM-DD.files/        attached to that one message
sent/YYYY-MM-DD/                delivered, moved here automatically
sent/YYYY-MM-DD.html            same, for a broadcast
send_config.yaml                recipients, sender address, subject template
tools/mail/send.py              the sender
.github/workflows/send-scheduled-email.yml
```

Use the per-recipient layout whenever the content differs by reader, which is
most of the time. A broadcast puts every address on one To: line and hands
each recipient every attachment, so one person's document is visible to all of
them. That is a distribution decision, not a formatting one. Get it wrong and
it cannot be undone.

The job runs at 13:00 UTC on Mondays and Thursdays, which is 9am Eastern during
daylight saving and 8am Eastern after it ends. GitHub cron is always UTC and
does not follow local clock changes, so the hour shifts by one in November.

On the scheduled day the sender looks for `outbox/<today>/` first and
`outbox/<today>.html` second, where today is the date in America/New_York
rather than UTC. If neither is there the run fails with a clear message and
nothing is sent. If both are there it refuses, because sending both would mail
people twice. If something of that name is already sitting in `sent/`, the run
refuses rather than sending a second copy, which makes it safe to press the
manual trigger after a scheduled run has already gone out.

Credentials never live in the repository. They come from two repository secrets
and are read from the environment at run time.

### Per-recipient sends

Make a directory named after the date and put one `<address>.html` inside it
per person. Attachments go in a matching `<address>.files/`:

```
outbox/2026-09-28/
    rshaker2@gmail.com.html
    rshaker2@gmail.com.files/Bob_Shaker_Role_Sweep_28Sep.docx
    edanmejias@gmail.com.html
    edanmejias@gmail.com.files/Edan_Mejias_Role_Sweep_28Sep.docx
```

Each address gets its own message with its own body and its own attachments.
Nobody sees anybody else's address, body or files. `send_config.yaml` is not
consulted for the recipient list in this mode: the filenames decide, so an
address with no `.html` simply gets no mail. Every file directly inside the
directory must be named after a valid email address, or the run refuses.

When the send succeeds the whole `outbox/<date>/` directory moves to
`sent/<date>/` in one move.

### Attachments

Put files in a directory named after the email with `.files` on the end, and
every file directly inside it is attached, sorted by name:

```
outbox/2026-09-25.html
outbox/2026-09-25.files/
    Bob_Shaker_Role_Sweep_25Sep.docx
    Edan_Mejias_Role_Sweep_25Sep.docx
    Robbie_Shaker_Role_Sweep_25Sep.docx
```

That is the broadcast form, where all three documents go to all recipients.
The directory is optional. Without it the email goes out as body text only.
Subdirectories and dotfiles are skipped. When the send succeeds the directory
moves into `sent/` alongside its HTML, so a delivered day stays together.

Word, Excel and PowerPoint files are given their correct MIME types explicitly,
because `mimetypes` does not know the Office formats on every system and a
wrong type makes Word refuse to open the attachment.

Attachments are capped at 20MB per message. Gmail refuses anything over 25MB, and
base64 encoding inflates a file by about a third on the way out, so the cap
sits below Gmail's to leave room. Going over fails the run before it connects,
with a message naming the directory to trim. A warning prints from 15MB up.

A dry run lists what would be attached, with sizes and detected types, which is
the quickest way to confirm a file landed in the right place.

### 1. Create a Gmail app password

An app password is a 16 character credential that lets a script authenticate
without your real password, and it can be revoked on its own.

1. Turn on 2-Step Verification for the Google account, at
   <https://myaccount.google.com/signinoptions/two-step-verification>. App
   passwords are not available until this is on.
2. Go to <https://myaccount.google.com/apppasswords>.
3. Name it something you will recognise later, such as `Jobsearch sender`, and
   create it.
4. Copy the 16 character value. Google shows it once. Spaces in the displayed
   value are cosmetic and can be included or stripped, either works.

If the account is on Google Workspace rather than a personal Gmail, an
administrator may have disabled app passwords, in which case this will not
appear as an option and the account owner has to enable it first.

### 2. Add the two repository secrets

In the repository, open Settings, then Secrets and variables, then Actions, and
add two repository secrets:

| Secret | Value |
|---|---|
| `GMAIL_USER` | the full Gmail address that authenticates, for example `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | the 16 character app password from step 1 |

`GMAIL_USER` is who logs in. The `sender:` line in `send_config.yaml` is what
appears on the From line. They are usually the same address. If they differ and
the From address is not a verified alias on that account, Gmail rewrites it back
to the authenticated address.

### 3. Test it

Queue a file dated today, in `America/New_York`, not UTC:

```bash
mkdir -p outbox
cat > outbox/$(TZ=America/New_York date +%F).html <<'EOF'
<!doctype html>
<html><body><p>Test send.</p></body></html>
EOF
git add outbox && git commit -m "Queue test email" && git push
```

Check it locally first. A dry run does everything except send, move and commit,
and needs no credentials:

```bash
python3 tools/mail/send.py --dry-run
```

A dry run deliberately returns before it reads the credentials, so it proves
the file and the config are right but says nothing about whether the secrets
work. To test those, log in and hang up without sending:

```bash
python3 tools/mail/send.py --check-auth
```

That needs nothing queued. From the Actions tab the same check is the
**check_auth** input on **Send scheduled email**, which is the right first
press after adding the secrets: it proves the credentials before any mail can
go out.

Then run it for real from the Actions tab: open **Send scheduled email**, press
**Run workflow**, and leave both inputs blank to send today's file. Tick
**dry_run** instead to have the workflow check everything without sending, which
is the safer first press because it proves the checkout, the Python setup and
the config parse before any mail moves.

The **date** input overrides which day is picked, so `2026-09-22` sends
`outbox/2026-09-22/` or `outbox/2026-09-22.html` regardless of what today is.
Useful for replaying a specific day.

The **to** input replaces the recipient list for one run. On a per-recipient
day that does not merge the messages: each candidate's message still goes out
separately, all of them to the test address, so you see exactly what each
person would have received.

After a successful send the workflow commits the move as `Sent YYYY-MM-DD` and
pushes, so `git pull` will show the file has left `outbox/` and arrived in
`sent/`.

### Tests

```bash
python3 tools/mail/test_send.py
```

Twenty tests, standard library only, no network. They cover the message
structure, attachment integrity (payloads are hashed against the originals and
reopened as zips to prove Word will still accept them), ordering, the size cap,
every refusal path, and the config parser.

```bash
python3 tools/sweep/test_run.py
```

Twenty-four more for the sweep pipeline: the profile schema, the location
rules against the real strings both channels produce, band extraction, and
experience-floor parsing. Every case is derived from a bug that actually
shipped, so a failure means something that once broke is broken again.

`.github/workflows/test-sender.yml` runs both suites on **every** pull
request, with no paths filter. It also checks that every profile resolves,
that the document builders parse, that every address in the mail config is an
address, and that nobody is swept without being emailed. The sender and the
sweep only execute on a schedule, so without this a change that breaks either
would merge green and surface as an email that never arrived.

```bash
python3 tools/check_no_em_dashes.py
```

The same workflow runs this, which fails the build on an em dash in any
tracked text file. The rule is easy to satisfy and easy to forget: seventeen
were found sitting in the document builder, rendering into the .docx being
emailed to people. The script builds the character with `chr(8212)` rather
than writing it out, so it cannot trip its own check.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | sent, or the dry run or auth check finished |
| 1 | configuration or credentials problem |
| 2 | nothing queued for that date |
| 3 | already sent, a file of that name is in `sent/` |
| 4 | delivery failed, or the mail went but the commit did not |

Code 4 is the one to read carefully. If delivery succeeded and only the git step
failed, the message says so explicitly, and the file has to be moved into
`sent/` by hand. Otherwise the next run for that date will send a duplicate.

### Notes

`send_config.yaml` is read by a small parser inside `send.py` rather than by
PyYAML, because the sender is restricted to the Python standard library and
there is no YAML parser in it. Only flat `key: value` pairs and `- item` lists
are understood, which is all the config needs. Keep it flat.

The sender builds a `multipart/alternative` message and derives a plain text
part from the HTML automatically, so the mail is not HTML only. HTML only
messages score poorly with spam filters.
