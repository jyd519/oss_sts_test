const fs = require("fs");
const path = require("path");

async function uploadFileToOSS(filePath) {
  // 使用 token.json 中的 V4 签名信息
  const params = JSON.parse(fs.readFileSync("./token.json", "utf-8"));
  console.log(params);

  const fileName = path.basename(filePath);
  const fileBuffer = fs.readFileSync(filePath);
  const blob = new Blob([fileBuffer]);

  const formData = new FormData();
  formData.append("key", params.dir + fileName);
  formData.append("policy", params.policy);
  formData.append(
    "x-oss-signature-version",
    params.x_oss_signature_version,
  );
  formData.append("x-oss-credential", params.x_oss_credential);
  formData.append("x-oss-date", params.x_oss_date);
  formData.append("x-oss-signature", params.x_oss_signature);

  if (params.x_oss_security_token) {
    formData.append("x-oss-security-token", params.x_oss_security_token);
  }
  if (params.callback) {
    formData.append("callback", params.callback);
  }

  // file 表单域必须放在最后追加
  formData.append("file", blob, fileName);

  const uploadRes = await fetch(params.host, {
    method: "POST",
    body: formData,
  });

  if (uploadRes.status >= 200 && uploadRes.status < 300) {
    console.log(
      "上传成功！文件 URL:",
      `${params.host}/${params.dir}${fileName}`,
      uploadRes.status,
    );
  } else {
    const errorText = await uploadRes.text();
    console.error("上传失败，状态码:", uploadRes.status, errorText);
  }
}

// 调用示例
uploadFileToOSS("./README.md").catch((error) => {
  console.error("上传请求失败:", error);
});
