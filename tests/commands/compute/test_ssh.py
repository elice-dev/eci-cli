from __future__ import annotations

from unittest.mock import MagicMock

from click.testing import CliRunner

from app.commands.compute.ssh import vm_ssh
from app.utils.name_resolver import AppContext


def _app(client: MagicMock) -> AppContext:
    return AppContext(client=client)


def _client_with_ip() -> MagicMock:
    client = MagicMock()
    client.list_vms.return_value = [{"id": "vm-1", "name": "demo"}]
    client.get_vm.return_value = {"id": "vm-1", "name": "demo", "username": "ubuntu"}
    client.list_nics.return_value = [{"id": "nic-1"}]
    client.list_public_ips.return_value = [
        {"id": "ip-1", "ip": "1.2.3.4", "attached_network_interface_id": "nic-1"}
    ]
    return client


def test_ssh_invokes_ssh_with_stored_username(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "os.execvp", lambda file, argv: captured.update(file=file, argv=argv)
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")

    client = _client_with_ip()
    result = CliRunner().invoke(vm_ssh, ["demo"], obj=_app(client))
    assert result.exit_code == 0, result.output
    assert captured["file"] == "ssh"
    assert captured["argv"] == ["ssh", "ubuntu@1.2.3.4"]


def test_ssh_forwards_long_options_and_extra_args(monkeypatch):
    """Long-form options (--login/--port/--identity) are placed BEFORE the
    destination; anything after them goes after the destination as the
    remote command. Short-form -l/-p/-i are intentionally NOT consumed by
    this wrapper (see `test_ssh_does_not_swallow_short_flags_in_remote_cmd`)."""
    captured: dict = {}
    monkeypatch.setattr(
        "os.execvp", lambda file, argv: captured.update(file=file, argv=argv)
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")

    client = _client_with_ip()
    result = CliRunner().invoke(
        vm_ssh,
        [
            "demo",
            "--login",
            "root",
            "--port",
            "2222",
            "--identity",
            "/keys/id_rsa",
            "--",
            "ls",
            "/var/log",
        ],
        obj=_app(client),
    )
    assert result.exit_code == 0, result.output
    assert captured["argv"] == [
        "ssh",
        "-p",
        "2222",
        "-i",
        "/keys/id_rsa",
        "root@1.2.3.4",
        "ls",
        "/var/log",
    ]


def test_ssh_does_not_swallow_short_flags_in_remote_cmd(monkeypatch):
    """Regression: `eci compute ssh vm tail -i /var/log/x` must pass `-i`
    through as part of the remote command, not consume it as an identity
    file. Previously Click consumed `-i` anywhere in the argv."""
    captured: dict = {}
    monkeypatch.setattr(
        "os.execvp", lambda file, argv: captured.update(file=file, argv=argv)
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")

    client = _client_with_ip()
    result = CliRunner().invoke(
        vm_ssh,
        ["demo", "tail", "-i", "/var/log/x"],
        obj=_app(client),
    )
    assert result.exit_code == 0, result.output
    assert captured["argv"] == [
        "ssh",
        "ubuntu@1.2.3.4",
        "tail",
        "-i",
        "/var/log/x",
    ]


def test_ssh_short_flags_passed_through_to_ssh_as_remote_cmd(monkeypatch):
    """`-l`, `-p`, `-i` are no longer wrapper options; they reach ssh as
    part of the remote-command tail. Users who want CLI-level handling use
    `--login`/`--port`/`--identity` instead."""
    captured: dict = {}
    monkeypatch.setattr(
        "os.execvp", lambda file, argv: captured.update(file=file, argv=argv)
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")

    client = _client_with_ip()
    result = CliRunner().invoke(
        vm_ssh,
        ["demo", "ps", "-p", "1"],
        obj=_app(client),
    )
    assert result.exit_code == 0, result.output
    assert captured["argv"] == [
        "ssh",
        "ubuntu@1.2.3.4",
        "ps",
        "-p",
        "1",
    ]


def test_ssh_passes_remote_command_after_destination(monkeypatch):
    """Trailing args (remote command) MUST come after the user@host destination.

    Regression: the wrapper previously appended destination last, which made
    `eci compute ssh vm-1 echo hello` invoke `ssh echo hello user@ip`. OpenSSH
    then treats 'echo' as the destination hostname.
    """
    captured: dict = {}
    monkeypatch.setattr(
        "os.execvp", lambda file, argv: captured.update(file=file, argv=argv)
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")

    client = _client_with_ip()
    result = CliRunner().invoke(vm_ssh, ["demo", "echo", "hello"], obj=_app(client))
    assert result.exit_code == 0, result.output
    assert captured["argv"] == ["ssh", "ubuntu@1.2.3.4", "echo", "hello"]


def test_ssh_passes_remote_command_with_separator(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "os.execvp", lambda file, argv: captured.update(file=file, argv=argv)
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")

    client = _client_with_ip()
    result = CliRunner().invoke(
        vm_ssh, ["demo", "--", "ls", "/var/log"], obj=_app(client)
    )
    assert result.exit_code == 0, result.output
    # Click consumes the `--` separator; remaining args reach ssh as the remote
    # command after destination.
    assert captured["argv"] == [
        "ssh",
        "ubuntu@1.2.3.4",
        "ls",
        "/var/log",
    ]


def test_ssh_errors_when_no_nic(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")
    client = _client_with_ip()
    client.list_nics.return_value = []

    result = CliRunner().invoke(vm_ssh, ["demo"], obj=_app(client))
    assert result.exit_code != 0
    assert "no NIC attached" in result.output
    client.list_public_ips.assert_not_called()


def test_ssh_errors_when_no_public_ip(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ssh")
    client = _client_with_ip()
    client.list_public_ips.return_value = []

    result = CliRunner().invoke(vm_ssh, ["demo"], obj=_app(client))
    assert result.exit_code != 0
    assert "no public IP attached" in result.output


def test_ssh_errors_when_ssh_binary_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    client = _client_with_ip()

    result = CliRunner().invoke(vm_ssh, ["demo"], obj=_app(client))
    assert result.exit_code != 0
    assert "`ssh` not found" in result.output
