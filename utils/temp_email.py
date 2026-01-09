"""临时邮箱服务 - 使用 mail.tm API"""
import re
import time
import random
import string
import logging
import httpx
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class TempEmailService:
    """临时邮箱服务，用于接收 SheerID 验证邮件"""

    BASE_URL = "https://api.mail.tm"

    def __init__(self):
        self.http_client = httpx.Client(timeout=30.0)
        self.email: Optional[str] = None
        self.password: Optional[str] = None
        self.token: Optional[str] = None
        self.account_id: Optional[str] = None

    def __del__(self):
        if hasattr(self, "http_client"):
            self.http_client.close()

    def _generate_password(self, length: int = 12) -> str:
        """生成随机密码"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def _generate_username(self, first_name: str, last_name: str) -> str:
        """生成用户名"""
        random_num = random.randint(100, 9999)
        return f"{first_name.lower()}.{last_name.lower()}{random_num}"

    def get_available_domain(self) -> Optional[str]:
        """获取可用的邮箱域名"""
        try:
            response = self.http_client.get(f"{self.BASE_URL}/domains")
            if response.status_code == 200:
                data = response.json()
                domains = data.get("hydra:member", [])
                if domains:
                    # 返回第一个可用域名
                    return domains[0].get("domain")
            logger.error(f"获取域名失败: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"获取域名异常: {e}")
            return None

    def create_account(self, first_name: str = "John", last_name: str = "Doe") -> Optional[str]:
        """
        创建临时邮箱账号

        Args:
            first_name: 名字（用于生成邮箱地址）
            last_name: 姓氏（用于生成邮箱地址）

        Returns:
            str: 创建的邮箱地址，失败返回 None
        """
        try:
            # 获取可用域名
            domain = self.get_available_domain()
            if not domain:
                logger.error("无法获取可用域名")
                return None

            # 生成邮箱地址和密码
            username = self._generate_username(first_name, last_name)
            self.email = f"{username}@{domain}"
            self.password = self._generate_password()

            # 创建账号
            response = self.http_client.post(
                f"{self.BASE_URL}/accounts",
                json={
                    "address": self.email,
                    "password": self.password
                }
            )

            if response.status_code == 201:
                data = response.json()
                self.account_id = data.get("id")
                logger.info(f"临时邮箱创建成功: {self.email}")

                # 登录获取 token
                if self._login():
                    return self.email
                else:
                    logger.error("登录临时邮箱失败")
                    return None
            else:
                logger.error(f"创建邮箱失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"创建临时邮箱异常: {e}")
            return None

    def _login(self) -> bool:
        """登录获取 token"""
        try:
            response = self.http_client.post(
                f"{self.BASE_URL}/token",
                json={
                    "address": self.email,
                    "password": self.password
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                logger.info("临时邮箱登录成功")
                return True
            else:
                logger.error(f"登录失败: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False

    def _get_auth_headers(self) -> Dict[str, str]:
        """获取认证头"""
        return {
            "Authorization": f"Bearer {self.token}"
        }

    def get_messages(self) -> list:
        """获取邮件列表"""
        if not self.token:
            logger.error("未登录，无法获取邮件")
            return []

        try:
            response = self.http_client.get(
                f"{self.BASE_URL}/messages",
                headers=self._get_auth_headers()
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("hydra:member", [])
            else:
                logger.error(f"获取邮件失败: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"获取邮件异常: {e}")
            return []

    def get_message_content(self, message_id: str) -> Optional[Dict]:
        """获取邮件详情"""
        if not self.token:
            return None

        try:
            response = self.http_client.get(
                f"{self.BASE_URL}/messages/{message_id}",
                headers=self._get_auth_headers()
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"获取邮件详情异常: {e}")
            return None

    def wait_for_sheerid_email(
        self,
        max_wait: int = 60,
        poll_interval: int = 5
    ) -> Optional[str]:
        """
        等待 SheerID 验证邮件并提取验证链接

        Args:
            max_wait: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            str: 验证链接，超时或失败返回 None
        """
        start_time = time.time()
        logger.info(f"开始等待 SheerID 验证邮件 (最多 {max_wait} 秒)...")

        while time.time() - start_time < max_wait:
            messages = self.get_messages()

            for msg in messages:
                # 检查是否是 SheerID 的邮件
                sender = msg.get("from", {}).get("address", "").lower()
                subject = msg.get("subject", "").lower()

                if "sheerid" in sender or "sheerid" in subject or "verify" in subject:
                    logger.info(f"收到 SheerID 邮件: {msg.get('subject')}")

                    # 获取邮件详情
                    content = self.get_message_content(msg.get("id"))
                    if content:
                        # 从邮件内容中提取验证链接
                        verification_url = self._extract_verification_url(content)
                        if verification_url:
                            logger.info(f"提取到验证链接: {verification_url}")
                            return verification_url

            # 等待后继续轮询
            elapsed = int(time.time() - start_time)
            logger.info(f"等待验证邮件中... ({elapsed}/{max_wait}秒)")
            time.sleep(poll_interval)

        logger.warning(f"等待 SheerID 邮件超时 ({max_wait}秒)")
        return None

    def _extract_verification_url(self, message: Dict) -> Optional[str]:
        """
        从邮件内容中提取 SheerID 验证链接

        Args:
            message: 邮件内容

        Returns:
            str: 验证链接
        """
        # 尝试从 HTML 内容提取
        html_content = message.get("html", "") or ""
        text_content = message.get("text", "") or ""

        content = html_content + text_content

        # SheerID 验证链接模式
        patterns = [
            # 完整的验证链接
            r'https?://[^\s"\'<>]*sheerid\.com[^\s"\'<>]*verify[^\s"\'<>]*',
            # 带 token 的链接
            r'https?://[^\s"\'<>]*sheerid\.com[^\s"\'<>]*token=[^\s"\'<>]+',
            # 邮件确认链接
            r'https?://[^\s"\'<>]*sheerid\.com[^\s"\'<>]*confirm[^\s"\'<>]*',
            # 通用 sheerid 链接
            r'https?://[^\s"\'<>]*sheerid\.com/[^\s"\'<>]+',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # 清理链接（移除 HTML 实体等）
                url = matches[0].replace("&amp;", "&")
                # 移除可能的尾部引号或标签
                url = re.sub(r'["\'>].*$', '', url)
                return url

        logger.warning("未能从邮件中提取验证链接")
        return None

    def click_verification_link(self, url: str) -> Tuple[bool, str]:
        """
        访问验证链接完成邮箱验证

        Args:
            url: 验证链接

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            logger.info(f"访问验证链接: {url}")
            response = self.http_client.get(url, follow_redirects=True)

            if response.status_code == 200:
                # 检查响应内容是否表示成功
                content = response.text.lower()
                if "success" in content or "verified" in content or "confirmed" in content:
                    logger.info("邮箱验证成功")
                    return True, "邮箱验证成功"
                elif "error" in content or "expired" in content:
                    logger.warning("验证链接已过期或无效")
                    return False, "验证链接已过期或无效"
                else:
                    # 假设访问成功就是验证成功
                    logger.info("验证链接已访问")
                    return True, "验证链接已访问"
            else:
                return False, f"访问验证链接失败: {response.status_code}"

        except Exception as e:
            logger.error(f"访问验证链接异常: {e}")
            return False, str(e)


def create_temp_email(first_name: str = "John", last_name: str = "Doe") -> Tuple[Optional[TempEmailService], Optional[str]]:
    """
    创建临时邮箱的便捷函数

    Args:
        first_name: 名字
        last_name: 姓氏

    Returns:
        Tuple[TempEmailService, str]: (邮箱服务实例, 邮箱地址)
    """
    service = TempEmailService()
    email = service.create_account(first_name, last_name)
    if email:
        return service, email
    return None, None
