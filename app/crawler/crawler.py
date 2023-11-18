import os
from typing import Set
from urllib.parse import urljoin, urlparse, urlunparse

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


def crawl(start_url: str, save_documents: bool = False, max_pages: int = 1000):
	urls: Set[str] = set()
	urls_crawled: Set[str] = set()
	urls.add(start_url)
	TARGET_HOST = "www.cit.tum.de"
	TARGET_PATH = "/cit/studium"
	DIR_NAME = "sites"
	if save_documents and not os.path.exists(f"./{DIR_NAME}"):
		os.makedirs(f"./{DIR_NAME}")
	count_pages = 0
	chunks = []
	with requests.Session() as session:
		while count_pages < max_pages:
			count_pages += 1
			current_url = get_next_url(urls, urls_crawled)
			if current_url is None:
				break
			response = session.get(url=current_url)
			soup = BeautifulSoup(response.text, 'html.parser')
			page_urls: Set[str] = parse_urls(soup)
			page_urls = refactor_links(TARGET_HOST, TARGET_PATH, current_url, page_urls)

			urls.update(page_urls)
			urls_crawled.add(current_url)

			print(f"crawled: {current_url}")

			filename = f"{DIR_NAME}/{current_url.replace('/', '_').replace(':', '_')}.html"
			if save_documents:
				if os.path.exists(filename):
					os.remove(filename)
				with open(filename, 'w', encoding='utf-8') as file:
					file.write(response.text)
				print(f"Content written to {filename}")

		chunks += db.get_chunk(response.text, current_url)

	db.save_chunks(chunks)
	print(f"Content saved to pinecone index {db.PINECONE_INDEX_NAME}")

	print(f"{urls_crawled=}")
	print(f"{urls=}")
	print(f"{count_pages=}")


if __name__ == '__main__':
	crawl("https://www.cit.tum.de/cit/studium/", max_pages=100)
