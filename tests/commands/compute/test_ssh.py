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


def test_ssh_forwards_port_identity_login_and_extra_args(monkeypatch):
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
            "-l",
            "root",
            "-p",
            "2222",
            "-i",
            "/keys/id_rsa",
            "--",
            "-v",
            "-L",
            "8080:localhost:8080",
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
        "-v",
        "-L",
        "8080:localhost:8080",
        "root@1.2.3.4",
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
