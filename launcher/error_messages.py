"""
Turns raw failures into something a user can act on.

Installation problems surface as whatever pip, uv, urllib or the OS happened to
say - a wall of output, a bare "[WinError 2]", a TLS handshake dump. Those
belong in the log file; the UI needs one sentence telling the user what to do.
`classify()` maps the common signatures to that sentence, and keeps the raw
text available for the log.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Failure:
    code: str
    message: str


# Ordered: the first pattern that matches wins, so specific signatures
# (a TLS error is also a network error) must come before general ones.
_PATTERNS = [
    (
        "tls",
        r"certificate_verify_failed|invalid peer certificate|unknownissuer|"
        r"ssl: certificate|certificate verify failed|sslcertverificationerror|self.signed certificate",
        "Secure connection failed. A corporate proxy, VPN or antivirus may be "
        "intercepting HTTPS traffic - try another network, or allow python.exe "
        "through it.",
    ),
    (
        "github_rate_limit",
        r"rate limit|api rate limit exceeded",
        "GitHub is temporarily rate-limiting this computer. Wait about an hour "
        "and try again.",
    ),
    (
        "network",
        r"getaddrinfo|name or service not known|temporary failure in name resolution|"
        r"nodename nor servname|failed to establish a new connection|network is unreachable|"
        r"connection reset|connection aborted|error sending request|failed to fetch|"
        r"no route to host|urlopen error|winerror 10054|winerror 10060|winerror 10061",
        "Could not reach the internet. Check your connection and try again.",
    ),
    (
        "timeout",
        r"timed out|timeout",
        "The operation timed out - the connection may be very slow. Try again.",
    ),
    (
        "disk_full",
        r"no space left|not enough space on the disk|errno 28|winerror 112|disk quota exceeded",
        "Not enough free disk space. Free up some space and try again "
        "(a full setup needs roughly 8 GB).",
    ),
    (
        "read_only",
        r"read-only file system|errno 30",
        "PyPottery cannot write to its own folder. Move the application to a "
        "normal folder (on macOS: Applications; on Windows: not Program Files) "
        "and start it again.",
    ),
    (
        "permission",
        r"permission denied|access is denied|errno 13|winerror 5",
        "Permission denied while writing files. Check the folder's permissions, "
        "or move PyPottery somewhere your user can write.",
    ),
    (
        "file_in_use",
        r"winerror 32|being used by another process|text file busy",
        "A file is in use by another program. Close the application (and any "
        "antivirus scan on this folder) and try again.",
    ),
    (
        "package_unavailable",
        r"no matching distribution|could not find a version|no solution found",
        "A required package isn't available for this system. Please report this "
        "with the log file.",
    ),
    (
        "missing_binary",
        r"winerror 2|no such file or directory|is not recognized as an internal|"
        r"cannot find the file specified|executable not found",
        "A required program could not be started. Reinstalling PyPottery usually "
        "fixes this - the log file has the details.",
    ),
    (
        "not_found",
        r"404|not found",
        "The requested download was not found. It may have been removed or "
        "renamed - please report this.",
    ),
    (
        "forbidden",
        r"403|forbidden",
        "The download was refused by the server. Try again later.",
    ),
]

_UNKNOWN = "Something went wrong. The details are in the log file (Console panel > Open logs folder)."


def classify(error: Union[BaseException, str, None]) -> Failure:
    """Best-effort mapping of an exception or raw tool output to a Failure."""
    if error is None:
        return Failure("unknown", _UNKNOWN)

    if isinstance(error, subprocess.TimeoutExpired):
        return Failure("timeout", "The operation timed out - the connection may be very slow. Try again.")

    text = str(error)
    if isinstance(error, BaseException):
        # The class name carries the signal for several of these (SSLCertVerificationError,
        # PermissionError, ...) even when the message itself is unhelpful.
        text = f"{type(error).__name__}: {text}"

    haystack = text.lower()
    for code, pattern, message in _PATTERNS:
        if re.search(pattern, haystack):
            return Failure(code, message)

    return Failure("unknown", _UNKNOWN)


def describe(error: Union[BaseException, str, None], prefix: str = "") -> str:
    """A user-facing one-liner, optionally prefixed with what was being done."""
    message = classify(error).message
    return f"{prefix}: {message}" if prefix else message
