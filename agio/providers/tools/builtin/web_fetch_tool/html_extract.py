from dataclasses import dataclass
import json
import re
from pydantic import BaseModel
from trafilatura import extract
from trafilatura.settings import use_config
from agio.providers.tools.builtin.adapter import get_logger

logger = get_logger(__name__)

config = use_config()

# config.set("DEFAULT", "language_score_threshold", "0.5") # 调整语言检测阈值
config.set("DEFAULT", "image_len_threshold", "2048")  # 跳过超过2048字符的URL
config.set("DEFAULT", "timeout", "10")  # 防止图片验证卡死
config.set("DEFAULT", "favor_precision", "False")  # 关闭精确度优先
config.set("DEFAULT", "no_fallback", "False")  # 启用回退策略
# 将最小文本长度从默认的10-15字符降低到5字符
config.set("DEFAULT", "min_extracted_size", "5")
config.set("DEFAULT", "min_output_size", "5")
# 提高链接密度容忍度
config.set("DEFAULT", "link_density_max", "0.6")  # 允许60%链接密度


# {
#   "title": "万字解码 Agentic AI 时代的记忆系统演进之路",
#   "author": "名称已清空",
#   "hostname": "weixin.qq.com",
#   "date": "2025-08-14",
#   "fingerprint": "e70ee15feb429436",
#   "id": null,
#   "license": null,
#   "comments": "",
#   "raw_text": "当下阶段 AI 应用正在从 Generative AI 向 Agentic AI 阶段迈进，..",
#   "text": "当下阶段 AI 应用正在从 Generative AI 向 Agentic AI 阶段迈进，2025 ",
#   "language": null,
#   "image": "https://mmbiz.qpic.cn/mmbiz_jpg/Z6bicxIx5naJa4viaDLQtG3qYgwG0cQwxBNacGibhaBLHg28ZWNrGBsZ07ia7ibIYIyYHlg0VgLrmqDWjFO0p2ibfOicg/0?wx_fmt=jpeg",
#   "pagetype": "article",
#   "filedate": "2025-11-12",
#   "source": "https://mp.weixin.qq.com/s/LYx4pV1L9aVjd5u5iiI2zg",
#   "source-hostname": "微信公众平台",
#   "excerpt": null,
#   "categories": "",
#   "tags": ""
# }
class HtmlContent(BaseModel):
    title: str | None = None
    author: str | None = None
    hostname: str | None = None
    date: str | None = None
    fingerprint: str | None = None
    id: str | None = None
    license: str | None = None
    comments: str | None = None
    raw_text: str | None = None
    text: str | None = None
    raw_html: str | None = None
    language: str | None = None
    image: str | None = None
    pagetype: str | None = None
    filedate: str | None = None
    source: str | None = None
    source_hostname: str | None = None
    excerpt: str | None = None
    categories: str | None = None
    tags: str | None = None


from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Comment


def clean_base_url(url):
    """移除查询参数和锚点"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def normalize_image_url(url, base_url):
    """将相对路径转为绝对URL"""
    if not url or url.startswith(("http://", "https://", "data:")):
        return url

    # 处理协议相对URL //cdn.example.com/img.jpg
    if url.startswith("//"):
        return f"https:{url}"

    # 使用base_url补全相对路径
    return urljoin(clean_base_url(base_url), url)


AD_PATTERNS = [
    "ad-",
    "ads-",
    "advert-",
    "sponsor-",
    "google-",
    "doubleclick",
    "taboola",
]


def remove_empty_tags(soup: BeautifulSoup) -> BeautifulSoup:
    """移除仅含空白字符的元素"""
    for tag in soup.find_all():
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()
    return soup


def remove_ads(soup: BeautifulSoup) -> BeautifulSoup:
    for tag in soup.find_all(class_=re.compile("|".join(AD_PATTERNS))):
        tag.decompose()
    return soup


def remove_framework_noise(soup: BeautifulSoup) -> BeautifulSoup:
    # 移除Vue/React属性
    for tag in soup.find_all(attrs={"data-v": True}):
        del tag["data-v"]
    return soup


# 完整预处理函数
def preprocess_lazy_images(html, base_url):
    """
    参数:
        html: 原始HTML字符串
        base_url: 文章页面的完整URL，用于补全相对路径
    """
    if not base_url:
        raise ValueError("base_url 不能为空，用于处理相对路径")

    soup = BeautifulSoup(html, "html.parser")

    soup = remove_ads(soup)
    soup = remove_empty_tags(soup)
    soup = remove_framework_noise(soup)
    # 图片链接处理
    for img in soup.find_all("img"):
        # 检查是否有有效的src（避免覆盖已有src）
        current_src: str | None = img.get("src")
        if current_src and not current_src.startswith("data:"):
            img["src"] = normalize_image_url(current_src, base_url)
            continue

        # 查找各种懒加载属性（按优先级）
        lazy_attrs = [
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-srcset",
            "data-lazy-srcset",
        ]

        for attr in lazy_attrs:
            if img.get(attr):
                # 对data-srcset/srcset特殊处理（响应式图片）
                if "srcset" in attr:
                    img["srcset"] = normalize_image_url(img[attr], base_url)
                else:
                    img["src"] = normalize_image_url(img[attr], base_url)
                break

    # 1. 删除<script>但保留<script type="application/ld+json">
    for script in soup.find_all("script"):
        if script.get("type") != "application/ld+json":
            script.decompose()

    # 2. 提取关键CSS（图片、表格相关）后删除<style>
    for style in soup.find_all("style"):
        style.decompose()

    # 3. 删除注释和无用属性
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 5. 查找所有aria-hidden="true"的元素
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        # 检查是否有重要子元素（如<img>）
        # 如果图片在aria-hidden容器内，但data-src在别处，可能需要保留
        if tag.find("img"):
            # 将图片移出容器，而非删除容器
            img = tag.find("img")
            tag.insert_before(img)
        # 删除容器
        tag.decompose()

    return str(soup)


def extract_content_from_html(html: str, original_url: str) -> HtmlContent | None:
    """提取页面内容

    Args:
        html: 要处理的 HTML 内容

    Returns:
        提取的内容 JSON 字符串，如果提取失败返回 None
    """
    if not html or not html.strip():
        logger.warning("Empty HTML content provided")
        return None

    try:
        # 图片懒加载情况
        html = preprocess_lazy_images(html, base_url=original_url)

        result = extract(
            html,
            url=original_url,
            output_format="json",
            with_metadata=True,
            # 扩展元素
            include_links=True,
            include_images=True,
            include_tables=True,  # 保留表格
            include_formatting=True,  # 保留粗体、斜体等格式
            include_comments=True,  # 通常不需要评论区
            config=config,
        )
        if not result or len(result) == 0:
            logger.warning("No content extracted")
            return None

        json_data = json.loads(result)

        return HtmlContent(**json_data, raw_html=html)
    except Exception as e:
        logger.error("Content extraction failed", error=str(e))
        return None
