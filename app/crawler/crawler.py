from typing import Set
from urllib.parse import urljoin, urlparse
import vector_database as db
import validators
import os
import requests
from bs4 import BeautifulSoup
import pinecone

def parse_urls(soup) -> Set[str]:
	urls: Set[str] = set()
	for link in soup.find_all('a'):
		urls.add(link.get('href'))
	return urls


def refactor_links(target_url, base_url, links):
	refactored_links = set()
	for link in links:
		if link is None or link.startswith("#") or link.endswith(".pdf") or "typo3" in link:
			continue

		refactored_link = urljoin(base_url, link)

		if not validators.url(refactored_link):
			continue

		parsed_url = urlparse(refactored_link)

		if target_url in parsed_url.hostname:
			refactored_links.add(refactored_link)

	return refactored_links


def get_next_url(urls, urls_crawled):
	while True:
		current = urls.pop()
		if current not in urls_crawled:
			return current
		if len(urls) == 0:
			return ""


def crawl(start_url: str, save_documents: bool = False):
	urls: Set[str] = set()
	urls_crawled: Set[str] = set()
	urls.add(start_url)
	TARGET_URL = "cit.tum.de"
	DIR_NAME = "sites"
	if save_documents and not os.path.exists(f"./{DIR_NAME}"):
		os.makedirs(f"./{DIR_NAME}")

	with requests.Session() as session:
		while len(urls) != 0:
			current_url = get_next_url(urls, urls_crawled)
			if current_url == "":
				break
			response = session.get(url=current_url)
			soup = BeautifulSoup(response.text, 'html.parser')
			page_urls: Set[str] = parse_urls(soup)
			page_urls = refactor_links(TARGET_URL, current_url, page_urls)

			urls.update(page_urls)
			urls_crawled.add(current_url)

			print(f"crawled: {current_url}...")

			filename = f"{DIR_NAME}/{current_url.replace('/', '_').replace(':', '_')}.html"
			if save_documents and os.path.exists(filename):
				os.remove(filename)
				with open(filename, 'w', encoding='utf-8') as file:
					file.write(response.text)
				print(f"Content written to {filename}")

			db.save_website(response.text, current_url)
			print(f"Content saved to pinecone index {db.PINECONE_INDEX_NAME}")


	

if __name__ == '__main__':
	crawl("https://www.cit.tum.de/cit/studium/")
