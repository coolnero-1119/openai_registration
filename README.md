# OpenAI 自动化注册 & Token 获取工具

一个基于纯 HTTP 协议的 OpenAI 账号自动注册脚本，无需 Selenium，所有注册逻辑在内存中完成。

## 功能特点

- ✅ 全自动注册 OpenAI 账号（含邮箱验证码与账号创建）
- ✅ 注册成功后自动登录并提取 `access_token` / `refresh_token` / `id_token`
- ✅ Token 保存为本地 JSON 文件（`tokens/<email>.json`）
- ✅ 支持动态住宅代理（IPRoyal 等）
- ✅ 完全绕过 Sentinel 反爬指纹验证（纯 Python 逆向实现）


## 依赖

- Python 3.10+
- IPRoyal 动态住宅代理账号（或其他兼容代理）
- Cloudflare Temp Email 收件后端（[dreamhunter2333/cloudflare_temp_email](https://github.com/dreamhunter2333/cloudflare_temp_email)）


## 安装

```bash
# 克隆项目
git clone https://github.com/你的用户名/openai_registration.git
cd openai_registration

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```


## 配置

修改 `openai_registration.py` 顶部的配置常量：

```python
# 1. 邮箱后缀（你的 Cloudflare 收信域名，OpenAI 需要能接收）
CF_EMAIL_DOMAIN = "your-domain.engineer"

# 2. 邮箱管理 API（你部署的 cloudflare_temp_email worker 地址）
MAIL_API_BASE = "https://apimail.your-domain.com"
MAIL_API_ADMIN_AUTH = "你的管理员密码"        # 对应 worker 环境变量 ADMIN_PASSWORDS

# 3. 代理配置（在 generate_proxy_url 函数中修改）
# 默认使用 IPRoyal，修改 auth_user / auth_pass / proxy_host 为你自己的代理信息
```

### Cloudflare 邮箱收件配置

1. 将你的域名托管到 Cloudflare
2. 进入 **Email → Email Routing → Catch-all**
3. 设置目标为 **Send to a Worker**，绑定你部署的 `worker.js`


## 运行

```bash
source venv/bin/activate
python run_test.py
```

成功后，Token 文件将保存在：`../tokens/<email>.json`


## Token 文件格式

```json
{
  "id_token": "...",
  "access_token": "...",
  "refresh_token": "...",
  "account_id": "...",
  "last_refresh": "2026-03-01T23:31:55+08:00",
  "email": "xxx@your-domain.engineer",
  "type": "codex",
  "expired": "..."
}
```


## 注意事项

- 本项目**仅供学习和个人研究**，请勿用于违法或违反 OpenAI 服务条款的行为
- 代理 IP 质量直接影响注册成功率，推荐使用住宅代理
- OpenAI 会定期更新 Sentinel 指纹算法，若成功率下降请检查 `SentinelTokenGenerator` 中的配置


## 项目结构

```
openai_registration/
├── openai_registration.py   # 核心注册逻辑
├── run_test.py              # 运行入口（单次注册测试）
├── requirements.txt         # 依赖列表
└── README.md                # 本文件
```
