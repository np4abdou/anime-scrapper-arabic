#!/usr/bin/env python3
"""
Simplified Anime Scraper for repl.it - Works without Playwright browser dependencies
"""

import os
import sys
import re
import json
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import base64

# Constants
CONFIG_DIR = Path.home() / ".anime_downloader"
DATABASE_FILE = CONFIG_DIR / "database.json"
DOWNLOAD_DIR = Path.home() / "Downloads" / "Anime"

# Ensure directories exist
CONFIG_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)

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

# User agent to simulate a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

class AnimeScraperNoPlaywright:
    """Simplified Anime Scraper that doesn't use Playwright browser"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
        # Load or create the database
        self.database = self._load_database()
        
        # Default site
        self.default_site = "https://witanime.cyou"
    
    def _load_database(self):
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
                    "history": [],
                    "preferences": {}
                }
        except Exception as e:
            print(f"Error loading database: {e}")
            # Return empty database as fallback
            return {
                "anime": {},
                "normalized_titles": {},
                "aliases": {},
                "history": [],
                "preferences": {}
            }
    
    def save_database(self):
        """Save the current database to file."""
        try:
            with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.database, f, indent=2)
            print(f"Database saved to {DATABASE_FILE}")
        except Exception as e:
            print(f"Error saving database: {e}")
    
    def search_anime(self, query, site=None):
        """Search for anime using requests and BeautifulSoup"""
        if not site:
            site = self.default_site
        
        print(f"{bcolors.HEADER}Searching for '{query}' on {site}...{bcolors.ENDC}")
        
        # Format search URL
        search_url = f"{site}/?search_param=animes&s={query}"
        
        try:
            # Fetch the search page
            response = self.session.get(search_url)
            response.raise_for_status()
            
            # Save HTML for debugging
            with open("search_response.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"{bcolors.WARNING}Saved HTML response to search_response.html for debugging{bcolors.ENDC}")
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try multiple selectors for anime cards
            selectors = [
                '.anime-card', 
                '.post-item', 
                'article', 
                '.card',
                'div.anime',
                '.anime-list-content .anime-card',
                '.anime-list-content li',
                '.page-content-container .anime-card',
                'div[class*="anime"]',
                '.post'
            ]
            
            anime_cards = []
            for selector in selectors:
                cards = soup.select(selector)
                if cards:
                    print(f"{bcolors.OKGREEN}Found {len(cards)} anime cards with selector: {selector}{bcolors.ENDC}")
                    anime_cards = cards
                    break
            
            if not anime_cards:
                print(f"{bcolors.FAIL}No anime found with any selectors. Try entering a direct URL.{bcolors.ENDC}")
                direct_url = input(f"{bcolors.HEADER}Enter anime URL directly (or press Enter to cancel): {bcolors.ENDC}")
                if direct_url and direct_url.startswith("http"):
                    return [{'title': query, 'link': direct_url}]
                return []
            
            results = []
            for card in anime_cards:
                try:
                    # Try multiple title selectors
                    title_selectors = ['h3', '.title', 'h2', '.name', 'h3 a', '.card-title', 
                                       'a[title]', '[class*="title"]', 'a']
                    title = None
                    for selector in title_selectors:
                        title_elem = card.select_one(selector)
                        if title_elem:
                            title = title_elem.get_text().strip() or title_elem.get('title')
                            if title:
                                break
                    
                    # If still no title, try getting from img alt
                    if not title:
                        img = card.select_one('img')
                        if img and img.get('alt'):
                            title = img.get('alt').strip()
                    
                    # Extract link - try different ways
                    link = None
                    link_elem = card.select_one('a')
                    if link_elem:
                        link = link_elem.get('href')
                    
                    # Skip if no title or link
                    if not title or not link:
                        continue
                        
                    # Ensure the link is absolute
                    if link and not link.startswith('http'):
                        link = f"{site}{link}"
                    
                    results.append({
                        'title': title,
                        'link': link
                    })
                except Exception as e:
                    print(f"{bcolors.FAIL}Error processing card: {e}{bcolors.ENDC}")
            
            if results:
                print(f"{bcolors.OKGREEN}Found {len(results)} anime matching '{query}'{bcolors.ENDC}")
            else:
                print(f"{bcolors.FAIL}Could not extract anime information from the page.{bcolors.ENDC}")
                direct_url = input(f"{bcolors.HEADER}Enter anime URL directly (or press Enter to cancel): {bcolors.ENDC}")
                if direct_url and direct_url.startswith("http"):
                    return [{'title': query, 'link': direct_url}]
            
            return results
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error during search: {e}{bcolors.ENDC}")
            direct_url = input(f"{bcolors.HEADER}Enter anime URL directly (or press Enter to cancel): {bcolors.ENDC}")
            if direct_url and direct_url.startswith("http"):
                return [{'title': query, 'link': direct_url}]
            return []
    
    def extract_episodes(self, anime_url):
        """Extract episodes from an anime page"""
        print(f"{bcolors.HEADER}Extracting episodes from {anime_url}{bcolors.ENDC}")
        
        try:
            # Fetch the anime page
            response = self.session.get(anime_url)
            response.raise_for_status()
            
            # Save HTML for debugging
            with open("anime_page.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"{bcolors.WARNING}Saved HTML response to anime_page.html for debugging{bcolors.ENDC}")
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try multiple selectors for episode elements
            episode_selectors = [
                '.episodes-card-container .episode-card',
                '.episodes-list-content .episode-card',
                '.episodes-list-content li',
                '.episodes-card-container a',
                '.page-content-container .episode-card',
                'a[href*="episode"]',
                'a[href*="الحلقة"]',
                'div[class*="episode"]',
                'li[class*="episode"]',
                'a[onclick*="openEpisode"]'
            ]
            
            episode_elements = []
            for selector in episode_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"{bcolors.OKGREEN}Found {len(elements)} episode elements with selector: {selector}{bcolors.ENDC}")
                    episode_elements = elements
                    break
            
            if not episode_elements:
                print(f"{bcolors.FAIL}No episodes found with any selector.{bcolors.ENDC}")
                
                # Try to find any links that might be episodes
                all_links = soup.select('a')
                episode_links = [a for a in all_links if 'episode' in a.get('href', '').lower() or 'الحلقة' in a.get('href', '')]
                
                if episode_links:
                    print(f"{bcolors.OKGREEN}Found {len(episode_links)} potential episode links by searching all anchors.{bcolors.ENDC}")
                    episode_elements = episode_links
                else:
                    return []
            
            episodes = []
            for element in episode_elements:
                try:
                    # Extract link
                    if element.name == 'a':
                        link = element.get('href')
                    else:
                        link_elem = element.select_one('a')
                        link = link_elem.get('href') if link_elem else None
                    
                    # Skip if no link
                    if not link:
                        continue
                    
                    # For onclick handlers (common in witanime)
                    onclick = element.get('onclick')
                    if onclick and 'openEpisode' in onclick:
                        try:
                            # Extract base64 from openEpisode('base64string')
                            import re
                            base64_match = re.search(r"openEpisode\('([^']+)'\)", onclick)
                            if base64_match:
                                base64_url = base64_match.group(1)
                                decoded_url = base64.b64decode(base64_url).decode('utf-8')
                                link = decoded_url
                        except Exception as decode_err:
                            print(f"{bcolors.FAIL}Error decoding base64 URL: {decode_err}{bcolors.ENDC}")
                    
                    # Try various ways to find episode number
                    episode_number = None
                    
                    # Try to find in URL
                    ep_match = re.search(r'الحلقة-(\d+)', link or '')
                    if ep_match:
                        episode_number = ep_match.group(1)
                    else:
                        # Try episode-X pattern
                        ep_match = re.search(r'episode-(\d+)', link.lower() or '')
                        if ep_match:
                            episode_number = ep_match.group(1)
                        else:
                            # Try to extract from text content
                            text = element.get_text()
                            ep_match = re.search(r'الحلقة\s*(\d+)', text)
                            if ep_match:
                                episode_number = ep_match.group(1)
                            else:
                                ep_match = re.search(r'حلقة\s*(\d+)', text)
                                if ep_match:
                                    episode_number = ep_match.group(1)
                                else:
                                    ep_match = re.search(r'episode\s*(\d+)', text.lower())
                                    if ep_match:
                                        episode_number = ep_match.group(1)
                                    else:
                                        # Try to find any number in text
                                        number_match = re.search(r'(\d+)', text)
                                        if number_match:
                                            episode_number = number_match.group(1)
                                        else:
                                            # Generate sequential number as last resort
                                            episode_number = str(len(episodes) + 1)
                    
                    # Ensure the link is absolute
                    if link and not link.startswith('http'):
                        link = f"{self.default_site}{link}"
                    
                    # Add to episodes only if we haven't seen this episode number before
                    if episode_number and link:
                        existing_episodes = [ep for ep in episodes if ep['number'] == episode_number]
                        if not existing_episodes:
                            episodes.append({
                                'number': episode_number,
                                'link': link
                            })
                except Exception as e:
                    print(f"{bcolors.FAIL}Error processing episode element: {e}{bcolors.ENDC}")
            
            # Sort episodes by number
            episodes.sort(key=lambda x: int(x['number']) if x['number'].isdigit() else float('inf'))
            
            print(f"{bcolors.OKGREEN}Found {len(episodes)} episodes{bcolors.ENDC}")
            return episodes
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error extracting episodes: {e}{bcolors.ENDC}")
            return []
    
    def extract_download_links(self, episode_url):
        """Extract download links from an episode page"""
        print(f"{bcolors.HEADER}Extracting download links from {episode_url}{bcolors.ENDC}")
        
        try:
            # Fetch the episode page
            response = self.session.get(episode_url)
            response.raise_for_status()
            
            # Save HTML for debugging
            with open("episode_page.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"{bcolors.WARNING}Saved HTML response to episode_page.html for debugging{bcolors.ENDC}")
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try multiple selectors for download buttons
            download_button_selectors = [
                'a:contains("تحميل الحلقة")', 
                'a:contains("تحميل")',
                'a.btn-site:contains("تحميل")',
                '.btn-site',
                'a.btn-site',
                '.episodes-buttons-list a',
                '.episode-buttons-container a',
                'a.btn-primary',
                'a.btn-download',
                'a[href*="download"]',
                'a[class*="download"]'
            ]
            
            download_button = None
            for selector in download_button_selectors:
                try:
                    button = soup.select_one(selector)
                    if button:
                        print(f"{bcolors.OKGREEN}Found download button with selector: {selector}{bcolors.ENDC}")
                        download_button = button
                        break
                except Exception:
                    continue
            
            # If can't find with CSS selectors, try text matching
            if not download_button:
                print(f"{bcolors.WARNING}Trying text matching for download buttons...{bcolors.ENDC}")
                download_texts = ["تحميل الحلقة", "تحميل", "download", "تنزيل"]
                for a in soup.find_all('a'):
                    if any(text.lower() in a.get_text().lower() for text in download_texts):
                        download_button = a
                        print(f"{bcolors.OKGREEN}Found download button by text: {a.get_text()}{bcolors.ENDC}")
                        break
            
            if not download_button:
                print(f"{bcolors.FAIL}No download button found. Trying direct server extraction...{bcolors.ENDC}")
                # Try to find direct server links on the current page
                server_links = self._extract_server_links(soup)
                if server_links:
                    return server_links
                return []
            
            # Get the download page URL
            download_url = download_button.get('href')
            
            # Ensure the URL is absolute
            if download_url and not download_url.startswith('http'):
                download_url = f"{self.default_site}{download_url}"
            
            print(f"{bcolors.OKGREEN}Navigating to download page: {download_url}{bcolors.ENDC}")
            
            # Fetch the download page
            download_response = self.session.get(download_url)
            download_response.raise_for_status()
            
            # Save download page HTML for debugging
            with open("download_page.html", "w", encoding="utf-8") as f:
                f.write(download_response.text)
            print(f"{bcolors.WARNING}Saved download page HTML to download_page.html for debugging{bcolors.ENDC}")
            
            # Parse the download page HTML
            download_soup = BeautifulSoup(download_response.text, 'lxml')
            
            # Extract server links from the download page
            return self._extract_server_links(download_soup)
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error extracting download links: {e}{bcolors.ENDC}")
            return []
    
    def _extract_server_links(self, soup):
        """Extract server links from a soup object"""
        # Try various selectors for server elements
        server_selectors = [
            '.download-servers a', 
            '.server-list a', 
            'a[href*="drive.google"]', 
            'a[href*="mediafire"]',
            '.servers a',
            '.servers-list a',
            '.server-item a',
            '.server a',
            'a.dashboard-button',
            'a.download-link',
            'a[class*="download"]',
            'a.btn-download'
        ]
        
        server_elements = []
        for selector in server_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"{bcolors.OKGREEN}Found {len(elements)} server elements with selector: {selector}{bcolors.ENDC}")
                server_elements = elements
                break
        
        if not server_elements:
            print(f"{bcolors.FAIL}No download servers found with any selector.{bcolors.ENDC}")
            
            # Try finding any links to common file hosts
            all_links = soup.find_all('a')
            host_keywords = ['drive.google', 'mediafire', 'mega.nz', 'solidfiles', 'mp4upload']
            server_elements = [a for a in all_links if any(host in a.get('href', '').lower() for host in host_keywords)]
            
            if server_elements:
                print(f"{bcolors.OKGREEN}Found {len(server_elements)} potential server links by checking all links.{bcolors.ENDC}")
            else:
                return []
        
        download_links = []
        for element in server_elements:
            try:
                url = element.get('href')
                
                # Skip invalid URLs
                if not url or url == "#" or url.startswith('javascript:'):
                    continue
                
                # Try to get server name
                name_elem = element.select_one('.server-name, .dashboard-button-text, .notice, .server-content')
                if name_elem:
                    name = name_elem.get_text().strip()
                else:
                    # Use element text if available
                    name = element.get_text().strip()
                    # If empty text, determine name from URL
                    if not name:
                        if "drive.google" in url:
                            name = "Google Drive"
                        elif "mediafire" in url:
                            name = "MediaFire"
                        elif "mega" in url:
                            name = "MEGA"
                        elif "solidfiles" in url:
                            name = "SolidFiles"
                        elif "mp4upload" in url:
                            name = "MP4Upload"
                        elif "4shared" in url:
                            name = "4shared"
                        else:
                            name = "Unknown Server"
                
                # Add to download links if not already in the list
                existing_links = [link for link in download_links if link['url'] == url]
                if not existing_links:
                    download_links.append({
                        'host': name,
                        'url': url
                    })
                    print(f"{bcolors.OKGREEN}Found server: {name} - {url}{bcolors.ENDC}")
            except Exception as e:
                print(f"{bcolors.FAIL}Error processing server element: {e}{bcolors.ENDC}")
        
        print(f"{bcolors.OKGREEN}Found {len(download_links)} download links{bcolors.ENDC}")
        return download_links
    
    def download_file(self, url, destination):
        """Download a file from URL to destination"""
        print(f"{bcolors.HEADER}Downloading from {url} to {destination}{bcolors.ENDC}")
        
        try:
            # Create directory if it doesn't exist
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            # Get file size
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress bar
            bytes_downloaded = 0
            with open(destination, 'wb') as f:
                start_time = time.time()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Print progress
                        if total_size > 0:
                            percent = int(bytes_downloaded * 100 / total_size)
                            bar = '#' * (percent // 5)
                            spaces = ' ' * (20 - (percent // 5))
                            
                            # Calculate speed
                            elapsed_time = time.time() - start_time
                            if elapsed_time > 0:
                                speed = bytes_downloaded / elapsed_time / 1024
                                speed_unit = "KB/s"
                                if speed >= 1024:
                                    speed /= 1024
                                    speed_unit = "MB/s"
                                
                                sys.stdout.write(f"\r{bcolors.OKBLUE}Progress: [{bar}{spaces}] {percent}% ({speed:.2f} {speed_unit}){bcolors.ENDC}")
                                sys.stdout.flush()
            
            print(f"\n{bcolors.OKGREEN}Download completed: {destination}{bcolors.ENDC}")
            return True
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error downloading file: {e}{bcolors.ENDC}")
            return False

def display_logo():
    """Display ASCII art logo"""
    logo_path = "ascciilogoart.txt"
    try:
        if os.path.exists(logo_path):
            with open(logo_path, 'r', encoding='utf-8') as f:
                logo = f.read()
            print(f"\n{logo}\n")
    except:
        print("\n===== Anime Downloader (repl.it version) =====\n")

def main():
    display_logo()
    print(f"{bcolors.OKGREEN}Welcome to the repl.it version of Anime Downloader!{bcolors.ENDC}")
    print(f"{bcolors.WARNING}This is a simplified version that works without browser dependencies.{bcolors.ENDC}\n")
    
    scraper = AnimeScraperNoPlaywright()
    
    while True:
        print("\nOptions:")
        print(f"1. {bcolors.OKCYAN}Search for anime{bcolors.ENDC}")
        print(f"2. {bcolors.OKCYAN}Exit{bcolors.ENDC}")
        
        choice = input(f"\n{bcolors.HEADER}Enter your choice (1-2) or anime name: {bcolors.ENDC}")
        
        if choice == "1":
            query = input(f"{bcolors.HEADER}Enter anime title to search: {bcolors.ENDC}")
            search_and_process(scraper, query)
        elif choice == "2":
            print(f"\n{bcolors.OKGREEN}Thank you for using Anime Downloader!{bcolors.ENDC}")
            sys.exit(0)
        else:
            # Treat input as anime name
            search_and_process(scraper, choice)

def search_and_process(scraper, query):
    """Search for anime and process selection"""
    results = scraper.search_anime(query)
    
    if not results:
        return
    
    # Display results
    print("\nSearch Results:")
    print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
    print(f"{bcolors.OKCYAN}{'#':<4}{'Title':<50}{bcolors.ENDC}")
    print(f"{bcolors.OKBLUE}{'-'*60}{bcolors.ENDC}")
    
    for i, result in enumerate(results, 1):
        title = result['title']
        if len(title) > 45:
            title = title[:42] + "..."
        print(f"{i:<4}{title:<50}")
    
    print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
    
    # Get user selection
    while True:
        try:
            selection = input(f"\n{bcolors.HEADER}Enter the number of your selection (0 to cancel): {bcolors.ENDC}")
            
            if not selection.strip():
                continue
                
            selection = int(selection)
            if selection == 0:
                return
            
            if selection < 1 or selection > len(results):
                print(f"{bcolors.FAIL}Invalid selection. Please choose between 1 and {len(results)}.{bcolors.ENDC}")
                continue
            
            selected_anime = results[selection - 1]
            print(f"\n{bcolors.OKGREEN}Selected: {selected_anime['title']}{bcolors.ENDC}")
            
            # Get episodes
            episodes = scraper.extract_episodes(selected_anime['link'])
            
            if not episodes:
                return
            
            # Display episodes
            print("\nAvailable Episodes:")
            print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
            
            # Group episodes in rows of 10
            for i in range(0, len(episodes), 10):
                row = episodes[i:i+10]
                print(" ".join([f"{bcolors.OKCYAN}{ep['number'].rjust(4)}{bcolors.ENDC}" for ep in row]))
            
            print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
            
            # Get episode selection
            while True:
                ep_selection = input(f"\n{bcolors.HEADER}Enter episode number to download (0 to go back): {bcolors.ENDC}")
                
                if ep_selection == "0":
                    return
                
                # Find the selected episode
                selected_episode = None
                for ep in episodes:
                    if ep['number'] == ep_selection:
                        selected_episode = ep
                        break
                
                if not selected_episode:
                    print(f"{bcolors.FAIL}Episode {ep_selection} not found. Please try again.{bcolors.ENDC}")
                    continue
                
                # Get download links
                download_links = scraper.extract_download_links(selected_episode['link'])
                
                if not download_links:
                    print(f"{bcolors.FAIL}No download links found for this episode.{bcolors.ENDC}")
                    continue
                
                # Display download options
                print("\nAvailable Download Options:")
                print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
                print(f"{bcolors.OKCYAN}{'#':<4}{'Server':<20}{'URL':<36}{bcolors.ENDC}")
                print(f"{bcolors.OKBLUE}{'-'*60}{bcolors.ENDC}")
                
                for i, link in enumerate(download_links, 1):
                    url = link['url']
                    if len(url) > 35:
                        url = url[:32] + "..."
                    print(f"{i:<4}{link['host']:<20}{url:<36}")
                
                print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
                
                # Get link selection
                while True:
                    link_selection = input(f"\n{bcolors.HEADER}Enter the number of the server to download from (0 to go back): {bcolors.ENDC}")
                    
                    if link_selection == "0":
                        break
                    
                    try:
                        link_selection = int(link_selection)
                        if link_selection < 1 or link_selection > len(download_links):
                            print(f"{bcolors.FAIL}Invalid selection. Please choose between 1 and {len(download_links)}.{bcolors.ENDC}")
                            continue
                        
                        selected_link = download_links[link_selection - 1]
                        print(f"\n{bcolors.OKGREEN}Selected: {selected_link['host']}{bcolors.ENDC}")
                        
                        # Download the file
                        filename = f"{selected_anime['title']}_Episode_{selected_episode['number']}.mp4"
                        destination = DOWNLOAD_DIR / filename
                        
                        # For direct download (this is simplified - some servers might need special handling)
                        print(f"\n{bcolors.WARNING}Note: This is a simplified version that may not support all download servers.{bcolors.ENDC}")
                        print(f"{bcolors.WARNING}For MediaFire, Google Drive, or other services, you might need to manually download.{bcolors.ENDC}")
                        print(f"\n{bcolors.HEADER}Download URL: {selected_link['url']}{bcolors.ENDC}")
                        
                        download = input(f"\n{bcolors.HEADER}Attempt direct download? (y/n): {bcolors.ENDC}")
                        if download.lower() == 'y':
                            scraper.download_file(selected_link['url'], destination)
                        
                        # Ask if they want to download more
                        more_downloads = input(f"\n{bcolors.HEADER}Download another episode? (y/n): {bcolors.ENDC}")
                        if more_downloads.lower() != 'y':
                            return
                        else:
                            break  # Break the link selection loop to go back to episode selection
                    except ValueError:
                        print(f"{bcolors.FAIL}Invalid selection. Please enter a number.{bcolors.ENDC}")
            
        except ValueError:
            print(f"{bcolors.FAIL}Invalid selection. Please enter a number.{bcolors.ENDC}")
        except Exception as e:
            print(f"{bcolors.FAIL}Error: {e}{bcolors.ENDC}")
            break

if __name__ == "__main__":
    main() 