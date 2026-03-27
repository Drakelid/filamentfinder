"""Tests for the shared network utility module."""

import os
import pytest
from shared.network import _rewrite_service_hostname, normalize_container_service_urls


class TestRewriteServiceHostname:
    def test_rewrites_matching_hostname(self):
        url = "postgresql://user:pass@db:5432/mydb"
        result = _rewrite_service_hostname(url, "db", "172.30.0.3")
        assert result == "postgresql://user:pass@172.30.0.3:5432/mydb"

    def test_no_rewrite_when_hostname_differs(self):
        url = "postgresql://user:pass@otherhost:5432/mydb"
        result = _rewrite_service_hostname(url, "db", "172.30.0.3")
        assert result == url

    def test_empty_url_returns_empty(self):
        assert _rewrite_service_hostname("", "db", "172.30.0.3") == ""

    def test_none_url_returns_none(self):
        assert _rewrite_service_hostname(None, "db", "172.30.0.3") is None

    def test_preserves_path_and_query(self):
        url = "redis://redis:6379/0?timeout=5"
        result = _rewrite_service_hostname(url, "redis", "172.30.0.4")
        assert result == "redis://172.30.0.4:6379/0?timeout=5"

    def test_no_port(self):
        url = "http://db/path"
        result = _rewrite_service_hostname(url, "db", "172.30.0.3")
        assert result == "http://172.30.0.3/path"

    def test_credentials_without_password(self):
        url = "redis://admin@redis:6379/0"
        result = _rewrite_service_hostname(url, "redis", "172.30.0.4")
        assert result == "redis://admin@172.30.0.4:6379/0"


class TestNormalizeContainerServiceUrls:
    def test_no_rewrite_when_gluetun_disabled(self, monkeypatch):
        monkeypatch.delenv("GLUETUN_ENABLED", raising=False)
        url = "postgresql://user:pass@db:5432/mydb"
        assert normalize_container_service_urls(url) == url

    def test_no_rewrite_when_gluetun_false(self, monkeypatch):
        monkeypatch.setenv("GLUETUN_ENABLED", "false")
        url = "postgresql://user:pass@db:5432/mydb"
        assert normalize_container_service_urls(url) == url

    def test_rewrites_db_when_gluetun_enabled(self, monkeypatch):
        monkeypatch.setenv("GLUETUN_ENABLED", "true")
        url = "postgresql://user:pass@db:5432/mydb"
        result = normalize_container_service_urls(url)
        assert "172.30.0.3" in result
        assert "db" not in result.split("://")[1].split("/")[0]

    def test_rewrites_redis_when_gluetun_enabled(self, monkeypatch):
        monkeypatch.setenv("GLUETUN_ENABLED", "1")
        url = "redis://redis:6379/0"
        result = normalize_container_service_urls(url)
        assert "172.30.0.4" in result
