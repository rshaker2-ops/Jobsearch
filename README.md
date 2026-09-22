# Jobsearch

Working repository for an active job search across several people. Candidate
folders (`Bob/`, `Edan/`, `Robbie/`, and others) hold resumes and role analysis.
`tools/sweep/` holds the twice-weekly role sweep. The rest of this file covers
the scheduled email sender.

## Scheduled email sender

Sends a queued HTML file to a fixed list of recipients every Monday and
Thursday, then files it away so it can never go out twice.

```
outbox/YYYY-MM-DD.html          queued, waiting for its date to come up
outbox/YYYY-MM-DD.files/        anything in here is attached to that email
sent/YYYY-MM-DD.html            delivered, moved here automatically
sent/YYYY-MM-DD.files/          its attachments, moved with it
send_config.yaml                recipients, sender address, subject template
tools/mail/send.py              the sender
.github/workflows/send-scheduled-email.yml
```

The job runs at 13:00 UTC on Mondays and Thursdays, which is 9am Eastern during
daylight saving and 8am Eastern after it ends. GitHub cron is always UTC and
does not follow local clock changes, so the hour shifts by one in November.

On the scheduled day the sender looks for `outbox/<today>.html`, where today is
the date in America/New_York rather than UTC. If that file is not there the run
fails with a clear message and nothing is sent. If a file of the same name is
already sitting in `sent/`, the run refuses rather than sending a second copy,
which makes it safe to press the manual trigger after a scheduled run has
already gone out.

Credentials never live in the repository. They come from two repository secrets
and are read from the environment at run time.

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

The directory is optional. Without it the email goes out as body text only.
Subdirectories and dotfiles are skipped. When the send succeeds the directory
moves into `sent/` alongside its HTML, so a delivered day stays together.

Word, Excel and PowerPoint files are given their correct MIME types explicitly,
because `mimetypes` does not know the Office formats on every system and a
wrong type makes Word refuse to open the attachment.

Attachments are capped at 20MB total. Gmail refuses anything over 25MB, and
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

Then run it for real from the Actions tab: open **Send scheduled email**, press
**Run workflow**, and leave both inputs blank to send today's file. Tick
**dry_run** instead to have the workflow check everything without sending, which
is the safer first press because it proves the checkout, the Python setup and
the config parse before any mail moves.

The **date** input overrides which file is picked, so
`2026-09-22` sends `outbox/2026-09-22.html` regardless of what today is. Useful
for replaying a specific day.

After a successful send the workflow commits the move as `Sent YYYY-MM-DD` and
pushes, so `git pull` will show the file has left `outbox/` and arrived in
`sent/`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | sent, or the dry run finished |
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
