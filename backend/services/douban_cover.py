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

# Headers to mimic browser request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://book.douban.com/",
}


async def search_douban_cover(book_name: str) -> Optional[str]:
    """Search Douban for audiobook cover and download to local.
    
    Args:
        book_name: Name of the audiobook to search for
        
    Returns:
        Local cover file path or None if not found
    """
    if not book_name or not book_name.strip():
        return None
    
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            # Use Douban suggest API
            response = await client.get(
                DOUBAN_SUGGEST_URL,
                params={"q": book_name},
            )
            
            if response.status_code != 200:
                logger.warning("Douban search failed with status %d", response.status_code)
                return None
            
            # Parse JSON response
            try:
                results = response.json()
            except json.JSONDecodeError:
                logger.warning("Failed to parse Douban response")
                return None
            
            if not results:
                logger.info("No Douban book found for: %s", book_name)
                return None
            
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
            
            return None
            
    except httpx.HTTPError as e:
        logger.warning("HTTP error fetching Douban cover for '%s': %s", book_name, e)
        return None
    except Exception as e:
        logger.warning("Error fetching Douban cover for '%s': %s", book_name, e)
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