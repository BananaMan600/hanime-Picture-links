"""Collect image URLs from a hanime.tv community-images channel.

The downloader writes one normalized, original-size image URL per line. It
supports a low-dependency HTTP mode and an optional visible-browser mode for
pages that require a browser session to load.
"""

from __future__ import annotations

import argparse
import html
import importlib
import random
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


DEFAULT_URL = "https://hanime.tv/browse/images"
DEFAULT_OUTPUT = "picture_links.txt"
DEFAULT_PAGE_SIZE = 96
DEFAULT_BROWSER_PROFILE = Path(".browser-profile")
USER_AGENTS = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
	"Gecko/20100101 Firefox/133.0",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
	"(KHTML, like Gecko) Version/18.1 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)


class PageParser(HTMLParser):
	"""Collect image attributes and the site's cursor-based next-page URL."""

	def __init__(self) -> None:
		super().__init__()
		self.image_urls: list[str] = []
		self.next_href: str | None = None

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		attributes = dict(attrs)
		if tag == "img":
			# The site has used several lazy-loading attributes over time. Read all
			# of them and let normalization below remove duplicates and thumbnails.
			for name in ("src", "data-src", "data-original"):
				value = attributes.get(name)
				if value:
					self.image_urls.append(value)
			srcset = attributes.get("srcset") or attributes.get("data-srcset")
			if srcset:
				self.image_urls.extend(
					item.strip().split(" ", 1)[0]
					for item in srcset.split(",")
					if item.strip()
				)

		if tag == "astro-island" and self.next_href is None:
			match = re.search(
				r"next_href(?:&quot;|\")[ ]*:[ ]*\[[01],[ ]*(?:&quot;|\")(.*?)(?:&quot;|\")[ ]*\]",
				str(attrs),
			)
			if match:
				self.next_href = html.unescape(match.group(1)) or None


def normalize_image_url(raw_url: str, page_url: str) -> str | None:
	"""Return an allowed absolute image URL, preferring the original over `_200`.

	Only the image hosts used by the channel are accepted. This keeps unrelated
	URLs embedded in the page from being written to the output file.
	"""
	image_url = urljoin(page_url, html.unescape(raw_url))
	parsed = urlparse(image_url)
	if (
		parsed.scheme not in {"http", "https"}
		or not re.fullmatch(r"cu-images\.image[a-z]+\.top", parsed.netloc)
	):
		return None
	path = re.sub(r"_200(?=\.[^./]+$)", "", parsed.path)
	return urlunparse(parsed._replace(path=path))


def fetch_page(url: str) -> str:
	request = Request(
		url,
		headers={
			"User-Agent": random.choice(USER_AGENTS),
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "en-US,en;q=0.9",
			"Referer": "https://hanime.tv/",
		},
	)
	with urlopen(request, timeout=30) as response:
		return response.read().decode("utf-8", errors="replace")


def add_page_size(url: str, page_size: int) -> str:
	separator = "&" if "?" in url else "?"
	if re.search(r"(?:[?&])size=\d+", url):
		return re.sub(r"([?&])size=\d+", rf"\g<1>size={page_size}", url)
	return f"{url}{separator}size={page_size}"


def scrape_with_browser(
	start_url: str,
	delay: float = 0.5,
	max_pages: int | None = None,
	known_links: set[str] | None = None,
	page_size: int = DEFAULT_PAGE_SIZE,
) -> list[str]:
	"""Scrape with a visible Chrome session so the user can solve challenges."""
	try:
		playwright_api = importlib.import_module("playwright.sync_api")
		PlaywrightTimeoutError = playwright_api.TimeoutError
		sync_playwright = playwright_api.sync_playwright
	except ImportError as error:
		raise RuntimeError(
			"Browser mode requires Playwright. Install it with: "
			"python -m pip install playwright"
		) from error

	start_url = add_page_size(start_url, page_size)
	with sync_playwright() as playwright:
		chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
		launch_args = {
			"headless": False,
			"args": ["--disable-blink-features=AutomationControlled"],
			"ignore_default_args": ["--enable-automation", "--no-sandbox"],
		}
		if chrome_path.exists():
			launch_args["executable_path"] = str(chrome_path)
		context = playwright.chromium.launch_persistent_context(
			str(DEFAULT_BROWSER_PROFILE),
			**launch_args,
			viewport={"width": 1440, "height": 900},
			locale="en-US",
		)
		page = context.pages[0] if context.pages else context.new_page()
		try:
			page_url = start_url
			links: list[str] = []
			seen_links: set[str] = set()
			seen_pages: set[str] = set()
			page_number = 0

			while page_url and page_url not in seen_pages:
				if max_pages is not None and page_number >= max_pages:
					break
				seen_pages.add(page_url)
				page_number += 1
				print(f"Page {page_number}: {page_url}", file=sys.stderr)
				try:
					page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
					page.wait_for_selector(
						"img[src*='cu-images.'], img[data-src*='cu-images.'], "
						"img[data-original*='cu-images.']",
						timeout=30000,
					)
				except PlaywrightTimeoutError:
					print(
						"Browser check detected. Solve it in the opened window; "
						"the scraper will continue automatically when pictures appear "
						"(up to 5 minutes).",
						file=sys.stderr,
					)
					try:
						page.wait_for_selector(
							"img[src*='cu-images.'], img[data-src*='cu-images.'], "
							"img[data-original*='cu-images.']",
							timeout=300000,
						)
					except PlaywrightTimeoutError:
						raise RuntimeError(
							"No picture links appeared after 5 minutes. "
							"The browser protection check may still be incomplete."
						) from None

				source = page.content()
				parser = PageParser()
				parser.feed(source)
				page_links = {
					link
					for raw_url in parser.image_urls
					if (link := normalize_image_url(raw_url, page_url)) is not None
				}
				if not page_links:
					raise RuntimeError(
						"The page loaded but contained no picture links; "
						"the browser protection check may not be complete."
					)
				for link in page_links:
					if link not in seen_links:
						seen_links.add(link)
						links.append(link)

				if known_links is not None and page_links and page_links <= known_links:
					# Update mode can stop once an entire page is already in the output.
					break
				page_url = urljoin(page_url, html.unescape(parser.next_href or ""))
				if page_url and delay:
					time.sleep(delay)
			return links
		finally:
			context.close()


def scrape(
	start_url: str,
	delay: float = 0.5,
	max_pages: int | None = None,
	known_links: set[str] | None = None,
) -> list[str]:
	"""Follow the site's cursor pagination and return unique picture URLs."""
	page_url = start_url
	links: list[str] = []
	seen_links: set[str] = set()
	seen_pages: set[str] = set()
	page_number = 0

	while page_url and page_url not in seen_pages:
		if max_pages is not None and page_number >= max_pages:
			break
		seen_pages.add(page_url)
		page_number += 1
		print(f"Page {page_number}: {page_url}", file=sys.stderr)

		last_error: Exception | None = None
		for attempt in range(3):
			try:
				source = fetch_page(page_url)
				last_error = None
				break
			except (HTTPError, URLError, TimeoutError) as error:
				last_error = error
				if attempt < 2:
					time.sleep(2**attempt)
		if last_error is not None:
			if isinstance(last_error, HTTPError) and last_error.code == 403:
				raise RuntimeError(
					"hanime.tv rejected the request with HTTP 403. "
					"This is a site-side block; wait and try again later, "
					"or run from a network/browser session that can access the site."
				) from None
			raise RuntimeError(f"Could not fetch {page_url}: {last_error}") from last_error

		parser = PageParser()
		parser.feed(source)
		page_links = {
			link
			for raw_url in parser.image_urls
			if (link := normalize_image_url(raw_url, page_url)) is not None
		}
		for link in page_links:
			if link not in seen_links:
				seen_links.add(link)
				links.append(link)

		if known_links is not None and page_links and page_links <= known_links:
			# Update mode avoids walking older pages after reaching known content.
			break

		page_url = urljoin(page_url, html.unescape(parser.next_href or ""))
		if page_url and delay:
			time.sleep(delay)

	return links


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--url", default=DEFAULT_URL, help="First browse-images URL")
	parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path, help="Output txt file")
	parser.add_argument("--delay", default=0.5, type=float, help="Seconds between pages")
	parser.add_argument("--max-pages", type=int, help="Optional limit for testing")
	parser.add_argument("--browser", action="store_true", help="Use a visible browser so Cloudflare checks can be completed manually",)
	parser.add_argument("--size", default=DEFAULT_PAGE_SIZE, type=int, help="Images requested per page (default: 96)",)
	parser.add_argument("--update",	action="store_true", help="Merge new links into an existing output file and stop at known links",)
	parser.add_argument("--new-links", type=Path, help="Write links found during update to a separate txt file",)
	return parser.parse_args()


def main() -> None:
	try:
		args = parse_args()
		if args.new_links is not None and not args.update:
			raise RuntimeError("--new-links can only be used together with --update")
		existing_links: list[str] = []
		if args.update and args.output.exists():
			existing_links = [
				line.strip()
				for line in args.output.read_text(encoding="utf-8").splitlines()
				if line.strip()
			]

		scrape_args = {
			"start_url": add_page_size(args.url, args.size),
			"delay": args.delay,
			"max_pages": args.max_pages,
			"known_links": set(existing_links) if args.update else None,
		}
		if args.browser:
			links = scrape_with_browser(**scrape_args, page_size=args.size)
		else:
			links = scrape(**scrape_args)
		existing_set = set(existing_links)
		new_links = [link for link in links if link not in existing_set]
		merged_links = existing_links + new_links
		args.output.write_text(
			"\n".join(merged_links) + ("\n" if merged_links else ""), encoding="utf-8"
		)
		print(f"Saved {len(merged_links)} unique image links to {args.output}")
		if args.new_links is not None:
			args.new_links.write_text(
				"\n".join(new_links) + ("\n" if new_links else ""), encoding="utf-8"
			)
			print(f"Saved {len(new_links)} new image links to {args.new_links}")
			print("")
		
	except RuntimeError as error:
		print(f"Error: {error}", file=sys.stderr)
		raise SystemExit(1) from None


if __name__ == "__main__":
	main()