"""
psycopg capabilities objects
"""

# Copyright (C) 2024 The Psycopg Team

from . import pq
from . import _cmodule
from .errors import NotSupportedError


class Capabilities:
    """
    An object to check if a feature is supported by the libpq available on the client.
    """

    def has_encrypt_password(self, check: bool = False) -> bool:
        """Check if the `PGconn.encrypt_password()` method is implemented.

        The feature requires libpq 10.0 and greater.
        """
        return self._has_feature("pq.PGconn.encrypt_password()", 100000, check=check)

    def has_hostaddr(self, check: bool = False) -> bool:
        """Check if the `ConnectionInfo.hostaddr` attribute is implemented.

        The feature requires libpq 12.0 and greater.
        """
        return self._has_feature("Connection.info.hostaddr", 120000, check=check)

    def has_pipeline(self, check: bool = False) -> bool:
        """Check if the :ref:`pipeline mode <pipeline-mode>` is supported.

        The feature requires libpq 14.0 and greater.
        """
        return self._has_feature("Connection.pipeline()", 140000, check=check)

    def has_set_trace_flags(self, check: bool = False) -> bool:
        """Check if the `pq.PGconn.set_trace_flags()` method is implemented.

        The feature requires libpq 14.0 and greater.
        """
        return self._has_feature("PGconn.set_trace_flags()", 140000, check=check)

    def has_cancel_safe(self, check: bool = False) -> bool:
        """Check if the `Connection.cancel_safe()` method is implemented.

        The feature requires libpq 17.0 and greater.
        """
        return self._has_feature("Connection.cancel_safe()", 170000, check=check)

    def has_pgbouncer_prepared(self, check: bool = False) -> bool:
        """Check if prepared statements in PgBouncer are supported.

        The feature requires libpq 17.0 and greater.
        """
        return self._has_feature(
            "PgBouncer prepared statements compatibility", 170000, check=check
        )

    def _has_feature(self, feature: str, want_version: int, check: bool) -> bool:
        """
        Check is a version is supported.

        If `check` is true, raise an exception with an explicative message
        explaining why the feature is not supported.

        The expletive messages, are left to the user.
        """
        msg = ""
        if pq.version() < want_version:
            msg = (
                f"the feature '{feature}' is not available:"
                f" the client libpq version (imported from {self._libpq_source()})"
                f" is {pq.version_pretty(pq.version())}; the feature"
                f" requires libpq version {pq.version_pretty(want_version)}"
                " or newer"
            )

        elif pq.__build_version__ < want_version:
            msg = (
                f"the feature '{feature}' is not available:"
                f" you are using a psycopg[{pq.__impl__}] libpq wrapper built"
                f" with libpq version {pq.version_pretty(pq.__build_version__)};"
                " the feature requires libpq version"
                f" {pq.version_pretty(want_version)} or newer"
            )

        if not msg:
            return True
        elif check:
            raise NotSupportedError(msg)
        else:
            return False

    def _libpq_source(self) -> str:
        """Return a string reporting where the libpq comes from."""
        if pq.__impl__ == "binary":
            version: str = _cmodule.__version__ or "unknown"
            return f"the psycopg[binary] package version {version}"
        else:
            return "system libraries"
