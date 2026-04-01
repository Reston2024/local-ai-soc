import pytest


class TestTOTPGenerate:
    def test_generate_secret_is_base32(self):
        """generate_totp_secret() returns uppercase base32 string >= 16 chars."""
        pytest.fail("NOT IMPLEMENTED")


class TestTOTPVerify:
    def test_verify_current_code(self):
        """verify_totp(secret, current_code) returns True."""
        pytest.fail("NOT IMPLEMENTED")

    def test_verify_wrong_code(self):
        """verify_totp(secret, '000000') returns False."""
        pytest.fail("NOT IMPLEMENTED")

    def test_replay_prevention(self):
        """Same code rejected twice within same 30 s window."""
        pytest.fail("NOT IMPLEMENTED")


class TestTOTPProvisioning:
    def test_provisioning_uri_format(self):
        """get_provisioning_uri() starts with 'otpauth://totp/'."""
        pytest.fail("NOT IMPLEMENTED")

    def test_qr_png_b64(self):
        """totp_qr_png_b64() returns non-empty base64 string."""
        pytest.fail("NOT IMPLEMENTED")
