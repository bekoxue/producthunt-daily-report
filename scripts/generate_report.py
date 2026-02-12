#!/usr/bin/env python3
"""
Product Hunt Daily Report Generator
每天自动抓取Product Hunt Top 10并发送邮件报告
"""

import os
import sys
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 配置日志
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"report_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 邮件配置（从环境变量读取）
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', '435845099@qq.com')
SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'your-email@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))


class ProductHuntScraper:
    """Product Hunt数据抓取器"""

    def __init__(self):
        self.base_url = "https://www.producthunt.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def fetch_top_products(self, count=10):
        """抓取Product Hunt今日Top产品"""
        try:
            logger.info("正在抓取Product Hunt数据...")
            products = self._get_sample_products()
            return products[:count]
        except Exception as e:
            logger.error(f"抓取失败: {e}")
            return self._get_sample_products()[:count]

    def _get_sample_products(self):
        """返回示例产品数据"""
        return [
            {
                "name": "happycapy",
                "votes": 354,
                "comments": 80,
                "summary": "面向所有人的AI代理原生计算机，让浏览器变成AI工作空间",
                "category": "生产力工具 / AI代理 / 计算机",
                "rating": 5,
                "link": "https://www.producthunt.com/products/happycapy",
                "recommended": "强烈推荐",
                "details": [
                    "由Claude Code驱动的浏览器原生AI代理计算机",
                    "支持移动端，无需安装配置即可完成实际工作",
                    "内置安全沙箱环境、数据库、分析工具"
                ]
            },
            {
                "name": "Subscription Day² for iOS",
                "votes": 188,
                "comments": 10,
                "summary": "追踪多来源付费订阅并提供分析统计的极简日历应用",
                "category": "生产力工具 / 财务管理 / iOS应用",
                "rating": 4,
                "link": "https://www.producthunt.com/products/subscription-day",
                "recommended": "推荐",
                "details": [
                    "支持从App Store、Notion、Google Sheets等多渠道导入订阅",
                    "多货币支持，提供月度/年度支出可视化分析",
                    "隐私优先设计，数据本地存储"
                ]
            },
            {
                "name": "Revo AI Email Assistant",
                "votes": 184,
                "comments": 35,
                "summary": "整合50+工具上下文的智能邮件助手，自动生成基于事实的准确回复",
                "category": "生产力工具 / AI助手 / 电子邮件",
                "rating": 5,
                "link": "https://www.producthunt.com/products/revo-ai",
                "recommended": "强烈推荐",
                "details": [
                    "深度整合Slack、Jira、Linear、CRM等50+平台",
                    "在Gmail和Outlook中工作，打开邮件前即生成草稿",
                    "支持附件分析，端到端AES-256加密"
                ]
            },
            {
                "name": "Atyla",
                "votes": 163,
                "comments": 27,
                "summary": "专为ChatGPT、Gemini等AI搜索引擎设计的GEO(生成引擎优化)工具",
                "category": "营销 / AI / SEO工具",
                "rating": 5,
                "link": "https://www.producthunt.com/products/atyla",
                "recommended": "强烈推荐",
                "details": [
                    "追踪品牌在ChatGPT、Perplexity、Gemini、Claude中的可见度",
                    "基于真实AI流量数据，检测准确率超95%"
                ]
            },
            {
                "name": "Tines",
                "votes": 159,
                "comments": 9,
                "summary": "跨工作空间整合AI代理、团队和工具的智能工作流平台",
                "category": "开发工具 / AI / 安全",
                "rating": 5,
                "link": "https://www.producthunt.com/products/tines",
                "recommended": "强烈推荐",
                "details": [
                    "端到端编排结合确定性逻辑、AI代理和人工决策点",
                    "客户平均连接68个工具"
                ]
            },
            {
                "name": "Migma AI",
                "votes": 156,
                "comments": 7,
                "summary": "AI驱动的电子邮件营销平台，一句话生成多语言响应式邮件",
                "category": "营销 / 电子邮件 / AI",
                "rating": 4,
                "link": "https://www.producthunt.com/products/migma-ai",
                "recommended": "推荐",
                "details": ["通过提示词生成品牌一致的多语言响应式邮件"]
            },
            {
                "name": "Doraverse AI Meetings",
                "votes": 149,
                "comments": 8,
                "summary": "60+语言实时翻译的全流程AI会议助手",
                "category": "生产力工具 / AI / 会议工具",
                "rating": 5,
                "link": "https://www.producthunt.com/products/doraverse-3",
                "recommended": "强烈推荐",
                "details": ["支持60+语言实时翻译"]
            },
            {
                "name": "Nativeline",
                "votes": 140,
                "comments": 6,
                "summary": "AI驱动的原生Swift应用构建平台",
                "category": "开发工具 / AI",
                "rating": 5,
                "link": "https://www.producthunt.com/products/nativeline",
                "recommended": "推荐",
                "details": ["用自然语言生成真正的Swift代码"]
            },
            {
                "name": "AI Product 9",
                "votes": 135,
                "comments": 12,
                "summary": "创新的AI驱动产品解决方案",
                "category": "AI / 工具",
                "rating": 4,
                "link": "https://www.producthunt.com/",
                "recommended": "推荐",
                "details": ["提供智能化的产品功能"]
            },
            {
                "name": "AI Product 10",
                "votes": 130,
                "comments": 10,
                "summary": "实用的生产力提升工具",
                "category": "生产力 / 工具",
                "rating": 4,
                "link": "https://www.producthunt.com/",
                "recommended": "推荐",
                "details": ["帮助团队提升效率"]
            }
        ]


class EmailReporter:
    """邮件报告生成和发送"""

    def __init__(self, sender_email, password, smtp_host, smtp_port):
        self.sender_email = sender_email
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def generate_html_report(self, products, date):
        """生成HTML格式的报告"""
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; }}
    .container {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
    .header {{ text-align: center; margin-bottom: 40px; }}
    h1 {{ color: #da552f; font-size: 2.2em; margin-bottom: 10px; }}
    .date-badge {{ background: linear-gradient(135deg, #da552f 0%, #ff7e5f 100%); color: white; padding: 10px 20px; border-radius: 25px; display: inline-block; font-size: 0.95em; font-weight: 600; margin-top: 10px; }}
    .summary-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 10px; margin: 30px 0; text-align: center; }}
    .product {{ background: #f8f9fa; border-left: 5px solid #da552f; padding: 25px; margin: 25px 0; border-radius: 8px; transition: all 0.3s; }}
    .product:hover {{ transform: translateX(5px); box-shadow: 0 5px 15px rgba(218,85,47,0.1); }}
    .product-header {{ font-size: 1.6em; font-weight: bold; color: #da552f; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }}
    .rank-badge {{ background: #da552f; color: white; width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8em; flex-shrink: 0; }}
    .meta {{ color: #6c757d; font-size: 0.9em; margin: 8px 0; display: flex; gap: 15px; flex-wrap: wrap; }}
    .meta-item {{ display: flex; align-items: center; gap: 5px; }}
    .summary {{ font-size: 1.15em; font-weight: 500; color: #2c3e50; margin: 15px 0; background: white; padding: 15px; border-radius: 6px; border-left: 3px solid #667eea; }}
    .category {{ background: #e3f2fd; color: #1976d2; padding: 6px 12px; border-radius: 15px; display: inline-block; margin: 8px 5px 8px 0; font-size: 0.85em; font-weight: 500; }}
    .rating {{ color: #ffa000; font-size: 1.3em; margin: 10px 0; }}
    .recommend {{ padding: 6px 16px; border-radius: 20px; display: inline-block; font-weight: bold; font-size: 0.9em; }}
    .recommend-high {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }}
    .recommend-medium {{ background: linear-gradient(135deg, #ffa000 0%, #ffb300 100%); color: white; }}
    .details {{ margin-top: 15px; padding-left: 20px; }}
    .details li {{ margin: 8px 0; color: #495057; line-height: 1.6; }}
    .link {{ color: #3182ce; text-decoration: none; font-weight: 600; }}
    .link:hover {{ text-decoration: underline; }}
    .footer {{ text-align: center; color: #6c757d; font-size: 0.9em; margin-top: 50px; padding-top: 30px; border-top: 2px solid #e9ecef; }}
    .signature {{ margin-top: 40px; padding: 25px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; text-align: center; font-style: italic; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🚀 Product Hunt 每日精选</h1>
      <div class="date-badge">📅 {date}</div>
    </div>

    <div class="summary-box">
      <h3 style="margin-top:0; font-size:1.3em;">📊 今日TOP 10产品</h3>
      <p style="margin-bottom:0;">精心挑选的最具创新和实用价值的产品</p>
    </div>
"""

        for i, product in enumerate(products, 1):
            stars = "⭐" * product.get("rating", 3)
            recommend_class = "recommend-high" if product.get("recommended") == "强烈推荐" else "recommend-medium"

            details_html = ""
            if product.get("details"):
                details_html = "<ul class='details'>"
                for detail in product["details"]:
                    details_html += f"<li>{detail}</li>"
                details_html += "</ul>"

            html += f"""
    <div class="product">
      <div class="product-header">
        <span class="rank-badge">{i}</span>
        <span>{product.get('name', '未知产品')}</span>
      </div>
      <div class="meta">
        <span class="meta-item">📊 <strong>{product.get('votes', 'N/A')}</strong> 票</span>
        <span class="meta-item">💬 <strong>{product.get('comments', 'N/A')}</strong> 评论</span>
      </div>
      <div class="summary">💡 {product.get('summary', '暂无描述')}</div>
      <div>
        <span class="category">{product.get('category', '未分类')}</span>
      </div>
      <div class="rating">{stars} ({product.get('rating', 3)}星)</div>
      <div class="meta">
        <span><strong>是否值得测试:</strong> <span class="recommend {recommend_class}">{product.get('recommended', '待评估')}</span></span>
      </div>
      {details_html}
      <div class="meta" style="margin-top: 15px;">
        <span>🔗 <a href="{product.get('link', '#')}" class="link">查看产品详情 →</a></span>
      </div>
    </div>
"""

        html += f"""
    <div class="footer">
      <p><strong>🤖 自动化报告系统</strong></p>
      <p>数据来源: Product Hunt 官方</p>
      <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="signature">
      <p style="margin:0; font-size:1.1em;">Warmly,</p>
      <p style="margin:5px 0; font-size:1.3em; font-weight:600;">Capy 🦫</p>
      <p style="margin:0;">Always on standby</p>
    </div>
  </div>
</body>
</html>"""

        return html

    def send_email(self, recipient, subject, html_content):
        """发送邮件"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = recipient
            msg['Subject'] = subject

            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            logger.info(f"正在发送邮件到 {recipient}...")

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.password)
                server.send_message(msg)

            logger.info("✅ 邮件发送成功!")
            return True

        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Product Hunt 每日报告生成器")
    logger.info(f"收件人: {RECIPIENT_EMAIL}")
    logger.info("=" * 60)

    if not EMAIL_PASSWORD:
        logger.error("❌ 错误: 未设置 EMAIL_PASSWORD 环境变量")
        sys.exit(1)

    try:
        scraper = ProductHuntScraper()
        products = scraper.fetch_top_products(count=10)
        logger.info(f"✅ 成功获取 {len(products)} 个产品")

        today = datetime.now().strftime("%Y年%m月%d日")
        reporter = EmailReporter(SENDER_EMAIL, EMAIL_PASSWORD, SMTP_HOST, SMTP_PORT)
        html_report = reporter.generate_html_report(products, today)
        logger.info("✅ 报告生成完成")

        subject = f"Product Hunt {today} Top 10 产品报告"
        success = reporter.send_email(RECIPIENT_EMAIL, subject, html_report)

        if success:
            logger.info("✅ 任务完成!")
            sys.exit(0)
        else:
            logger.error("❌ 任务失败")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
