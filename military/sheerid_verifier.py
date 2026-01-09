"""ChatGPT 军人 SheerID 验证器"""
import re
import random
import logging
import httpx
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from . import config

# 导入临时邮箱服务
try:
    from utils.temp_email import TempEmailService
except ImportError:
    TempEmailService = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class NameGenerator:
    """英文名字生成器（军人版）"""

    FIRST_NAMES = [
        'James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph',
        'Thomas', 'Charles', 'Christopher', 'Daniel', 'Matthew', 'Anthony', 'Mark',
        'Donald', 'Steven', 'Paul', 'Andrew', 'Joshua', 'Kenneth', 'Kevin', 'Brian',
        'George', 'Timothy', 'Ronald', 'Edward', 'Jason', 'Jeffrey', 'Ryan'
    ]

    LAST_NAMES = [
        'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
        'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
        'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
        'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson'
    ]

    @classmethod
    def generate(cls) -> Dict[str, str]:
        """生成随机英文名字"""
        first_name = random.choice(cls.FIRST_NAMES)
        last_name = random.choice(cls.LAST_NAMES)
        return {
            'first_name': first_name,
            'last_name': last_name,
            'full_name': f"{first_name} {last_name}"
        }


def generate_birth_date() -> str:
    """
    生成随机生日（1960-1995年，适合退役军人）

    Returns:
        str: YYYY-MM-DD 格式的日期
    """
    year = random.randint(1960, 1995)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def generate_discharge_date() -> str:
    """
    生成随机退役日期（过去5年内）

    Returns:
        str: YYYY-MM-DD 格式的日期
    """
    today = datetime.now()
    # 随机选择过去1-5年内的某一天
    days_ago = random.randint(365, 365 * 5)
    discharge_date = today - timedelta(days=days_ago)
    return discharge_date.strftime("%Y-%m-%d")


def generate_email(first_name: str, last_name: str) -> str:
    """
    生成随机邮箱

    Args:
        first_name: 名字
        last_name: 姓氏

    Returns:
        str: 邮箱地址
    """
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']
    random_num = random.randint(1, 999)
    domain = random.choice(domains)
    return f"{first_name.lower()}.{last_name.lower()}{random_num}@{domain}"


class SheerIDVerifier:
    """ChatGPT 军人 SheerID 验证器"""

    def __init__(self, verification_id: str, use_temp_email: bool = True):
        """
        初始化验证器

        Args:
            verification_id: SheerID 验证 ID
            use_temp_email: 是否使用临时邮箱（用于自动处理邮箱验证）
        """
        self.verification_id = verification_id
        self.http_client = httpx.Client(timeout=30.0)
        self.use_temp_email = use_temp_email and TempEmailService is not None
        self.temp_email_service: Optional[TempEmailService] = None

    def __del__(self):
        if hasattr(self, "http_client"):
            self.http_client.close()

    @staticmethod
    def parse_verification_id(url: str) -> Optional[str]:
        """从 URL 解析 verificationId"""
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _sheerid_request(
        self, method: str, url: str, body: Optional[Dict] = None
    ) -> Tuple[Dict, int]:
        """发送 SheerID API 请求"""
        headers = {
            "Content-Type": "application/json",
        }

        try:
            response = self.http_client.request(
                method=method, url=url, json=body, headers=headers
            )
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}
            return data, response.status_code
        except Exception as e:
            logger.error(f"SheerID 请求失败: {e}")
            raise

    def verify(
        self,
        first_name: str = None,
        last_name: str = None,
        email: str = None,
        birth_date: str = None,
        organization_id: str = None,
        discharge_date: str = None,
        military_status: str = None,
    ) -> Dict:
        """
        执行军人验证流程

        流程:
        1. collectMilitaryStatus - 设置军人状态
        2. collectInactiveMilitaryPersonalInfo - 提交个人信息
        3. (如果需要) 自动处理邮箱验证
        """
        try:
            # 生成默认值
            if not first_name or not last_name:
                name = NameGenerator.generate()
                first_name = name["first_name"]
                last_name = name["last_name"]

            # 使用临时邮箱或生成假邮箱
            if not email:
                if self.use_temp_email:
                    logger.info("正在创建临时邮箱...")
                    self.temp_email_service = TempEmailService()
                    email = self.temp_email_service.create_account(first_name, last_name)
                    if not email:
                        logger.warning("临时邮箱创建失败，使用普通邮箱")
                        email = generate_email(first_name, last_name)
                        self.temp_email_service = None
                else:
                    email = generate_email(first_name, last_name)
            if not birth_date:
                birth_date = generate_birth_date()
            if not discharge_date:
                discharge_date = generate_discharge_date()
            if not organization_id:
                organization_id = random.choice(config.ORGANIZATION_IDS)
            if not military_status:
                military_status = config.DEFAULT_MILITARY_STATUS

            organization = config.ORGANIZATIONS[organization_id]

            logger.info(f"军人信息: {first_name} {last_name}")
            logger.info(f"邮箱: {email}")
            logger.info(f"生日: {birth_date}")
            logger.info(f"退役日期: {discharge_date}")
            logger.info(f"军种: {organization['name']}")
            logger.info(f"军人状态: {military_status}")
            logger.info(f"验证 ID: {self.verification_id}")

            # 步骤 1: 收集军人状态 (collectMilitaryStatus)
            logger.info("步骤 1/2: 设置军人状态...")
            step1_body = {
                "status": military_status
            }
            step1_url = f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectMilitaryStatus"

            step1_data, step1_status = self._sheerid_request("POST", step1_url, step1_body)

            if step1_status != 200:
                raise Exception(f"步骤 1 失败 (状态码 {step1_status}): {step1_data}")
            if step1_data.get("currentStep") == "error":
                error_msg = ", ".join(step1_data.get("errorIds", ["Unknown error"]))
                raise Exception(f"步骤 1 错误: {error_msg}")

            current_step = step1_data.get("currentStep")
            submission_url = step1_data.get("submissionUrl")
            logger.info(f"步骤 1 完成: currentStep={current_step}")

            # 步骤 2: 收集非现役军人个人信息 (collectInactiveMilitaryPersonalInfo)
            logger.info("步骤 2/2: 提交个人信息...")

            # 使用 submissionUrl 或构造 URL
            if submission_url:
                step2_url = submission_url
            else:
                step2_url = f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectInactiveMilitaryPersonalInfo"

            step2_body = {
                "firstName": first_name,
                "lastName": last_name,
                "birthDate": birth_date,
                "email": email,
                "phoneNumber": "",
                "organization": {
                    "id": organization["id"],
                    "name": organization["name"]
                },
                "dischargeDate": discharge_date,
                "locale": "en-US",
                "country": "US",
                "metadata": {
                    "marketConsentValue": False,
                    "refererUrl": "",
                    "verificationId": self.verification_id,
                    "flags": '{"doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","include-cvec-field-france-student":"not-labeled-optional","org-search-overlay":"default","org-selected-display":"default"}',
                    "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount, and I understand that my personal information will be shared with SheerID as a processor/third-party service provider in order for SheerID to confirm my eligibility for a special offer."
                }
            }

            step2_data, step2_status = self._sheerid_request("POST", step2_url, step2_body)

            if step2_status != 200:
                raise Exception(f"步骤 2 失败 (状态码 {step2_status}): {step2_data}")
            if step2_data.get("currentStep") == "error":
                error_msg = ", ".join(step2_data.get("errorIds", ["Unknown error"]))
                raise Exception(f"步骤 2 错误: {error_msg}")

            final_step = step2_data.get("currentStep")
            logger.info(f"步骤 2 完成: currentStep={final_step}")

            # 检查是否需要邮箱验证
            if final_step == "emailLoop":
                logger.info("SheerID 要求邮箱验证")

                # 如果有临时邮箱服务，尝试自动完成邮箱验证
                if self.temp_email_service:
                    logger.info("正在等待验证邮件...")
                    verification_url = self.temp_email_service.wait_for_sheerid_email(
                        max_wait=90,  # 最多等待 90 秒
                        poll_interval=5
                    )

                    if verification_url:
                        logger.info("收到验证邮件，正在完成验证...")
                        success, msg = self.temp_email_service.click_verification_link(verification_url)

                        if success:
                            logger.info("邮箱验证完成，检查最终状态...")
                            # 重新检查验证状态
                            status_url = f"{config.SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}"
                            final_data, _ = self._sheerid_request("GET", status_url)
                            final_step = final_data.get("currentStep", "unknown")

                            if final_step == "success":
                                return {
                                    "success": True,
                                    "pending": False,
                                    "message": "认证成功（已自动完成邮箱验证）",
                                    "verification_id": self.verification_id,
                                    "redirect_url": final_data.get("redirectUrl"),
                                    "reward_code": final_data.get("rewardCode"),
                                    "status": final_data,
                                }
                            elif final_step == "pending":
                                return {
                                    "success": True,
                                    "pending": True,
                                    "message": "邮箱已验证，等待审核",
                                    "verification_id": self.verification_id,
                                    "redirect_url": final_data.get("redirectUrl"),
                                    "current_step": final_step,
                                    "status": final_data,
                                }
                            else:
                                logger.warning(f"邮箱验证后状态: {final_step}")
                        else:
                            logger.warning(f"点击验证链接失败: {msg}")
                    else:
                        logger.warning("未收到验证邮件")

                # 临时邮箱不可用或验证失败
                logger.warning("邮箱验证无法自动完成")
                return {
                    "success": False,
                    "message": "SheerID 要求验证邮箱，自动验证失败。请使用真实可接收邮件的邮箱重新获取验证链接。",
                    "verification_id": self.verification_id,
                    "current_step": final_step,
                    "status": step2_data,
                }

            # 检查是否需要文档上传
            if final_step == "docUpload":
                logger.info("需要文档上传，当前版本暂不支持自动上传军人文档")
                return {
                    "success": False,
                    "message": "需要上传军人身份证明文档，当前版本暂不支持",
                    "verification_id": self.verification_id,
                    "current_step": final_step,
                    "status": step2_data,
                }

            # 检查是否直接成功
            if final_step == "success":
                return {
                    "success": True,
                    "pending": False,
                    "message": "认证成功",
                    "verification_id": self.verification_id,
                    "redirect_url": step2_data.get("redirectUrl"),
                    "reward_code": step2_data.get("rewardCode"),
                    "status": step2_data,
                }

            # 检查是否在审核中
            if final_step == "pending":
                return {
                    "success": True,
                    "pending": True,
                    "message": "信息已提交，等待审核",
                    "verification_id": self.verification_id,
                    "redirect_url": step2_data.get("redirectUrl"),
                    "current_step": final_step,
                    "status": step2_data,
                }

            # 其他未知状态
            logger.warning(f"未知状态: {final_step}")
            return {
                "success": False,
                "message": f"未知状态: {final_step}",
                "verification_id": self.verification_id,
                "redirect_url": step2_data.get("redirectUrl"),
                "current_step": final_step,
                "status": step2_data,
            }

        except Exception as e:
            logger.error(f"军人验证失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "verification_id": self.verification_id
            }


def main():
    """主函数 - 命令行界面"""
    import sys

    print("=" * 60)
    print("ChatGPT 军人 SheerID 验证工具")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("请输入 SheerID 验证 URL: ").strip()

    if not url:
        print("错误: 未提供 URL")
        sys.exit(1)

    verification_id = SheerIDVerifier.parse_verification_id(url)
    if not verification_id:
        print("错误: 无效的验证 ID 格式")
        sys.exit(1)

    print(f"解析到验证 ID: {verification_id}")
    print()

    verifier = SheerIDVerifier(verification_id)
    result = verifier.verify()

    print()
    print("=" * 60)
    print("验证结果:")
    print("=" * 60)
    print(f"状态: {'成功' if result['success'] else '失败'}")
    print(f"消息: {result['message']}")
    if result.get("redirect_url"):
        print(f"跳转 URL: {result['redirect_url']}")
    if result.get("reward_code"):
        print(f"奖励码: {result['reward_code']}")
    print("=" * 60)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
