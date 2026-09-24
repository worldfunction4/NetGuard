"""重连策略回归：ValueError 立即失败；OSError 仍重试；认证失败仍不重试"""

from unittest.mock import patch

import pytest
from netmiko import NetMikoAuthenticationException

from devices.try_connect import connect_with_retry


class TestRetryPolicy:
    @patch("devices.try_connect.time.sleep")
    def test_value_error_raises_immediately_without_retry(self, mock_sleep):
        """修复前 ValueError 会进入通用重试，sleep 且多次调用 connect_fn"""
        calls = {"n": 0}
        exc = ValueError("非法设备参数")

        def boom():
            calls["n"] += 1
            raise exc

        with pytest.raises(ValueError) as exc_info:
            connect_with_retry(boom, max_retries=5, retry_interval=1.0)

        assert exc_info.value is exc
        assert calls["n"] == 1
        mock_sleep.assert_not_called()

    @patch("devices.try_connect.time.sleep")
    def test_oserror_still_retries(self, mock_sleep):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("网络抖动")
            return "connected"

        result = connect_with_retry(flaky, max_retries=3, retry_interval=0.2)

        assert result == "connected"
        assert calls["n"] == 2
        mock_sleep.assert_called_once_with(0.2)

    @patch("devices.try_connect.time.sleep")
    def test_auth_failure_still_does_not_retry(self, mock_sleep):
        calls = {"n": 0}
        exc = NetMikoAuthenticationException("密码错误")

        def auth_fail():
            calls["n"] += 1
            raise exc

        with pytest.raises(NetMikoAuthenticationException) as exc_info:
            connect_with_retry(auth_fail, max_retries=5, retry_interval=1.0)

        assert exc_info.value is exc
        assert calls["n"] == 1
        mock_sleep.assert_not_called()
