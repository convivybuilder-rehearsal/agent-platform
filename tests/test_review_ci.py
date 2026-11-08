"""Tests for `agentctl review-ci` (platform/specs/reviewers-run-under-their-allow-list):
the one CI read a review-class dispatch's allow-list grants, in place of raw `gh api`.

NO TEST HERE CALLS GITHUB. `agentctl._gh_api_json` — the one function that would shell
out to `gh` — is always stubbed; a positive-control test confirms the stub is actually
consulted, not bypassed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

_AGENTCTL_BIN = Path(__file__).resolve().parent.parent / "bin" / "agentctl"


def _run(agentctl, monkeypatch, *, env=None, api=None):
    """Run `cmd_review_ci` with `env` as the run's environment (replacing
    AGENTCTL_REPO/AGENTCTL_REVIEW_SHA wholesale, never merging onto the real
    process's own) and `api` standing in for `_gh_api_json` — a callable
    `path -> dict | None`, or `None` to make every call a bug (nothing here
    should reach it when the env vars are absent)."""
    monkeypatch.delenv("AGENTCTL_REPO", raising=False)
    monkeypatch.delenv("AGENTCTL_REVIEW_SHA", raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)

    def _refuse(path):
        raise AssertionError(f"_gh_api_json called with {path!r} when it must not be")

    monkeypatch.setattr(agentctl, "_gh_api_json", api or _refuse)
    return agentctl.cmd_review_ci(types.SimpleNamespace())


def test_review_ci_takes_no_arguments():
    """The grant is `Bash(agentctl review-ci)`, an exact command with no flag
    space — the subparser must accept none. Run as a real subprocess (no CLI
    parser object is exposed to import) so this is the same argv parsing a
    reviewer's Bash call would hit."""
    env = {k: v for k, v in os.environ.items()
          if k not in ("AGENTCTL_REPO", "AGENTCTL_REVIEW_SHA")}
    refused = subprocess.run(
        [sys.executable, str(_AGENTCTL_BIN), "review-ci", "--pr", "1"],
        capture_output=True, text=True, timeout=30, env=env)
    assert refused.returncode != 0
    assert "unrecognized arguments" in refused.stderr

    accepted = subprocess.run(
        [sys.executable, str(_AGENTCTL_BIN), "review-ci"],
        capture_output=True, text=True, timeout=30, env=env)
    # Neither env var is set in THIS subprocess's own env — refuses for that
    # reason (exit 1), never an argparse error (exit 2), confirming the bare
    # form is accepted at the parser layer.
    assert accepted.returncode == 1
    assert "unrecognized arguments" not in accepted.stderr


def test_review_ci_refuses_with_neither_env_var_set_and_calls_no_api(agentctl, monkeypatch):
    code = _run(agentctl, monkeypatch, env={})
    assert code == 1


def test_review_ci_refuses_with_only_repo_set(agentctl, monkeypatch):
    code = _run(agentctl, monkeypatch, env={"AGENTCTL_REPO": "agent-platform"})
    assert code == 1


def test_review_ci_refuses_with_only_sha_set(agentctl, monkeypatch):
    code = _run(agentctl, monkeypatch, env={"AGENTCTL_REVIEW_SHA": "a" * 40})
    assert code == 1


def test_review_ci_reads_only_the_two_env_vars_never_argv(agentctl, monkeypatch, capsys):
    """Positive control: with both vars set, the stub IS consulted — proving the
    refusal tests above are refusing on a real check, not a stub that is simply
    never reached."""
    calls = []

    def api(path):
        calls.append(path)
        return {"check_runs": []}

    code = _run(agentctl, monkeypatch,
               env={"AGENTCTL_REPO": "agent-platform", "AGENTCTL_REVIEW_SHA": "a" * 40},
               api=api)
    assert code == 0
    assert calls == [f"repos/convivy/agent-platform/commits/{'a' * 40}/check-runs"]


def test_review_ci_issues_only_a_get_never_gh_api_directly(agentctl, monkeypatch):
    """The one GitHub call goes through `_gh_api_json` (a GET-only `gh api <path>`
    wrapper), never a `subprocess.run` this test didn't stub — if `cmd_review_ci`
    ever grew a second, unstubbed call site, this would catch it."""
    def boom(*a, **k):
        raise AssertionError("cmd_review_ci called subprocess.run directly")

    monkeypatch.setattr(agentctl.subprocess, "run", boom)
    code = _run(agentctl, monkeypatch,
               env={"AGENTCTL_REPO": "agent-platform", "AGENTCTL_REVIEW_SHA": "a" * 40},
               api=lambda path: {"check_runs": []})
    assert code == 0


def test_review_ci_prints_name_status_conclusion_and_run_id(agentctl, monkeypatch, capsys):
    payload = {"check_runs": [
        {"name": "pytest", "status": "completed", "conclusion": "success",
         "details_url": "https://github.com/convivy/agent-platform/actions/runs/123/job/456"},
        {"name": "lint", "status": "in_progress", "conclusion": None,
         "details_url": None},
    ]}
    code = _run(agentctl, monkeypatch,
               env={"AGENTCTL_REPO": "agent-platform", "AGENTCTL_REVIEW_SHA": "a" * 40},
               api=lambda path: payload)
    out = capsys.readouterr().out
    assert code == 0
    assert "pytest" in out and "status=completed" in out and "conclusion=success" in out
    assert "run_id=123" in out
    assert "lint" in out and "status=in_progress" in out and "run_id=?" in out


def test_review_ci_refuses_when_the_api_call_fails(agentctl, monkeypatch):
    code = _run(agentctl, monkeypatch,
               env={"AGENTCTL_REPO": "agent-platform", "AGENTCTL_REVIEW_SHA": "a" * 40},
               api=lambda path: None)
    assert code == 1


def test_review_ci_resolves_the_repo_to_its_github_slug(agentctl, monkeypatch):
    """`AGENTCTL_REPO` carries the bare short name (`args.on`'s own value, e.g.
    `"widget"`), never the owner/repo slug — `cmd_review_ci` must resolve it the
    same way `tool_policy.repo_slug` already does, not pass it through raw."""
    calls = []

    def api(path):
        calls.append(path)
        return {"check_runs": []}

    code = _run(agentctl, monkeypatch, env={"AGENTCTL_REPO": "widget", "AGENTCTL_REVIEW_SHA": "b" * 40}, api=api)
    assert code == 0
    assert calls == [f"repos/convivy/widget/commits/{'b' * 40}/check-runs"]
