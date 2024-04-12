"""
Various functionalities to make easier to work with the libpq.
"""

# Copyright (C) 2020 The Psycopg Team

import re
import os
import sys
import logging
import ctypes.util
from typing import cast, NamedTuple, Optional, Union

from .abc import PGconn, PGresult
from ._enums import ConnStatus, TransactionStatus, PipelineStatus
from .._compat import cache
from .._encodings import pgconn_encoding

logger = logging.getLogger("psycopg.pq")

OK = ConnStatus.OK


class PGnotify(NamedTuple):
    relname: bytes
    be_pid: int
    extra: bytes


class ConninfoOption(NamedTuple):
    keyword: bytes
    envvar: Optional[bytes]
    compiled: Optional[bytes]
    val: Optional[bytes]
    label: bytes
    dispchar: bytes
    dispsize: int


class PGresAttDesc(NamedTuple):
    name: bytes
    tableid: int
    columnid: int
    format: int
    typid: int
    typlen: int
    atttypmod: int


@cache
def find_libpq_full_path() -> Optional[str]:
    if sys.platform == "win32":
        libname = ctypes.util.find_library("libpq.dll")

    elif sys.platform == "darwin":
        libname = ctypes.util.find_library("libpq.dylib")
        # (hopefully) temporary hack: libpq not in a standard place
        # https://github.com/orgs/Homebrew/discussions/3595
        # If pg_config is available and agrees, let's use its indications.
        if not libname:
            try:
                import subprocess as sp

                libdir = sp.check_output(["pg_config", "--libdir"]).strip().decode()
                libname = os.path.join(libdir, "libpq.dylib")
                if not os.path.exists(libname):
                    libname = None
            except Exception as ex:
                logger.debug("couldn't use pg_config to find libpq: %s", ex)

    else:
        libname = ctypes.util.find_library("pq")

    return libname


def error_message(obj: Union[PGconn, PGresult], encoding: str = "utf8") -> str:
    """
    Return an error message from a `PGconn` or `PGresult`.

    The return value is a `!str` (unlike pq data which is usually `!bytes`):
    use the connection encoding if available, otherwise the `!encoding`
    parameter as a fallback for decoding. Don't raise exceptions on decoding
    errors.

    """
    bmsg: bytes

    if hasattr(obj, "error_field"):
        # obj is a PGresult
        obj = cast(PGresult, obj)
        bmsg = obj.error_message

    elif hasattr(obj, "error_message"):
        # obj is a PGconn
        if obj.status == OK:
            encoding = pgconn_encoding(obj)
        bmsg = obj.error_message

    else:
        raise TypeError(f"PGconn or PGresult expected, got {type(obj).__name__}")

    if bmsg:
        msg = strip_severity(bmsg.decode(encoding, "replace"))
    else:
        msg = "no details available"

    return msg


# Possible prefixes to strip for error messages, in the known localizations.
# This regular expression is generated from PostgreSQL sources using the
# `tools/update_error_prefixes.py` script
PREFIXES = re.compile(
    # autogenerated: start
    r"""
    ^ (?:
      DEBUG | INFO | HINWEIS | WARNUNG | FEHLER | LOG | FATAL | PANIK  # de
    | DEBUG | INFO | NOTICE | WARNING | ERROR | LOG | FATAL | PANIC  # en
    | DEBUG | INFO | NOTICE | WARNING | ERROR | LOG | FATAL | PANIC  # es
    | DEBUG | INFO | NOTICE | ATTENTION | ERREUR | LOG | FATAL | PANIC  # fr
    | DEBUG | INFO | NOTICE | PERINGATAN | ERROR | LOG | FATAL | PANIK  # id
    | DEBUG | INFO | NOTIFICA | ATTENZIONE | ERRORE | LOG | FATALE | PANICO  # it
    | DEBUG | INFO | NOTICE | WARNING | ERROR | LOG | FATAL | PANIC  # ja
    | 디버그 | 정보 | 알림 | 경고 | 오류 | 로그 | 치명적오류 | 손상  # ko
    | DEBUG | INFORMACJA | UWAGA | OSTRZEŻENIE | BŁĄD | DZIENNIK | KATASTROFALNY | PANIKA  # pl
    | DEPURAÇÃO | INFO | NOTA | AVISO | ERRO | LOG | FATAL | PÂNICO  # pt_BR
    | ОТЛАДКА | ИНФОРМАЦИЯ | ЗАМЕЧАНИЕ | ПРЕДУПРЕЖДЕНИЕ | ОШИБКА | СООБЩЕНИЕ | ВАЖНО | ПАНИКА  # ru
    | DEBUG | INFO | NOTIS | VARNING | FEL | LOGG | FATALT | PANIK  # sv
    | DEBUG | BİLGİ | NOT | UYARI | HATA | LOG | ÖLÜMCÜL\ \(FATAL\) | KRİTİK  # tr
    | НАЛАГОДЖЕННЯ | ІНФОРМАЦІЯ | ПОВІДОМЛЕННЯ | ПОПЕРЕДЖЕННЯ | ПОМИЛКА | ЗАПИСУВАННЯ | ФАТАЛЬНО | ПАНІКА  # uk
    | 调试 | 信息 | 注意 | 警告 | 错误 | 日志 | 致命错误 | 比致命错误还过分的错误  # zh_CN
    ) : \s+
    """,  # noqa: E501
    # autogenerated: end
    re.VERBOSE | re.MULTILINE,
)


def strip_severity(msg: str) -> str:
    """Strip severity and whitespaces from error message."""
    m = PREFIXES.match(msg)
    if m:
        msg = msg[m.span()[1] :]

    return msg.strip()


def connection_summary(pgconn: PGconn) -> str:
    """
    Return summary information on a connection.

    Useful for __repr__
    """
    parts = []
    if pgconn.status == OK:
        # Put together the [STATUS]
        status = TransactionStatus(pgconn.transaction_status).name
        if pgconn.pipeline_status:
            status += f", pipeline={PipelineStatus(pgconn.pipeline_status).name}"

        # Put together the (CONNECTION)
        if not pgconn.host.startswith(b"/"):
            parts.append(("host", pgconn.host.decode()))
        if pgconn.port != b"5432":
            parts.append(("port", pgconn.port.decode()))
        if pgconn.user != pgconn.db:
            parts.append(("user", pgconn.user.decode()))
        parts.append(("database", pgconn.db.decode()))

    else:
        status = ConnStatus(pgconn.status).name

    sparts = " ".join("%s=%s" % part for part in parts)
    if sparts:
        sparts = f" ({sparts})"
    return f"[{status}]{sparts}"


def version_pretty(version: int) -> str:
    """
    Return a pretty representation of a PostgreSQL version

    For instance: 140002 -> 14.2, 90610 -> 9.6.10
    """
    version, patch = divmod(version, 100)
    major, minor = divmod(version, 100)
    if major >= 10 and minor == 0:
        return f"{major}.{patch}"
    else:
        return f"{major}.{minor}.{patch}"
