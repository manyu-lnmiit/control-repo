from __future__ import annotations

from agent_code_sandbox.core.policy import SandboxPolicy


def test_build_env_drops_unlisted_vars() -> None:
    policy = SandboxPolicy()
    parent_env = {
        "PATH": "/usr/bin",
        "HOME": "/home/x",
        "SECRET_API_KEY": "super-secret",
    }
    env = policy.build_env(parent_env)
    assert env.get("PATH") == "/usr/bin"
    assert env.get("HOME") == "/home/x"
    assert "SECRET_API_KEY" not in env


def test_build_env_applies_extra_env_overrides() -> None:
    policy = SandboxPolicy(extra_env={"PATH": "/custom/bin", "FOO": "bar"})
    env = policy.build_env({"PATH": "/usr/bin"})
    assert env["PATH"] == "/custom/bin"
    assert env["FOO"] == "bar"


def test_build_env_strips_network_vars_when_network_disallowed() -> None:
    policy = SandboxPolicy(allow_network=False)
    parent_env = {"PATH": "/usr/bin", "https_proxy": "http://proxy:8080"}
    policy2 = SandboxPolicy(
        allow_network=False, env_allowlist=("PATH", "https_proxy")
    )
    env = policy2.build_env(parent_env)
    assert "https_proxy" not in env
    assert policy.allow_network is False


def test_shell_allowlist_allows_known_commands() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("echo hello world")
    assert ok is True
    assert reason is None


def test_shell_allowlist_blocks_unknown_command() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("rm -rf /")
    assert ok is False
    assert "not in the allowlist" in reason


def test_shell_allowlist_blocks_path_traversal_around_allowlist() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("/bin/rm -rf /")
    assert ok is False
    assert reason is not None


def test_shell_operator_rejected_by_default() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("echo hi && rm -rf /")
    assert ok is False
    assert "operator" in reason


def test_shell_operator_pipe_rejected() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("cat foo | grep bar")
    assert ok is False


def test_shell_operator_command_substitution_rejected() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("echo $(whoami)")
    assert ok is False


def test_shell_operator_allowed_when_explicitly_enabled() -> None:
    policy = SandboxPolicy(allow_shell_operators=True)
    ok, reason = policy.check_shell_command("echo hi && echo bye")
    # Operators no longer rejected outright, but each token is still
    # parsed with shlex; "echo hi && echo bye" as one shlex-split argv
    # means the leading executable is still "echo" so this should pass.
    assert ok is True


def test_empty_command_rejected() -> None:
    policy = SandboxPolicy()
    ok, reason = policy.check_shell_command("   ")
    assert ok is False
