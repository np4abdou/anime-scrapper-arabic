#!/usr/bin/env python3
"""
Anime Downloader - A terminal app for finding and downloading anime from free streaming sites.
"""

import os
import sys
import argparse
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import random
import signal
import hashlib
import http.client
import urllib.parse
from io import BytesIO
from gzip import GzipFile
import requests
from threading import BoundedSemaphore, Thread, Event
from datetime import timedelta
import shutil

try:
    from playwright.sync_api import sync_playwright, Page, Browser
except ImportError:
    print("Playwright not found. Installing required packages...")
    os.system("pip install playwright")
    os.system("playwright install")
    from playwright.sync_api import sync_playwright, Page, Browser

# Constants
CONFIG_DIR = Path.home() / ".anime_downloader"
DATABASE_FILE = CONFIG_DIR / "database.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
DOWNLOAD_DIR = Path.home() / "Downloads" / "Anime"

# Ensure directories exist
CONFIG_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)

# Print database information for debugging
print(f"Database path: {DATABASE_FILE}")
print(f"Database exists: {DATABASE_FILE.exists()}")

# ANSI Colors for terminal output
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

# Constants for direct downloads
NON_ALPHANUM_FILE_OR_FOLDER_NAME_CHARACTERS = "-_. "
NON_ALPHANUM_FILE_OR_FOLDER_NAME_CHARACTER_REPLACEMENT = "-"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Accept-Encoding": "gzip",
}

# Check if we're running on repl.it
def is_replit():
    return 'REPL_ID' in os.environ

# Ensure Playwright browsers are installed
def ensure_playwright_browsers():
    try:
        # First check if we're on repl.it
        if is_replit():
            print("Running on repl.it environment, checking for Playwright browsers...")
            
            # Try to detect if browsers are missing
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    browser.close()
                print("Playwright browsers are already installed!")
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    print("Playwright browsers are missing. Installing now...")
                    os.system("python -m playwright install chromium")
                    print("Installation complete. If you still encounter issues, please run:")
                    print("python -m playwright install")
                    print("in the terminal/shell.")
                else:
                    print(f"Unexpected error with Playwright: {e}")
    except Exception as e:
        print(f"Error while ensuring Playwright browsers: {e}")
        print("If you encounter browser errors, please run:")
        print("python -m playwright install")
        print("in the terminal/shell.")

# Run the browser check early
ensure_playwright_browsers()


class AnimeDatabase:
    """Handles storage and retrieval of anime metadata and navigation patterns."""
    
    def __init__(self):
        self.data = self._load_database()
    
    def _load_database(self) -> Dict[str, Any]:
        """Load the database from file or create a new one if it doesn't exist."""
        try:
            if DATABASE_FILE.exists():
                print(f"Loading database from {DATABASE_FILE}")
                with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Creating new database at {DATABASE_FILE}")
                # Ensure parent directory exists
                DATABASE_FILE.parent.mkdir(exist_ok=True, parents=True)
                return {
                    "anime": {},
                    "normalized_titles": {},  # Maps normalized titles to actual titles
                    "aliases": {},            # Maps aliases to actual titles
                    "navigation_patterns": {},
                    "history": [],
                    "preferences": {}
                }
        except Exception as e:
            print(f"Error loading database: {e}")
            import traceback
            traceback.print_exc()
            # Return empty database as fallback
            return {
                "anime": {},
                "normalized_titles": {},
                "aliases": {},
                "navigation_patterns": {},
                "history": [],
                "preferences": {}
            }
    
    def save(self):
        """Save the current database to file."""
        try:
            # Ensure directory exists
            DATABASE_FILE.parent.mkdir(exist_ok=True, parents=True)
            
            with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
            print(f"Database saved to {DATABASE_FILE}")
        except Exception as e:
            print(f"Error saving database: {e}")
            import traceback
            traceback.print_exc()
    
    def normalize_title(self, title: str) -> str:
        """Normalize a title for better matching (lowercase, remove spaces and special chars)."""
        import re
        # Convert to lowercase, remove spaces and special characters
        normalized = re.sub(r'[^a-z0-9]', '', title.lower())
        print(f"Normalized title: '{title}' -> '{normalized}'")
        return normalized
    
    def add_anime(self, title: str, metadata: Dict[str, Any]):
        """Add or update anime metadata in the database."""
        print(f"Adding/updating anime in database: '{title}'")
        
        # Store the anime with its original title
        self.data["anime"][title] = metadata
        
        # Add normalized title mapping
        normalized_title = self.normalize_title(title)
        self.data["normalized_titles"][normalized_title] = title
        print(f"Added normalized title mapping: '{normalized_title}' -> '{title}'")
        
        # Auto-generate some common aliases
        # For titles with spaces, add a version without spaces
        if ' ' in title:
            self.add_alias(title.replace(' ', ''), title)
        
        # For titles that are not all lowercase, add lowercase version
        if title.lower() != title:
            self.add_alias(title.lower(), title)
        
        # For titles that are not all uppercase, add uppercase version
        if title.upper() != title:
            self.add_alias(title.upper(), title)
            
        self.save()
    
    def add_alias(self, alias: str, title: str):
        """Add an alias for an anime title."""
        if alias == title:
            return
            
        normalized_alias = self.normalize_title(alias)
        # Only add if the normalized alias doesn't exist yet
        if normalized_alias not in self.data["normalized_titles"]:
            self.data["aliases"][normalized_alias] = title
            print(f"Added alias: '{alias}' -> '{title}'")
            self.save()
    
    def find_anime_by_title(self, search_title: str) -> Optional[str]:
        """Find anime by title, using normalization and aliases for better matching."""
        print(f"Searching for anime with title: '{search_title}'")
        
        # First try direct match
        if search_title in self.data["anime"]:
            print(f"Found direct match for '{search_title}'")
            return search_title
            
        # Try normalized title
        normalized_search = self.normalize_title(search_title)
        print(f"Checking normalized title: '{normalized_search}'")
        print(f"Available normalized titles: {list(self.data['normalized_titles'].keys())}")
        
        # Check in normalized titles
        if normalized_search in self.data["normalized_titles"]:
            found_title = self.data["normalized_titles"][normalized_search]
            print(f"Found match in normalized titles: '{normalized_search}' -> '{found_title}'")
            return found_title
            
        # Check in aliases
        print(f"Checking aliases for: '{normalized_search}'")
        print(f"Available aliases: {list(self.data['aliases'].keys())}")
        if normalized_search in self.data["aliases"]:
            found_title = self.data["aliases"][normalized_search]
            print(f"Found match in aliases: '{normalized_search}' -> '{found_title}'")
            return found_title
            
        # No match found
        print(f"No match found for '{search_title}'")
        return None
    
    def get_anime(self, title: str) -> Optional[Dict[str, Any]]:
        """Get anime metadata by title."""
        # Try to find the anime with the title as-is
        anime_data = self.data["anime"].get(title)
        if anime_data:
            return anime_data
            
        # Try to find with normalization and aliases
        actual_title = self.find_anime_by_title(title)
        if actual_title:
            return self.data["anime"].get(actual_title)
            
        return None
    
    def add_navigation_pattern(self, site: str, pattern: Dict[str, Any]):
        """Add or update a navigation pattern for a site."""
        self.data["navigation_patterns"][site] = pattern
        self.save()
    
    def get_navigation_pattern(self, site: str) -> Optional[Dict[str, Any]]:
        """Get a navigation pattern for a site."""
        return self.data["navigation_patterns"].get(site)
    
    def add_to_history(self, entry: Dict[str, Any]):
        """Add an entry to the user's history."""
        self.data["history"].append(entry)
        self.save()


class SiteInteractor:
    """Handles interactions with anime websites using Playwright."""
    
    def __init__(self, database: AnimeDatabase):
        self.database = database
        self.playwright = None
        self.browser = None
        self.current_page = None
        self.site_patterns = {
            "witanime.cyou": {
                "search_url": "https://witanime.cyou/?search_param=animes&s={}",
                "search_results": ".anime-list-content .anime-card, .page-content-container .anime-card",
                "title_selector": ".anime-card-title h3, .anime-card-title h3 a",
                "link_selector": ".overlay-link, .anime-card-title h3 a",
                "episode_list": ".episodes-list-content .episode-card, .episodes-card-container .episode-card, .overlay",
                "episode_link": "a.overlay, a[onclick*='openEpisode'], .overlay",
                "download_page_link": ".episodes-buttons-list a:has-text('تحميل الحلقة'), .episode-buttons-container a:has-text('تحميل'), a:has-text('تحميل')",
                "download_servers": ".download-servers .server-item, .server-list .server-item, .download-servers a.dashboard-button, a[href*='drive.google'], a[href*='mediafire']",
                "server_name": ".server-name, .dashboard-button-text, .server-content"
            }
        }
    
    def start_browser(self, headless: bool = True):
        """Start the browser."""
        try:
            self.playwright = sync_playwright().start()
            try:
                # Special configuration for repl.it
                browser_args = []
                if is_replit():
                    browser_args = [
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage"
                    ]
                    print("Using repl.it-specific browser configuration")
                
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=browser_args
                )
                self.current_page = self.browser.new_page()
                # Set timeout to 60 seconds for slow connections
                self.current_page.set_default_timeout(60000)
                # Add user agent to avoid detection
                self.current_page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"})
                # Enable JavaScript to handle dynamic content
                self.current_page.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception as e:
                if "Executable doesn't exist" in str(e) and is_replit():
                    print("=" * 50)
                    print("Playwright browser executable not found. Trying to install...")
                    print("=" * 50)
                    os.system("export PLAYWRIGHT_BROWSERS_PATH=0 && python -m playwright install chromium --with-deps")
                    print("Installation attempted. Trying to launch browser again...")
                    # Try one more time after installation with repl.it flags
                    browser_args = [
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage"
                    ]
                    self.browser = self.playwright.chromium.launch(headless=True, args=browser_args)
                    self.current_page = self.browser.new_page()
                    self.current_page.set_default_timeout(60000)
                    self.current_page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"})
                    self.current_page.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                elif "Host system is missing dependencies" in str(e) and is_replit():
                    print("=" * 50)
                    print("Missing system dependencies. Using special repl.it configuration...")
                    print("=" * 50)
                    # Try with special repl.it configuration
                    browser_args = [
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage"
                    ]
                    # Force headless mode
                    self.browser = self.playwright.chromium.launch(headless=True, args=browser_args)
                    self.current_page = self.browser.new_page()
                    self.current_page.set_default_timeout(60000)
                    self.current_page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"})
                    self.current_page.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                else:
                    raise e
        except Exception as e:
            print(f"Error starting browser: {e}")
            if "Executable doesn't exist" in str(e):
                print("\n" + "=" * 60)
                print("ERROR: Playwright browser binaries not installed.")
                print("Please run: python -m playwright install")
                print("Or if you're using repl.it, visit the Shell tab and run:")
                print("export PLAYWRIGHT_BROWSERS_PATH=0 && python -m playwright install chromium --with-deps")
                print("=" * 60 + "\n")
            elif "Host system is missing dependencies" in str(e):
                print("\n" + "=" * 60)
                print("ERROR: System dependencies missing.")
                print("If you're using repl.it, try one of these options:")
                print("1. Visit the Shell tab and run: python -m playwright install-deps")
                print("2. Add these args to your code: ['--no-sandbox', '--disable-setuid-sandbox']")
                print("=" * 60 + "\n")
            raise e
    
    def close_browser(self):
        """Close the browser."""
        try:
            if self.browser:
                print("Closing browser...")
                for page in self.browser.contexts[0].pages:
                    try:
                        page.close()
                    except Exception:
                        pass
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
            self.current_page = None
            print("Browser closed successfully")
        except Exception as e:
            print(f"Warning: Error closing browser: {e}")
            # Reset browser objects even if close fails
            self.browser = None
            self.playwright = None
            self.current_page = None
    
    def navigate_to(self, url: str):
        """Navigate to a URL."""
        if not self.current_page:
            self.start_browser()
        
        # Remove the @ symbol if present at the beginning of the URL
        if url.startswith('@'):
            url = url[1:]
        
        self.current_page.goto(url)
    
    def search_anime(self, site_url: str, query: str) -> List[Dict[str, Any]]:
        """Search for anime on a site and return the results."""
        try:
            # Remove the @ symbol if present at the beginning of the URL
            if site_url.startswith('@'):
                site_url = site_url[1:]
            
            # Get the site's pattern or use a generic one
            site_domain = self._extract_domain(site_url)
            pattern = self.site_patterns.get(site_domain)
            
            if not pattern:
                print(f"Warning: No predefined patterns for {site_domain}. Using generic patterns.")
                return self._generic_search(site_url, query)
                
            # Navigate to the search page with the query
            # Properly encode the search query (replace spaces with plus signs)
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            search_url = pattern["search_url"].format(encoded_query)
            print(f"Navigating to search URL: {search_url}")
            self.navigate_to(search_url)
            
            # Wait for page to load completely
            print("Waiting for page to load completely...")
            self.current_page.wait_for_load_state("networkidle", timeout=60000)
            
            # Additional wait to ensure JavaScript has executed
            print("Giving extra time for JavaScript to execute...")
            time.sleep(5)
            
            # Take a screenshot for debugging
            self.current_page.screenshot(path="search_page.png")
            print("Screenshot saved as search_page.png")
            
            # Print page title for debugging
            print(f"Page title: {self.current_page.title()}")
            
            # Try different selector combinations for search results
            selectors_to_try = [
                ".anime-card",
                ".post-item",
                ".anime-list-content .anime-card",
                ".page-content-container .anime-card",
                "article",
                "[class*='anime']",
                ".card",
                ".movie-item"
            ]
            
            elements = []
            for selector in selectors_to_try:
                print(f"Trying selector: {selector}")
                try:
                    found_elements = self.current_page.query_selector_all(selector)
                    if found_elements and len(found_elements) > 0:
                        print(f"Found {len(found_elements)} elements with selector {selector}")
                        elements = found_elements
                        break
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
            
            if not elements:
                print("No anime results found with any selector")
                return []
                
            # Extract the search results
            results = []
            print(f"Processing {len(elements)} anime results")
            
            # Use set to track unique URLs and avoid duplicates
            seen_urls = set()
            normalized_urls = {}
            
            for element in elements:
                try:
                    # Get title using various methods
                    title = None
                    
                    # Try to find the title
                    title_selectors = [
                        "h3", ".title", "h2", ".name", ".anime-title", 
                        "h3 a", ".post-title", "[class*='title']"
                    ]
                    
                    for title_sel in title_selectors:
                        title_elem = element.query_selector(title_sel)
                        if title_elem:
                            title = title_elem.inner_text().strip()
                            break
                    
                    if not title:
                        # Try to get the alt attribute from any img element
                        img = element.query_selector("img")
                        if img:
                            title = img.get_attribute("alt")
                    
                    # If still no title, try to use aria-label or any text content
                    if not title:
                        title = element.get_attribute("aria-label") or element.inner_text().strip()
                    
                    # Find link
                    link = None
                    
                    # Try to get link from the card itself or any anchor inside
                    if element.get_attribute("href"):
                        link = element.get_attribute("href")
                    else:
                        link_elem = element.query_selector("a")
                        if link_elem:
                            link = link_elem.get_attribute("href")
                    
                    if link and not link.startswith("http"):
                        link = f"{self._get_base_url(site_url)}{link}"
                    
                    # Normalize the URL to anime/(animename) format if possible
                    normalized_link = link
                    anime_path_match = re.search(r'(https?://[^/]+/anime/[^/]+)/?', link)
                    if anime_path_match:
                        normalized_link = anime_path_match.group(1)
                    
                    # Skip URL if we've already seen it
                    if normalized_link in seen_urls:
                        continue
                    
                    if title and normalized_link:
                        # Make sure the result somewhat matches the query (case-insensitive)
                        if query.lower() in title.lower():
                            # Check if we've seen this title before
                            if title in normalized_urls:
                                # If we've seen this title, keep the anime URL, not category URL
                                if "/anime/" in normalized_link and "/anime-type/" in normalized_urls[title]:
                                    seen_urls.remove(normalized_urls[title])
                                    seen_urls.add(normalized_link)
                                    normalized_urls[title] = normalized_link
                                    
                                    # Update the existing result
                                    for i, existing in enumerate(results):
                                        if existing["title"] == title:
                                            results[i]["link"] = normalized_link
                                            break
                            else:
                                # If we haven't seen this title, add it
                                results.append({"title": title, "link": normalized_link})
                                seen_urls.add(normalized_link)
                                normalized_urls[title] = normalized_link
                                print(f"Found anime: {title} - {normalized_link}")
                except Exception as e:
                    print(f"Error extracting anime info: {e}")
            
            print(f"Total results matching '{query}': {len(results)}")
            return results
        except Exception as e:
            print(f"Error during search: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_episodes(self, anime_url: str) -> List[Dict[str, Any]]:
        """Extract episodes list from an anime page."""
        try:
            # Initialize URL counter
            url_counter = 0
            
            site_domain = self._extract_domain(anime_url)
            pattern = self.site_patterns.get(site_domain)
            
            if not pattern:
                print(f"Warning: No predefined patterns for {site_domain} episodes. Using generic patterns.")
                return []
            
            self.navigate_to(anime_url)
            
            # Wait for page to load completely
            print("Waiting for page to load completely...")
            self.current_page.wait_for_load_state("networkidle", timeout=60000)
            
            # Additional wait to ensure JavaScript has executed
            print("Giving extra time for JavaScript to execute...")
            time.sleep(5)
            
            # Take a screenshot for debugging
            self.current_page.screenshot(path="anime_page.png")
            print("Screenshot saved as anime_page.png")
            
            # Print page title for debugging
            print(f"Page title: {self.current_page.title()}")
            
            # For witanime.cyou, episodes are in buttons with onclick handlers
            if "witanime.cyou" in anime_url:
                print("Detected witanime.cyou, using special episode extraction...")
                
                # Look for episode elements with onclick attributes
                episodes = []
                
                # Try different selectors for episode elements
                selectors_to_try = [
                    "a[onclick*='openEpisode']",
                    ".episodes-card-container a.overlay",
                    ".episodes-list-content a.overlay",
                    ".episode-card a",
                    "a.overlay",
                    "[onclick*='openEpisode']",
                    ".card a"
                ]
                
                elements = []
                for selector in selectors_to_try:
                    print(f"Trying episode selector: {selector}")
                    try:
                        found_elements = self.current_page.query_selector_all(selector)
                        if found_elements and len(found_elements) > 0:
                            print(f"Found {len(found_elements)} episode elements with selector {selector}")
                            elements = found_elements
                            break
                    except Exception as e:
                        print(f"Error with selector {selector}: {e}")
                
                if not elements:
                    print("No episode elements found with any selector")
                    # Try to evaluate JavaScript to find episodes
                    try:
                        print("Attempting JavaScript evaluation to find episodes...")
                        elements = self.current_page.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('a')).filter(a => 
                                    a.getAttribute('onclick') && a.getAttribute('onclick').includes('openEpisode')
                                );
                            }
                        """)
                        if elements:
                            print(f"Found {len(elements)} episodes using JavaScript evaluation")
                    except Exception as e:
                        print(f"JavaScript evaluation failed: {e}")
                
                if not elements:
                    # Last resort - try to look for numbered elements
                    try:
                        print("Looking for numbered elements as last resort...")
                        numbered_elements = self.current_page.evaluate("""
                            () => {
                                const results = [];
                                const elements = document.querySelectorAll('*');
                                for (const el of elements) {
                                    const text = el.innerText || el.textContent;
                                    if (text && /الحلقة\\s+\\d+/.test(text)) {
                                        results.push({
                                            element: el,
                                            text: text,
                                            number: text.match(/\\d+/)[0]
                                        });
                                    }
                                }
                                return results;
                            }
                        """)
                        if numbered_elements:
                            print(f"Found {len(numbered_elements)} numbered elements")
                            # Process these elements differently
                            for item in numbered_elements:
                                episodes.append({
                                    "number": item["number"],
                                    "link": anime_url  # We'll need special handling for these
                                })
                            
                            # Remove duplicates by episode number
                            unique_episodes = {}
                            for ep in episodes:
                                unique_episodes[ep["number"]] = ep
                            
                            episodes = list(unique_episodes.values())
                            
                            # Sort by episode number
                            episodes.sort(key=lambda x: int(x["number"]) if x["number"].isdigit() else float('inf'))
                            return episodes
                    except Exception as e:
                        print(f"Numbered element search failed: {e}")
                    
                    return []
                
                # Process found elements
                import base64
                episode_dict = {}  # Use dictionary to avoid duplicates
                
                for element in elements:
                    try:
                        # Get the onclick attribute and extract the base64 parameter
                        onclick = element.get_attribute("onclick")
                        if onclick and "openEpisode" in onclick:
                            # Extract the base64-encoded URL
                            import re
                            base64_match = re.search(r"openEpisode\('([^']+)'\)", onclick)
                            if base64_match:
                                base64_url = base64_match.group(1)
                                try:
                                    # Decode the URL
                                    decoded_url = base64.b64decode(base64_url).decode('utf-8')
                                    # Update on the same line instead of adding new lines
                                    sys.stdout.write(f"\rProcessing URL: {decoded_url[:70]}..." + " " * 20)
                                    sys.stdout.flush()
                                    
                                    # Extract episode number from URL
                                    ep_match = re.search(r'/episode/[^/]+-(\d+)/?$', decoded_url)
                                    if ep_match:
                                        episode_number = ep_match.group(1)
                                    else:
                                        # Try alternative pattern
                                        ep_match = re.search(r'الحلقة-(\d+)', decoded_url)
                                        if ep_match:
                                            episode_number = ep_match.group(1)
                                        else:
                                            # Generate sequential number
                                            episode_number = str(len(episode_dict) + 1)
                                    
                                    # Store in dictionary to avoid duplicates
                                    episode_dict[episode_number] = {
                                        "number": episode_number,
                                        "link": decoded_url
                                    }
                                except Exception as decode_err:
                                    print(f"Error decoding base64 URL: {decode_err}")
                        else:
                            # Try to find episode number in parent elements text content
                            parent_text = element.evaluate("el => el.closest('.episode-card, .card')?.innerText")
                            if parent_text:
                                ep_match = re.search(r'الحلقة\s*(\d+)', parent_text)
                                if ep_match:
                                    episode_number = ep_match.group(1)
                                    # Construct URL based on pattern
                                    episode_url = f"{self._get_base_url(anime_url)}/episode/{anime_url.split('/')[-2]}-{episode_number}/"
                                    
                                    # Store in dictionary to avoid duplicates
                                    episode_dict[episode_number] = {
                                        "number": episode_number,
                                        "link": episode_url
                                    }
                    except Exception as e:
                        print(f"Error processing episode element: {e}")
                
                # Convert dictionary to list
                episodes = list(episode_dict.values())
                
                # Sort episodes by number
                episodes.sort(key=lambda x: int(x["number"]) if x["number"].isdigit() else float('inf'))
                
                # Print a newline to finish the URL processing status
                print(f"\nProcessed {len(episodes)} episode URLs")
                return episodes
            
            # Standard episode extraction for other sites
            # Wait for the episodes list to load
            try:
                print(f"Waiting for selector: {pattern['episode_list']}")
                self.current_page.wait_for_selector(pattern["episode_list"], timeout=30000)
            except Exception as e:
                print(f"Could not find episode list with selector {pattern['episode_list']}. Error: {e}")
                return []
            
            # Extract episodes
            episode_dict = {}  # Use dictionary to avoid duplicates
            elements = self.current_page.query_selector_all(pattern["episode_list"])
            
            print(f"Found {len(elements)} episode elements")
            for element in elements:
                try:
                    link_elem = element.query_selector(pattern["episode_link"])
                    if link_elem:
                        link = link_elem.get_attribute("href")
                        number = link_elem.inner_text().strip()
                        
                        if number.isdigit():
                            episode_number = number
                        else:
                            # Try to extract the episode number from the URL or text
                            match = re.search(r'الحلقة-(\d+)', link)
                            if match:
                                episode_number = match.group(1)
                            else:
                                # Try to extract from element text
                                match = re.search(r'الحلقة\s*(\d+)', element.inner_text())
                                if match:
                                    episode_number = match.group(1)
                                else:
                                    # Last resort - look for any number in text
                                    match = re.search(r'(\d+)', number)
                                    if match:
                                        episode_number = match.group(1)
                                    else:
                                        episode_number = "Unknown"
                        
                        if link and not link.startswith("http"):
                            link = f"{self._get_base_url(anime_url)}{link}"
                        
                        # Store in dictionary to avoid duplicates
                        episode_dict[episode_number] = {
                            "number": episode_number,
                            "link": link
                        }
                except Exception as e:
                    print(f"Error extracting episode info: {e}")
            
            # Convert dictionary to list
            episodes = list(episode_dict.values())
            
            # Sort episodes by number
            episodes.sort(key=lambda x: int(x["number"]) if x["number"].isdigit() else float('inf'))
            
            # Print a newline to finish the URL processing status
            print(f"\nProcessed {len(episodes)} episode URLs")
            return episodes
        except Exception as e:
            print(f"Error extracting episodes: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_download_links(self, episode_url: str) -> List[Dict[str, str]]:
        """Extract download links from an episode page."""
        try:
            # URL counter for progress tracking
            processed_urls = 0
            
            site_domain = self._extract_domain(episode_url)
            pattern = self.site_patterns.get(site_domain)
            
            if not pattern:
                print(f"Warning: No predefined patterns for {site_domain} download links. Using generic patterns.")
                return []
            
            self.navigate_to(episode_url)
            
            # Wait for page to load completely
            print("Waiting for page to load completely...")
            self.current_page.wait_for_load_state("networkidle", timeout=60000)
            
            # Additional wait to ensure JavaScript has executed
            print("Giving extra time for JavaScript to execute...")
            time.sleep(5)
            
            # Take a screenshot for debugging
            self.current_page.screenshot(path="episode_page.png")
            print("Screenshot saved as episode_page.png")
            
            # Print page title for debugging
            print(f"Page title: {self.current_page.title()}")
            
            # Special handling for witanime.cyou
            if "witanime.cyou" in episode_url:
                print("Detected witanime.cyou, using special download link extraction...")
                
                # First try to look directly for the download container
                download_container_selectors = [
                    ".episode-download-container",
                    ".content.episode-download-container",
                    ".download-container",
                    "[class*='download-container']",
                    ".mwidget",
                    ".quality-list"
                ]
                
                download_container = None
                for selector in download_container_selectors:
                    print(f"Looking for download container with selector: {selector}")
                    try:
                        container = self.current_page.query_selector(selector)
                        if container:
                            download_container = container
                            print(f"Found download container with selector: {selector}")
                            break
                    except Exception as e:
                        print(f"Error finding download container with selector {selector}: {e}")
                
                # If we found the download container, extract links directly
                if download_container:
                    print("Processing download links from container...")
                    
                    # Extract download links with their server names
                    download_links = []
                    
                    # Look for download links in the container
                    link_selectors = [
                        "a.download-link",
                        "a.btn.download-link",
                        "a.btn.btn-default.download-link",
                        "a[data-index]",
                        "a[class*='download']",
                        "a.btn"
                    ]
                    
                    for link_selector in link_selectors:
                        try:
                            links = download_container.query_selector_all(link_selector)
                            if links and len(links) > 0:
                                print(f"Found {len(links)} download links with selector {link_selector}")
                                
                                for link in links:
                                    try:
                                        # Get the server name from the span.notice
                                        notice = link.query_selector("span.notice")
                                        server_name = notice.inner_text().strip() if notice else "Unknown Server"
                                        
                                        # Get the data-index or href
                                        data_index = link.get_attribute("data-index")
                                        href = link.get_attribute("href")
                                        
                                        if href and href != "#":
                                            download_links.append({
                                                "host": server_name,
                                                "url": href if href.startswith("http") else f"{self._get_base_url(episode_url)}{href}"
                                            })
                                            print(f"Found direct download link for {server_name}: {href}")
                                        elif data_index:
                                            # These are JavaScript-based links, we need to extract real URLs
                                            print(f"Found JavaScript-based link for {server_name} with data-index {data_index}")
                                            
                                            # Click on the link to trigger the JavaScript
                                            link.click()
                                            time.sleep(2)  # Wait for any popups or redirects
                                            
                                            # Check if a new tab was opened
                                            pages = self.current_page.context.pages
                                            if len(pages) > 1:
                                                # A new tab was opened, get the URL
                                                new_page = pages[-1]
                                                new_url = new_page.url
                                                # Update status on same line
                                                sys.stdout.write(f"\rFound URL: {new_url[:70]}..." + " " * 20)
                                                sys.stdout.flush()
                                                processed_urls += 1
                                                
                                                download_links.append({
                                                    "host": server_name,
                                                    "url": new_url
                                                })
                                                
                                                # Close the new tab
                                                new_page.close()
                                            else:
                                                print(f"No new tab was opened for {server_name}")
                                    except Exception as e:
                                        print(f"Error processing download link: {e}")
                                
                                # If we found links, no need to try other selectors
                                if download_links:
                                    break
                        except Exception as e:
                            print(f"Error with link selector {link_selector}: {e}")
                    
                    # If we found download links, return them
                    if download_links:
                        return download_links
                
                # Try JavaScript evaluation to find download links if we couldn't find them directly
                try:
                    print("Using JavaScript evaluation to find download links...")
                    download_info = self.current_page.evaluate("""
                        () => {
                            const links = [];
                            // Look for quality-list elements
                            document.querySelectorAll('.quality-list').forEach(list => {
                                const quality = list.querySelector('li')?.innerText || 'Unknown Quality';
                                
                                // Get all download links in this quality section
                                list.querySelectorAll('a.download-link, a.btn.download-link, a[data-index]').forEach(link => {
                                    const notice = link.querySelector('span.notice')?.innerText || 'Unknown Server';
                                    const dataIndex = link.getAttribute('data-index');
                                    const href = link.getAttribute('href');
                                    
                                    links.push({
                                        quality,
                                        server: notice,
                                        dataIndex,
                                        href
                                    });
                                });
                            });
                            return links;
                        }
                    """)
                    
                    if download_info and len(download_info) > 0:
                        print(f"Found {len(download_info)} download links using JavaScript evaluation")
                        
                        # Process the JavaScript-found links
                        download_links = []
                        for info in download_info:
                            server_name = f"{info['server']} ({info['quality']})"
                            
                            if info['href'] and info['href'] != "#":
                                download_links.append({
                                    "host": server_name,
                                    "url": info['href'] if info['href'].startswith("http") else f"{self._get_base_url(episode_url)}{info['href']}"
                                })
                            elif info['dataIndex']:
                                # These are JavaScript-based links, we might need to click them
                                # For now, just log that we found them
                                print(f"Found JavaScript link: {server_name} with data-index {info['dataIndex']}")
                                
                                # Add a placeholder - the actual clicking will need to be done interactively
                                download_links.append({
                                    "host": server_name,
                                    "url": f"javascript:index={info['dataIndex']}"  # This is a placeholder
                                })
                        
                        if download_links:
                            return download_links
                except Exception as e:
                    print(f"JavaScript evaluation for download links failed: {e}")
                
                # If we still haven't found download links, try to find the download button
                # and navigate to the download page
                download_button_selectors = [
                    "a:has-text('تحميل الحلقة')",
                    "a:has-text('تحميل')",
                    ".btn-site:has-text('تحميل')",
                    ".btn-site",
                    "a.btn-site",
                    ".episodes-buttons-list a",
                    ".episode-buttons-container a"
                ]
                
                download_button = None
                for selector in download_button_selectors:
                    print(f"Looking for download button with selector: {selector}")
                    try:
                        button = self.current_page.query_selector(selector)
                        if button:
                            download_button = button
                            print(f"Found download button with selector: {selector}")
                            break
                    except Exception as e:
                        print(f"Error finding download button with selector {selector}: {e}")
                
                if not download_button:
                    print("Could not find download button with any selector")
                    
                    # Try JavaScript evaluation
                    try:
                        print("Attempting JavaScript evaluation to find download button...")
                        download_button = self.current_page.evaluate("""
                            () => {
                                // Look for elements with text containing Arabic word for download
                                const elements = Array.from(document.querySelectorAll('a, button'));
                                return elements.find(el => 
                                    (el.innerText || '').includes('تحميل') ||
                                    (el.textContent || '').includes('تحميل')
                                );
                            }
                        """)
                        if download_button:
                            print("Found download button using JavaScript evaluation")
                    except Exception as e:
                        print(f"JavaScript evaluation failed: {e}")
                
                if not download_button:
                    print("No download button found, cannot proceed")
                    return []
                
                # Click the download button to navigate to the download page
                try:
                    print("Clicking download button...")
                    with self.current_page.expect_navigation(timeout=60000):
                        download_button.click()
                    
                    # Wait after navigation
                    self.current_page.wait_for_load_state("networkidle", timeout=60000)
                    time.sleep(5)
                    
                    # Take another screenshot
                    self.current_page.screenshot(path="download_page.png")
                    print("Screenshot saved as download_page.png")
                    
                    print(f"New page title: {self.current_page.title()}")
                except Exception as e:
                    print(f"Error clicking download button: {e}")
                    
                    # Try a direct navigation to the download page if possible
                    if download_button.get_attribute("href"):
                        download_url = download_button.get_attribute("href")
                        if download_url:
                            if not download_url.startswith("http"):
                                download_url = f"{self._get_base_url(episode_url)}{download_url}"
                            print(f"Navigating directly to: {download_url}")
                            self.navigate_to(download_url)
                    else:
                        return []
                
                # Now try to find the download servers on the download page
                server_selectors = [
                    ".download-servers a.dashboard-button",
                    ".download-servers a",
                    ".server-list a",
                    ".server-item a",
                    "a.dashboard-button",
                    "a[href*='drive.google']",
                    "a[href*='mediafire']",
                    ".quality-list a",
                    "a.download-link",
                    "a[class*='download']"
                ]
                
                servers = []
                for selector in server_selectors:
                    print(f"Looking for servers with selector: {selector}")
                    try:
                        found_servers = self.current_page.query_selector_all(selector)
                        if found_servers and len(found_servers) > 0:
                            servers = found_servers
                            print(f"Found {len(servers)} servers with selector {selector}")
                            break
                    except Exception as e:
                        print(f"Error finding servers with selector {selector}: {e}")
                
                if not servers:
                    print("Could not find any download servers")
                    # Try JavaScript evaluation
                    try:
                        print("Attempting JavaScript evaluation to find servers...")
                        servers = self.current_page.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('a')).filter(a => {
                                    const href = a.getAttribute('href') || '';
                                    return href.includes('drive.google') || 
                                           href.includes('mediafire') ||
                                           href.includes('mega') ||
                                           href.includes('solidfiles') ||
                                           href.includes('mp4upload');
                                });
                            }
                        """)
                        if servers:
                            print(f"Found {len(servers)} servers using JavaScript evaluation")
                    except Exception as e:
                        print(f"JavaScript evaluation failed: {e}")
                
                if not servers:
                    return []
                
                # Extract download links
                download_links = []
                
                for server in servers:
                    try:
                        url = server.get_attribute("href")
                        if not url:
                            continue
                        
                        # Get server name/text
                        text = server.inner_text().strip()
                        if not text:
                            # Try to extract from elements inside
                            text_elem = server.query_selector(".dashboard-button-text, .server-name, .notice")
                            if text_elem:
                                text = text_elem.inner_text().strip()
                        
                        # If still no text, try to determine from URL
                        if not text:
                            if "drive.google" in url:
                                text = "Google Drive"
                            elif "mediafire" in url:
                                text = "MediaFire"
                            elif "mega" in url:
                                text = "MEGA"
                            elif "solidfiles" in url:
                                text = "SolidFiles"
                            elif "mp4upload" in url:
                                text = "MP4Upload"
                            elif "4shared" in url:
                                text = "4shared"
                            elif "yandex" in url:
                                text = "Yandex"
                            else:
                                text = "Unknown Server"
                        
                        download_links.append({
                            "host": text,
                            "url": url
                        })
                        print(f"Found server: {text} - {url}")
                    except Exception as e:
                        print(f"Error extracting server info: {e}")
                
                return download_links
            
            # Standard extraction for other sites
            # First, find and click the download page link
            try:
                download_button = self.current_page.query_selector(pattern["download_page_link"])
                if download_button:
                    with self.current_page.expect_navigation():
                        download_button.click()
                else:
                    print("Download button not found")
                    return []
            except Exception as e:
                print(f"Error clicking download button: {e}")
                return []
            
            # Now on the download page, extract servers
            try:
                self.current_page.wait_for_selector(pattern["download_servers"], timeout=30000)
            except Exception as e:
                print(f"Could not find download servers with selector {pattern['download_servers']}. Error: {e}")
                return []
            
            # Extract download links from all available servers
            download_links = []
            servers = self.current_page.query_selector_all(pattern["download_servers"])
            
            print(f"Found {len(servers)} download servers")
            for server in servers:
                try:
                    name_elem = server.query_selector(pattern["server_name"])
                    name = name_elem.inner_text().strip() if name_elem else "Unknown server"
                    
                    url = server.get_attribute("href")
                    if url:
                        download_links.append({
                            "host": name,
                            "url": url
                        })
                except Exception as e:
                    print(f"Error extracting server info: {e}")
            
            return download_links
        except Exception as e:
            print(f"Error extracting download links: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generic_search(self, site_url: str, query: str) -> List[Dict[str, Any]]:
        """Generic search method when no patterns are available."""
        print("Using generic search method. Results may be less accurate.")
        
        # Try to find a search form
        self.navigate_to(site_url)
        
        # Look for common search elements
        search_box = None
        for selector in ["input[type='search']", "input[name='s']", ".search-field", "input.search-input"]:
            search_box = self.current_page.query_selector(selector)
            if search_box:
                break
        
        if not search_box:
            print("Could not find search box")
            return []
        
        # Fill in the search box
        search_box.fill(query)
        
        # Try to submit the form
        form = search_box.evaluate("el => el.closest('form')")
        if form:
            with self.current_page.expect_navigation():
                self.current_page.evaluate("form => form.submit()", form)
        else:
            # If no form, try pressing Enter
            with self.current_page.expect_navigation():
                search_box.press("Enter")
        
        # Wait for results to load
        self.current_page.wait_for_load_state("networkidle")
        
        # Try common patterns for anime items
        results = []
        for selector in [".anime-item", ".anime-card", ".show-card", "article", ".post"]:
            items = self.current_page.query_selector_all(selector)
            if items:
                for item in items:
                    title_elem = None
                    for title_sel in ["h2", "h3", ".title", ".name"]:
                        title_elem = item.query_selector(title_sel)
                        if title_elem:
                            break
                    
                    link_elem = item.query_selector("a")
                    
                    if title_elem and link_elem:
                        title = title_elem.inner_text()
                        link = link_elem.get_attribute("href")
                        
                        if link and not link.startswith("http"):
                            link = f"{self._get_base_url(site_url)}{link}"
                        
                        results.append({"title": title, "link": link})
                
                break  # Stop if we found some items
        
        return results
    
    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        # Remove the @ symbol if present at the beginning of the URL
        if url.startswith('@'):
            url = url[1:]
            
        import re
        match = re.search(r'https?://([^/]+)', url)
        return match.group(1) if match else url
    
    def _get_base_url(self, url: str) -> str:
        """Get the base URL from a full URL."""
        # Remove the @ symbol if present at the beginning of the URL
        if url.startswith('@'):
            url = url[1:]
            
        import re
        match = re.search(r'(https?://[^/]+)', url)
        return match.group(1) if match else ""

    def _handle_javascript_download_link(self, link_info: Dict[str, Any]) -> str:
        """Handle a JavaScript-based download link and return the actual URL."""
        if not link_info.get("url", "").startswith("javascript:"):
            return link_info.get("url", "")
            
        data_index = link_info.get("url").split("=")[-1] if link_info.get("url") else None
        if not data_index:
            return ""
            
        sys.stdout.write(f"\rHandling JavaScript link for {link_info.get('host')} with index {data_index}..." + " " * 20)
        sys.stdout.flush()
        
        try:
            # Execute JavaScript to simulate clicking the link with this data-index
            result = self.current_page.evaluate(f"""
                () => {{
                    const link = document.querySelector('a.download-link[data-index="{data_index}"]');
                    if (!link) return null;
                    
                    // Get the full URL from the link (might be set by JavaScript)
                    if (link.href && link.href !== "#" && !link.href.startsWith("javascript")) {{
                        return link.href;
                    }}
                    
                    // Try to dispatch a click event
                    link.click();
                    return "clicked";
                }}
            """)
            
            if result and result != "clicked":
                sys.stdout.write(f"\rGot direct URL: {result[:70]}..." + " " * 20 + "\n")
                sys.stdout.flush()
                return result
            
            # If we've clicked the link, check if a new tab was opened
            time.sleep(2)  # Wait for any redirects or new tabs
            
            pages = self.current_page.context.pages
            if len(pages) > 1:
                # A new tab was opened, get the URL
                new_page = pages[-1]
                new_url = new_page.url
                sys.stdout.write(f"\rFound URL in new tab: {new_url[:70]}..." + " " * 20 + "\n")
                sys.stdout.flush()
                
                # Close the new tab
                new_page.close()
                return new_url
                
            # Check if the current page URL has changed
            current_url = self.current_page.url
            if current_url != link_info.get("original_page_url", ""):
                sys.stdout.write(f"\rPage redirected to: {current_url[:70]}..." + " " * 20 + "\n")
                sys.stdout.flush()
                
                # Go back to the original page
                self.navigate_to(link_info.get("original_page_url", ""))
                return current_url
                
            sys.stdout.write("\rNo URL change detected" + " " * 50 + "\n")
            sys.stdout.flush()
            return ""
            
        except Exception as e:
            sys.stdout.write(f"\rError handling JavaScript link: {str(e)[:70]}..." + " " * 20 + "\n")
            sys.stdout.flush()
            return ""


class PatternRecognition:
    """Handles pattern recognition for identifying elements on anime sites."""
    
    def __init__(self, database: AnimeDatabase):
        self.database = database
        # Common patterns for anime sites
        self.common_patterns = {
            "search_box": [
                "input[type='search']", 
                "input[name='s']", 
                ".search-input", 
                ".search-field",
                "input[placeholder*='search' i]",
                "input[placeholder*='بحث' i]"  # Arabic word for search
            ],
            "search_button": [
                "button[type='submit']",
                "input[type='submit']",
                ".search-submit",
                "button.search-button",
                "i.fa-search"
            ],
            "anime_items": [
                ".anime-item", 
                ".anime-card", 
                "article", 
                ".post", 
                ".show-card",
                ".anime-block",
                ".result-item"
            ],
            "title": [
                "h2", 
                "h3", 
                ".title", 
                ".name",
                ".anime-title",
                ".post-title"
            ],
            "episode_items": [
                ".episode-item",
                ".episode-card",
                ".eps-item",
                ".episode",
                ".ep-card"
            ],
            "download_buttons": [
                "a.download",
                "a:has-text('Download')",
                "a:has-text('تحميل')",  # Arabic word for download
                ".download-button",
                ".btn-download"
            ],
            "server_items": [
                ".server-item",
                ".server-list-item",
                ".mirror-item",
                ".download-server",
                ".server"
            ]
        }
    
    def learn_site_structure(self, site_url: str, page: Page):
        """Learn and store the structure of a site."""
        print(f"Learning site structure for {site_url}...")
        
        pattern = {
            "search_box": self._find_element(page, self.common_patterns["search_box"]),
            "search_button": self._find_element(page, self.common_patterns["search_button"]),
            "anime_items": self._find_element(page, self.common_patterns["anime_items"]),
            "title": self._find_element(page, self.common_patterns["title"]),
            "episode_items": self._find_element(page, self.common_patterns["episode_items"]),
            "download_buttons": self._find_element(page, self.common_patterns["download_buttons"]),
            "server_items": self._find_element(page, self.common_patterns["server_items"])
        }
        
        # Store learned pattern
        self.database.add_navigation_pattern(site_url, pattern)
        print(f"Site structure learned and stored for {site_url}")
        
        return pattern
    
    def _find_element(self, page: Page, selectors: List[str]) -> Dict[str, Any]:
        """Find an element on a page using a list of possible selectors."""
        for selector in selectors:
            try:
                count = page.evaluate(f"document.querySelectorAll('{selector}').length")
                if count > 0:
                    return {"selector": selector, "confidence": min(count/5 + 0.5, 0.95), "count": count}
            except Exception:
                continue
        
        return {"selector": None, "confidence": 0, "count": 0}
    
    def analyze_page(self, page: Page, purpose: str) -> Dict[str, Any]:
        """Analyze a page to find important elements based on the purpose."""
        print(f"Analyzing page for {purpose}...")
        
        if purpose == "search":
            result = {
                "search_box": self._find_element(page, self.common_patterns["search_box"]),
                "search_button": self._find_element(page, self.common_patterns["search_button"])
            }
        elif purpose == "anime_list":
            result = {
                "anime_items": self._find_element(page, self.common_patterns["anime_items"]),
                "title": self._find_element(page, self.common_patterns["title"])
            }
        elif purpose == "episode_list":
            result = {
                "episode_items": self._find_element(page, self.common_patterns["episode_items"])
            }
        elif purpose == "download_page":
            result = {
                "download_buttons": self._find_element(page, self.common_patterns["download_buttons"]),
                "server_items": self._find_element(page, self.common_patterns["server_items"])
            }
        else:
            # Analyze everything
            result = {
                "search_box": self._find_element(page, self.common_patterns["search_box"]),
                "search_button": self._find_element(page, self.common_patterns["search_button"]),
                "anime_items": self._find_element(page, self.common_patterns["anime_items"]),
                "title": self._find_element(page, self.common_patterns["title"]),
                "episode_items": self._find_element(page, self.common_patterns["episode_items"]),
                "download_buttons": self._find_element(page, self.common_patterns["download_buttons"]),
                "server_items": self._find_element(page, self.common_patterns["server_items"])
            }
        
        # Print what was found
        found_elements = [k for k, v in result.items() if v["selector"] is not None]
        print(f"Found elements: {', '.join(found_elements) if found_elements else 'None'}")
        
        return result
    
    def update_site_pattern(self, site_url: str, new_pattern: Dict[str, Any]):
        """Update the stored pattern for a site with new information."""
        existing_pattern = self.database.get_navigation_pattern(site_url)
        
        if existing_pattern:
            # Merge existing pattern with new information
            for key, value in new_pattern.items():
                if value["selector"] is not None and value["confidence"] > 0.5:
                    existing_pattern[key] = value
            
            self.database.add_navigation_pattern(site_url, existing_pattern)
        else:
            # Store new pattern
            self.database.add_navigation_pattern(site_url, new_pattern)
    
    def adapt_to_changes(self, site_url: str, page: Page, purpose: str) -> Dict[str, Any]:
        """Analyze page and adapt to changes if the current pattern doesn't work."""
        existing_pattern = self.database.get_navigation_pattern(site_url)
        
        if not existing_pattern:
            # Learn from scratch
            return self.learn_site_structure(site_url, page)
        
        # Check if existing pattern still works
        pattern_works = True
        for key, value in existing_pattern.items():
            if value["selector"]:
                try:
                    count = page.evaluate(f"document.querySelectorAll('{value['selector']}').length")
                    if count == 0:
                        pattern_works = False
                        break
                except Exception:
                    pattern_works = False
                    break
        
        if pattern_works:
            return existing_pattern
        
        # Pattern doesn't work, analyze and adapt
        print(f"Existing pattern for {site_url} no longer works. Adapting...")
        new_pattern = self.analyze_page(page, purpose)
        self.update_site_pattern(site_url, new_pattern)
        
        return new_pattern


class DownloadManager:
    """Handles the downloading of anime files from various sources."""
    
    def __init__(self, download_dir: Path = DOWNLOAD_DIR):
        self.download_dir = download_dir
        self.download_queue = []
        # Import additional required modules
        try:
            import requests
            self.requests = requests
        except ImportError:
            print("Installing requests module...")
            os.system("pip install requests")
            import requests
            self.requests = requests
    
    def add_to_queue(self, link: Dict[str, str], anime_title: str, episode: str):
        """Add a download link to the queue."""
        self.download_queue.append({
            "link": link,
            "anime_title": anime_title,
            "episode": episode,
            "status": "queued",
            "progress": 0
        })
        print(f"Added to queue: {anime_title} - Episode {episode} from {link['host']}")
    
    def process_queue(self):
        """Process the download queue."""
        for item in self.download_queue:
            if item["status"] == "queued":
                print(f"\nDownloading {item['anime_title']} - Episode {item['episode']} from {item['link']['host']}")
                item["status"] = "downloading"
                
                # Create anime directory if it doesn't exist
                anime_dir = self.download_dir / item["anime_title"].replace(':', ' -').replace('/', '-')
                anime_dir.mkdir(exist_ok=True, parents=True)
                
                # Download file
                filename = f"{item['anime_title']}_Episode_{item['episode']}.mp4"
                destination = anime_dir / filename
                
                success = self._download_file(
                    item["link"], 
                    destination
                )
                
                if success:
                    item["status"] = "completed"
                    item["progress"] = 100
                    print(f"Download completed: {destination}")
                else:
                    item["status"] = "failed"
                    print(f"Download failed: {item['link']['url']}")
    
    def _download_file(self, link: Dict[str, str], destination: Path) -> bool:
        """Download a file from a link and save it to the destination."""
        host = link["host"].lower()
        url = link["url"]
        
        print(f"Processing download from {host}: {url}")
        
        try:
            if "google" in host or "drive" in host:
                return self._download_from_google_drive(url, destination)
            elif "mediafire.com" in url.lower() or ("mediafire" in host and not "4shared" in host):
                # Stricter check for MediaFire URLs - must have mediafire.com in the URL
                # and not be a 4shared link mistakenly labeled as MediaFire
                return self._download_from_mediafire(url, destination)
            elif "mega" in host:
                return self._download_from_mega(url, destination)
            elif "dropbox" in host:
                return self._download_from_dropbox(url, destination)
            elif "mp4upload" in host:
                return self._download_from_mp4upload(url, destination)
            elif "solidfiles" in host:
                return self._download_from_solidfiles(url, destination)
            elif "4shared" in host:
                return self._download_from_4shared(url, destination)
            else:
                return self._download_generic(url, destination)
        except Exception as e:
            print(f"Error downloading from {host}: {e}")
            return False
    
    def _download_with_progress(self, url: str, destination: Path, headers=None) -> bool:
        """Download a file with progress reporting."""
        try:
            response = self.requests.get(url, stream=True, headers=headers)
            response.raise_for_status()
            
            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            
            # Download with progress
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Print progress
                        if total_size > 0:
                            percent = int(bytes_downloaded * 100 / total_size)
                            progress_bar = '#' * (percent // 5)
                            spaces = ' ' * (20 - (percent // 5))
                            print(f"\rProgress: [{progress_bar}{spaces}] {percent}% ({bytes_downloaded}/{total_size} bytes)", end='')
                
            print()  # New line after progress bar
            return True
        except Exception as e:
            print(f"\nError during download: {e}")
            return False
    
    def _download_from_google_drive(self, url: str, destination: Path) -> bool:
        """Download a file from Google Drive."""
        try:
            print(f"Processing Google Drive URL: {url}")
            
            # Extract file ID from Google Drive URL
            import re
            file_id = None
            patterns = [
                r'https?://drive\.google\.com/file/d/([^/]+)',
                r'https?://drive\.google\.com/open\?id=([^&]+)',
                r'https?://drive\.google\.com/uc\?id=([^&]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    file_id = match.group(1)
                    break
            
            if not file_id:
                print("Could not extract Google Drive file ID")
                return False
            
            # Use the direct download URL
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download"
            print(f"Direct download URL: {download_url}")
            
            # Start the initial request to get cookies and confirm token
            session = self.requests.Session()
            response = session.get(download_url, stream=True)
            
            # Check if we need to handle the confirmation page
            for k, v in response.cookies.items():
                if k.startswith('download_warning'):
                    # We need to confirm the download
                    token = v
                    download_url = f"{download_url}&confirm={token}"
                    print(f"Download confirmation required. New URL: {download_url}")
                    break
            
            # Download the file
            return self._download_with_progress(download_url, destination, headers=session.headers)
            
        except Exception as e:
            print(f"Error downloading from Google Drive: {e}")
            return False
    
    def _download_from_mediafire(self, url: str, destination: Path) -> bool:
        """Download a file from Mediafire using the dedicated mediafire.py module."""
        try:
            # Import necessary modules upfront
            import os
            import re
            import shutil
            import traceback
            
            print(f"{bcolors.HEADER}Processing Mediafire URL: {url}{bcolors.ENDC}")
            
            # First check if it's truly a MediaFire URL
            if "mediafire.com" not in url.lower():
                print(f"{bcolors.FAIL}Not a valid MediaFire URL: {url}{bcolors.ENDC}")
                return False

            # Remove the @ symbol if present at the beginning of the URL
            if url.startswith('@'):
                url = url[1:]
            
            # Extract the file key from the URL using multiple patterns
            file_key = None
            
            # Pattern 1: Standard MediaFire file URL
            folder_or_file = re.findall(
                r"mediafire\.com/(folder|file|file_premium)\/([a-zA-Z0-9]+)", url
            )
            
            if folder_or_file:
                # Get the file type and key
                t, file_key = folder_or_file[0]
                print(f"{bcolors.OKGREEN}Found file key: {file_key}{bcolors.ENDC}")
            else:
                # Pattern 2: Alternative MediaFire URL format
                alt_pattern = re.findall(r"mediafire\.com/\?([a-zA-Z0-9]+)", url)
                if alt_pattern:
                    file_key = alt_pattern[0]
                    print(f"{bcolors.OKGREEN}Found file key using alternative pattern: {file_key}{bcolors.ENDC}")
                else:
                    # Pattern 3: Extract from download button URL
                    try:
                        print(f"{bcolors.WARNING}Trying to extract key from webpage...{bcolors.ENDC}")
                        response = self.requests.get(url)
                        download_link_match = re.search(r'href="(https://download[^"]+)"', response.text)
                        if download_link_match:
                            # Found direct link, just use it instead of mediafire.py
                            direct_url = download_link_match.group(1)
                            print(f"{bcolors.OKGREEN}Found direct download URL: {direct_url}{bcolors.ENDC}")
                            return self._download_with_progress(direct_url, destination)
                    except Exception as web_e:
                        print(f"{bcolors.WARNING}Error trying to extract key from webpage: {web_e}{bcolors.ENDC}")
            
            if not file_key:
                print(f"{bcolors.FAIL}Could not extract MediaFire file key from URL: {url}{bcolors.ENDC}")
                return False
            
            # Close the browser if it's open to free up resources before download
            try:
                if hasattr(self, 'site_interactor') and self.site_interactor:
                    print(f"{bcolors.OKCYAN}Closing browser to improve download speed...{bcolors.ENDC}")
                    self.site_interactor.close_browser()
            except Exception as browser_e:
                print(f"{bcolors.WARNING}Error closing browser: {browser_e}{bcolors.ENDC}")
            
            # Import functions from mediafire.py
            try:
                from mediafire import get_file
            except ImportError:
                print(f"{bcolors.FAIL}mediafire.py module not found or could not be imported{bcolors.ENDC}")
                print(f"{bcolors.WARNING}Attempting to download directly...{bcolors.ENDC}")
                return self._download_generic(url, destination)
            
            # Determine output path
            output_dir = str(destination.parent)
            
            # Use mediafire.py's get_file function to download
            try:
                print(f"{bcolors.OKGREEN}Using mediafire.py module to download file with key: {file_key}{bcolors.ENDC}")
                
                # Pass the correct output directory
                os.makedirs(output_dir, exist_ok=True)
                
                # Call get_file with explicit parameters
                downloaded_path = get_file(file_key, output_dir)
                
                # Check the result
                if not downloaded_path:
                    print(f"{bcolors.FAIL}get_file returned None or empty string{bcolors.ENDC}")
                    print(f"{bcolors.WARNING}Attempting direct download as fallback...{bcolors.ENDC}")
                    return self._download_generic(url, destination)
                
                # Rename the file if necessary
                if destination.name and downloaded_path != str(destination):
                    import os
                    if os.path.exists(downloaded_path):
                        print(f"Renaming {downloaded_path} to {destination}")
                        shutil.move(downloaded_path, destination)
                        return True
                    else:
                        print(f"{bcolors.FAIL}Downloaded file not found at {downloaded_path}{bcolors.ENDC}")
                        return False
                
                return True
            except Exception as e:
                print(f"{bcolors.FAIL}Error using mediafire.py to download: {e}{bcolors.ENDC}")
                import traceback
                traceback.print_exc()
                
                # Try direct download as fallback
                print(f"{bcolors.WARNING}Attempting direct download as fallback...{bcolors.ENDC}")
                return self._download_generic(url, destination)
                
        except Exception as e:
            print(f"{bcolors.FAIL}Error with MediaFire download: {e}{bcolors.ENDC}")
            import traceback
            traceback.print_exc()
            return False
    
    def _download_from_mega(self, url: str, destination: Path) -> bool:
        """Download a file from Mega.nz."""
        try:
            print(f"Processing Mega URL: {url}")
            print("Mega.nz downloads require installing the mega.py package.")
            
            try:
                from mega import Mega
            except ImportError:
                print("Installing mega.py module...")
                os.system("pip install mega.py")
                from mega import Mega
            
            mega = Mega()
            # Anonymous login
            m = mega.login()
            
            # Download file
            print("Starting Mega download (this may take some time)...")
            file_path = m.download_url(url, str(destination.parent))
            
            # Rename file if needed
            if Path(file_path) != destination:
                Path(file_path).rename(destination)
            
            print(f"Mega download completed: {destination}")
            return True
            
        except Exception as e:
            print(f"Error downloading from Mega: {e}")
            return False
    
    def _download_from_dropbox(self, url: str, destination: Path) -> bool:
        """Download a file from Dropbox."""
        try:
            print(f"Processing Dropbox URL: {url}")
            
            # Convert sharing URL to direct download URL
            direct_url = url.replace("www.dropbox.com", "dl.dropboxusercontent.com")
            direct_url = direct_url.replace("?dl=0", "?dl=1")
            
            print(f"Direct download URL: {direct_url}")
            
            # Download the file
            return self._download_with_progress(direct_url, destination)
            
        except Exception as e:
            print(f"Error downloading from Dropbox: {e}")
            return False
    
    def _download_from_mp4upload(self, url: str, destination: Path) -> bool:
        """Download a file from MP4Upload."""
        try:
            print(f"Processing MP4Upload URL: {url}")
            print("MP4Upload requires browser automation for download.")
            
            # Import playwright here to keep it isolated
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                print("Playwright required for MP4Upload downloads.")
                return False
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)  # Needs user interaction
                page = browser.new_page()
                
                try:
                    # Navigate to the page
                    page.goto(url)
                    
                    # Wait for the player to load
                    page.wait_for_selector("div#player")
                    
                    # Try to find the video source
                    video_src = page.evaluate('''() => {
                        const video = document.querySelector('video');
                        return video ? video.src : null;
                    }''')
                    
                    if video_src:
                        print(f"Found video source: {video_src}")
                        browser.close()
                        return self._download_with_progress(video_src, destination)
                    else:
                        print("Could not find direct video source. Manual download required.")
                        print("Please visit the URL and download manually.")
                        browser.close()
                        return False
                    
                except Exception as e:
                    print(f"Error with MP4Upload browser automation: {e}")
                    browser.close()
                    return False
            
        except Exception as e:
            print(f"Error downloading from MP4Upload: {e}")
            return False
    
    def _download_from_solidfiles(self, url: str, destination: Path) -> bool:
        """Download a file from Solidfiles."""
        try:
            print(f"Processing Solidfiles URL: {url}")
            
            # Get the page content
            response = self.requests.get(url)
            response.raise_for_status()
            
            # Extract the direct download link
            import re
            pattern = r'downloadUrl":"([^"]+)"'
            match = re.search(pattern, response.text)
            
            if not match:
                print("Could not find direct download link")
                return False
            
            direct_url = match.group(1).replace('\\', '')
            print(f"Direct download URL: {direct_url}")
            
            # Download the file
            return self._download_with_progress(direct_url, destination)
            
        except Exception as e:
            print(f"Error downloading from Solidfiles: {e}")
            return False
    
    def _download_generic(self, url: str, destination: Path) -> bool:
        """Download a file from a generic URL."""
        try:
            print(f"Processing generic URL: {url}")
            
            # Special case for MediaFire URLs - try to extract the direct download link
            if "mediafire.com" in url.lower():
                try:
                    import re
                    print(f"{bcolors.OKCYAN}Detected MediaFire URL, trying to extract direct download link...{bcolors.ENDC}")
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                    }
                    response = self.requests.get(url, headers=headers)
                    
                    # Look for download link in page content
                    download_link_match = re.search(r'href="(https://download[^"]+)"', response.text)
                    if download_link_match:
                        direct_url = download_link_match.group(1)
                        print(f"{bcolors.OKGREEN}Found direct MediaFire download URL: {direct_url}{bcolors.ENDC}")
                        return self._download_with_progress(direct_url, destination, headers=headers)
                    else:
                        print(f"{bcolors.FAIL}Could not find direct download link in MediaFire page{bcolors.ENDC}")
                except Exception as e:
                    print(f"{bcolors.FAIL}Error extracting direct download link: {e}{bcolors.ENDC}")
            
            # Try direct download first
            return self._download_with_progress(url, destination)
            
        except Exception as e:
            print(f"Error with generic download: {e}")
            return False
    
    def _download_from_4shared(self, url: str, destination: Path) -> bool:
        """Download a file from 4shared."""
        try:
            print(f"{bcolors.HEADER}Processing 4shared URL: {url}{bcolors.ENDC}")
            
            # Verify it's a 4shared URL
            if "4shared.com" not in url.lower():
                print(f"{bcolors.FAIL}Not a valid 4shared URL: {url}{bcolors.ENDC}")
                return False
            
            # Get the page content
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.4shared.com/",
                "Connection": "keep-alive"
            }
            
            # First request to get cookies
            session = self.requests.Session()
            try:
                response = session.get(url, headers=headers)
                response.raise_for_status()
            except Exception as e:
                print(f"{bcolors.FAIL}Error accessing 4shared page: {e}{bcolors.ENDC}")
                return False
            
            # Extract the direct download link
            # 4shared has multiple ways to get the download link
            
            # Method 1: Try to find the download button directly
            direct_link = None
            download_patterns = [
                r'id="baseDownloadButton".*?href="([^"]+)"',
                r'id="directDownloadLink".*?href="([^"]+)"',
                r'<a.*?class="dbtn.*?href="([^"]+)"',
                r'href="(https?://[^"]+?/get/[^"]+?)"',
                r'<a.*?class="linkShowD".*?href="([^"]+)"'
            ]
            
            for pattern in download_patterns:
                match = re.search(pattern, response.text, re.DOTALL)
                if match:
                    direct_link = match.group(1)
                    print(f"Found direct download link: {direct_link}")
                    break
            
            # Method 2: If we couldn't find a direct link, check for the free download option
            if not direct_link:
                # Check if we need to switch to the free download page
                free_download_link = None
                free_download_patterns = [
                    r'href="([^"]+download/free/[^"]+)"',
                    r'<a.*?class="freeDownloadButton".*?href="([^"]+)"',
                    r'id="freeDownloadButton".*?href="([^"]+)"'
                ]
                
                for pattern in free_download_patterns:
                    match = re.search(pattern, response.text, re.DOTALL)
                    if match:
                        free_download_link = match.group(1)
                        print(f"Found free download link: {free_download_link}")
                        break
                
                if free_download_link:
                    # Navigate to the free download page
                    try:
                        print("Navigating to free download page...")
                        response = session.get(free_download_link, headers=headers)
                        response.raise_for_status()
                        
                        # Check for a countdown
                        countdown_match = re.search(r'var c = (\d+);', response.text)
                        if countdown_match:
                            countdown = int(countdown_match.group(1))
                            print(f"4shared countdown: {countdown} seconds")
                            # Sleep for the countdown + 1 second buffer
                            time.sleep(countdown + 1)
                        
                        # Now try to find the download link
                        for pattern in download_patterns:
                            match = re.search(pattern, response.text, re.DOTALL)
                            if match:
                                direct_link = match.group(1)
                                print(f"Found direct download link after countdown: {direct_link}")
                                break
                    except Exception as e:
                        print(f"{bcolors.FAIL}Error during free download process: {e}{bcolors.ENDC}")
            
            # If we still can't find a direct link, try extracting from JavaScript
            if not direct_link:
                print("Trying to extract download link from JavaScript...")
                js_patterns = [
                    r'var dlLink = "([^"]+)";',
                    r'var url = "([^"]+)";'
                ]
                
                for pattern in js_patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        direct_link = match.group(1)
                        print(f"Found direct download link in JavaScript: {direct_link}")
                        break
            
            if not direct_link:
                print(f"{bcolors.FAIL}Could not find download link on 4shared page{bcolors.ENDC}")
                return False
            
            # Make sure the URL is absolute
            if not direct_link.startswith('http'):
                if direct_link.startswith('/'):
                    direct_link = f"https://www.4shared.com{direct_link}"
                else:
                    direct_link = f"https://www.4shared.com/{direct_link}"
            
            print(f"Proceeding with download from: {direct_link}")
            
            # Download the file
            try:
                response = session.get(direct_link, stream=True, headers=headers)
                response.raise_for_status()
                
                # Get the filename from Content-Disposition header if available
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                    if filename_match:
                        filename = filename_match.group(1)
                        # If destination is a directory, append the filename
                        if destination.is_dir():
                            destination = destination / filename
                
                # Download with progress bar
                total_size = int(response.headers.get('content-length', 0))
                bytes_downloaded = 0
                
                # Create a progress bar
                print(f"{bcolors.OKGREEN}Downloading {destination.name}...{bcolors.ENDC}")
                progress_length = 50
                
                with open(destination, 'wb') as f:
                    start_time = time.time()
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            
                            # Update progress bar
                            if total_size > 0:
                                percent = 100 * bytes_downloaded / total_size
                                bar = '█' * int(percent / 2)
                                spaces = ' ' * (progress_length - len(bar))
                                
                                # Calculate speed
                                elapsed_time = time.time() - start_time
                                if elapsed_time > 0:
                                    speed = bytes_downloaded / elapsed_time
                                    speed_str = f"{self._format_size(speed)}/s"
                                else:
                                    speed_str = "? KB/s"
                                
                                sys.stdout.write(f"\r{bcolors.OKBLUE}Progress: |{bar}{spaces}| {percent:.1f}% | {speed_str}{bcolors.ENDC}")
                                sys.stdout.flush()
                
                print(f"\n{bcolors.OKGREEN}Download complete: {destination}{bcolors.ENDC}")
                return True
            except Exception as e:
                print(f"{bcolors.FAIL}Error downloading file: {e}{bcolors.ENDC}")
                return False
                
        except Exception as e:
            print(f"{bcolors.FAIL}Error with 4shared download: {e}{bcolors.ENDC}")
            import traceback
            traceback.print_exc()
            return False
    
    def download_anime_episode(self, download_links: List[Dict[str, str]], anime_title: str, episode_number: str, custom_path: str = None) -> bool:
        """
        Download an anime episode prioritizing Mediafire, then Google Drive links.
        
        Args:
            download_links: List of download links with host information
            anime_title: Title of the anime
            episode_number: Episode number
            custom_path: Custom download path (optional)
            
        Returns:
            bool: True if download was successful, False otherwise
        """
        if not download_links:
            print(f"{bcolors.FAIL}No download links available for {anime_title} episode {episode_number}{bcolors.ENDC}")
            return False
        
        # Prioritize links: Mediafire first, then Google Drive, then others
        # More strict filtering for mediafire links - check both host and URL, and verify it's actually mediafire.com
        mediafire_links = [link for link in download_links if 
                          ("mediafire" in link["host"].lower() and "mediafire.com" in link["url"].lower()) or 
                          (link["url"].lower().startswith("https://www.mediafire.com/") or 
                           link["url"].lower().startswith("https://mediafire.com/"))]
        
        # Debug output
        print(f"\nFound {len(mediafire_links)} genuine MediaFire links for {anime_title} episode {episode_number}")
        if mediafire_links:
            for i, link in enumerate(mediafire_links):
                print(f"MediaFire link {i+1}: {link['url'][:70]}..." if len(link['url']) > 70 else link['url'])
        
        google_links = [link for link in download_links if 
                        ("google" in link["host"].lower() or "drive" in link["host"].lower()) and
                        ("drive.google.com" in link["url"].lower() or "drive.usercontent.google.com" in link["url"].lower())]
        
        other_links = [link for link in download_links if 
                      link not in mediafire_links and 
                      link not in google_links]
        
        prioritized_links = mediafire_links + google_links + other_links
        
        if not prioritized_links:
            print(f"{bcolors.FAIL}No valid download links after prioritization{bcolors.ENDC}")
            return False
        
        # Determine download location
        if custom_path:
            download_path = Path(custom_path)
        else:
            # Ask user where to save
            print(f"\n{bcolors.HEADER}Where would you like to save {anime_title} - Episode {episode_number}?{bcolors.ENDC}")
            print(f"1. Default location ({DOWNLOAD_DIR})")
            print("2. Custom location")
            choice = input(f"{bcolors.OKCYAN}Enter your choice (1/2, default is 1): {bcolors.ENDC}")
            
            if choice == "2":
                custom_location = input(f"{bcolors.OKCYAN}Enter the full path to save the file (e.g., D:\\Files\\op): {bcolors.ENDC}")
                download_path = Path(custom_location)
            else:
                download_path = DOWNLOAD_DIR
        
        # Create directory if it doesn't exist
        if not download_path.exists():
            try:
                download_path.mkdir(parents=True, exist_ok=True)
                print(f"{bcolors.OKGREEN}Created directory: {download_path}{bcolors.ENDC}")
            except Exception as e:
                print(f"{bcolors.FAIL}Error creating directory {download_path}: {e}{bcolors.ENDC}")
                return False
        
        # Create anime-specific subfolder
        anime_folder = download_path / anime_title.replace(':', ' -').replace('/', '-')
        anime_folder.mkdir(exist_ok=True, parents=True)
        
        # Filename for download
        filename = f"{anime_title}_Episode_{episode_number}.mp4"
        destination = anime_folder / filename
        
        # Try downloading from prioritized links
        for link in prioritized_links:
            print(f"\n{bcolors.HEADER}Trying download from {link['host']}{bcolors.ENDC}")
            print(f"URL: {link['url'][:70]}..." if len(link['url']) > 70 else link['url'])
            
            # For Mediafire links, show special handling message
            if "mediafire.com" in link["url"].lower():
                print(f"{bcolors.OKGREEN}Using optimized Mediafire downloader{bcolors.ENDC}")
            
            if self._download_file(link, destination):
                print(f"\n{bcolors.OKGREEN}Successfully downloaded {anime_title} episode {episode_number} to {destination}{bcolors.ENDC}")
                return True
            
            print(f"{bcolors.WARNING}Failed to download from {link['host']}. Trying next link...{bcolors.ENDC}")
        
        print(f"{bcolors.FAIL}All download attempts failed for {anime_title} episode {episode_number}{bcolors.ENDC}")
        return False


class CLI:
    """Command-line interface for the anime downloader."""
    
    def __init__(self):
        self.database = AnimeDatabase()
        self.site_interactor = SiteInteractor(self.database)
        self.pattern_recognition = PatternRecognition(self.database)
        self.download_manager = DownloadManager()
        # Default site for anime downloads
        self.default_site = "@https://witanime.cyou"
        # ASCII logo path
        self.logo_path = "ascciilogoart.txt"
    
    def start(self):
        """Start the CLI."""
        # Display ASCII logo
        self._display_logo()
        
        parser = argparse.ArgumentParser(description="Anime Downloader CLI")
        parser.add_argument("--search", "-s", help="Search for an anime")
        parser.add_argument("--download", "-d", help="Download an anime")
        parser.add_argument("--list", "-l", action="store_true", help="List saved anime")
        parser.add_argument("--site", help="Specify the site to use")
        parser.add_argument("--episode", "-e", help="Specify episode number to download")
        parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
        
        args = parser.parse_args()
        
        if args.search:
            self.search_anime(args.search, args.site, not args.headless)
        elif args.download and args.episode:
            self.download_specific_anime(args.download, args.episode, args.site)
        elif args.download:
            self.download_anime(args.download)
        elif args.list:
            self.list_saved_anime()
        else:
            self.interactive_mode()
    
    def _display_logo(self):
        """Display the ASCII art logo."""
        try:
            if os.path.exists(self.logo_path):
                with open(self.logo_path, 'r', encoding='utf-8') as f:
                    logo_lines = f.readlines()
                
                # Get terminal width for centering
                try:
                    terminal_width = os.get_terminal_size().columns
                except:
                    terminal_width = 80  # Default if can't get terminal size
                
                # Pick a random color for the logo with enhanced colors
                colors = ['red', 'green', 'yellow', 'blue', 'magenta', 'cyan']
                logo_color = random.choice(colors)
                
                print("\n")  # Add some space before the logo
                
                # Display logo with proper centering
                max_line_length = max(len(line.rstrip()) for line in logo_lines)
                for line in logo_lines:
                    line_content = line.rstrip()
                    padding = (terminal_width - max_line_length) // 2
                    if padding < 0:
                        padding = 0
                    print(" " * padding + self._colorize(line_content, logo_color))
                
                # Calculate center for title text
                title = "✨ Anime Downloader ✨"
                title_padding = (terminal_width - len(title)) // 2
                if title_padding < 0:
                    title_padding = 0
                
                print("\n" + " " * title_padding + self._colorize(title, "bold"))
                
                # Center the separator line
                separator = "=" * min(70, terminal_width - 10)
                sep_padding = (terminal_width - len(separator)) // 2
                if sep_padding < 0:
                    sep_padding = 0
                
                print(" " * sep_padding + self._colorize(separator, "yellow"))
                
                # Center the version info
                version_info = f"Version: 1.0.0 | Default Site: {self._colorize(self.default_site, 'green')}"
                version_padding = (terminal_width - len(version_info) + len(self._colorize('', 'green'))) // 2
                if version_padding < 0:
                    version_padding = 0
                print(" " * version_padding + version_info)
                
                print(" " * sep_padding + self._colorize(separator, "yellow") + "\n")
        except Exception as e:
            print(f"Error displaying logo: {e}")
            import traceback
            traceback.print_exc()
    
    def _colorize(self, text, color):
        """Colorize text for terminal output."""
        colors = {
            'reset': '\033[0m',
            'black': '\033[30m',
            'red': '\033[31m',
            'green': '\033[32m',
            'yellow': '\033[33m',
            'blue': '\033[34m',
            'magenta': '\033[35m',
            'cyan': '\033[36m',
            'white': '\033[37m',
            'bold': '\033[1m',
            'underline': '\033[4m'
        }
        
        return f"{colors.get(color, '')}{text}{colors['reset']}"
    
    def search_anime(self, query: str, site: Optional[str] = None, show_browser: bool = False):
        """Search for an anime."""
        # Default site if none specified
        if not site:
            site = self.default_site
        
        try:
            # Check if we already have this anime in the database
            cached_anime = self.database.find_anime_by_title(query)
            if cached_anime:
                cached_data = self.database.get_anime(cached_anime)
                if cached_data and "episodes" in cached_data and cached_data["episodes"]:
                    print(f"\n{self._colorize('Found in cache:', 'green')} {self._colorize(cached_anime, 'cyan')}")
                    
                    use_cache = input(f"Use cached data? ({self._colorize('y/n', 'yellow')}): ").lower()
                    if use_cache == 'y' or use_cache == "":
                        print(f"\nSelected: {self._colorize(cached_anime, 'green')}")
                        
                        # Display episodes from cache
                        episodes = cached_data["episodes"]
                        self._display_episodes(episodes)
                        
                        # Get user selection for episode
                        ep_selection = input(f'\nEnter episode number(s) to download ({self._colorize("e.g., 1, 3-5, or all", "yellow")}): ')
                        
                        if ep_selection.lower() == 'all':
                            selected_episodes = episodes
                        else:
                            selected_episodes = self._parse_episode_selection(ep_selection, episodes)
                        
                        if not selected_episodes:
                            print(f"{self._colorize('No valid episodes selected.', 'red')}")
                            return
                        
                        # Download selected episodes
                        self._download_episodes(cached_anime, selected_episodes)
                        return
            
            print(f"\nSearching for '{self._colorize(query, 'cyan')}' on {self._colorize(site, 'green')}...")
            
            try:
                self.site_interactor.start_browser(headless=not show_browser)
                
                # Give the site a moment to load fully
                time.sleep(2)
                
                results = self.site_interactor.search_anime(site, query)
            except Exception as e:
                print(f"{self._colorize(f'Error during search: {e}', 'red')}")
                print("Browser may have crashed. Please try again.")
                return
            
            if not results:
                print(f"\n{self._colorize('No results found. Try another search query.', 'red')}")
                return
            
            # Display results in a nicely formatted table
            print("\nSearch Results:")
            print(self._colorize("=" * 60, "blue"))
            print(f"{self._colorize('#', 'yellow'):<4}{self._colorize('Title', 'yellow'):<50}{self._colorize('Match', 'yellow'):<6}")
            print(self._colorize("-" * 60, "blue"))
            
            # Sort results by how closely they match the query (exact match first)
            results.sort(key=lambda x: self._calculate_match_score(x['title'], query), reverse=True)
            
            for i, result in enumerate(results, 1):
                # Calculate match percentage
                match_score = self._calculate_match_score(result['title'], query)
                match_display = f"{int(match_score * 100)}%"
                
                # Color code match percentages
                if match_score >= 0.9:
                    match_color = "green"
                elif match_score >= 0.7:
                    match_color = "cyan"
                else:
                    match_color = "yellow"
                
                # Truncate title if too long
                title = result['title']
                if len(title) > 45:
                    title = title[:42] + "..."
                
                print(f"{self._colorize(str(i), 'cyan'):<4}{title:<50}{self._colorize(match_display, match_color):<6}")
            
            print(self._colorize("=" * 60, "blue"))
            
            # Get user selection
            try:
                selection = input(f"\nEnter the number of your selection ({self._colorize('0 to cancel', 'yellow')}): ")
                if selection.strip() == "":
                    print(f"{self._colorize('Selection cancelled.', 'red')}")
                    return
                    
                selection = int(selection)
                if selection == 0:
                    print(f"{self._colorize('Search cancelled.', 'red')}")
                    return
                
                if selection < 1 or selection > len(results):
                    print(f"{self._colorize(f'Invalid selection. Please choose between 1 and {len(results)}.', 'red')}")
                    return
                
                selected_anime = results[selection - 1]
                print(f"\nSelected: {self._colorize(selected_anime['title'], 'green')}")
                
                # Get episodes list
                print(f"\n{self._colorize('Fetching episodes list...', 'magenta')}")
                episodes = self.site_interactor.extract_episodes(selected_anime['link'])
                
                if not episodes:
                    print(f"{self._colorize('No episodes found for this anime.', 'red')}")
                    return
                
                # Store the anime in the database with its episodes
                anime_metadata = {
                    "title": selected_anime['title'],
                    "link": selected_anime['link'],
                    "site": site,
                    "episodes": episodes,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                print(f"\n{self._colorize('Storing anime in cache:', 'green')} {self._colorize(selected_anime['title'], 'cyan')}")
                print(f"Episodes count: {len(episodes)}")
                self.database.add_anime(selected_anime['title'], anime_metadata)
                
                # Explicitly save database to ensure data is written
                self.database.save()
                
                # Display episodes in groups
                self._display_episodes(episodes)
                
                # Get user selection for episode
                ep_selection = input(f'\nEnter episode number(s) to download ({self._colorize("e.g., 1, 3-5, or all", "yellow")}): ')
                
                if ep_selection.lower() == 'all':
                    selected_episodes = episodes
                else:
                    selected_episodes = self._parse_episode_selection(ep_selection, episodes)
                
                if not selected_episodes:
                    print(f"{self._colorize('No valid episodes selected.', 'red')}")
                    return
                
                # Download selected episodes
                self._download_episodes(selected_anime['title'], selected_episodes)
            except ValueError:
                print(f"{self._colorize('Invalid input. Please enter a number.', 'red')}")
                return
            
        except Exception as e:
            print(f"\n{self._colorize(f'Error during search: {e}', 'red')}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                self.site_interactor.close_browser()
            except Exception as e:
                print(f"Warning: Error closing browser: {e}")
    
    def _calculate_match_score(self, title: str, query: str) -> float:
        """
        Calculate how closely a title matches the search query.
        Returns a score between 0 and 1, with 1 being an exact match.
        """
        title_lower = title.lower()
        query_lower = query.lower()
        
        # Exact match
        if title_lower == query_lower:
            return 1.0
            
        # Title contains exact query
        if query_lower in title_lower:
            return 0.9
            
        # Check if all words in query appear in title
        query_words = query_lower.split()
        title_words = title_lower.split()
        
        # If all query words are in the title (in any order)
        if all(word in title_lower for word in query_words):
            return 0.8
            
        # Calculate word match percentage
        matching_words = sum(1 for word in query_words if word in title_lower)
        if query_words:
            return 0.5 + (0.3 * matching_words / len(query_words))
            
        return 0.2  # Low relevance fallback
    
    def _display_episodes(self, episodes: List[Dict[str, Any]]):
        """Display episodes in a readable format."""
        # Sort episodes by number if possible
        try:
            sorted_episodes = sorted(episodes, key=lambda x: int(x['number']) if x['number'].isdigit() else float('inf'))
        except:
            sorted_episodes = episodes
        
        # Count total episodes
        total_episodes = len(sorted_episodes)
        print(f"\nFound {total_episodes} episodes")
        
        # Display in a nice table format
        print("\nAvailable Episodes:")
        print("=" * 80)
        
        # Group episodes in batches of 10 for display
        batch_size = 10
        num_batches = (total_episodes + batch_size - 1) // batch_size
        
        for batch in range(num_batches):
            start_idx = batch * batch_size
            end_idx = min(start_idx + batch_size, total_episodes)
            batch_episodes = sorted_episodes[start_idx:end_idx]
            
            # Format the episode numbers with color and padding
            line = ""
            for ep in batch_episodes:
                ep_num = ep['number'].rjust(4)
                line += f"{self._colorize(ep_num, 'cyan')} | "
            
            print(line)
        
        print("=" * 80)
        print("Enter episode numbers to download. Examples:")
        print(f"{self._colorize('  * Single episode:', 'yellow')} 5")
        print(f"{self._colorize('  * Multiple episodes:', 'yellow')} 1,3,5")
        print(f"{self._colorize('  * Range of episodes:', 'yellow')} 1-10")
        print(f"{self._colorize('  * Combination:', 'yellow')} 1,3,5-10,15")
        print(f"{self._colorize('  * All episodes:', 'yellow')} all")
    
    def _parse_episode_selection(self, selection: str, episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse user input for episode selection."""
        selected = []
        
        # Create a dictionary for quick lookup by episode number
        ep_dict = {ep['number']: ep for ep in episodes if ep['number'].isdigit()}
        
        # Process each part of the selection (comma-separated)
        parts = selection.split(',')
        for part in parts:
            part = part.strip()
            
            # Check if it's a range (e.g., "1-5")
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    for num in range(start, end + 1):
                        if str(num) in ep_dict:
                            selected.append(ep_dict[str(num)])
                except ValueError:
                    print(f"Invalid range format: {part}")
                    continue
            
            # Check if it's a single episode number
            elif part.isdigit():
                if part in ep_dict:
                    selected.append(ep_dict[part])
                else:
                    print(f"Episode {part} not found.")
            
            else:
                print(f"Invalid episode format: {part}")
        
        return selected
    
    def _download_episodes(self, anime_title: str, episodes: List[Dict[str, Any]]):
        """Download the selected episodes."""
        print(f"\nPreparing to download {len(episodes)} episode(s) of {anime_title}")
        
        # Make sure we have a browser for initial extraction
        browser_started = False
        if not hasattr(self.site_interactor, 'browser') or not self.site_interactor.browser:
            self.site_interactor.start_browser()
            browser_started = True
        
        for i, episode in enumerate(episodes, 1):
            print(f"\n[{i}/{len(episodes)}] Processing episode {episode['number']}...")
            
            # Extract download links
            try:
                download_links = self.site_interactor.extract_download_links(episode['link'])
            except Exception as e:
                print(f"Error extracting download links: {e}")
                print(f"Skipping episode {episode['number']}")
                continue
            
            if not download_links:
                print(f"No download links found for episode {episode['number']}.")
                continue
            
            # Categorize all available links for better decision making
            mediafire_links = []
            google_drive_links = []
            fourshared_links = []
            mega_links = []
            other_links = []
            
            # Categorize links by source
            for link in download_links:
                url = link["url"].lower()
                host = link["host"].lower()
                
                # Debug output for link classification
                print(f"Classifying link: URL={url[:50]}... Host={host}")
                
                if "mediafire.com" in url and not "4shared" in url:
                    print(f"Identified as MediaFire link")
                    mediafire_links.append(link)
                elif any(x in url for x in ["drive.google.com", "docs.google.com"]):
                    google_drive_links.append(link)
                elif "4shared.com" in url:
                    fourshared_links.append(link)
                elif "mega.nz" in url:
                    mega_links.append(link)
                else:
                    other_links.append(link)
            
            # Print summary of available links
            print(f"\n{bcolors.HEADER}Available download sources for episode {episode['number']}:{bcolors.ENDC}")
            print(f"MediaFire: {len(mediafire_links)} links")
            print(f"Google Drive: {len(google_drive_links)} links")
            print(f"4shared: {len(fourshared_links)} links")
            print(f"MEGA: {len(mega_links)} links")
            print(f"Other: {len(other_links)} links")
            
            # Ask user for download preference
            print(f"\n{bcolors.HEADER}Download sources preference:{bcolors.ENDC}")
            print("1. MediaFire (Default)")
            print("2. Google Drive")
            print("3. 4shared")
            print("4. MEGA")
            print("5. Try all available sources")
            
            choice = input(f"{bcolors.OKCYAN}Enter your choice (1-5, default is 1): {bcolors.ENDC}")
            
            # Create prioritized list based on user preference
            prioritized_links = []
            
            if choice == "2":
                prioritized_links = google_drive_links + mediafire_links + fourshared_links + mega_links + other_links
            elif choice == "3":
                prioritized_links = fourshared_links + mediafire_links + google_drive_links + mega_links + other_links
            elif choice == "4":
                prioritized_links = mega_links + mediafire_links + google_drive_links + fourshared_links + other_links
            elif choice == "5":
                # Try all sources - already in the order we want
                prioritized_links = mediafire_links + google_drive_links + fourshared_links + mega_links + other_links
            else:
                # Default to MediaFire first
                prioritized_links = mediafire_links + google_drive_links + fourshared_links + mega_links + other_links
            
            if not prioritized_links:
                print(f"{bcolors.FAIL}No suitable download links available for episode {episode['number']}.{bcolors.ENDC}")
                continue
            
            # Ask for custom path
            custom_path = input(f"{bcolors.OKCYAN}Enter custom download path or press Enter for default: {bcolors.ENDC}")
            path_to_use = custom_path if custom_path.strip() else None
            
            # Close the browser before starting downloads to save resources
            if self.site_interactor.browser:
                print(f"{bcolors.OKCYAN}Closing browser to improve download speed...{bcolors.ENDC}")
                self.site_interactor.close_browser()
            
            # Try each link in the prioritized order
            success = False
            for link in prioritized_links:
                # Try to download using the download manager
                try:
                    if self.download_manager.download_anime_episode([link], anime_title, episode['number'], path_to_use):
                        success = True
                        break
                except Exception as e:
                    print(f"{bcolors.FAIL}Error during download attempt: {e}{bcolors.ENDC}")
                    continue
            
            if not success:
                print(f"{bcolors.FAIL}All download attempts failed for {anime_title} episode {episode['number']}.{bcolors.ENDC}")
                print(f"{bcolors.WARNING}You may want to try again with a different source or check your internet connection.{bcolors.ENDC}")
            
            # Restart browser for next episode if needed
            if i < len(episodes) and not self.site_interactor.browser:
                self.site_interactor.start_browser()
                browser_started = True
    
    def _prioritize_servers(self, links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Sort download links by server priority."""
        # Updated prioritization: Mediafire first, then Google Drive, then others
        def get_priority(link):
            host_lower = link['host'].lower()
            if "mediafire" in host_lower:
                return 0  # Highest priority
            elif "google" in host_lower or "drive" in host_lower:
                return 1  # Second priority
            elif "mega" in host_lower:
                return 2
            elif "solidfiles" in host_lower:
                return 3
            elif "mp4upload" in host_lower:
                return 4
            elif "dropbox" in host_lower:
                return 5
            else:
                return 6  # Lowest priority
        
        # Sort links by priority
        return sorted(links, key=get_priority)
    
    def download_specific_anime(self, title: str, episode: str, site: Optional[str] = None):
        """Download a specific anime episode by title and episode number."""
        if not site:
            site = self.default_site
        
        try:
            # First check if we have this anime in cache
            cached_anime = self.database.find_anime_by_title(title)
            if cached_anime:
                cached_data = self.database.get_anime(cached_anime)
                if cached_data and "episodes" in cached_data and cached_data["episodes"]:
                    print(f"\n{self._colorize('Found in cache:', 'green')} {self._colorize(cached_anime, 'cyan')}")
                    
                    # Find the requested episode in cache
                    episodes = cached_data["episodes"]
                    target_episode = None
                    for ep in episodes:
                        if ep['number'] == episode:
                            target_episode = ep
                            break
                    
                    if target_episode:
                        print(f"\nDownloading episode {episode} of {cached_anime} from cache")
                        self._download_episodes(cached_anime, [target_episode])
                        return
                    else:
                        print(f"Episode {episode} not found in cache for {cached_anime}.")
                        print("Available episodes:")
                        self._display_episodes(episodes)
                        return
            
            print(f"\nSearching for '{title}' on {site}...")
            self.site_interactor.start_browser()
            
            results = self.site_interactor.search_anime(site, title)
            
            if not results:
                print("\nNo anime found with that title.")
                return
            
            # Find the best match
            best_match = None
            for result in results:
                if title.lower() in result['title'].lower():
                    best_match = result
                    break
            
            if not best_match:
                best_match = results[0]  # Take the first result if no good match
            
            print(f"\nSelected: {best_match['title']}")
            
            # Get episodes list
            print("\nFetching episodes list...")
            episodes = self.site_interactor.extract_episodes(best_match['link'])
            
            if not episodes:
                print("No episodes found for this anime.")
                return
            
            # Store the anime in the database with its episodes
            anime_metadata = {
                "title": best_match['title'],
                "link": best_match['link'],
                "site": site,
                "episodes": episodes,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.database.add_anime(best_match['title'], anime_metadata)
            
            # Find the requested episode
            target_episode = None
            for ep in episodes:
                if ep['number'] == episode:
                    target_episode = ep
                    break
            
            if not target_episode:
                print(f"Episode {episode} not found. Available episodes:")
                self._display_episodes(episodes)
                return
            
            # Download the episode
            self._download_episodes(best_match['title'], [target_episode])
            
        except Exception as e:
            print(f"\nError during download: {e}")
        finally:
            self.site_interactor.close_browser()
    
    def download_anime(self, title: str):
        """Download a saved anime."""
        # Try to find the anime in the database
        actual_title = self.database.find_anime_by_title(title)
        
        if not actual_title:
            print(self._colorize(f'Anime "{title}" not found in the database.', 'red'))
            print("Attempting to search online instead...")
            self.search_anime(title)
            return
        
        anime_data = self.database.get_anime(actual_title)
        if not anime_data:
            print(self._colorize(f'Data for "{actual_title}" not found.', 'red'))
            return
        
        print(f"\n{self._colorize('Found:', 'green')} {self._colorize(actual_title, 'cyan')}")
        
        if "episodes" in anime_data and anime_data["episodes"]:
            episodes = anime_data["episodes"]
            print(f"\nFound {len(episodes)} saved episodes.")
            
            # Display last update time if available
            if "last_updated" in anime_data:
                print(f"Last updated: {anime_data['last_updated']}")
            
            # Display episodes for selection
            self._display_episodes(episodes)
            
            # Get user selection for episode
            ep_selection = input(f'\nEnter episode number(s) to download ({self._colorize("e.g., 1, 3-5, or all", "yellow")}): ')
            
            if ep_selection.lower() == 'all':
                selected_episodes = episodes
            else:
                selected_episodes = self._parse_episode_selection(ep_selection, episodes)
            
            if not selected_episodes:
                print(f"{self._colorize('No valid episodes selected.', 'red')}")
                return
            
            # Download selected episodes
            self._download_episodes(actual_title, selected_episodes)
        else:
            print(f"{self._colorize('No episodes found in the database for this anime.', 'red')}")
    
    def list_saved_anime(self):
        """List all saved anime."""
        anime_list = self.database.data["anime"]
        
        if not anime_list:
            print(f"{self._colorize('No anime saved in the database.', 'red')}")
            return
        
        print("\nSaved Anime:")
        print(self._colorize("=" * 80, "blue"))
        print(f"{self._colorize('#', 'yellow'):<4}{self._colorize('Title', 'yellow'):<40}{self._colorize('Episodes', 'yellow'):<10}{self._colorize('Last Updated', 'yellow'):<26}")
        print(self._colorize("-" * 80, "blue"))
        
        for i, (title, data) in enumerate(sorted(anime_list.items()), 1):
            episodes_count = len(data.get("episodes", []))
            last_updated = data.get("last_updated", "Unknown")
            
            # Truncate title if too long
            display_title = title
            if len(display_title) > 37:
                display_title = display_title[:34] + "..."
            
            print(f"{self._colorize(str(i), 'cyan'):<4}{display_title:<40}{episodes_count:<10}{last_updated:<26}")
        
        print(self._colorize("=" * 80, "blue"))
        
        # Show alternative title lookup option
        print(f"\nYou can download anime by entering its title or number.")
        selection = input(f"\nEnter anime title or number to download (or {self._colorize('0 to cancel', 'yellow')}): ")
        
        if selection.strip() == "" or selection == "0":
            return
            
        try:
            # Check if selection is a number
            idx = int(selection)
            if 1 <= idx <= len(anime_list):
                # Get the title at this index
                title = list(sorted(anime_list.keys()))[idx-1]
                self.download_anime(title)
            else:
                error_msg = f'Invalid selection. Please choose between 1 and {len(anime_list)}.'
                print(self._colorize(error_msg, 'red'))
        except ValueError:
            # Selection is a title string
            self.download_anime(selection)
    
    def interactive_mode(self):
        """Start interactive mode."""
        print(f"\n{self._colorize('Welcome to Anime Downloader!', 'bold')}")
        print(self._colorize("----------------------------", "yellow"))
        
        while True:
            print("\nOptions:")
            print(f"{self._colorize('1.', 'cyan')} {self._colorize('Search for anime', 'white')}")
            print(f"{self._colorize('2.', 'cyan')} {self._colorize('List saved anime', 'white')}")
            print(f"{self._colorize('3.', 'cyan')} {self._colorize('Download from saved', 'white')}")
            print(f"{self._colorize('4.', 'cyan')} {self._colorize('Change default site', 'white')}")
            print(f"{self._colorize('5.', 'cyan')} {self._colorize('Exit', 'white')}")
            print(f"{self._colorize('Tip:', 'yellow')} You can also type an anime name directly to search")
            
            choice = input(f"\n{self._colorize('Enter your choice (1-5) or anime name:', 'yellow')} ")
            
            if choice == "1":
                query = input(f"Enter anime title to search: ")
                site = input(f"Enter site URL (or leave empty for default [{self._colorize(self.default_site, 'green')}]): ")
                show_browser = input("Show browser window? (y/n): ").lower() == 'y'
                self.search_anime(query, site if site else None, show_browser)
            elif choice == "2":
                self.list_saved_anime()
            elif choice == "3":
                title = input("Enter the title of the anime to download: ")
                self.download_anime(title)
            elif choice == "4":
                new_site = input("Enter new default site URL: ")
                if new_site:
                    self.default_site = new_site
                    print(f"Default site changed to: {self._colorize(self.default_site, 'green')}")
            elif choice == "5":
                print(f"{self._colorize('Goodbye!', 'green')}")
                sys.exit(0)
            else:
                # If the input is not a menu option, treat it as an anime title to search
                print(f"Searching for: {self._colorize(choice, 'cyan')}")
                self.search_anime(choice)


if __name__ == "__main__":
    # Add import for regular expressions if not already imported
    import re
    
    # Add signal handler for clean shutdown
    def signal_handler(sig, frame):
        print("\nOperation cancelled by user.")
        try:
            # Try to close the browser if it's open
            if 'cli' in locals() and hasattr(cli, 'site_interactor'):
                cli.site_interactor.close_browser()
        except Exception as e:
            print(f"Error cleaning up: {e}")
        sys.exit(0)
    
    # Register signal handler for CTRL+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        cli = CLI()
        cli.start()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        try:
            cli.site_interactor.close_browser()
        except:
            pass
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
