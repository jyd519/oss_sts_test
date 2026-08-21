import json
import logging
from dataclasses import dataclass
from typing import Optional

from alibabacloud_sts20150401.client import Client as StsClient
from alibabacloud_sts20150401 import models as sts_models
from alibabacloud_tea_openapi.models import Config as OpenApiConfig

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
    """获取阿里云 STS 临时凭证的服务（v2 SDK：alibabacloud_sts20150401）。

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
        client: Optional[StsClient] = None,
    ) -> None:
        self._endpoint = endpoint or "sts.aliyuncs.com"
        if client is not None:
            self._client = client
        else:
            config = OpenApiConfig(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                region_id=region_id,
                endpoint=self._endpoint,
            )
            self._client = StsClient(config)

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
        request = sts_models.AssumeRoleRequest(
            role_arn=role_arn,
            role_session_name=role_session_name,
            duration_seconds=duration_seconds,
        )
        if policy:
            request.policy = json.dumps(policy)

        try:
            response = self._client.assume_role(request)
        except Exception as exc:
            logger.exception("STS AssumeRole 请求失败: %s", exc)
            raise STSAssumeRoleError(f"STS AssumeRole 请求失败: {exc}") from exc

        body = response.body
        credentials = body.credentials
        if not credentials:
            raise STSAssumeRoleError("STS 响应中缺少 Credentials 字段")

        return STSAssumeRoleResult(
            access_key_id=credentials.access_key_id,
            access_key_secret=credentials.access_key_secret,
            security_token=credentials.security_token,
            expiration=credentials.expiration,
            request_id=body.request_id or "",
        )
