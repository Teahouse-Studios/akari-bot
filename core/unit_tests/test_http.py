import socket
from unittest.mock import patch

import pytest

from core.utils.http import private_ip_check


def test_private_ip_check_allows_public_ip():
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 0))]
        private_ip_check("http://example.com")


def test_private_ip_check_blocks_private_ip():
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.0.1', 0))]
        with pytest.raises(ValueError):
            private_ip_check("http://example.com")


def test_private_ip_check_ipv6_private():
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('::1', 0))]
        with pytest.raises(ValueError):
            private_ip_check("http://localhost")
