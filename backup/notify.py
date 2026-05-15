"""
钉钉 Webhook 告警模块
发现备份异常时通过钉钉自定义机器人推送告警消息
"""
import os
import time
import hmac
import hashlib
import base64
import urllib.parse

from dotenv import load_dotenv

import requests

from src.logger import logger

load_dotenv()


class DingTalkNotifier:

    def __init__(self):
        self.webhook_url = os.getenv("DINGTALK_WEBHOOK_URL")
        self.secret = os.getenv("DINGTALK_SECRET")

        if not self.webhook_url or not self.secret:
            logger.warning("钉钉 Webhook 配置不完整，告警功能不可用")
            self._enabled = False
        else:
            self._enabled = True

    def _generate_sign(self):

        if not self._enabled:
            return None, None

        # TODO(human): 实现 HMAC-SHA256 加签
        # 步骤：
        # 1. timestamp = str(round(time.time() * 1000))  → 毫秒级时间戳
        # 2. 拼接签名字符串: f"{timestamp}\n{self.secret}"
        # 3. 用 hmac.new() 生成签名:
        #    hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).digest()
        # 4. base64.b64encode(hmac_code).decode('utf-8')  → 转为字符串
        # 5. 对 sign 做 URL 编码: urllib.parse.quote(sign)
        # 6. return timestamp, sign
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        sign = urllib.parse.quote(sign)
        return timestamp, sign

    def send_markdown(self, title, text):
        """
        发送 markdown 格式消息到钉钉群

        Args:
            title: 消息标题
            text: markdown 格式消息正文

        Returns:
            成功返回 True，失败返回 False
        """
        if not self._enabled:
            return False

        timestamp, sign = self._generate_sign()
        if timestamp is None:
            return False

        signed_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text,
            },
        }

        try:
            resp = requests.post(signed_url, json=payload, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                logger.info(f"钉钉告警已发送: {title}")
                return True
            else:
                logger.warning(f"钉钉返回错误: {data}")
                return False
        except requests.RequestException as e:
            logger.warning(f"钉钉告警发送失败: {e}")
            return False
