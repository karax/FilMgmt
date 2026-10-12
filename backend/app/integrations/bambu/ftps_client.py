"""Minimal read-only implicit FTPS client for a Bambu LAN printer."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import ftplib
from pathlib import Path, PurePosixPath
import socket
import ssl
from typing import Callable, Iterator

from app.integrations.bambu.config import BambuFtpsSettings


_PRINT_DIRECTORIES = ("/cache", "/model")


class BambuFtpsError(Exception):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class BambuFtpsNotConfiguredError(BambuFtpsError):
    pass


class BambuFtpsFileNotFoundError(BambuFtpsError):
    pass


@dataclass(frozen=True)
class BambuRemoteFile:
    path: str
    name: str
    size_bytes: int | None = None
    modified_at: datetime | None = None


class _ImplicitFTP_TLS(ftplib.FTP_TLS):
    """Wrap the control socket in TLS before reading the FTP welcome banner."""

    def connect(
        self,
        host: str = "",
        port: int = 0,
        timeout: object = socket._GLOBAL_DEFAULT_TIMEOUT,
        source_address: tuple[str, int] | None = None,
    ) -> str:
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            self.timeout = timeout  # type: ignore[assignment]
        if source_address is not None:
            self.source_address = source_address
        self.sock = socket.create_connection(
            (self.host, self.port),
            self.timeout,
            source_address=self.source_address,
        )
        self.af = self.sock.family
        self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome


class BambuFtpsClient:
    """Expose only listing, stat, and download operations."""

    def __init__(
        self,
        settings: BambuFtpsSettings,
        *,
        ftp_factory: Callable[[], ftplib.FTP_TLS] | None = None,
    ) -> None:
        self.settings = settings
        self._ftp_factory = ftp_factory or self._new_ftp

    def list_print_files(self) -> tuple[BambuRemoteFile, ...]:
        files: dict[str, BambuRemoteFile] = {}
        with self._session() as ftp:
            available_directory = False
            for directory in _PRINT_DIRECTORIES:
                try:
                    ftp.cwd(directory)
                    names = ftp.nlst()
                    available_directory = True
                except ftplib.error_perm:
                    continue
                except ftplib.all_errors as error:
                    raise BambuFtpsError("LIST_FAILED") from error
                for raw_name in names:
                    remote = _remote_file(directory, raw_name)
                    if remote is not None:
                        files[remote.path] = remote
            if not available_directory:
                raise BambuFtpsError("PRINT_DIRECTORIES_UNAVAILABLE")
        return tuple(sorted(files.values(), key=lambda item: item.path.casefold()))

    def stat_file(self, remote_file: BambuRemoteFile) -> BambuRemoteFile:
        directory, name = _validated_remote_path(remote_file.path)
        with self._session() as ftp:
            try:
                ftp.cwd(directory)
                ftp.voidcmd("TYPE I")
                size = ftp.size(name)
                modified_response = ftp.sendcmd(f"MDTM {name}")
            except ftplib.error_perm as error:
                raise BambuFtpsFileNotFoundError("FILE_NOT_FOUND") from error
            except ftplib.all_errors as error:
                raise BambuFtpsError("STAT_FAILED") from error
        return BambuRemoteFile(
            path=remote_file.path,
            name=remote_file.name,
            size_bytes=size,
            modified_at=_parse_mdtm(modified_response),
        )

    def download(self, remote_file: BambuRemoteFile, destination: Path) -> int:
        directory, name = _validated_remote_path(remote_file.path)
        transferred = 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("xb") as output, self._session() as ftp:
                ftp.cwd(directory)

                def write_chunk(chunk: bytes) -> None:
                    nonlocal transferred
                    transferred += len(chunk)
                    if transferred > self.settings.max_download_bytes:
                        raise BambuFtpsError("DOWNLOAD_TOO_LARGE")
                    output.write(chunk)

                ftp.retrbinary(f"RETR {name}", write_chunk, blocksize=256 * 1024)
                output.flush()
        except BambuFtpsError:
            destination.unlink(missing_ok=True)
            raise
        except ftplib.error_perm as error:
            destination.unlink(missing_ok=True)
            raise BambuFtpsFileNotFoundError("FILE_NOT_FOUND") from error
        except (OSError, *ftplib.all_errors) as error:
            destination.unlink(missing_ok=True)
            raise BambuFtpsError("TRANSFER_FAILED") from error
        return transferred

    @contextmanager
    def _session(self) -> Iterator[ftplib.FTP_TLS]:
        if not self.settings.configured:
            raise BambuFtpsNotConfiguredError("FTPS_NOT_CONFIGURED")
        ftp = self._ftp_factory()
        try:
            try:
                ftp.connect(
                    self.settings.host or "",
                    self.settings.port,
                    timeout=self.settings.timeout_seconds,
                )
            except (OSError, ssl.SSLError, EOFError, ftplib.Error) as error:
                raise BambuFtpsError("CONNECTION_FAILED") from error
            try:
                ftp.login(self.settings.username, self.settings.access_code or "")
            except ftplib.error_perm as error:
                raise BambuFtpsError("AUTHENTICATION_FAILED") from error
            except (OSError, EOFError, ftplib.Error) as error:
                raise BambuFtpsError("CONNECTION_FAILED") from error
            try:
                ftp.prot_p()
                ftp.set_pasv(True)
            except ftplib.all_errors as error:
                raise BambuFtpsError("DATA_CHANNEL_FAILED") from error
            yield ftp
        finally:
            ftp.close()

    def _new_ftp(self) -> ftplib.FTP_TLS:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return _ImplicitFTP_TLS(context=context, timeout=self.settings.timeout_seconds)


def _remote_file(directory: str, raw_name: str) -> BambuRemoteFile | None:
    if "\r" in raw_name or "\n" in raw_name or "\\" in raw_name:
        return None
    parsed = PurePosixPath(raw_name)
    if ".." in parsed.parts:
        return None
    name = parsed.name
    if name in {"", ".", ".."} or not name.casefold().endswith((".3mf", ".gcode.3mf")):
        return None
    return BambuRemoteFile(path=f"{directory}/{name}", name=name)


def _validated_remote_path(path: str) -> tuple[str, str]:
    if "\r" in path or "\n" in path or "\\" in path:
        raise BambuFtpsError("UNSAFE_REMOTE_PATH")
    parsed = PurePosixPath(path)
    if not parsed.is_absolute() or ".." in parsed.parts:
        raise BambuFtpsError("UNSAFE_REMOTE_PATH")
    directory = str(parsed.parent)
    if directory not in _PRINT_DIRECTORIES or parsed.name in {"", ".", ".."}:
        raise BambuFtpsError("UNSAFE_REMOTE_PATH")
    return directory, parsed.name


def _parse_mdtm(response: str) -> datetime | None:
    value = response.removeprefix("213 ").strip()
    try:
        return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None
