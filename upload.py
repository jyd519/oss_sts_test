import json
import sys
from pathlib import Path

import requests


def upload_file_to_oss(file_path: str | Path) -> None:
    """Upload a local file to OSS using the policy in token.json."""
    params = json.loads(Path("./token.json").read_text(encoding="utf-8"))
    print(params)

    file_path = Path(file_path)
    file_name = file_path.name

    form_fields = [
        ("key", params["dir"] + file_name),
        ("policy", params["policy"]),
        ("OSSAccessKeyId", params["ossAccessKeyId"]),
    ]
    if params.get("callback"):
        form_fields.append(("callback", params["callback"]))
    form_fields.extend(
        [
            ("success_action_status", "200"),
            ("signature", params["signature"]),
        ]
    )
    if params.get("securityToken"):
        form_fields.append(("x-oss-security-token", params["securityToken"]))

    # requests encodes data fields before files, so file remains the last part.
    with file_path.open("rb") as file:
        upload_res = requests.post(
            params["host"],
            data=form_fields,
            files=[("file", (file_name, file))],
        )

    if upload_res.status_code == 200:
        file_url = f'{params["host"]}/{params["dir"]}{file_name}'
        print("上传成功！文件 URL:", file_url)
    else:
        print(
            "上传失败，状态码:",
            upload_res.status_code,
            upload_res.text,
            file=sys.stderr,
        )


if __name__ == "__main__":
    upload_file_to_oss("./README.md")
