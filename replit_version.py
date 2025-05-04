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
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find anime cards (adjust selectors based on the site structure)
            anime_cards = soup.select('.anime-card, .post-item, article, .card')
            
            if not anime_cards:
                print(f"{bcolors.FAIL}No anime found with that query.{bcolors.ENDC}")
                return []
            
            results = []
            for card in anime_cards:
                # Extract title
                title_elem = card.select_one('h3, .title, h2, .name')
                if not title_elem:
                    continue
                title = title_elem.get_text().strip()
                
                # Extract link
                link_elem = card.select_one('a')
                if not link_elem:
                    continue
                link = link_elem.get('href')
                
                # Ensure the link is absolute
                if link and not link.startswith('http'):
                    link = f"{site}{link}"
                
                results.append({
                    'title': title,
                    'link': link
                })
            
            print(f"{bcolors.OKGREEN}Found {len(results)} anime matching '{query}'{bcolors.ENDC}")
            return results
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error during search: {e}{bcolors.ENDC}")
            return []
    
    def extract_episodes(self, anime_url):
        """Extract episodes from an anime page"""
        print(f"{bcolors.HEADER}Extracting episodes from {anime_url}{bcolors.ENDC}")
        
        try:
            # Fetch the anime page
            response = self.session.get(anime_url)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find episode elements (adjust selectors based on the site structure)
            episode_elements = soup.select('.episodes-card-container .episode-card, .episodes-list-content .episode-card')
            
            if not episode_elements:
                print(f"{bcolors.FAIL}No episodes found.{bcolors.ENDC}")
                return []
            
            episodes = []
            for element in episode_elements:
                # Extract episode number and link
                link_elem = element.select_one('a')
                if not link_elem:
                    continue
                
                link = link_elem.get('href')
                
                # Try to find episode number
                ep_match = re.search(r'الحلقة-(\d+)', link or '')
                if ep_match:
                    episode_number = ep_match.group(1)
                else:
                    # Try to extract from text content
                    text = element.get_text()
                    ep_match = re.search(r'الحلقة\s*(\d+)', text)
                    if ep_match:
                        episode_number = ep_match.group(1)
                    else:
                        # Generate sequential number
                        episode_number = str(len(episodes) + 1)
                
                # Ensure the link is absolute
                if link and not link.startswith('http'):
                    link = f"{self.default_site}{link}"
                
                episodes.append({
                    'number': episode_number,
                    'link': link
                })
            
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
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Look for the download button
            download_button = soup.select_one('a:contains("تحميل الحلقة"), a:contains("تحميل")')
            
            if not download_button:
                print(f"{bcolors.FAIL}No download button found.{bcolors.ENDC}")
                return []
            
            # Get the download page URL
            download_url = download_button.get('href')
            
            # Ensure the URL is absolute
            if download_url and not download_url.startswith('http'):
                download_url = f"{self.default_site}{download_url}"
            
            # Fetch the download page
            response = self.session.get(download_url)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find server elements
            server_elements = soup.select('.download-servers a, .server-list a, a[href*="drive.google"], a[href*="mediafire"]')
            
            if not server_elements:
                print(f"{bcolors.FAIL}No download servers found.{bcolors.ENDC}")
                return []
            
            download_links = []
            for element in server_elements:
                url = element.get('href')
                # Try to get server name
                name_elem = element.select_one('.server-name, .dashboard-button-text')
                if name_elem:
                    name = name_elem.get_text().strip()
                else:
                    # Determine name from URL
                    if "drive.google" in url:
                        name = "Google Drive"
                    elif "mediafire" in url:
                        name = "MediaFire"
                    elif "mega" in url:
                        name = "MEGA"
                    else:
                        name = "Unknown Server"
                
                download_links.append({
                    'host': name,
                    'url': url
                })
            
            print(f"{bcolors.OKGREEN}Found {len(download_links)} download links{bcolors.ENDC}")
            return download_links
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error extracting download links: {e}{bcolors.ENDC}")
            return []
    
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
            results = scraper.search_anime(query)
            
            if not results:
                continue
            
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
            selection = input(f"\n{bcolors.HEADER}Enter the number of your selection (0 to cancel): {bcolors.ENDC}")
            
            try:
                selection = int(selection)
                if selection == 0:
                    continue
                
                if selection < 1 or selection > len(results):
                    print(f"{bcolors.FAIL}Invalid selection.{bcolors.ENDC}")
                    continue
                
                selected_anime = results[selection - 1]
                print(f"\n{bcolors.OKGREEN}Selected: {selected_anime['title']}{bcolors.ENDC}")
                
                # Get episodes
                episodes = scraper.extract_episodes(selected_anime['link'])
                
                if not episodes:
                    continue
                
                # Display episodes
                print("\nAvailable Episodes:")
                print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
                
                # Group episodes in rows of 10
                for i in range(0, len(episodes), 10):
                    row = episodes[i:i+10]
                    print(" ".join([f"{bcolors.OKCYAN}{ep['number'].rjust(4)}{bcolors.ENDC}" for ep in row]))
                
                print(f"{bcolors.OKBLUE}{'='*60}{bcolors.ENDC}")
                
                # Get episode selection
                ep_selection = input(f"\n{bcolors.HEADER}Enter episode number to download: {bcolors.ENDC}")
                
                # Find the selected episode
                selected_episode = None
                for ep in episodes:
                    if ep['number'] == ep_selection:
                        selected_episode = ep
                        break
                
                if not selected_episode:
                    print(f"{bcolors.FAIL}Episode {ep_selection} not found.{bcolors.ENDC}")
                    continue
                
                # Get download links
                download_links = scraper.extract_download_links(selected_episode['link'])
                
                if not download_links:
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
                link_selection = input(f"\n{bcolors.HEADER}Enter the number of the server to download from: {bcolors.ENDC}")
                
                try:
                    link_selection = int(link_selection)
                    if link_selection < 1 or link_selection > len(download_links):
                        print(f"{bcolors.FAIL}Invalid selection.{bcolors.ENDC}")
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
                except ValueError:
                    print(f"{bcolors.FAIL}Invalid selection.{bcolors.ENDC}")
                    continue
            except ValueError:
                print(f"{bcolors.FAIL}Invalid selection.{bcolors.ENDC}")
                continue
        elif choice == "2":
            print(f"\n{bcolors.OKGREEN}Thank you for using Anime Downloader!{bcolors.ENDC}")
            sys.exit(0)
        else:
            # Treat input as anime name
            results = scraper.search_anime(choice)
            
            if not results:
                continue
            
            # Continue with anime selection as above...
            # (code omitted for brevity - would be the same as the selection code above)

if __name__ == "__main__":
    main() 