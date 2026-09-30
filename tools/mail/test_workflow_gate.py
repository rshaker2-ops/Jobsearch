"""The send workflow's exit-code policy, tested by running the real thing.

On 30 September the 18:28 UTC cron went red on exit 2, which the workflow is
supposed to treat as "nothing to do, not a failure". The policy was correct and
unreachable: GitHub runs a `run:` step as `bash -e {0}`, so errexit is on before
the first line, and `set -uo pipefail` does not clear it. send.py exited 2 and
bash killed the script before `STATUS=$?`.

So these tests do not re-implement the policy, they execute the shipped script.
The run block is lifted out of the YAML, the `${{ }}` expressions are filled in
the way GitHub would, send.py is replaced by a stub that exits on demand, and
the whole thing runs under `bash -e` exactly as the runner invokes it. Delete
the `set +e` and these fail.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "send-scheduled-email.yml"


def send_step_script():
    doc = yaml.safe_load(WORKFLOW.read_text())
    for step in doc["jobs"]["send"]["steps"]:
        if step.get("name") == "Send":
            return step["run"]
    raise AssertionError("no step named 'Send' in the workflow")


def run_gate(exit_code, trigger, inputs=None):
    """Run the real Send script with send.py stubbed to exit `exit_code`."""
    script = send_step_script()

    # Fill the ${{ }} expressions the way GitHub would. Inputs are empty on a
    # schedule firing, which is the case that broke.
    values = {"inputs.check_auth": "", "inputs.dry_run": "",
              "inputs.date": "", "inputs.to": ""}
    values.update(inputs or {})
    script = re.sub(
        r"\$\{\{\s*([^}]+?)\s*\}\}",
        lambda m: values.get(m.group(1), ""),
        script,
    )

    with tempfile.TemporaryDirectory() as tmp:
        stub = Path(tmp) / "tools" / "mail"
        stub.mkdir(parents=True)
        (stub / "send.py").write_text(
            "import sys\n"
            "sys.stderr.write('stub send.py\\n')\n"
            f"sys.exit({exit_code})\n"
        )
        path = Path(tmp) / "step.sh"
        path.write_text(script)
        # bash -e {0} is GitHub's default shell for a run: block. Using plain
        # bash here would hide the very bug this file exists for.
        proc = subprocess.run(
            ["bash", "-e", str(path)],
            cwd=tmp,
            env={**os.environ, "TRIGGER": trigger},
            capture_output=True,
            text=True,
        )
    return proc


class ExitCodePolicyTestCase(unittest.TestCase):
    def test_nothing_queued_on_a_cron_passes_with_a_notice(self):
        """Exit 2 on a schedule firing is the normal outcome once the sweep
        run has already delivered the day. It must not go red."""
        proc = run_gate(2, "schedule")
        self.assertEqual(proc.returncode, 0,
                         f"cron exit 2 went red.\nstdout:\n{proc.stdout}\n"
                         f"stderr:\n{proc.stderr}")
        self.assertIn("::notice::", proc.stdout)

    def test_already_sent_on_a_cron_passes_with_a_notice(self):
        proc = run_gate(3, "schedule")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("::notice::", proc.stdout)

    def test_nothing_queued_on_a_dispatch_still_fails(self):
        """A person or the sweep run pressing the button IS expecting a send,
        so silence there is a real failure and has to stay one."""
        proc = run_gate(2, "workflow_dispatch")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("::error::", proc.stdout)

    def test_already_sent_on_a_dispatch_still_fails(self):
        proc = run_gate(3, "workflow_dispatch")
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("::error::", proc.stdout)

    def test_credential_failure_is_red_on_every_trigger(self):
        """Exit 1 and 4 are genuine breakage. A cron must never swallow them,
        or the mailbox goes quiet and nothing says so."""
        for trigger in ("schedule", "workflow_dispatch"):
            for code in (1, 4):
                with self.subTest(trigger=trigger, code=code):
                    proc = run_gate(code, trigger)
                    self.assertEqual(proc.returncode, code,
                                     proc.stdout + proc.stderr)
                    self.assertNotIn("::notice::", proc.stdout)

    def test_a_successful_send_passes(self):
        for trigger in ("schedule", "workflow_dispatch"):
            with self.subTest(trigger=trigger):
                self.assertEqual(run_gate(0, trigger).returncode, 0)


class ErrexitTestCase(unittest.TestCase):
    def test_the_script_clears_the_inherited_errexit(self):
        """The direct regression guard. Without this the exit-code policy
        below it is unreachable and every branch above passes by accident."""
        script = send_step_script()
        first = next(line.strip() for line in script.splitlines()
                     if line.strip() and not line.strip().startswith("#"))
        self.assertTrue(
            first.startswith("set ") and "+e" in first.split("#")[0],
            "the first command must clear errexit, because GitHub starts this "
            f"step as 'bash -e'. Found: {first!r}",
        )

    def test_set_uo_pipefail_alone_would_not_be_enough(self):
        """Proves the claim the fix rests on, so nobody has to take it on
        trust when they next read that comment."""
        probe = 'case "$-" in *e*) echo ON;; *) echo OFF;; esac'
        self.assertEqual(
            subprocess.run(["bash", "-e", "-c", f"set -uo pipefail; {probe}"],
                           capture_output=True, text=True).stdout.strip(),
            "ON")
        self.assertEqual(
            subprocess.run(["bash", "-e", "-c", f"set +e -uo pipefail; {probe}"],
                           capture_output=True, text=True).stdout.strip(),
            "OFF")


if __name__ == "__main__":
    unittest.main()
