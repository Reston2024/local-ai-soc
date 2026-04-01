import pyotp
import pytest

from backend.core.totp_utils import (
    generate_totp_secret,
    get_provisioning_uri,
    totp_qr_png_b64,
    verify_totp,
    _seen_totp,
)


class TestTOTPGenerate:
    def test_generate_secret_is_base32(self):
        """generate_totp_secret() returns uppercase base32 string >= 16 chars."""
        s = generate_totp_secret()
        assert isinstance(s, str)
        assert len(s) >= 16
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
        assert all(c in valid_chars for c in s)


class TestTOTPVerify:
    def test_verify_current_code(self):
        """verify_totp(secret, current_code) returns True."""
        s = generate_totp_secret()
        code = pyotp.TOTP(s).now()
        assert verify_totp(s, code, "op-test-verify") is True

    def test_verify_wrong_code(self):
        """verify_totp(secret, '000000') returns False."""
        s = generate_totp_secret()
        # "000000" is astronomically unlikely to be the current TOTP code
        result = verify_totp(s, "000000", "op-test-wrong")
        assert result is False

    def test_replay_prevention(self):
        """Same code rejected twice within same 30 s window."""
        s = generate_totp_secret()
        code = pyotp.TOTP(s).now()
        # Clear any prior state for this operator to avoid cross-test pollution
        _seen_totp.pop("op-test-replay", None)
        first = verify_totp(s, code, "op-test-replay")
        second = verify_totp(s, code, "op-test-replay")
        assert first is True
        assert second is False


class TestTOTPProvisioning:
    def test_provisioning_uri_format(self):
        """get_provisioning_uri() starts with 'otpauth://totp/'."""
        uri = get_provisioning_uri(generate_totp_secret(), "alice")
        assert uri.startswith("otpauth://totp/")

    def test_qr_png_b64(self):
        """totp_qr_png_b64() returns non-empty base64 data URI string."""
        uri = get_provisioning_uri(generate_totp_secret(), "bob")
        result = totp_qr_png_b64(uri)
        assert result.startswith("data:image/png;base64,")
        assert len(result) > 100
