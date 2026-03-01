import json
import os
import re
import time
import uuid
import random
import string
import secrets
import hashlib
import base64
import logging
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs, urlencode, quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

try:
    from core.email_fetcher import connect_imap
except ImportError:
    connect_imap = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("openai_registration")

# =================== 配置常量 (来自 1132.py) ===================

OAUTH_ISSUER = "https://auth.openai.com"
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_REDIRECT_URI = "http://localhost:1455/auth/callback"
OPENAI_AUTH_BASE = "https://auth.openai.com"

# CF 域名邮箱配置
CF_EMAIL_DOMAIN = "dev-group.engineer"

# 新版邮箱 API 配置
MAIL_API_BASE = "https://apimail.cslovelh.top"
MAIL_API_ADMIN_AUTH = "19881119"
MAIL_API_FINGERPRINT = "4df0981a0aed57582196c7ba5fbb9c40"

# tempmail.plus 收件配置（保留备用）
TEMPMAIL_CONFIG = {
    "username": "otvopob",
    "email_extension": "@mailto.plus",
    "epin": "",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

COMMON_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": OPENAI_AUTH_BASE,
    "user-agent": USER_AGENT,
    "sec-ch-ua": '"Google Chrome";v="145", "Not?A_Brand";v="8", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

NAVIGATE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": USER_AGENT,
    "sec-ch-ua": '"Google Chrome";v="145", "Not?A_Brand";v="8", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}


# =================== 辅助工具 ===================

def create_session(proxy=None):
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session

def generate_device_id():
    return str(uuid.uuid4())

def generate_random_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%"
    pwd = list(
        random.choice(string.ascii_uppercase)
        + random.choice(string.ascii_lowercase)
        + random.choice(string.digits)
        + random.choice("!@#$%")
        + "".join(random.choice(chars) for _ in range(length - 4))
    )
    random.shuffle(pwd)
    return "".join(pwd)

def generate_random_name():
    first = [
        "James", "Robert", "John", "Michael", "David", "William", "Richard",
        "Mary", "Jennifer", "Linda", "Elizabeth", "Susan", "Jessica", "Sarah",
        "Emily", "Emma", "Olivia", "Sophia", "Liam", "Noah", "Oliver", "Ethan",
    ]
    last = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Martin",
    ]
    return random.choice(first), random.choice(last)

def generate_random_birthday():
    year = random.randint(1996, 2006)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"

def generate_datadog_trace():
    trace_id = str(random.getrandbits(64))
    parent_id = str(random.getrandbits(64))
    trace_hex = format(int(trace_id), '016x')
    parent_hex = format(int(parent_id), '016x')
    return {
        "traceparent": f"00-0000000000000000{trace_hex}-{parent_hex}-01",
        "tracestate": "dd=s:1;o:rum",
        "x-datadog-origin": "rum",
        "x-datadog-parent-id": parent_id,
        "x-datadog-sampling-priority": "1",
        "x-datadog-trace-id": trace_id,
    }

def generate_pkce():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge

# =================== Sentinel Token 生成器 ===================

class SentinelTokenGenerator:
    MAX_ATTEMPTS = 500000
    ERROR_PREFIX = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"

    def __init__(self, device_id=None):
        self.device_id = device_id or generate_device_id()
        self.requirements_seed = str(random.random())
        self.sid = str(uuid.uuid4())

    @staticmethod
    def _fnv1a_32(text):
        h = 2166136261
        for ch in text:
            code = ord(ch)
            h ^= code
            h = ((h * 16777619) & 0xFFFFFFFF)
        h ^= (h >> 16)
        h = ((h * 2246822507) & 0xFFFFFFFF)
        h ^= (h >> 13)
        h = ((h * 3266489909) & 0xFFFFFFFF)
        h ^= (h >> 16)
        h = h & 0xFFFFFFFF
        return format(h, '08x')

    def _get_config(self):
        screen_info = f"1920x1080"
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)")
        js_heap_limit = 4294705152
        nav_random1 = random.random()
        ua = USER_AGENT
        script_src = "https://sentinel.openai.com/sentinel/20260124ceb8/sdk.js"
        script_version = None
        data_build = None
        language = "en-US"
        languages = "en-US,en"
        nav_random2 = random.random()
        nav_props = [
            "vendorSub", "productSub", "vendor", "maxTouchPoints",
            "scheduling", "userActivation", "doNotTrack", "geolocation",
            "connection", "plugins", "mimeTypes", "pdfViewerEnabled",
            "webkitTemporaryStorage", "webkitPersistentStorage",
            "hardwareConcurrency", "cookieEnabled", "credentials",
            "mediaDevices", "permissions", "locks", "ink",
        ]
        nav_prop = random.choice(nav_props)
        nav_val = f"{nav_prop}−undefined"
        doc_key = random.choice(["location", "implementation", "URL", "documentURI", "compatMode"])
        win_key = random.choice(["Object", "Function", "Array", "Number", "parseFloat", "undefined"])
        perf_now = random.uniform(1000, 50000)
        hardware_concurrency = random.choice([4, 8, 12, 16])
        time_origin = time.time() * 1000 - perf_now

        config = [
            screen_info, date_str, js_heap_limit, nav_random1, ua, script_src,
            script_version, data_build, language, languages, nav_random2,
            nav_val, doc_key, win_key, perf_now, self.sid, "",
            hardware_concurrency, time_origin,
        ]
        return config

    @staticmethod
    def _base64_encode(data):
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        encoded = json_str.encode('utf-8')
        return base64.b64encode(encoded).decode('ascii')

    def _run_check(self, start_time, seed, difficulty, config, nonce):
        config[3] = nonce
        config[9] = round((time.time() - start_time) * 1000)
        data = self._base64_encode(config)
        hash_input = seed + data
        hash_hex = self._fnv1a_32(hash_input)
        diff_len = len(difficulty)
        if hash_hex[:diff_len] <= difficulty:
            return data + "~S"
        return None

    def generate_token(self, seed=None, difficulty=None):
        if seed is None:
            seed = self.requirements_seed
            difficulty = difficulty or "0"
        start_time = time.time()
        config = self._get_config()
        for i in range(self.MAX_ATTEMPTS):
            result = self._run_check(start_time, seed, difficulty, config, i)
            if result:
                return "gAAAAAB" + result
        return "gAAAAAB" + self.ERROR_PREFIX + self._base64_encode(str(None))

    def generate_requirements_token(self):
        config = self._get_config()
        config[3] = 1
        config[9] = round(random.uniform(5, 50))
        data = self._base64_encode(config)
        return "gAAAAAC" + data


# =================== Sentinel API 交互 ===================

def fetch_sentinel_challenge(session, device_id, flow="authorize_continue"):
    gen = SentinelTokenGenerator(device_id=device_id)
    p_token = gen.generate_requirements_token()
    req_body = {"p": p_token, "id": device_id, "flow": flow}
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "Referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html",
        "User-Agent": USER_AGENT,
        "Origin": "https://sentinel.openai.com",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    try:
        resp = session.post(
            "https://sentinel.openai.com/backend-api/sentinel/req",
            data=json.dumps(req_body), headers=headers, timeout=15, verify=False,
        )
        if resp.status_code != 200:
            logger.error(f"Sentinel API 错误: {resp.status_code}")
            return None
        return resp.json()
    except Exception as e:
        logger.error(f"Sentinel API 异常: {e}")
        return None

def build_sentinel_token(session, device_id, flow="authorize_continue"):
    challenge = fetch_sentinel_challenge(session, device_id, flow)
    if not challenge:
        return None
    c_value = challenge.get("token", "")
    pow_data = challenge.get("proofofwork", {})
    gen = SentinelTokenGenerator(device_id=device_id)
    if pow_data.get("required") and pow_data.get("seed"):
        p_value = gen.generate_token(seed=pow_data["seed"], difficulty=pow_data.get("difficulty", "0"))
    else:
        p_value = gen.generate_requirements_token()
    return json.dumps({"p": p_value, "t": "", "c": c_value, "id": device_id, "flow": flow})


# =================== CF 域名邮箱生成 ===================

def generate_cf_email():
    """生成随机 CF 域名邮箱地址"""
    name_len = random.randint(10, 14)
    name_chars = list(random.choices(string.ascii_lowercase, k=name_len))
    for _ in range(random.choice([1, 2])):
        pos = random.randint(2, len(name_chars) - 1)
        name_chars.insert(pos, random.choice(string.digits))
    name = "".join(name_chars)
    return f"{name}@{CF_EMAIL_DOMAIN}"


# =================== 邮箱 API 验证码获取 ===================

def _fetch_emails_by_address(email_addr, proxies=None):
    """通过管理员 API 获取指定邮箱地址的邮件列表"""
    url = f"{MAIL_API_BASE}/admin/mails"
    try:
        resp = requests.get(
            url,
            params={"limit": 20, "offset": 0},
            headers={
                "x-admin-auth": MAIL_API_ADMIN_AUTH,
                "x-fingerprint": MAIL_API_FINGERPRINT,
                "x-lang": "zh",
                "Content-Type": "application/json",
            },
            timeout=30, verify=False, # Removed proxies=proxies
        )
        if resp.status_code == 200:
            all_mails = resp.json().get("results", [])
            # 按 address 过滤出属于当前邮箱的邮件
            return [m for m in all_mails if isinstance(m, dict) and m.get("address") == email_addr]
        return None
    except Exception as e:
        logger.error(f"邮箱 API 获取邮件列表失败: {e}")
        return None


def extract_verification_code(content):
    """从邮件内容中提取 6 位数字验证码（与 JS 示例相同的正则）"""
    if not content:
        return None
    # 策略1：HTML body 样式匹配
    m = re.search(r'background-color:\s*#F3F3F3[^>]*>[\s\S]*?(\d{6})[\s\S]*?</p>', content)
    if m:
        return m.group(1)
    # 策略2：Subject
    m = re.search(r'Subject:.*?(\d{6})', content)
    if m and m.group(1) != "177010":
        return m.group(1)
    # 策略3：通用正则
    m = re.search(r'(?<![a-zA-Z@.])\b(\d{6})\b', content)
    return m.group(1) if m else None


def poll_verification_code(account=None, timeout=120, config=None, proxies=None, stop_check=None):
    """
    通过邮箱管理员 API 轮询验证码。

    改进版本：每次都扫描全部邮件，避免因竞态条件（邮件在第一次快照后立刻到达）
    导致验证码被永久跳过的问题。通过记录"已处理且无验证码"的邮件 ID 来避免重复
    打印日志，但不会跳过任何邮件的验证码检查。

    :param account: dict，需包含 'email' 字段
    :param stop_check: 可调用对象，返回 True 时立即停止轮询
    """
    email_addr = None
    if account and isinstance(account, dict):
        email_addr = account.get("email", "")
    if not email_addr:
        logger.warning("未提供邮箱地址，无法轮询验证码")
        return None

    logger.info(f"正在通过邮箱 API 轮询验证码 (邮箱: {email_addr})...")

    # 记录已经检查过且无验证码的邮件 ID，仅用于去重日志，不跳过验证码检查
    checked_no_code_ids = set()

    start_time = time.time()
    while time.time() - start_time < timeout:
        if stop_check and stop_check():
            logger.info("轮询被用户停止")
            return None
        try:
            mails = _fetch_emails_by_address(email_addr, proxies=proxies)
            if mails:
                for item in mails:
                    if not isinstance(item, dict):
                        continue
                    mail_id = item.get("id")
                    raw = item.get("raw", "")
                    code = extract_verification_code(raw)
                    if code:
                        logger.info(f"找到验证码: {code}")
                        return code
                    # 没有验证码，仅首次打印日志
                    if mail_id not in checked_no_code_ids:
                        source = item.get("source", "未知")
                        logger.warning(f"邮件 {mail_id} from={source[:40]} 未含验证码")
                        checked_no_code_ids.add(mail_id)
            else:
                logger.info("暂无匹配邮件，继续等待...")

            _interruptible_sleep(2, stop_check)
        except Exception as e:
            logger.error(f"邮箱 API 轮询出错: {e}")
            _interruptible_sleep(2, stop_check)

    logger.warning("验证码等待超时")
    return None


def _interruptible_sleep(seconds, stop_check=None):
    """可中断的 sleep，每 0.5 秒检查一次 stop_check"""
    for _ in range(int(seconds * 2)):
        if stop_check and stop_check():
            return
        time.sleep(0.5)


def generate_proxy_url(username=None, password=None, country="us", scheme="http", encode_auth=False):
    """
    根据用户提供的 IPRoyal 凭据生成动态代理 URL。
    如果未传入 username/password，将使用默认的 IPRoyal 配置。
    """
    # 默认使用您提供的 IPRoyal 代理池
    proxy_host = "geo.iproyal.com:12321"
    auth_user = username.strip() if username else "sA2kavFArObbaV2l"
    auth_pass = password.rstrip("\r\n") if password else "7Denv6fS3q71GXQQ"

    if encode_auth:
        auth_user = quote(auth_user, safe="")
        auth_pass = quote(auth_pass, safe="")

    # 构建代理 URL (去除了原版不需要的 session 拼接逻辑)
    proxy_url = f"{scheme}://{auth_user}:{auth_pass}@{proxy_host}"
    return proxy_url


def fetch_proxy_from_api(appkey, protocol="http", country="", timeout=10):
    """
    从海外代理 API 获取一个代理端点 (ip:port)。
    """
    appkey = (appkey or "").strip()
    if not appkey:
        return None

    protocol = (protocol or "http").strip().lower()
    country = (country or "").strip()
    api_url = (
        "https://api.haiwaidaili.net/abroad"
        f"?token={appkey}&num=1&format=1&protocol={protocol}&country={country}&sep=1&csep="
    )
    try:
        resp = requests.get(api_url, timeout=timeout)
        if resp.status_code != 200:
            logger.error(f"代理 API 请求失败: HTTP {resp.status_code}")
            return None
        lines = [x.strip() for x in resp.text.splitlines() if x.strip()]
        for line in lines:
            if ":" in line:
                return line
    except Exception as e:
        logger.error(f"代理 API 获取失败: {e}")
    return None


def build_proxy_url_from_addr(proxy_addr, protocol="http"):
    """
    从 ip:port 构建 requests 代理 URL。
    """
    if not proxy_addr:
        return None
    protocol = (protocol or "http").strip().lower()
    if protocol not in ("http", "socks5", "socks5h"):
        protocol = "http"
    if protocol == "socks5":
        protocol = "socks5h"
    return f"{protocol}://{proxy_addr}"


# Token 输出目录
TOKENS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tokens")


# =================== Token 保存 ===================

def decode_jwt_payload(token):
    """解析 JWT token 的 payload 部分"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def save_token_json(email, access_token, refresh_token=None, id_token=None):
    """
    保存 Token JSON 文件，文件名按邮箱名称保存。
    保存路径: tokens/{email}.json
    格式: 单行紧凑 JSON
    """
    try:
        os.makedirs(TOKENS_DIR, exist_ok=True)

        payload = decode_jwt_payload(access_token)

        auth_info = payload.get("https://api.openai.com/auth", {})
        account_id = auth_info.get("chatgpt_account_id", "")

        exp_timestamp = payload.get("exp", 0)
        if exp_timestamp:
            exp_dt = datetime.fromtimestamp(exp_timestamp, tz=timezone(timedelta(hours=8)))
            expired_str = exp_dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        else:
            expired_str = ""

        now = datetime.now(tz=timezone(timedelta(hours=8)))
        last_refresh_str = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")

        # 按指定字段顺序构建（使用列表保证顺序）
        from collections import OrderedDict
        token_data = OrderedDict([
            ("id_token", id_token or ""),
            ("access_token", access_token),
            ("refresh_token", refresh_token or ""),
            ("account_id", account_id),
            ("last_refresh", last_refresh_str),
            ("email", email),
            ("type", "codex"),
            ("expired", expired_str),
        ])

        filename = os.path.join(TOKENS_DIR, f"{email}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False, separators=(",", ":"))
        logger.info(f"Token JSON 已保存: {filename}")
        return filename
    except Exception as e:
        logger.error(f"保存 Token JSON 失败: {e}")
        return None


# =================== OAuth 登录提取 Token ===================

def _extract_code_from_url(url):
    """从 URL 中提取 authorization code"""
    if not url or "code=" not in url:
        return None
    try:
        return parse_qs(urlparse(url).query).get("code", [None])[0]
    except Exception:
        return None


def _decode_auth_session(session_obj):
    """
    从 oai-client-auth-session cookie 解码 JSON。
    格式: base64(json).timestamp.signature
    """
    for c in session_obj.cookies:
        if c.name == "oai-client-auth-session":
            val = c.value
            first_part = val.split(".")[0] if "." in val else val
            pad = 4 - len(first_part) % 4
            if pad != 4:
                first_part += "=" * pad
            try:
                raw = base64.urlsafe_b64decode(first_part)
                return json.loads(raw.decode("utf-8"))
            except Exception:
                pass
    return None


def _follow_and_extract_code(session_obj, url, max_depth=10):
    """跟随重定向链，从 302 Location 或 ConnectionError 中提取 code"""
    if max_depth <= 0:
        return None
    try:
        r = session_obj.get(url, headers=NAVIGATE_HEADERS, verify=False,
                            timeout=15, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("Location", "")
            code = _extract_code_from_url(loc)
            if code:
                return code
            if loc.startswith("/"):
                loc = f"{OAUTH_ISSUER}{loc}"
            return _follow_and_extract_code(session_obj, loc, max_depth - 1)
        elif r.status_code == 200:
            return _extract_code_from_url(r.url)
    except requests.exceptions.ConnectionError as e:
        url_match = re.search(r'(https?://localhost[^\s\'"]+)', str(e))
        if url_match:
            return _extract_code_from_url(url_match.group(1))
    except Exception:
        pass
    return None


def codex_exchange_code(session, code, code_verifier):
    """用 authorization code 换取 tokens"""
    logger.info("正在换取 Token...")
    for attempt in range(2):
        try:
            resp = session.post(
                f"{OAUTH_ISSUER}/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": OAUTH_REDIRECT_URI,
                    "client_id": OAUTH_CLIENT_ID,
                    "code_verifier": code_verifier,
                },
                verify=False,
                timeout=60,
            )
            break
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Token 交换超时，重试...")
                time.sleep(2)
                continue
            logger.error(f"Token 交换失败: {e}")
            return None

    if resp.status_code == 200:
        data = resp.json()
        logger.info(f"Token 获取成功! access_token 长度: {len(data.get('access_token', ''))}")
        return data
    else:
        logger.error(f"Token 交换失败: {resp.status_code} - {resp.text[:300]}")
        return None


def perform_oauth_login(session, email, password, account_data=None, log=None):
    """
    纯 HTTP OAuth 登录获取 Token。

    流程:
      步骤1: GET  /oauth/authorize       → 获取 login_session
      步骤2: POST /api/accounts/authorize/continue → 提交邮箱
      步骤3: POST /api/accounts/password/verify    → 提交密码
      步骤3.5: （可选）邮箱验证 — 新注册账号首次登录时触发
      步骤4: consent 多步流程 → 提取 code → POST /oauth/token 换取 tokens

    返回: dict (含 access_token/refresh_token/id_token)，失败返回 None
    """
    if log is None:
        log = lambda msg: logger.info(msg)

    log("[登录] 开始 OAuth 登录获取 Token...")

    device_id = generate_device_id()
    session.cookies.set("oai-did", device_id, domain=".auth.openai.com")
    session.cookies.set("oai-did", device_id, domain="auth.openai.com")

    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(32)

    authorize_params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": "openid profile email offline_access",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    authorize_url = f"{OAUTH_ISSUER}/oauth/authorize?{urlencode(authorize_params)}"

    # ===== 步骤1: GET /oauth/authorize =====
    try:
        resp = session.get(authorize_url, headers=NAVIGATE_HEADERS,
                           allow_redirects=True, verify=False, timeout=30)
        log(f"[登录 步骤1] OAuth 授权: {resp.status_code}")
    except Exception as e:
        log(f"[登录 步骤1] OAuth 授权请求失败: {e}")
        return None

    # ===== 步骤2: POST authorize/continue =====
    headers = dict(COMMON_HEADERS)
    headers["referer"] = f"{OAUTH_ISSUER}/log-in"
    headers["oai-device-id"] = device_id
    headers.update(generate_datadog_trace())

    sentinel_email = build_sentinel_token(session, device_id, flow="authorize_continue")
    if not sentinel_email:
        log("[登录 步骤2] 无法获取 sentinel token")
        return None
    headers["openai-sentinel-token"] = sentinel_email

    try:
        resp = session.post(
            f"{OAUTH_ISSUER}/api/accounts/authorize/continue",
            json={"username": {"kind": "email", "value": email}},
            headers=headers, verify=False, timeout=30,
        )
        log(f"[登录 步骤2] 提交邮箱: {resp.status_code}")
    except Exception as e:
        log(f"[登录 步骤2] 邮箱提交失败: {e}")
        return None

    if resp.status_code != 200:
        log("[登录 步骤2] 邮箱提交失败")
        return None

    page_type = ""
    try:
        data = resp.json()
        page_type = data.get("page", {}).get("type", "")
    except Exception:
        pass

    # ===== 步骤3: POST password/verify =====
    headers["referer"] = f"{OAUTH_ISSUER}/log-in/password"
    headers.update(generate_datadog_trace())

    sentinel_pwd = build_sentinel_token(session, device_id, flow="password_verify")
    if not sentinel_pwd:
        log("[登录 步骤3] 无法获取 sentinel token")
        return None
    headers["openai-sentinel-token"] = sentinel_pwd

    try:
        resp = session.post(
            f"{OAUTH_ISSUER}/api/accounts/password/verify",
            json={"password": password},
            headers=headers, verify=False, timeout=30, allow_redirects=False,
        )
        log(f"[登录 步骤3] 密码验证: {resp.status_code}")
    except Exception as e:
        log(f"[登录 步骤3] 密码提交失败: {e}")
        return None

    if resp.status_code != 200:
        log("[登录 步骤3] 密码验证失败")
        return None

    continue_url = None
    try:
        data = resp.json()
        continue_url = data.get("continue_url", "")
        page_type = data.get("page", {}).get("type", "")
    except Exception:
        page_type = ""

    if not continue_url:
        log("[登录 步骤3] 未获取到 continue_url")
        return None

    # ===== 步骤3.5: 邮箱验证（新注册账号首次登录时可能触发） =====
    if page_type == "email_otp_verification" or "email-verification" in continue_url:
        log("[登录 步骤3.5] 需要邮箱验证（新注册账号首次登录）")

        if not account_data:
            log("[登录 步骤3.5] 无邮箱账号信息，无法接收验证码")
            return None

        h_val = dict(COMMON_HEADERS)
        h_val["referer"] = f"{OAUTH_ISSUER}/email-verification"
        h_val["oai-device-id"] = device_id
        h_val.update(generate_datadog_trace())

        log("[登录 步骤3.5] 等待验证码...")
        otp_code = poll_verification_code(account_data, timeout=120, proxies=session.proxies)
        if not otp_code:
            log("[登录 步骤3.5] 验证码等待超时")
            return None

        log(f"[登录 步骤3.5] 收到验证码: {otp_code}")
        resp = session.post(
            f"{OAUTH_ISSUER}/api/accounts/email-otp/validate",
            json={"code": otp_code},
            headers=h_val, verify=False, timeout=30,
        )
        if resp.status_code != 200:
            log(f"[登录 步骤3.5] 验证码验证失败: {resp.status_code}")
            return None

        log("[登录 步骤3.5] 验证码验证通过")
        try:
            data = resp.json()
            continue_url = data.get("continue_url", "")
            page_type = data.get("page", {}).get("type", "")
        except Exception:
            pass

        # 如果需要填写 about-you
        if continue_url and "about-you" in continue_url:
            log("[登录 步骤3.5] 处理 about-you...")
            h_about = dict(NAVIGATE_HEADERS)
            h_about["referer"] = f"{OAUTH_ISSUER}/email-verification"
            resp_about = session.get(f"{OAUTH_ISSUER}/about-you",
                                     headers=h_about, verify=False, timeout=30, allow_redirects=True)
            if "consent" in resp_about.url or "organization" in resp_about.url:
                continue_url = resp_about.url
            else:
                first_name, last_name = generate_random_name()
                birthdate = generate_random_birthday()
                h_create = dict(COMMON_HEADERS)
                h_create["referer"] = f"{OAUTH_ISSUER}/about-you"
                h_create["oai-device-id"] = device_id
                h_create.update(generate_datadog_trace())
                resp_create = session.post(
                    f"{OAUTH_ISSUER}/api/accounts/create_account",
                    json={"name": f"{first_name} {last_name}", "birthdate": birthdate},
                    headers=h_create, verify=False, timeout=30,
                )
                if resp_create.status_code == 200:
                    try:
                        data = resp_create.json()
                        continue_url = data.get("continue_url", "")
                    except Exception:
                        pass
                elif resp_create.status_code == 400 and "already_exists" in resp_create.text:
                    continue_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"

        if "consent" in page_type:
            continue_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"

        if not continue_url or "email-verification" in continue_url:
            log("[登录 步骤3.5] 邮箱验证后未获取到 consent URL")
            return None

    # ===== 步骤4: consent 多步流程 → 提取 code → 换 token =====
    log("[登录 步骤4] consent 流程，提取 authorization code...")

    if continue_url.startswith("/"):
        consent_url = f"{OAUTH_ISSUER}{continue_url}"
    else:
        consent_url = continue_url

    auth_code = None

    # 步骤4a: GET consent 页面
    try:
        resp = session.get(consent_url, headers=NAVIGATE_HEADERS,
                           verify=False, timeout=30, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            auth_code = _extract_code_from_url(loc)
            if not auth_code:
                auth_code = _follow_and_extract_code(session, loc)
        elif resp.status_code == 200:
            pass  # 需要继续 workspace/org select
    except requests.exceptions.ConnectionError as e:
        url_match = re.search(r'(https?://localhost[^\s\'"]+)', str(e))
        if url_match:
            auth_code = _extract_code_from_url(url_match.group(1))
    except Exception as e:
        log(f"[登录 步骤4a] consent 请求异常: {e}")

    # 步骤4b: workspace/select
    if not auth_code:
        session_data = _decode_auth_session(session)
        workspace_id = None
        if session_data:
            workspaces = session_data.get("workspaces", [])
            if workspaces:
                workspace_id = workspaces[0].get("id")

        if workspace_id:
            h_consent = dict(COMMON_HEADERS)
            h_consent["referer"] = consent_url
            h_consent["oai-device-id"] = device_id
            h_consent.update(generate_datadog_trace())

            try:
                resp = session.post(
                    f"{OAUTH_ISSUER}/api/accounts/workspace/select",
                    json={"workspace_id": workspace_id},
                    headers=h_consent, verify=False, timeout=30, allow_redirects=False,
                )
                if resp.status_code in (301, 302, 303, 307, 308):
                    auth_code = _extract_code_from_url(resp.headers.get("Location", ""))
                elif resp.status_code == 200:
                    ws_data = resp.json()
                    ws_next = ws_data.get("continue_url", "")
                    ws_page = ws_data.get("page", {}).get("type", "")

                    # 步骤4c: organization/select
                    if "organization" in ws_next or "organization" in ws_page:
                        org_url = ws_next if ws_next.startswith("http") else f"{OAUTH_ISSUER}{ws_next}"
                        org_id = None
                        project_id = None
                        ws_orgs = ws_data.get("data", {}).get("orgs", [])
                        if ws_orgs:
                            org_id = ws_orgs[0].get("id")
                            projects = ws_orgs[0].get("projects", [])
                            if projects:
                                project_id = projects[0].get("id")

                        if org_id:
                            body = {"org_id": org_id}
                            if project_id:
                                body["project_id"] = project_id
                            h_org = dict(COMMON_HEADERS)
                            h_org["referer"] = org_url
                            h_org["oai-device-id"] = device_id
                            h_org.update(generate_datadog_trace())

                            resp = session.post(
                                f"{OAUTH_ISSUER}/api/accounts/organization/select",
                                json=body, headers=h_org,
                                verify=False, timeout=30, allow_redirects=False,
                            )
                            if resp.status_code in (301, 302, 303, 307, 308):
                                loc = resp.headers.get("Location", "")
                                auth_code = _extract_code_from_url(loc)
                                if not auth_code:
                                    auth_code = _follow_and_extract_code(session, loc)
                            elif resp.status_code == 200:
                                org_data = resp.json()
                                org_next = org_data.get("continue_url", "")
                                if org_next:
                                    full_next = org_next if org_next.startswith("http") else f"{OAUTH_ISSUER}{org_next}"
                                    auth_code = _follow_and_extract_code(session, full_next)
                        else:
                            auth_code = _follow_and_extract_code(session, org_url)
                    elif ws_next:
                        full_next = ws_next if ws_next.startswith("http") else f"{OAUTH_ISSUER}{ws_next}"
                        auth_code = _follow_and_extract_code(session, full_next)
            except Exception as e:
                log(f"[登录 步骤4b] workspace/select 异常: {e}")

    # 步骤4d: 备用策略
    if not auth_code:
        try:
            resp = session.get(consent_url, headers=NAVIGATE_HEADERS,
                               verify=False, timeout=30, allow_redirects=True)
            auth_code = _extract_code_from_url(resp.url)
            if not auth_code and resp.history:
                for r in resp.history:
                    loc = r.headers.get("Location", "")
                    auth_code = _extract_code_from_url(loc)
                    if auth_code:
                        break
        except requests.exceptions.ConnectionError as e:
            url_match = re.search(r'(https?://localhost[^\s\'"]+)', str(e))
            if url_match:
                auth_code = _extract_code_from_url(url_match.group(1))
        except Exception:
            pass

    if not auth_code:
        log("[登录 步骤4] 未获取到 authorization code")
        return None

    log("[登录 步骤4] 获取到 authorization code，正在换取 Token...")
    return codex_exchange_code(session, auth_code, code_verifier)


# =================== 协议注册器 ===================

class ProtocolRegistrar:
    def __init__(self, proxy_config=None, proxy_url=None):
        """
        :param proxy_config: dict with keys 'username', 'password', 'country'
        :param proxy_url: 直接传入代理 URL，跳过代理解析（用于 IP 复用）
        """
        self.proxy_config = proxy_config

        # 如果直接传入了 proxy_url 则跳过解析
        if proxy_url:
            safe_log = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
            logger.info(f"复用代理: {safe_log}")
        elif self.proxy_config:
            mode = (self.proxy_config.get("mode") or "auth").strip().lower()
            if mode == "api":
                protocol = self.proxy_config.get("protocol", "http")
                country = self.proxy_config.get("country", "")
                proxy_addr = fetch_proxy_from_api(
                    self.proxy_config.get("appkey"),
                    protocol=protocol,
                    country=country,
                )
                if proxy_addr:
                    proxy_url = build_proxy_url_from_addr(proxy_addr, protocol=protocol)
                    logger.info(f"使用 API 代理: {proxy_addr} ({protocol})")
                else:
                    logger.warning("API 代理模式已启用，但获取代理地址失败")
            else:
                proxy_url = generate_proxy_url(
                    self.proxy_config.get("username"),
                    self.proxy_config.get("password"),
                    self.proxy_config.get("country", "us")
                )
            if proxy_url:
                # 日志只显示 @ 后面的部分，避免泄露凭据
                safe_log = proxy_url.split("@")[-1] if "@" in proxy_url else "hidden"
                logger.info(f"使用代理: {safe_log}")

        self.proxy_url = proxy_url  # 保存以便外部复用
        self.session = create_session(proxy_url)
        self.device_id = generate_device_id()
        self.sentinel_gen = SentinelTokenGenerator(device_id=self.device_id)
        self.code_verifier = None
        self.state = None

    def _build_headers(self, referer, with_sentinel=False):
        headers = dict(COMMON_HEADERS)
        headers["referer"] = referer
        headers["oai-device-id"] = self.device_id
        headers.update(generate_datadog_trace())
        if with_sentinel:
            token = self.sentinel_gen.generate_token()
            headers["openai-sentinel-token"] = token
        return headers

    def step0_init_oauth_session(self, email, log=None):
        if log is None:
            log = lambda msg: logger.info(msg)
        log("[步骤 0] 初始化 OAuth 会话")
        self.session.cookies.set("oai-did", self.device_id, domain=".auth.openai.com")
        self.session.cookies.set("oai-did", self.device_id, domain="auth.openai.com")

        code_verifier, code_challenge = generate_pkce()
        self.code_verifier = code_verifier
        self.state = secrets.token_urlsafe(32)

        authorize_params = {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self.state,
            "screen_hint": "signup",
            "prompt": "login",
        }
        authorize_url = f"{OPENAI_AUTH_BASE}/oauth/authorize?{urlencode(authorize_params)}"

        try:
            log("[步骤 0a] 发送 OAuth 授权请求...")
            resp = self.session.get(authorize_url, headers=NAVIGATE_HEADERS, allow_redirects=True, verify=False, timeout=30)
            if resp.status_code != 200:
                return False, f"授权请求失败: HTTP {resp.status_code}"
            log("[步骤 0a] OAuth 授权成功")
        except Exception as e:
            logger.error(f"步骤 0a 失败: {e}")
            return False, f"连接错误: {str(e)}"

        if not any(c.name == "login_session" for c in self.session.cookies):
            logger.warning("步骤 0a: 未获取到 login_session cookie")
            return False, "缺少 login_session cookie"

        headers = dict(COMMON_HEADERS)
        headers["referer"] = f"{OPENAI_AUTH_BASE}/create-account"
        headers["oai-device-id"] = self.device_id
        headers.update(generate_datadog_trace())

        log("[步骤 0b] 生成 Sentinel token...")
        sentinel_token = build_sentinel_token(self.session, self.device_id, flow="authorize_continue")
        if not sentinel_token:
            return False, "生成 Sentinel token 失败"
        headers["openai-sentinel-token"] = sentinel_token
        log("[步骤 0b] Sentinel token 生成成功，正在提交邮箱...")

        try:
            resp = self.session.post(
                f"{OPENAI_AUTH_BASE}/api/accounts/authorize/continue",
                json={"username": {"kind": "email", "value": email}, "screen_hint": "signup"},
                headers=headers, verify=False, timeout=30,
            )
            if resp.status_code == 200:
                log("[步骤 0] 完成")
                return True, "OK"
            return False, f"邮箱提交失败: HTTP {resp.status_code} - {resp.text[:200]}"
        except Exception as e:
            logger.error(f"步骤 0b 失败: {e}")
            return False, f"邮箱提交错误: {str(e)}"

    def step2_register_user(self, email, password):
        logger.info(f"[步骤 2] 注册用户: {email}")
        url = f"{OPENAI_AUTH_BASE}/api/accounts/user/register"
        headers = self._build_headers(referer=f"{OPENAI_AUTH_BASE}/create-account/password", with_sentinel=True)
        payload = {"username": email, "password": password}
        try:
            resp = self.session.post(url, json=payload, headers=headers, verify=False, timeout=30)
            if resp.status_code == 200:
                return True
            if resp.status_code in (301, 302):
                return True
            logger.error(f"步骤 2 失败: {resp.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"步骤 2 异常: {e}")
            return False

    def step3_send_otp(self):
        logger.info("[步骤 3] 触发 OTP 验证码发送")
        headers = dict(NAVIGATE_HEADERS)
        headers["referer"] = f"{OPENAI_AUTH_BASE}/create-account/password"
        try:
            self.session.get(f"{OPENAI_AUTH_BASE}/api/accounts/email-otp/send", headers=headers, verify=False, timeout=30)
            self.session.get(f"{OPENAI_AUTH_BASE}/email-verification", headers=headers, verify=False, timeout=30)
            return True
        except Exception as e:
            logger.error(f"步骤 3 异常: {e}")
            return False

    def step4_validate_otp(self, code):
        logger.info(f"[步骤 4] 验证 OTP: {code}")
        url = f"{OPENAI_AUTH_BASE}/api/accounts/email-otp/validate"
        headers = self._build_headers(referer=f"{OPENAI_AUTH_BASE}/email-verification")
        try:
            resp = self.session.post(url, json={"code": code}, headers=headers, verify=False, timeout=30)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"步骤 4 异常: {e}")
            return False

    def step5_create_account(self, first_name, last_name, birthdate):
        logger.info("[步骤 5] 创建账号")
        url = f"{OPENAI_AUTH_BASE}/api/accounts/create_account"
        headers = self._build_headers(referer=f"{OPENAI_AUTH_BASE}/about-you")
        payload = {"name": f"{first_name} {last_name}", "birthdate": birthdate}
        try:
            resp = self.session.post(url, json=payload, headers=headers, verify=False, timeout=30)
            logger.info(f"[步骤 5] 首次响应: HTTP {resp.status_code}")
            logger.info(f"[步骤 5] 首次响应 Body: {resp.text[:500]}")
            if resp.status_code == 200:
                return True
            if resp.status_code == 403 and "sentinel" in resp.text.lower():
                logger.info("[步骤 5] 检测到 sentinel 拦截，使用新 token 重试...")
                headers["openai-sentinel-token"] = self.sentinel_gen.generate_token()
                resp = self.session.post(url, json=payload, headers=headers, verify=False, timeout=30)
                logger.info(f"[步骤 5] 重试响应: HTTP {resp.status_code}")
                logger.info(f"[步骤 5] 重试响应 Body: {resp.text[:500]}")
                return resp.status_code == 200
            return False
        except Exception as e:
            logger.error(f"步骤 5 异常: {e}")
            return False

    def register(self, account_data, password, update_signal=None, stop_check=None):
        email = account_data["email"]

        def log(msg):
            logger.info(msg)
            if update_signal:
                update_signal.emit(f"{email}: {msg}")

        first_name, last_name = generate_random_name()
        birthdate = generate_random_birthday()

        log(f"开始注册 {email}")

        success, error = self.step0_init_oauth_session(email, log=log)
        if not success:
            msg = f"步骤 0 失败 ({error})"
            log(msg)
            return False, msg

        if stop_check and stop_check():
            return False, "用户停止"

        _interruptible_sleep(1, stop_check)

        if not self.step2_register_user(email, password):
            msg = "步骤 2 失败 (注册用户)"
            log(msg)
            return False, msg

        if stop_check and stop_check():
            return False, "用户停止"

        _interruptible_sleep(1, stop_check)
        self.step3_send_otp()

        log("正在等待验证码...")
        code = poll_verification_code(account_data, proxies=self.session.proxies, stop_check=stop_check)
        if not code:
            if stop_check and stop_check():
                return False, "用户停止"
            msg = "未收到验证码"
            log(msg)
            return False, msg

        log(f"收到验证码: {code}")

        if not self.step4_validate_otp(code):
            msg = "步骤 4 失败 (验证码无效)"
            log(msg)
            return False, msg

        if stop_check and stop_check():
            return False, "用户停止"

        _interruptible_sleep(1, stop_check)

        if not self.step5_create_account(first_name, last_name, birthdate):
            msg = "步骤 5 失败 (创建账号)"
            log(msg)
            return False, msg

        log("注册成功!")

        if stop_check and stop_check():
            return True, "注册成功，用户停止跳过 Token 获取"

        # ===== 注册成功后，执行 OAuth 登录获取 Token =====
        log("开始登录获取 Token...")
        _interruptible_sleep(2, stop_check)

        if stop_check and stop_check():
            return True, "注册成功，用户停止跳过 Token 获取"

        # 使用新 session 执行登录（注册 session 的 cookie 状态可能不适合登录）
        login_session = create_session(
            self.session.proxies.get("https") if self.session.proxies else None
        )
        tokens = perform_oauth_login(
            login_session, email, password,
            account_data=account_data, log=log,
        )

        if tokens and tokens.get("access_token"):
            saved_path = save_token_json(
                email,
                tokens["access_token"],
                tokens.get("refresh_token"),
                tokens.get("id_token"),
            )
            if saved_path:
                log(f"Token 已保存: {saved_path}")
            return True, "Success"
        else:
            log("注册成功，但获取 Token 失败，已存入待重试队列")
            _save_pending_account(email, password)
            return True, "注册成功，Token 获取失败"


def _save_pending_account(email, password):
    """
    将注册成功但 Token 获取失败的账号保存到 pending_accounts.json，
    以便后续批量重试获取 Token。
    """
    pending_file = os.path.join(TOKENS_DIR, "pending_accounts.json")
    try:
        os.makedirs(TOKENS_DIR, exist_ok=True)
        if os.path.exists(pending_file):
            with open(pending_file, "r", encoding="utf-8") as f:
                pending = json.load(f)
        else:
            pending = []

        # 去重：如果已存在相同 email 则更新密码
        pending = [p for p in pending if p.get("email") != email]
        pending.append({"email": email, "password": password})

        with open(pending_file, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)
        logger.info(f"已将账号存入待重试队列: {pending_file}")
    except Exception as e:
        logger.error(f"保存待重试账号失败: {e}")
