"""Douban cover service — fetch audiobook covers from Douban."""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

DOUBAN_SUGGEST_URL = "https://book.douban.com/j/subject_suggest"
DOUBAN_BOOK_URL = "https://book.douban.com/subject/"

# Headers to mimic browser request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://book.douban.com/",
}


def _extract_book_name(folder_name: str) -> str:
    """Extract book name from folder name for fuzzy search.
    
    Examples:
        "樊登讲《论语》第一季（完结）" -> "论语"
        "FD08 樊登：可复制的领导力（完结）" -> "可复制的领导力"
        "FD14 冯仑：不确定时代的生存法则" -> "不确定时代的生存法则"
        "三体" -> "三体"
    """
    # Remove common prefixes like "FD08", "001", etc.
    name = re.sub(r'^[A-Z]{2,}\d+\s*', '', folder_name)
    name = re.sub(r'^\d+\s*', '', name)
    
    # Extract content inside 《》
    match = re.search(r'《(.+?)》', name)
    if match:
        return match.group(1)
    
    # Remove common suffixes
    name = re.sub(r'[（(].+?[)）]$', '', name)
    name = re.sub(r'第.+季$', '', name)
    name = re.sub(r'(完结|完|全集|精编版|精华版|珍藏版)$', '', name)
    
    # Handle "作者：书名" pattern — take the part after separator
    parts = re.split(r'[：:\-—]', name)
    if len(parts) > 1:
        # Use the last meaningful part (likely the book name)
        name = parts[-1]
    
    name = re.sub(r'\s+', '', name)
    
    return name.strip() or folder_name


async def search_douban_cover(book_name: str) -> Optional[str]:
    """Search Douban for audiobook cover and download to local.
    
    Uses fuzzy matching: extracts core book name from folder name.
    
    Args:
        book_name: Name of the audiobook to search for
        
    Returns:
        Local cover file path or None if not found
    """
    if not book_name or not book_name.strip():
        return None
    
    # Extract clean book name for search
    search_name = _extract_book_name(book_name)
    logger.info("Searching Douban for '%s' (extracted: '%s')", book_name, search_name)
    
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            # Try extracted name first, then original
            for name_to_search in [search_name, book_name]:
                if not name_to_search:
                    continue
                    
                response = await client.get(
                    DOUBAN_SUGGEST_URL,
                    params={"q": name_to_search},
                )
                
                if response.status_code != 200:
                    continue
                
                try:
                    results = response.json()
                except json.JSONDecodeError:
                    continue
                
                if not results:
                    continue
                
                # Get the first result's cover image
                first_result = results[0]
                cover_url = first_result.get("pic", "")
                
                if cover_url:
                    # Get large image URL
                    large_url = _get_large_image_url(cover_url)
                    
                    # Download to local
                    local_path = await _download_cover(client, large_url, book_name)
                    if local_path:
                        logger.info("Downloaded Douban cover for '%s': %s", book_name, local_path)
                        return local_path
            
            logger.info("No Douban book found for: %s", book_name)
            return None
            
    except httpx.HTTPError as e:
        logger.warning("HTTP error fetching Douban cover for '%s': %s", book_name, e)
        return None
    except Exception as e:
        logger.warning("Error fetching Douban cover for '%s': %s", book_name, e)
        return None


async def fetch_cover_from_douban_url(douban_url: str, book_name: str) -> Optional[str]:
    """Fetch cover from a specific Douban book URL.
    
    Args:
        douban_url: Douban book URL (e.g., https://book.douban.com/subject/27598664)
        book_name: Book name for generating filename
        
    Returns:
        Local cover file path or None if not found
    """
    if not douban_url or not douban_url.strip():
        return None
    
    # Extract subject ID from URL
    match = re.search(r'subject/(\d+)', douban_url)
    if not match:
        logger.warning("Invalid Douban URL: %s", douban_url)
        return None
    
    subject_id = match.group(1)
    
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            # Fetch the book page
            response = await client.get(douban_url)
            
            if response.status_code != 200:
                logger.warning("Failed to fetch Douban page: HTTP %d", response.status_code)
                return None
            
            # Extract cover image from HTML
            html = response.text
            
            # Try to find cover image in meta tags or main content
            # Pattern 1: og:image meta tag
            match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if not match:
                # Pattern 2: main cover image
                match = re.search(r'<img[^>]+src="(https://img\d+\.doubanio\.com/view/[^"]+)"', html)
            
            if match:
                cover_url = match.group(1)
                large_url = _get_large_image_url(cover_url)
                
                local_path = await _download_cover(client, large_url, book_name)
                if local_path:
                    logger.info("Downloaded Douban cover from URL for '%s': %s", book_name, local_path)
                    return local_path
            
            logger.warning("No cover found on Douban page: %s", douban_url)
            return None
            
    except httpx.HTTPError as e:
        logger.warning("HTTP error fetching Douban cover from URL: %s", e)
        return None
    except Exception as e:
        logger.warning("Error fetching Douban cover from URL: %s", e)
        return None


async def _download_cover(client: httpx.AsyncClient, url: str, book_name: str) -> Optional[str]:
    """Download cover image to local file.
    
    Args:
        client: HTTP client
        url: Image URL to download
        book_name: Book name for generating filename
        
    Returns:
        Local file path or None if failed
    """
    try:
        response = await client.get(url)
        
        if response.status_code != 200:
            logger.warning("Failed to download cover: HTTP %d", response.status_code)
            return None
        
        # Generate filename based on book name hash
        name_hash = hashlib.md5(book_name.encode()).hexdigest()[:12]
        ext = get_cover_extension(url)
        filename = f"{name_hash}{ext}"
        
        # Ensure cover directory exists
        cover_dir = settings.audiobook_cover_dir
        cover_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = cover_dir / filename
        with open(file_path, "wb") as f:
            f.write(response.content)
        
        # Return relative path for database storage
        return f"/api/media/covers/{filename}"
        
    except Exception as e:
        logger.warning("Error downloading cover: %s", e)
        return None


def _get_large_image_url(url: str) -> str:
    """Convert Douban image URL to large version.
    
    Douban image URLs typically look like:
    https://img9.doubanio.com/view/subject/l/public/sXXXXXXX.jpg
    
    The 'l' in the path indicates large size. We can also try 'raw' for original.
    """
    if not url:
        return url
    
    # Replace medium size with large size
    # doubanio.com uses /view/subject/l/ for large images
    # and /view/subject/m/ for medium, /view/subject/s/ for small
    
    # If already has /l/ path, return as is
    if "/view/subject/l/" in url:
        return url
    
    # Try to convert to large
    large_url = re.sub(
        r'/view/subject/[a-z]/',
        '/view/subject/l/',
        url
    )
    
    # If the URL doesn't have the standard pattern, try adding raw parameter
    if large_url == url:
        # Add ?view=raw or similar for original image
        if "?" in url:
            large_url = url + "&view=raw"
        else:
            large_url = url + "?view=raw"
    
    return large_url


async def download_cover(url: str, save_path: Path) -> bool:
    """Download cover image to local file.
    
    Args:
        url: Image URL to download
        save_path: Path to save the image
        
    Returns:
        True if successful, False otherwise
    """
    if not url:
        return False
    
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning("Failed to download cover: HTTP %d", response.status_code)
                return False
            
            # Ensure parent directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save image
            with open(save_path, "wb") as f:
                f.write(response.content)
            
            logger.info("Downloaded cover to: %s", save_path)
            return True
            
    except Exception as e:
        logger.warning("Error downloading cover: %s", e)
        return False


def get_cover_extension(url: str) -> str:
    """Get file extension from cover URL."""
    # Remove query parameters
    url_path = url.split("?")[0]
    
    # Extract extension
    if url_path.endswith(".jpg") or url_path.endswith(".jpeg"):
        return ".jpg"
    elif url_path.endswith(".png"):
        return ".png"
    elif url_path.endswith(".webp"):
        return ".webp"
    else:
        return ".jpg"  # Default to jpg