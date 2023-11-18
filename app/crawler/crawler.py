import os
import time
from typing import Set
from urllib.parse import urljoin, urlparse, urlunparse
from tqdm import tqdm

import requests
import validators
from bs4 import BeautifulSoup

import vector_database as db


def parse_urls(soup) -> Set[str]:
	urls: Set[str] = set()
	for link in soup.find_all('a'):
		urls.add(link.get('href'))
	return urls


def refactor_links(target_hostname, target_path, base_url, links):
	refactored_links = set()
	for link in links:

		if link is None or link.startswith("#") or link.endswith(".pdf") or "typo3" in link:
			continue

		refactored_link = urljoin(base_url, link)

		if not validators.url(refactored_link):
			continue

		refactored_link = refactored_link.split('#')[0]

		parsed_url = urlparse(refactored_link)

		if target_hostname in parsed_url.hostname and target_path in parsed_url.path:
			refactored_links.add(refactored_link)

	return refactored_links


def get_next_url(urls, urls_crawled):
	while True:
		current = urls.pop()
		if current not in urls_crawled:
			return current
		if len(urls) == 0:
			return None


def crawl(start_url: str, save_documents: bool = False, max_pages: int = 1000, target_host: str = "www.cit.tum.de", target_path: str = "/cit"):
	urls: Set[str] = set()
	urls_crawled: Set[str] = set()
	urls.add(start_url)
	DIR_NAME = "sites"
	if save_documents and not os.path.exists(f"./{DIR_NAME}"):
		os.makedirs(f"./{DIR_NAME}")
	chunks = []
	with requests.Session() as session:
		for count_pages in tqdm(range(max_pages)):

			current_url = get_next_url(urls, urls_crawled)
			if current_url is None:
				break
			response = session.get(url=current_url)

			content_type = response.headers.get("Content-Type")

			if content_type != "text/html; charset=utf-8":
				urls_crawled.add(current_url)
				continue

			soup = BeautifulSoup(response.text, 'html.parser')
			page_urls: Set[str] = parse_urls(soup)
			page_urls = refactor_links(target_host, target_path, current_url, page_urls)

			urls.update(page_urls)
			urls_crawled.add(current_url)

			filename = f"{DIR_NAME}/{current_url.replace('/', '_').replace(':', '_')}.html"
			if save_documents:
				if os.path.exists(filename):
					os.remove(filename)
				with open(filename, 'w', encoding='utf-8') as file:
					file.write(response.text)
			chunks += db.get_chunk(response.text, current_url)
	return chunks

	print(f"{urls_crawled=}")
	print(f"{urls=}")
	print(f"{count_pages=}")




if __name__ == '__main__':
	chunks = crawl("https://www.cit.tum.de/cit/studium", max_pages=5000, target_path="/cit/")
	chunks += db.absence_chunks()
	db.save_chunks(chunks)


