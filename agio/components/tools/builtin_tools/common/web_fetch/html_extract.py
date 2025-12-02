"""HTML 内容提取

使用 trafilatura 提取网页主要内容。
"""

import json
import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment
from pydantic import BaseModel
from trafilatura import extract
from trafilatura.settings import use_config

logger = logging.getLogger(__name__)

config = use_config()
config.set("DEFAULT", "image_len_threshold", "2048")
config.set("DEFAULT", "timeout", "10")
config.set("DEFAULT", "favor_precision", "False")
config.set("DEFAULT", "no_fallback", "False")
config.set("DEFAULT", "min_extracted_size", "5")
config.set("DEFAULT", "min_output_size", "5")
config.set("DEFAULT", "link_density_max", "0.6")


class HtmlContent(BaseModel):
    """HTML 内容模型"""

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


def clean_base_url(url):
    """移除查询参数和锚点"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def normalize_image_url(url, base_url):
    """将相对路径转为绝对URL"""
    if not url or url.startswith(("http://", "https://", "data:")):
        return url

    if url.startswith("//"):
        return f"https:{url}"

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
    """移除广告元素"""
    for tag in soup.find_all(class_=re.compile("|".join(AD_PATTERNS))):
        tag.decompose()
    return soup


def remove_framework_noise(soup: BeautifulSoup) -> BeautifulSoup:
    """移除框架噪音"""
    for tag in soup.find_all(attrs={"data-v": True}):
        del tag["data-v"]
    return soup


def preprocess_lazy_images(html, base_url):
    """预处理懒加载图片"""
    if not base_url:
        raise ValueError("base_url 不能为空")

    soup = BeautifulSoup(html, "html.parser")

    soup = remove_ads(soup)
    soup = remove_empty_tags(soup)
    soup = remove_framework_noise(soup)

    # 图片链接处理
    for img in soup.find_all("img"):
        current_src: str | None = img.get("src")
        if current_src and not current_src.startswith("data:"):
            img["src"] = normalize_image_url(current_src, base_url)
            continue

        lazy_attrs = [
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-srcset",
            "data-lazy-srcset",
        ]

        for attr in lazy_attrs:
            if img.get(attr):
                if "srcset" in attr:
                    img["srcset"] = normalize_image_url(img[attr], base_url)
                else:
                    img["src"] = normalize_image_url(img[attr], base_url)
                break

    # 删除 script（保留 ld+json）
    for script in soup.find_all("script"):
        if script.get("type") != "application/ld+json":
            script.decompose()

    # 删除 style
    for style in soup.find_all("style"):
        style.decompose()

    # 删除注释
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 处理 aria-hidden
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        if tag.find("img"):
            img = tag.find("img")
            tag.insert_before(img)
        tag.decompose()

    return str(soup)


def extract_content_from_html(html: str, original_url: str) -> HtmlContent | None:
    """提取页面内容

    Args:
        html: HTML 内容
        original_url: 原始 URL

    Returns:
        提取的内容或 None
    """
    if not html or not html.strip():
        logger.warning("Empty HTML content provided")
        return None

    try:
        # 预处理图片
        html = preprocess_lazy_images(html, base_url=original_url)

        result = extract(
            html,
            url=original_url,
            output_format="json",
            with_metadata=True,
            include_links=True,
            include_images=True,
            include_tables=True,
            include_formatting=True,
            include_comments=True,
            config=config,
        )
        if not result or len(result) == 0:
            logger.warning("No content extracted")
            return None

        json_data = json.loads(result)

        return HtmlContent(**json_data, raw_html=html)
    except Exception as e:
        logger.error(f"Content extraction failed: {e}")
        return None
