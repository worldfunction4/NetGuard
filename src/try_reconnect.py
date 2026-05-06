"""
连接重试模块 —— 基于 tenacity 增强 SSH 连接稳定性
- 自动重试：超时/网络不可达最多重试 3 次
- 不重试：认证失败（密码错重试无意义）
- 每次重试记录日志，方便排查问题
"""
import logging
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception, before_sleep_log

from src.logger import logger

# ---- 异常类型处理 ----
# netmiko 未安装时提供占位异常，保证模块可正常导入
try:
    from netmiko.exceptions import (
        NetmikoTimeoutException,
        NetmikoAuthenticationException,
    )
except ImportError:
    class NetmikoTimeoutException(Exception):
        """SSH 连接超时 / 网络不可达"""
        pass

    class NetmikoAuthenticationException(Exception):
        """SSH 认证失败（用户名/密码错误）"""
        pass


# ---- 重试判断逻辑 ----
def _is_retryable(exception):
    """
    判断异常是否值得重试

    超时 / 网络波动 → 重试（瞬时故障，重试有概率恢复）
    认证失败 → 不重试（凭据错误，重试多少次都没用）
    其他未知异常 → 保守重试
    """
    if isinstance(exception, NetmikoAuthenticationException):
        logger.error(f"认证失败，不进行重试: {exception}")
        return False
    if isinstance(exception, NetmikoTimeoutException):
        logger.warning(f"连接超时/网络不可达，准备重试: {exception}")
        return True
    # 兜底：未知异常也重试
    logger.warning(f"遇到未知异常，尝试重试: {exception}")
    return True


# ---- 重试回调 ----
def _before_retry(retry_state):
    """每次重试前记录日志，方便追踪重试进度"""
    logger.warning(
        f"设备连接重试中...（第 {retry_state.attempt_number}/3 次失败，"
        f"{retry_state.next_action.sleep} 秒后重试）"
    )


# ---- 预配置的重试装饰器 ----
# 用法示例：
#   from src.try_reconnect import retry_on_network_error
#   @retry_on_network_error
#   def connect_to_device(ip, username, password):
#       ...
retry_on_network_error = retry(
    stop=stop_after_attempt(3),       # 含首次共 3 次尝试
    wait=wait_fixed(2),               # 每次重试间隔 2 秒
    retry=retry_if_exception(_is_retryable),
    before_sleep=_before_retry,
)
