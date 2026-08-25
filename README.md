# hanime.tv image link downloader

A small command-line downloader that collects image URLs from a hanime.tv
community-images channel and saves them as a newline-separated text file. 

## Requirements

- Python 3.10 or newer
- No third-party packages for normal HTTP mode
- Optional: Playwright and its Chromium browser for browser mode

Install the optional browser support with:

```powershell
python -m pip install playwright
python -m playwright install chromium
```

## Usage

Run the default channel with a deliberately conservative delay:

```powershell
python linkDownloader.py --output picture_links.txt
```

Useful options:

```text
--url URL             First browse-images URL
--output PATH         Output file (default: picture_links.txt)
--delay SECONDS       Pause between pages
--size COUNT          Images requested per page (default: 96)
--max-pages COUNT     Stop after COUNT pages; useful for testing
--update              Keep existing links and stop at known content
--browser             Use a visible Playwright browser session
```

For a site session that needs browser interaction, use:

```powershell
python linkDownloader.py --browser --delay 5
```

The browser mode stores its persistent session in `.browser-profile` so a
manually completed browser check can be reused during later runs. Treat that
directory as private local state and do not publish it.

## Responsible use

Use a delay appropriate for the site and its terms. A VPN may change whether a
network can reach the site, but it does not guarantee access or permission to
collect content. Do not use this tool to defeat access controls, and stop if
the site asks you to do so. Respect copyright, privacy, and applicable law
when storing or redistributing the resulting links.

The script does not download image files; it only writes URLs. HTTP 403
responses and browser checks are reported instead of being retried
indefinitely.
