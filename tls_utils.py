"""Verified TLS helpers for Learning Genie services under Python 3.14."""

from __future__ import annotations

import os
import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

# Python 3.14's strict X.509 mode rejects these otherwise trusted chains because
# an intermediate certificate lacks an Authority Key Identifier. Clearing only
# VERIFY_X509_STRICT retains CA-chain validation and hostname verification.
LEARNING_GENIE_HOSTS = {
    "api2.learning-genie.com",
    "apilearninggenie.quickblox.com",
    "s3.amazonaws.com",
    "com-learning-genie-prod-im.s3.us-west-1.amazonaws.com",
}


def verified_context_for_url(url: str) -> ssl.SSLContext:
    context = ssl.create_default_context()
    hostname = urllib.parse.urlparse(url).hostname
    if hostname in LEARNING_GENIE_HOSTS and hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def normalized_request_url(url: str) -> str:
    """Normalize LearningGenie's legacy S3 path without changing its object key."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname == "s3.amazonaws.com" and parsed.path.startswith("//"):
        parsed = parsed._replace(path=f"/{parsed.path.lstrip('/')}")
    return urllib.parse.urlunsplit(parsed)


def download_to_file(url: str, filepath: str, timeout: int = 120, attempts: int = 4) -> None:
    """Download atomically, retrying transient HTTP and network failures."""
    partial = f"{filepath}.part"
    request_url = normalized_request_url(url)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(
                request_url,
                context=verified_context_for_url(request_url),
                timeout=timeout,
            ) as response:
                with open(partial, "wb") as output:
                    shutil.copyfileobj(response, output)
            os.replace(partial, filepath)
            return
        except Exception as exc:
            try:
                os.remove(partial)
            except FileNotFoundError:
                pass

            transient_http = isinstance(exc, urllib.error.HTTPError) and (exc.code == 429 or 500 <= exc.code < 600)
            transient_network = isinstance(exc, (urllib.error.URLError, TimeoutError))
            if attempt == attempts or not (transient_http or transient_network):
                raise
            time.sleep(attempt * 2)
