from io import StringIO
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.integrations.bambu.config import (
    DEFAULT_BAMBU_FTPS_PORT,
    BambuFtpsSettings,
    load_bambu_ftps_settings,
)
from app.integrations.bambu.ftps_client import (
    BambuFtpsClient,
    BambuFtpsError,
    BambuRemoteFile,
    _ImplicitFTP_TLS,
)


class FakeFtp:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.directory = "/"

    def connect(self, host, port, timeout): self.calls.append(("connect", host, port, timeout))
    def login(self, username, password): self.calls.append(("login", username, password))
    def prot_p(self): self.calls.append(("prot_p",))
    def set_pasv(self, enabled): self.calls.append(("set_pasv", enabled))
    def cwd(self, directory): self.directory = directory; self.calls.append(("cwd", directory))
    def nlst(self): return ["Cube.3mf", "notes.txt", "../unsafe.3mf"]
    def voidcmd(self, command): self.calls.append(("voidcmd", command))
    def size(self, name): return 123
    def sendcmd(self, command): return "213 20261005200316"
    def retrbinary(self, command, callback, blocksize): callback(b"archive"); self.calls.append(("retrbinary", command, blocksize))
    def close(self): self.calls.append(("close",))


def settings(**overrides) -> BambuFtpsSettings:
    values = {"host": "192.0.2.10", "access_code": "never-log-secret"}
    values.update(overrides)
    return BambuFtpsSettings(**values)


def test_ftps_configuration_defaults_to_implicit_port_and_redacts_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAMBU_HOST", "192.0.2.10")
    monkeypatch.setenv("BAMBU_ACCESS_CODE", "never-log-secret")
    monkeypatch.delenv("BAMBU_FTPS_PORT", raising=False)
    configured = load_bambu_ftps_settings()

    assert configured.configured is True
    assert configured.port == DEFAULT_BAMBU_FTPS_PORT == 990
    assert configured.username == "bblp"
    assert "never-log-secret" not in repr(configured)


def test_implicit_tls_wraps_control_socket_before_reading_welcome(monkeypatch: pytest.MonkeyPatch) -> None:
    plain_socket = MagicMock()
    plain_socket.family = 2
    wrapped_socket = MagicMock()
    wrapped_socket.family = 2
    wrapped_socket.makefile.return_value = StringIO("220 ready\r\n")
    context = MagicMock()
    context.wrap_socket.return_value = wrapped_socket
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: plain_socket)
    ftp = _ImplicitFTP_TLS(context=context)

    assert ftp.connect("printer.local", 990) == "220 ready"
    context.wrap_socket.assert_called_once_with(plain_socket, server_hostname="printer.local")
    wrapped_socket.makefile.assert_called_once()


def test_client_lists_only_safe_3mf_files_and_protects_passive_data_channel() -> None:
    fake = FakeFtp()
    client = BambuFtpsClient(settings(), ftp_factory=lambda: fake)

    files = client.list_print_files()

    assert [item.path for item in files] == ["/cache/Cube.3mf", "/model/Cube.3mf"]
    assert ("login", "bblp", "never-log-secret") in fake.calls
    assert ("prot_p",) in fake.calls
    assert ("set_pasv", True) in fake.calls
    assert not hasattr(client, "upload")
    assert not hasattr(client, "delete")
    assert not hasattr(client, "rename")


def test_stat_and_bounded_download(tmp_path: Path) -> None:
    fake = FakeFtp()
    client = BambuFtpsClient(settings(max_download_bytes=7), ftp_factory=lambda: fake)
    remote = BambuRemoteFile(path="/cache/Cube.3mf", name="Cube.3mf")

    stat = client.stat_file(remote)
    assert stat.size_bytes == 123
    assert stat.modified_at and stat.modified_at.isoformat() == "2026-10-05T20:03:16+00:00"
    destination = tmp_path / "Cube.3mf"
    assert client.download(remote, destination) == 7
    assert destination.read_bytes() == b"archive"


def test_oversized_download_is_rejected_and_partial_file_is_removed(tmp_path: Path) -> None:
    client = BambuFtpsClient(settings(max_download_bytes=6), ftp_factory=FakeFtp)
    destination = tmp_path / "oversized.3mf"

    with pytest.raises(BambuFtpsError, match="DOWNLOAD_TOO_LARGE"):
        client.download(BambuRemoteFile(path="/cache/Cube.3mf", name="Cube.3mf"), destination)

    assert not destination.exists()


def test_credentials_do_not_appear_in_controlled_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenFtp(FakeFtp):
        def login(self, username, password):
            raise OSError(f"bad password {password}")

    caplog.set_level(logging.DEBUG)
    client = BambuFtpsClient(settings(), ftp_factory=BrokenFtp)
    with pytest.raises(BambuFtpsError) as caught:
        client.list_print_files()

    assert "never-log-secret" not in str(caught.value)
    assert "never-log-secret" not in caplog.text
