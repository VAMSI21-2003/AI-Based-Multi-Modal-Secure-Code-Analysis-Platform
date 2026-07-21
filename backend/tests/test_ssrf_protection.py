# =============================================================================
# test_ssrf_protection.py -- SSRF hardening regression tests for
# github_service._validate_url() (P0 item 4).
#
# Covers: loopback, unspecified/0.0.0.0, link-local/cloud-metadata,
# private RFC1918 ranges, IPv6 loopback (unit-level, since the URL syntax
# regex itself already rejects bracketed IPv6 literals), and the explicit
# "localhost" hostname short-circuit.
# =============================================================================

import pytest

import github_service


def test_is_unsafe_address_flags_loopback():
    assert github_service._is_unsafe_address("127.0.0.1") is True


def test_is_unsafe_address_flags_unspecified():
    assert github_service._is_unsafe_address("0.0.0.0") is True


def test_is_unsafe_address_flags_link_local_cloud_metadata():
    # 169.254.169.254 is the AWS/GCP/Azure instance-metadata address --
    # a classic SSRF target for credential theft.
    assert github_service._is_unsafe_address("169.254.169.254") is True


def test_is_unsafe_address_flags_rfc1918_private_ranges():
    assert github_service._is_unsafe_address("10.0.0.5") is True
    assert github_service._is_unsafe_address("172.16.0.5") is True
    assert github_service._is_unsafe_address("192.168.1.1") is True


def test_is_unsafe_address_flags_ipv6_loopback():
    assert github_service._is_unsafe_address("::1") is True


def test_is_unsafe_address_flags_ipv6_link_local():
    assert github_service._is_unsafe_address("fe80::1") is True


def test_is_unsafe_address_allows_a_real_public_ip():
    assert github_service._is_unsafe_address("8.8.8.8") is False


def test_validate_url_rejects_literal_loopback_ip():
    with pytest.raises(ValueError):
        github_service._validate_url("http://127.0.0.1/repo.git")


def test_validate_url_rejects_literal_cloud_metadata_ip():
    with pytest.raises(ValueError):
        github_service._validate_url("http://169.254.169.254/latest/meta-data/")


def test_validate_url_rejects_literal_private_ip():
    with pytest.raises(ValueError):
        github_service._validate_url("http://192.168.1.1/repo.git")


def test_validate_url_rejects_localhost_hostname():
    with pytest.raises(ValueError):
        github_service._validate_url("http://localhost/repo.git")


def test_validate_url_rejects_gcp_metadata_hostname():
    with pytest.raises(ValueError):
        github_service._validate_url("http://metadata.google.internal/computeMetadata/v1/")


def test_validate_url_accepts_a_real_public_github_url():
    # Real DNS resolution -- requires network access, matching the existing
    # (pre-SSRF-fix) test of the same name's behavior.
    result = github_service._validate_url("https://github.com/madler/zlib")
    assert result == "https://github.com/madler/zlib"
