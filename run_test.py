import logging
from openai_registration import (
    generate_cf_email,
    generate_random_password,
    generate_proxy_url,
    ProtocolRegistrar
)

# 配置日志输出格式，方便查看
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_run")

def main():
    logger.info("开始自动化注册获取 Token 测试...")
    
    # 1. 生成您的专属测试邮箱密码
    email = generate_cf_email()
    password = generate_random_password()
    logger.info(f"生成的邮箱: {email}")
    logger.info(f"生成的密码: {password}")
    
    # 账号配置字典传给内部函数用作获取验证码
    account_data = {"email": email}

    # 2. 生成代理 (会自动读取我们刚才改好的 IPRoyal 配置)
    proxy_url = generate_proxy_url()
    logger.info(f"正在配置代理: {proxy_url.replace('7Denv6fS3q71GXQQ', '***')}")
    
    # 3. 初始化带有代理的协议注册器
    registrar = ProtocolRegistrar(proxy_url=proxy_url)
    
    # 4. 执行完整自动化注册及提取 Token
    logger.info("=========== 下方开始进入自动化网络流程 ===========")
    success, reason = registrar.register(account_data=account_data, password=password)
    
    if success:
        logger.info("太棒了！成功注册并且获取到 Token！")
        logger.info(f"请检查 tokens 目录看是否生成了 {email}.json")
    else:
        logger.error(f"很遗憾，跑通失败: {reason}")
        logger.error("请查看上方网络执行日志找原因。")

if __name__ == "__main__":
    main()
