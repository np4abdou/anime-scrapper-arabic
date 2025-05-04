# Anime Downloader

A command-line tool for finding and downloading anime from free streaming sites.

## Recent Fixes

The latest update includes several important fixes for the MediaFire download functionality:

1. **Improved MediaFire URL validation**: Now correctly identifies genuine MediaFire links and prevents confusion with 4shared links
2. **Enhanced file key extraction**: Multiple patterns are now used to extract file keys from MediaFire URLs
3. **Better error handling**: Fallback to direct download if mediafire.py integration fails
4. **Improved download selection UI**: Better source identification and filtering

## Features

- Search for anime across various free streaming sites
- Extract download links from different hosts
- Manage download queue for multiple episodes
- Store anime metadata and successful navigation patterns
- Adapt to changes in website layouts using pattern recognition
- Support for different download sources (Google Drive, Mediafire, etc.)

## Requirements

- Python 3.6+
- Required packages (automatically installed):
  - requests
  - playwright
  - gazpacho (for MediaFire downloads)

## Installation

1. Clone or download this repository
2. Run the dependency checker:

```bash
python check_dependencies.py
```

This will automatically install any missing dependencies.

## Usage

### Basic Usage

```bash
python anime.py
```

This will start the interactive mode, allowing you to search for and download anime.

### Command-line Arguments

```bash
python anime.py --search "One Piece"  # Search for an anime
python anime.py --download "One Piece" --episode 301  # Download a specific episode
python anime.py --list  # List saved anime
```

### Interactive Mode

In interactive mode, you can:

1. Search for anime
2. List saved anime
3. Download from saved anime
4. Change the default site

## Downloading from MediaFire

The anime downloader supports downloading from various sources, including MediaFire. The recent fixes have improved the MediaFire download functionality to work reliably with all types of MediaFire links.

If you're still having trouble with MediaFire downloads, try the following:

1. **Run the debug script**:

```bash
python debug_mediafire.py
```

This will help diagnose issues with MediaFire downloads.

2. **Try the direct test script** for specific episodes:

```bash
python test_one_piece_301.py
```

3. **Check that mediafire.py is correctly installed**:

```bash
python check_dependencies.py
```

## Troubleshooting

If you encounter any issues:

1. Run `check_dependencies.py` to ensure all dependencies are installed
2. Check your internet connection
3. Verify that the MediaFire link is valid
4. Try using a different download source (Google Drive, etc.)

## Files

- `anime.py`: Main script
- `mediafire.py`: Module for MediaFire downloads
- `check_dependencies.py`: Script to check and install dependencies
- `debug_mediafire.py`: Debug script for MediaFire downloads
- `test_one_piece_301.py`: Test script for specific episodes

## Configuration

The application stores its configuration and database in the following locations:

- Configuration: `~/.anime_downloader/config.json`
- Database: `~/.anime_downloader/database.json`
- Downloads: `~/Downloads/Anime/`

You can modify these paths in the `anime.py` file if needed.

## Disclaimer

This tool is for educational purposes only. Please respect copyright laws and only download content that you have the right to access. The developers of this tool are not responsible for any misuse.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is for educational purposes only. Please respect copyright laws and only download content that you have the right to access. 