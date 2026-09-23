# -*- coding: utf-8 -*-
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#  Author: Mauro Soria

import ssl
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

import httpx
import requests

from lib.connection import requester as requester_module
from lib.connection.requester import (
    AsyncRequester,
    Requester,
    _find_ssl_error,
    _format_ssl_error,
)
from lib.core.data import options
from lib.core.exceptions import RequestException


def _with_cause(exc: Exception, cause: Exception) -> Exception:
    exc.__cause__ = cause
    return exc


def _with_context(exc: Exception, context: Exception) -> Exception:
    exc.__context__ = context
    return exc


class DummySyncResponse:
    status_code = 200
    headers = {"content-type": "text/plain"}
    history = []
    encoding = "utf-8"

    @staticmethod
    def iter_content(chunk_size):
        del chunk_size
        yield b"body"


class DummySyncSession:
    @staticmethod
    def prepare_request(request):
        return SimpleNamespace(url=request.url)

    def __init__(self, response):
        self.response = response

    def send(self, prep, **kwargs):
        del prep, kwargs
        return self.response


class DummyAsyncResponse:
    status_code = 200
    headers = {"content-type": "text/plain"}
    history = []
    encoding = "utf-8"

    def __init__(self):
        self.closed = False

    @staticmethod
    async def aiter_bytes(chunk_size):
        del chunk_size
        yield b"body"

    async def aclose(self):
        self.closed = True


class DummyAsyncSession:
    @staticmethod
    def build_request(*args, **kwargs):
        del args, kwargs
        return object()

    def __init__(self, response):
        self.response = response

    async def send(self, request, **kwargs):
        del request, kwargs
        return self.response


class BaseRequesterTestCase(TestCase):
    def setUp(self) -> None:
        self.original_options = dict(options)
        options["proxies"] = []
        options["headers"] = {}
        options["data"] = None
        options["cert_file"] = None
        options["key_file"] = None
        options["network_interface"] = None
        options["random_agents"] = False
        options["auth"] = None
        options["auth_type"] = None
        options["max_retries"] = 0
        options["max_rate"] = 0
        options["thread_count"] = 1
        options["follow_redirects"] = False
        options["http_method"] = "GET"
        options["timeout"] = 1
        options["proxy_auth"] = None

    def tearDown(self) -> None:
        options.clear()
        options.update(self.original_options)


class TestSSLHelpers(BaseRequesterTestCase):
    def test_find_ssl_error_direct(self):
        ssl_exc = ssl.SSLError("wrong version number")
        self.assertIs(_find_ssl_error(ssl_exc), ssl_exc)

    def test_find_ssl_error_from_cause(self):
        ssl_exc = ssl.SSLError("wrong version number")
        wrapped = _with_cause(httpx.ConnectError("handshake failed"), ssl_exc)
        self.assertIs(_find_ssl_error(wrapped), ssl_exc)

    def test_find_ssl_error_from_context(self):
        ssl_exc = ssl.SSLError("wrong version number")
        wrapped = _with_context(RuntimeError("wrapper"), ssl_exc)
        self.assertIs(_find_ssl_error(wrapped), ssl_exc)

    def test_format_ssl_error_for_certificate_failure(self):
        cert_exc = ssl.SSLCertVerificationError(
            1,
            "certificate verify failed: self signed certificate",
        )
        self.assertEqual(
            _format_ssl_error(cert_exc, "https://example.com/"),
            "SSL certificate verification failed (self-signed certificate): https://example.com/",
        )


class TestRequesterSSLHandling(BaseRequesterTestCase):
    def test_sync_requests_ssl_error_uses_specific_message(self):
        requester = Requester()
        requester.set_url("https://example.com/")
        error = requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED")

        with patch.object(requester.session, "send", side_effect=error):
            with self.assertRaises(RequestException) as ctx:
                requester.request("admin")

        self.assertEqual(
            str(ctx.exception),
            "SSL certificate verification failed: https://example.com/admin",
        )

    def test_sync_wrapped_certificate_error_uses_specific_message(self):
        requester = Requester()
        requester.set_url("https://example.com/")
        cert_exc = ssl.SSLCertVerificationError(
            1,
            "certificate verify failed: self signed certificate",
        )
        error = _with_cause(requests.exceptions.ConnectionError("boom"), cert_exc)

        with patch.object(requester.session, "send", side_effect=error):
            with self.assertRaises(RequestException) as ctx:
                requester.request("admin")

        self.assertEqual(
            str(ctx.exception),
            "SSL certificate verification failed (self-signed certificate): https://example.com/admin",
        )


class TestRequesterElapsed(TestCase):
    def test_request_elapsed_includes_stream_read(self):
        requester = object.__new__(Requester)
        requester._rate = 0
        requester._url = "https://example.com/"
        requester.proxy_cred = None
        requester.headers = {}
        requester.agents = []
        requester.session = DummySyncSession(DummySyncResponse())

        with patch.object(requester_module.time, "perf_counter", side_effect=[10.0, 10.25]):
            with patch.object(requester_module.logger, "info"):
                response = requester.request("admin")

        self.assertEqual(response.elapsed, 0.25, "Sync elapsed should measure the full streamed request lifecycle")


class TestAsyncRequesterSSLHandling(BaseRequesterTestCase, IsolatedAsyncioTestCase):
    async def test_async_connect_error_with_ssl_cause_uses_ssl_message(self):
        requester = AsyncRequester()
        requester.set_url("https://example.com/")
        error = _with_cause(
            httpx.ConnectError("connect failed"),
            ssl.SSLError("wrong version number"),
        )
        requester.session.send = AsyncMock(side_effect=error)

        with self.assertRaises(RequestException) as ctx:
            await requester.request("admin")

        self.assertEqual(
            str(ctx.exception),
            "SSL protocol version mismatch: https://example.com/admin",
        )

    async def test_async_connect_error_without_ssl_cause_stays_connect_error(self):
        requester = AsyncRequester()
        requester.set_url("https://example.com/")
        requester.session.send = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with self.assertRaises(RequestException) as ctx:
            await requester.request("admin")

        self.assertEqual(str(ctx.exception), "Cannot connect to: example.com")

    async def test_async_connect_error_with_cert_context_uses_cert_message(self):
        requester = AsyncRequester()
        requester.set_url("https://example.com/")
        cert_exc = ssl.SSLCertVerificationError(
            1,
            "certificate verify failed: self signed certificate",
        )
        error = _with_context(httpx.ConnectError("connect failed"), cert_exc)
        requester.session.send = AsyncMock(side_effect=error)

        with self.assertRaises(RequestException) as ctx:
            await requester.request("admin")

        self.assertEqual(
            str(ctx.exception),
            "SSL certificate verification failed (self-signed certificate): https://example.com/admin",
        )


class TestAsyncRequesterElapsed(IsolatedAsyncioTestCase):
    async def test_request_elapsed_waits_for_stream_close(self):
        requester = object.__new__(AsyncRequester)
        requester._rate = 0
        requester._url = "https://example.com/"
        requester.proxy_cred = None
        requester.headers = {}
        requester.agents = []
        requester.session = DummyAsyncSession(DummyAsyncResponse())

        with patch.object(requester_module.time, "perf_counter", side_effect=[20.0, 20.5]):
            with patch.object(requester_module.logger, "info"):
                response = await requester.request("admin")

        self.assertEqual(response.elapsed, 0.5, "Async elapsed should measure the full streamed request lifecycle")
        self.assertTrue(requester.session.response.closed, "Streamed async responses should be closed before elapsed is used")
