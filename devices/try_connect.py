"""重连机制模块——为不稳定网络环境下的设备连接提供自动重试

设计说明：
  - 最大重连次数：max_retries（默认 5 次，含第 1 次尝试）
  - 重试间隔：retry_interval 秒（默认 1 秒），最多等待 (max_retries-1)*interval 秒
  - 认证失败（密码/用户名错误）不重连，直接上抛——重试无意义且可能锁定账号
  - 可重连的异常：NetmikoTimeoutException / NetmikoBaseException（网络抖动类错误）
  - 上层（collector / inspector）完全感知不到重连，接口不变

使用方式（在驱动的 connect() 内调用）：
    from devices.try_connect import connect_with_retry
    connect_with_retry(self._do_connect, device_name="SW-01")
"""
import logging
import time

from netmiko import NetMikoAuthenticationException, NetmikoBaseException, NetmikoTimeoutException

logger = logging.getLogger("NetGuard")

# ── 默认参数常量 ──────────────────────────────────────────────────────────────
# 最大尝试次数（含第 1 次，所以最多重连 max_retries-1 次）
DEFAULT_MAX_RETRIES = 5
# 每两次尝试之间的等待时间（秒）
# 5 次尝试最多等 4 次 * 1s = 4s，满足"不超过 7 秒"的约束
DEFAULT_RETRY_INTERVAL = 1.0

# 这类异常属于"密码/账号问题"，重连没有意义
_NO_RETRY_EXCEPTIONS = (NetMikoAuthenticationException,)

# 这类异常属于"网络抖动"，值得重连
_RETRYABLE_EXCEPTIONS = (NetmikoTimeoutException, NetmikoBaseException)


def connect_with_retry(
    connect_fn,
    device_name: str = "",
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_interval: float = DEFAULT_RETRY_INTERVAL,
):
    """执行 connect_fn()，失败时自动重连。

    Args:
        connect_fn:     无参可调用对象，执行实际的连接动作（如 ConnectHandler(...)）
        device_name:    设备名，仅用于日志，不影响逻辑
        max_retries:    最大尝试次数（含第 1 次），默认 5
        retry_interval: 每次重试前等待的秒数，默认 1s
                        总等待上限 = (max_retries - 1) * retry_interval

    Returns:
        connect_fn() 的返回值（通常是 ConnectHandler 实例）

    Raises:
        NetMikoAuthenticationException: 认证失败，不重连，立即上抛
        最后一次尝试的异常：超出重连次数后，抛出最后一次捕获到的异常
    """
    if max_retries < 1:
        raise ValueError(f"max_retries 至少为 1，当前值: {max_retries}")

    label = f"[{device_name}] " if device_name else ""
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            result = connect_fn()
            if attempt > 1:
                logger.info(f"{label}第 {attempt} 次尝试连接成功")
            return result

        except _NO_RETRY_EXCEPTIONS as e:
            # 认证失败：立即上抛，不等待不重连
            logger.error(f"{label}认证失败（用户名或密码错误），不重连: {e}")
            raise

        except _RETRYABLE_EXCEPTIONS as e:
            last_exc = e
            if attempt < max_retries:
                logger.warning(
                    f"{label}连接失败（第 {attempt}/{max_retries} 次）: {e}，"
                    f"{retry_interval}s 后重试..."
                )
                time.sleep(retry_interval)
            else:
                logger.error(f"{label}已达最大重连次数（{max_retries}），放弃连接: {e}")

        except Exception as e:
            # 未预期的其他异常：同样重连（网络层可能有各种 OSError）
            last_exc = e
            if attempt < max_retries:
                logger.warning(
                    f"{label}连接遇到未预期异常（第 {attempt}/{max_retries} 次）: {e}，"
                    f"{retry_interval}s 后重试..."
                )
                time.sleep(retry_interval)
            else:
                logger.error(f"{label}已达最大重连次数（{max_retries}），放弃连接: {e}")

    # 所有尝试均失败
    raise last_exc
