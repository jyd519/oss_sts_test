import json
import logging
from dataclasses import dataclass
from typing import Optional

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

logger = logging.getLogger(__name__)


class STSAssumeRoleError(Exception):
    """STS AssumeRole API 调用失败时抛出。"""


@dataclass(frozen=True)
class STSAssumeRoleResult:
    """AssumeRole 成功后的临时凭证。"""
    access_key_id: str
    access_key_secret: str
    security_token: str
    expiration: str
    request_id: str


class AliyunSTSService:
    """获取阿里云 STS 临时凭证的服务。

    典型用法：
        service = AliyunSTSService(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
        result = service.assume_role(role_arn, "session-123", duration_seconds=3600, policy=policy)
    """

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        region_id: str = "cn-shanghai",
        endpoint: Optional[str] = None,
        *,
        client: Optional[AcsClient] = None,
    ) -> None:
        self._endpoint = endpoint or "sts.aliyuncs.com"
        self._client = client or AcsClient(access_key_id, access_key_secret, region_id)

    def assume_role(
        self,
        role_arn: str,
        role_session_name: str,
        duration_seconds: int = 3600,
        policy: Optional[dict] = None,
    ) -> STSAssumeRoleResult:
        """获取指定角色的临时凭证。

        :param role_arn: RAM 角色 ARN
        :param role_session_name: 会话名称（需在 1~64 字符内）
        :param duration_seconds: 凭证有效期（秒），默认 3600
        :param policy: 可选权限策略，限制临时凭证权限
        """
        request = CommonRequest()
        request.set_accept_format("json")
        request.set_method("POST")
        request.set_protocol_type("https")
        request.set_domain(self._endpoint)
        request.set_version("2015-04-01")
        request.set_action_name("AssumeRole")

        request.add_query_param("RoleArn", role_arn)
        request.add_query_param("RoleSessionName", role_session_name)
        request.add_query_param("DurationSeconds", duration_seconds)

        if policy:
            request.add_query_param("Policy", json.dumps(policy))

        try:
            response = self._client.do_action_with_exception(request)
        except Exception as exc:
            logger.exception("STS AssumeRole 请求失败: %s", exc)
            raise STSAssumeRoleError(f"STS AssumeRole 请求失败: {exc}") from exc

        result = json.loads(response)
        credentials = result.get("Credentials", {})
        if not credentials:
            raise STSAssumeRoleError("STS 响应中缺少 Credentials 字段")

        return STSAssumeRoleResult(
            access_key_id=credentials["AccessKeyId"],
            access_key_secret=credentials["AccessKeySecret"],
            security_token=credentials["SecurityToken"],
            expiration=credentials["Expiration"],
            request_id=result.get("RequestId", ""),
        )

