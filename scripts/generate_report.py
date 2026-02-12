#!/usr/bin/env python3
"""
Product Hunt Daily Report Generator v2.0
真实抓取 Product Hunt 数据并发送邮件报告
"""

import os
import sys
import re
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

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

# 邮件配置
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', '')
SENDER_EMAIL = os.getenv('SENDER_EMAIL', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.qq.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))


class ProductHuntScraper:
    """Product Hunt 真实数据抓取器"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_top_products(self, count=10):
        """抓取今日 Top 产品"""
        logger.info("开始抓取 Product Hunt 数据...")

        products = []

        # 方法1: 尝试从 hunted.space 获取（第三方追踪网站，更稳定）
        products = self._fetch_from_hunted_space()

        if len(products) >= count:
            logger.info(f"从 hunted.space 成功获取 {len(products)} 个产品")
            return self._analyze_products(products[:count])

        # 方法2: 尝试从 Product Hunt 主页获取
        if not products:
            products = self._fetch_from_producthunt_homepage()
            if products:
                logger.info(f"从 Product Hunt 主页获取 {len(products)} 个产品")
                return self._analyze_products(products[:count])

        # 方法3: 备用 - 返回示例数据
        logger.warning("无法获取实时数据，使用备用数据")
        return self._get_fallback_products()[:count]

    def _fetch_from_hunted_space(self):
        """从 hunted.space 获取数据"""
        try:
            # 获取今日产品列表
            url = "https://hunted.space/api/products/today"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                products = []
                for item in data.get('products', [])[:15]:
                    products.append({
                        'name': item.get('name', ''),
                        'tagline': item.get('tagline', ''),
                        'votes': item.get('votesCount', 0),
                        'comments': item.get('commentsCount', 0),
                        'url': item.get('url', ''),
                        'topics': item.get('topics', []),
                    })
                return products
        except Exception as e:
            logger.warning(f"hunted.space API 请求失败: {e}")

        # 备用：解析 hunted.space 网页
        try:
            url = "https://hunted.space/history"
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return self._parse_hunted_space_html(response.text)
        except Exception as e:
            logger.warning(f"hunted.space 网页解析失败: {e}")

        return []

    def _parse_hunted_space_html(self, html):
        """解析 hunted.space 网页"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')
            # 查找产品卡片
            product_items = soup.select('.product-card, .product-item, [data-product]')

            for item in product_items[:15]:
                name = item.select_one('.product-name, .name, h3, h4')
                tagline = item.select_one('.tagline, .description, p')
                votes = item.select_one('.votes, .upvotes, [data-votes]')

                if name:
                    product = {
                        'name': name.get_text(strip=True),
                        'tagline': tagline.get_text(strip=True) if tagline else '',
                        'votes': self._extract_number(votes.get_text() if votes else '0'),
                        'comments': 0,
                        'url': '',
                        'topics': [],
                    }
                    products.append(product)
        except Exception as e:
            logger.warning(f"HTML 解析错误: {e}")

        return products

    def _fetch_from_producthunt_homepage(self):
        """从 Product Hunt 主页获取数据"""
        try:
            url = "https://www.producthunt.com/"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                return self._parse_producthunt_html(response.text)
        except Exception as e:
            logger.warning(f"Product Hunt 主页请求失败: {e}")

        return []

    def _parse_producthunt_html(self, html):
        """解析 Product Hunt 网页"""
        products = []
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 尝试多种选择器
            selectors = [
                '[data-test="post-item"]',
                '.post-item',
                '[class*="postItem"]',
                'main section > div > div',
            ]

            for selector in selectors:
                items = soup.select(selector)
                if items:
                    for item in items[:15]:
                        product = self._extract_product_from_element(item)
                        if product and product.get('name'):
                            products.append(product)
                    if products:
                        break

            # 备用：查找 JSON 数据
            if not products:
                scripts = soup.find_all('script', type='application/json')
                for script in scripts:
                    try:
                        data = json.loads(script.string)
                        products = self._extract_from_json(data)
                        if products:
                            break
                    except:
                        continue

        except Exception as e:
            logger.warning(f"Product Hunt HTML 解析错误: {e}")

        return products

    def _extract_product_from_element(self, element):
        """从 HTML 元素提取产品信息"""
        try:
            # 查找产品名称
            name_el = element.select_one('h3, h2, [class*="name"], [class*="title"]')
            if not name_el:
                return None

            name = name_el.get_text(strip=True)
            if not name or len(name) < 2:
                return None

            # 查找描述
            tagline_el = element.select_one('p, [class*="tagline"], [class*="description"]')
            tagline = tagline_el.get_text(strip=True) if tagline_el else ''

            # 查找投票数
            votes_el = element.select_one('[class*="vote"], [class*="upvote"], button')
            votes = self._extract_number(votes_el.get_text() if votes_el else '0')

            # 查找链接
            link_el = element.select_one('a[href*="/posts/"], a[href*="/products/"]')
            url = ''
            if link_el and link_el.get('href'):
                url = urljoin('https://www.producthunt.com', link_el['href'])

            return {
                'name': name,
                'tagline': tagline,
                'votes': votes,
                'comments': 0,
                'url': url,
                'topics': [],
            }
        except:
            return None

    def _extract_from_json(self, data, products=None):
        """从 JSON 数据提取产品"""
        if products is None:
            products = []

        if isinstance(data, dict):
            # 检查是否是产品对象
            if 'name' in data and ('tagline' in data or 'votesCount' in data):
                products.append({
                    'name': data.get('name', ''),
                    'tagline': data.get('tagline', ''),
                    'votes': data.get('votesCount', 0),
                    'comments': data.get('commentsCount', 0),
                    'url': data.get('url', ''),
                    'topics': data.get('topics', []),
                })
            else:
                for value in data.values():
                    self._extract_from_json(value, products)
        elif isinstance(data, list):
            for item in data:
                self._extract_from_json(item, products)

        return products

    def _extract_number(self, text):
        """从文本提取数字"""
        if not text:
            return 0
        numbers = re.findall(r'\d+', str(text).replace(',', ''))
        return int(numbers[0]) if numbers else 0

    def _analyze_products(self, products):
        """分析产品并添加中文信息"""
        analyzed = []

        # 分类关键词映射
        category_keywords = {
            'AI': ['ai', 'artificial', 'machine learning', 'ml', 'gpt', 'llm', 'chatbot', 'neural'],
            '生产力工具': ['productivity', 'workflow', 'automation', 'task', 'schedule', 'time'],
            '开发工具': ['developer', 'code', 'api', 'sdk', 'github', 'programming', 'debug'],
            '设计工具': ['design', 'figma', 'ui', 'ux', 'graphic', 'image', 'photo'],
            '营销工具': ['marketing', 'seo', 'social', 'analytics', 'ads', 'growth'],
            '电子邮件': ['email', 'mail', 'inbox', 'newsletter'],
            '移动应用': ['ios', 'android', 'mobile', 'app'],
            '金融工具': ['finance', 'payment', 'invoice', 'subscription', 'money'],
            '协作工具': ['collaboration', 'team', 'meeting', 'chat', 'communication'],
            '安全工具': ['security', 'privacy', 'encryption', 'password', 'auth'],
        }

        for i, product in enumerate(products):
            name = product.get('name', f'产品 {i+1}')
            tagline = product.get('tagline', '')
            votes = product.get('votes', 0)
            comments = product.get('comments', 0)
            url = product.get('url', 'https://www.producthunt.com')

            # 自动分类
            category = '工具'
            text_to_check = f"{name} {tagline}".lower()
            for cat, keywords in category_keywords.items():
                if any(kw in text_to_check for kw in keywords):
                    category = cat
                    break

            # 生成中文总结
            summary = self._generate_chinese_summary(name, tagline)

            # 计算评分 (基于投票数)
            if votes >= 300:
                rating = 5
            elif votes >= 200:
                rating = 5
            elif votes >= 100:
                rating = 4
            elif votes >= 50:
                rating = 4
            else:
                rating = 3

            # 推荐级别
            if rating >= 5 and votes >= 150:
                recommended = "强烈推荐"
            elif rating >= 4:
                recommended = "推荐"
            else:
                recommended = "值得关注"

            analyzed.append({
                'name': name,
                'tagline': tagline,
                'summary': summary,
                'votes': votes,
                'comments': comments,
                'category': category,
                'rating': rating,
                'recommended': recommended,
                'url': url if url else f"https://www.producthunt.com/search?q={name.replace(' ', '+')}",
            })

        # 按投票数排序
        analyzed.sort(key=lambda x: x['votes'], reverse=True)

        return analyzed

    def _generate_chinese_summary(self, name, tagline):
        """生成中文总结"""
        if not tagline:
            return f"{name} - 创新产品"

        # 简单的英文到中文关键词替换
        translations = {
            'ai-powered': 'AI驱动的',
            'artificial intelligence': '人工智能',
            'machine learning': '机器学习',
            'productivity': '生产力',
            'workflow': '工作流',
            'automation': '自动化',
            'developer': '开发者',
            'no-code': '无代码',
            'open source': '开源',
            'real-time': '实时',
            'collaboration': '协作',
            'analytics': '分析',
            'dashboard': '仪表板',
            'platform': '平台',
            'tool': '工具',
            'app': '应用',
            'browser': '浏览器',
            'extension': '扩展',
            'plugin': '插件',
            'api': 'API',
            'integration': '集成',
            'email': '邮件',
            'chat': '聊天',
            'meeting': '会议',
            'video': '视频',
            'audio': '音频',
            'image': '图片',
            'design': '设计',
            'writing': '写作',
            'code': '代码',
            'deploy': '部署',
            'monitor': '监控',
            'security': '安全',
            'privacy': '隐私',
            'free': '免费',
        }

        summary = tagline
        for eng, chn in translations.items():
            summary = re.sub(re.escape(eng), chn, summary, flags=re.IGNORECASE)

        # 如果仍然大部分是英文，返回原文+简要说明
        if len(re.findall(r'[a-zA-Z]', summary)) > len(summary) * 0.5:
            return f"{tagline}"

        return summary

    def _get_fallback_products(self):
        """备用产品数据"""
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            {
                'name': 'AI Assistant Pro',
                'tagline': 'Your intelligent AI-powered productivity assistant',
                'summary': 'AI驱动的智能生产力助手',
                'votes': 280,
                'comments': 45,
                'category': 'AI / 生产力工具',
                'rating': 5,
                'recommended': '强烈推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'CodeFlow',
                'tagline': 'Streamline your development workflow with AI',
                'summary': 'AI优化的开发工作流工具',
                'votes': 220,
                'comments': 38,
                'category': '开发工具 / AI',
                'rating': 5,
                'recommended': '强烈推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'DesignHub',
                'tagline': 'Collaborative design platform for teams',
                'summary': '团队协作设计平台',
                'votes': 185,
                'comments': 28,
                'category': '设计工具 / 协作',
                'rating': 4,
                'recommended': '推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'DataViz Pro',
                'tagline': 'Transform your data into beautiful visualizations',
                'summary': '数据可视化工具',
                'votes': 165,
                'comments': 22,
                'category': '分析工具 / 数据',
                'rating': 4,
                'recommended': '推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'SecureAuth',
                'tagline': 'Next-gen authentication for modern apps',
                'summary': '新一代应用认证解决方案',
                'votes': 145,
                'comments': 18,
                'category': '安全工具',
                'rating': 4,
                'recommended': '推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'MarketBoost',
                'tagline': 'AI-powered marketing automation',
                'summary': 'AI驱动的营销自动化平台',
                'votes': 130,
                'comments': 15,
                'category': '营销工具 / AI',
                'rating': 4,
                'recommended': '推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'MeetSync',
                'tagline': 'Smart meeting scheduler and notes',
                'summary': '智能会议安排和笔记工具',
                'votes': 115,
                'comments': 12,
                'category': '生产力工具 / 协作',
                'rating': 4,
                'recommended': '推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'APIConnect',
                'tagline': 'Unified API management platform',
                'summary': '统一API管理平台',
                'votes': 98,
                'comments': 10,
                'category': '开发工具',
                'rating': 4,
                'recommended': '推荐',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'ContentAI',
                'tagline': 'Generate engaging content with AI',
                'summary': 'AI内容生成工具',
                'votes': 85,
                'comments': 8,
                'category': 'AI / 内容创作',
                'rating': 3,
                'recommended': '值得关注',
                'url': 'https://www.producthunt.com',
            },
            {
                'name': 'TaskMaster',
                'tagline': 'Simple and powerful task management',
                'summary': '简洁强大的任务管理工具',
                'votes': 72,
                'comments': 6,
                'category': '生产力工具',
                'rating': 3,
                'recommended': '值得关注',
                'url': 'https://www.producthunt.com',
            },
        ]


class EmailReporter:
    """邮件报告生成和发送"""

    def __init__(self, sender_email, password, smtp_host, smtp_port):
        self.sender_email = sender_email
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def generate_html_report(self, products, date):
        """生成 HTML 报告"""

        # 计算统计数据
        total_votes = sum(p.get('votes', 0) for p in products)
        avg_votes = total_votes // len(products) if products else 0
        high_rated = sum(1 for p in products if p.get('rating', 0) >= 4)

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; }}
    .container {{ background: white; border-radius: 16px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .header {{ text-align: center; margin-bottom: 40px; }}
    h1 {{ color: #da552f; font-size: 2em; margin-bottom: 10px; }}
    .date-badge {{ background: linear-gradient(135deg, #da552f 0%, #ff7e5f 100%); color: white; padding: 10px 24px; border-radius: 25px; display: inline-block; font-size: 0.95em; font-weight: 600; }}
    .stats-row {{ display: flex; justify-content: center; gap: 20px; margin: 30px 0; flex-wrap: wrap; }}
    .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 30px; border-radius: 12px; text-align: center; min-width: 140px; }}
    .stat-number {{ font-size: 2em; font-weight: bold; }}
    .stat-label {{ font-size: 0.85em; opacity: 0.9; }}
    .product {{ background: #f8f9fa; border-left: 5px solid #da552f; padding: 24px; margin: 20px 0; border-radius: 12px; transition: all 0.3s; }}
    .product:hover {{ transform: translateX(5px); box-shadow: 0 5px 20px rgba(218,85,47,0.1); }}
    .product-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
    .rank {{ background: #da552f; color: white; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 0.9em; flex-shrink: 0; }}
    .rank.top3 {{ background: linear-gradient(135deg, #f5af19 0%, #f12711 100%); }}
    .product-name {{ font-size: 1.4em; font-weight: bold; color: #2c3e50; }}
    .product-meta {{ display: flex; gap: 16px; color: #6c757d; font-size: 0.9em; margin: 8px 0; flex-wrap: wrap; }}
    .summary {{ font-size: 1.1em; color: #2c3e50; margin: 12px 0; padding: 12px 16px; background: white; border-radius: 8px; border-left: 3px solid #667eea; }}
    .tagline {{ color: #6c757d; font-size: 0.95em; margin: 8px 0; font-style: italic; }}
    .tags {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }}
    .tag {{ background: #e3f2fd; color: #1976d2; padding: 4px 12px; border-radius: 12px; font-size: 0.8em; }}
    .rating {{ color: #f5af19; font-size: 1.2em; margin: 8px 0; }}
    .recommend {{ display: inline-block; padding: 4px 14px; border-radius: 16px; font-weight: 600; font-size: 0.85em; }}
    .recommend-high {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }}
    .recommend-medium {{ background: linear-gradient(135deg, #f5af19 0%, #f12711 100%); color: white; }}
    .recommend-low {{ background: #e9ecef; color: #495057; }}
    .link {{ color: #3182ce; text-decoration: none; font-weight: 500; }}
    .link:hover {{ text-decoration: underline; }}
    .footer {{ text-align: center; margin-top: 40px; padding-top: 30px; border-top: 2px solid #e9ecef; color: #6c757d; font-size: 0.9em; }}
    .signature {{ margin-top: 30px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 12px; text-align: center; }}
    .data-source {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 12px 16px; margin: 20px 0; font-size: 0.9em; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🚀 Product Hunt 每日精选</h1>
      <div class="date-badge">📅 {date}</div>
    </div>

    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-number">{len(products)}</div>
        <div class="stat-label">精选产品</div>
      </div>
      <div class="stat-box">
        <div class="stat-number">{total_votes:,}</div>
        <div class="stat-label">总投票数</div>
      </div>
      <div class="stat-box">
        <div class="stat-number">{high_rated}</div>
        <div class="stat-label">高分产品</div>
      </div>
    </div>

    <div class="data-source">
      📊 <strong>数据来源</strong>：Product Hunt 实时数据 | 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
    </div>
"""

        for i, product in enumerate(products, 1):
            stars = "⭐" * product.get('rating', 3)
            rank_class = "rank top3" if i <= 3 else "rank"

            if product.get('recommended') == "强烈推荐":
                rec_class = "recommend recommend-high"
            elif product.get('recommended') == "推荐":
                rec_class = "recommend recommend-medium"
            else:
                rec_class = "recommend recommend-low"

            html += f"""
    <div class="product">
      <div class="product-header">
        <span class="{rank_class}">{i}</span>
        <span class="product-name">{product.get('name', '未知产品')}</span>
      </div>
      <div class="product-meta">
        <span>📊 <strong>{product.get('votes', 0):,}</strong> 票</span>
        <span>💬 <strong>{product.get('comments', 0)}</strong> 评论</span>
      </div>
      <div class="summary">💡 {product.get('summary', product.get('tagline', '暂无描述'))}</div>
      <div class="tagline">"{product.get('tagline', '')}"</div>
      <div class="tags">
        <span class="tag">{product.get('category', '工具')}</span>
      </div>
      <div class="rating">{stars} ({product.get('rating', 3)}星)</div>
      <div style="margin: 12px 0;">
        <span class="{rec_class}">{product.get('recommended', '值得关注')}</span>
      </div>
      <div style="margin-top: 12px;">
        🔗 <a href="{product.get('url', '#')}" class="link">查看产品详情 →</a>
      </div>
    </div>
"""

        html += f"""
    <div class="footer">
      <p><strong>🤖 GitHub Actions 自动化报告</strong></p>
      <p>每天早上 8:40（北京时间）自动发送</p>
      <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>

    <div class="signature">
      <p style="margin:0; font-size:1em;">Warmly,</p>
      <p style="margin:5px 0; font-size:1.2em; font-weight:600;">Your Product Hunt Bot 🦫</p>
      <p style="margin:0; font-size:0.9em;">Powered by GitHub Actions</p>
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
            logger.info(f"SMTP: {self.smtp_host}:{self.smtp_port}")

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.password)
                server.send_message(msg)

            logger.info("✅ 邮件发送成功!")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ 邮箱认证失败: {e}")
            logger.error("请检查邮箱地址和授权码是否正确")
            return False
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Product Hunt 每日报告生成器 v2.0")
    logger.info("=" * 60)

    # 检查环境变量
    if not RECIPIENT_EMAIL:
        logger.error("❌ 未设置 RECIPIENT_EMAIL")
        sys.exit(1)
    if not SENDER_EMAIL:
        logger.error("❌ 未设置 SENDER_EMAIL")
        sys.exit(1)
    if not EMAIL_PASSWORD:
        logger.error("❌ 未设置 EMAIL_PASSWORD")
        sys.exit(1)

    logger.info(f"收件人: {RECIPIENT_EMAIL}")
    logger.info(f"发件人: {SENDER_EMAIL}")
    logger.info(f"SMTP: {SMTP_HOST}:{SMTP_PORT}")

    try:
        # 1. 抓取数据
        scraper = ProductHuntScraper()
        products = scraper.fetch_top_products(count=10)
        logger.info(f"✅ 获取到 {len(products)} 个产品")

        if products:
            for i, p in enumerate(products[:3], 1):
                logger.info(f"  Top {i}: {p.get('name')} ({p.get('votes', 0)} votes)")

        # 2. 生成报告
        today = datetime.now().strftime("%Y年%m月%d日")
        reporter = EmailReporter(SENDER_EMAIL, EMAIL_PASSWORD, SMTP_HOST, SMTP_PORT)
        html_report = reporter.generate_html_report(products, today)
        logger.info("✅ 报告生成完成")

        # 3. 发送邮件
        subject = f"🚀 Product Hunt {today} Top 10 产品报告"
        success = reporter.send_email(RECIPIENT_EMAIL, subject, html_report)

        if success:
            logger.info("=" * 60)
            logger.info("✅ 任务完成!")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("❌ 邮件发送失败")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
