"""重连机制单元测试——无需真实网络，全部使用 mock"""
import pytest
from unittest.mock import MagicMock, patch, call
from netmiko import (
    NetmikoTimeoutException,
    NetMikoAuthenticationException,
    NetmikoBaseException,
)

from devices.try_connect import connect_with_retry, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_INTERVAL


# ── 辅助工厂 ──────────────────────────────────────────────────────────────────

def _ok_fn(return_val="conn"):
    """始终成功的连接函数"""
    return MagicMock(return_value=return_val)


def _fail_then_ok(fail_times: int, exc_type=NetmikoTimeoutException):
    """前 fail_times 次抛异常，之后成功的连接函数"""
    calls = [0]
    def fn():
        calls[0] += 1
        if calls[0] <= fail_times:
            raise exc_type(f"模拟失败 #{calls[0]}")
        return MagicMock()
    return fn


# ── 正常连接 ──────────────────────────────────────────────────────────────────

class TestConnectSuccess:

    @patch("devices.try_connect.time.sleep")
    def test_first_attempt_succeeds_no_sleep(self, mock_sleep):
        """第一次就成功，不应该 sleep"""
        mock_conn = MagicMock()
        result = connect_with_retry(lambda: mock_conn, device_name="SW-01")
        assert result is mock_conn
        mock_sleep.assert_not_called()

    @patch("devices.try_connect.time.sleep")
    def test_returns_connect_fn_return_value(self, _):
        sentinel = object()
        result = connect_with_retry(lambda: sentinel)
        assert result is sentinel


# ── 重连后成功 ────────────────────────────────────────────────────────────────

class TestRetryThenSuccess:

    @patch("devices.try_connect.time.sleep")
    def test_fail_once_then_succeed(self, mock_sleep):
        """失败 1 次后成功，应 sleep 1 次"""
        fn = _fail_then_ok(1)
        result = connect_with_retry(fn, max_retries=5, retry_interval=1.0)
        assert result is not None
        mock_sleep.assert_called_once_with(1.0)

    @patch("devices.try_connect.time.sleep")
    def test_fail_four_times_then_succeed(self, mock_sleep):
        """失败 4 次后第 5 次成功，恰好用完重连次数"""
        fn = _fail_then_ok(4)
        result = connect_with_retry(fn, max_retries=5, retry_interval=1.0)
        assert result is not None
        assert mock_sleep.call_count == 4

    @patch("devices.try_connect.time.sleep")
    def test_sleep_uses_configured_interval(self, mock_sleep):
        fn = _fail_then_ok(2)
        connect_with_retry(fn, max_retries=5, retry_interval=2.5)
        for c in mock_sleep.call_args_list:
            assert c == call(2.5)

    @patch("devices.try_connect.time.sleep")
    def test_base_exception_also_retries(self, mock_sleep):
        """NetmikoBaseException 也应触发重连"""
        fn = _fail_then_ok(2, NetmikoBaseException)
        result = connect_with_retry(fn, max_retries=5, retry_interval=0.1)
        assert result is not None
        assert mock_sleep.call_count == 2

    @patch("devices.try_connect.time.sleep")
    def test_generic_exception_also_retries(self, mock_sleep):
        """普通 OSError 也应触发重连"""
        fn = _fail_then_ok(1, OSError)
        result = connect_with_retry(fn, max_retries=3, retry_interval=0.1)
        assert result is not None


# ── 超出重连次数，最终失败 ────────────────────────────────────────────────────

class TestRetryExhausted:

    @patch("devices.try_connect.time.sleep")
    def test_all_retries_exhausted_raises(self, _):
        """5 次全部失败，应上抛最后一次异常"""
        fn = _fail_then_ok(99)  # 永远失败
        with pytest.raises(NetmikoTimeoutException):
            connect_with_retry(fn, max_retries=5, retry_interval=0.01)

    @patch("devices.try_connect.time.sleep")
    def test_sleep_count_equals_max_retries_minus_one(self, mock_sleep):
        """5 次全失败，sleep 应被调用 4 次（最后一次失败后不 sleep）"""
        fn = _fail_then_ok(99)
        with pytest.raises(Exception):
            connect_with_retry(fn, max_retries=5, retry_interval=0.01)
        assert mock_sleep.call_count == 4

    @patch("devices.try_connect.time.sleep")
    def test_max_retries_one_means_no_sleep(self, mock_sleep):
        """max_retries=1 时：只尝试一次，失败直接上抛，不 sleep"""
        fn = _fail_then_ok(99)
        with pytest.raises(Exception):
            connect_with_retry(fn, max_retries=1, retry_interval=0.01)
        mock_sleep.assert_not_called()


# ── 认证失败不重连 ────────────────────────────────────────────────────────────

class TestAuthFailureNoRetry:

    @patch("devices.try_connect.time.sleep")
    def test_auth_failure_raises_immediately(self, mock_sleep):
        """认证失败应立即上抛，不重连，不 sleep"""
        def auth_fail():
            raise NetMikoAuthenticationException("密码错误")

        with pytest.raises(NetMikoAuthenticationException):
            connect_with_retry(auth_fail, max_retries=5, retry_interval=1.0)
        mock_sleep.assert_not_called()

    @patch("devices.try_connect.time.sleep")
    def test_auth_failure_propagates_original_exception(self, _):
        """上抛的异常应是原始认证异常，不包装"""
        exc = NetMikoAuthenticationException("bad password")
        def fail():
            raise exc
        with pytest.raises(NetMikoAuthenticationException) as exc_info:
            connect_with_retry(fail, max_retries=5, retry_interval=0.1)
        assert exc_info.value is exc


# ── 参数校验 ──────────────────────────────────────────────────────────────────

class TestParameterValidation:

    def test_max_retries_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="max_retries"):
            connect_with_retry(lambda: None, max_retries=0)

    def test_max_retries_negative_raises_value_error(self):
        with pytest.raises(ValueError):
            connect_with_retry(lambda: None, max_retries=-1)


# ── 默认参数约束验证 ──────────────────────────────────────────────────────────

class TestDefaultConstraints:

    def test_default_max_retries_is_5(self):
        assert DEFAULT_MAX_RETRIES == 5

    def test_total_wait_within_7_seconds(self):
        """默认配置下总等待时间 ≤ 7 秒"""
        max_wait = (DEFAULT_MAX_RETRIES - 1) * DEFAULT_RETRY_INTERVAL
        assert max_wait <= 7.0, f"总等待 {max_wait}s 超过 7 秒限制"


# ── 与 MockDriver 的集成测试 ─────────────────────────────────────────────────

class TestMockDriverRetry:

    @patch("devices.try_connect.time.sleep")
    def test_mock_driver_fail_2_then_succeed(self, mock_sleep):
        """MockDriver 先失败 2 次再成功，验证 _mock_fail_times 参数生效"""
        from devices.mock import MockDriver

        conn = {
            "device_type": "mock_huawei",
            "ip": "127.0.0.1",
            "port": 23,
            "username": "admin",
            "password": "admin",
            "_mock_fail_times": 2,  # 前 2 次 connect() 抛超时
        }
        driver = MockDriver(conn)

        # MockDriver.connect() 不内置 retry，需要手动用 connect_with_retry 包装测试
        connect_with_retry(driver.connect, max_retries=5, retry_interval=0.1)
        assert mock_sleep.call_count == 2  # 失败 2 次，sleep 2 次

    @patch("devices.try_connect.time.sleep")
    def test_mock_driver_fail_exceeds_max_retries(self, _):
        """MockDriver 永远失败（fail_times > max_retries），最终抛出异常"""
        from devices.mock import MockDriver

        conn = {
            "device_type": "mock_huawei",
            "ip": "127.0.0.1",
            "port": 23,
            "username": "admin",
            "password": "admin",
            "_mock_fail_times": 99,
        }
        driver = MockDriver(conn)
        with pytest.raises(NetmikoTimeoutException):
            connect_with_retry(driver.connect, max_retries=3, retry_interval=0.01)
