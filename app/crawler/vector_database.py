from bs4 import BeautifulSoup
import re
import os
from langchain.vectorstores import Pinecone
from langchain.vectorstores.pinecone import Document
from langchain.embeddings import OpenAIEmbeddings
from langchain.document_loaders import WebBaseLoader
from os import listdir
from os.path import isfile, join

PATH = "sites"

if os.environ.get("PINECONE_API_KEY", None) is None:
    raise Exception("Missing `PINECONE_API_KEY` environment variable.")

if os.environ.get("PINECONE_ENVIRONMENT", None) is None:
    raise Exception("Missing `PINECONE_ENVIRONMENT` environment variable.")

PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX", "langchain-test")


def fix_whitespaces(text):
    text = re.sub(' {2,}',' ', text)
    text = re.sub('\n{2,}','\n', text)
    text = re.sub('\r{2,}',' ', text)
    text = re.sub('\t{2,}',' ', text)
    return text

def save_chunks(documents):
    vectorstore = Pinecone.from_documents(
        documents=documents, embedding=OpenAIEmbeddings(), index_name=PINECONE_INDEX_NAME
    )
    retriever = vectorstore.as_retriever()
    return retriever


def get_chunk(website, url):
    soup = BeautifulSoup(website, 'html.parser')
    documents = []
    if soup.find("title") is None:
        title = "No title"
    else:
        title = soup.find("title").text.strip()
    ignore = {"frame-type-carousel"}
    content = soup.find("div", class_="content")
    documents += get_documents(content, soup, url, title, ignore)
    sidebar = soup.find("div", class_="sidebar")
    documents += get_documents(sidebar, soup, url, title, ignore)
    return documents


def get_documents(current_soup, whole_soup, url, title, ignore):
    documents = []
    if current_soup is None:
        return documents
    top_layer_divs = [child for child in current_soup.children if child.name == 'div' and not (ignore & set(child.get('class', [])))]
    OVER_LAPPING = 3
    for i in range(len(top_layer_divs)):
        headings = []
        if whole_soup.find("nav", class_='breadcrumbs').child is not None:
            headings += [breadcrumbs.text for breadcrumbs in whole_soup.find("nav", class_='breadcrumbs').find_all('li')]
        if whole_soup.find('h1') is not None:
            headings.append(whole_soup.find('h1').text)
        headings += [top_layer_divs[i].find_previous(h).text for h in ['h2', 'h3', 'h4', 'h5', 'h6'] if
                     top_layer_divs[i].find_previous(h) is not None]
        description = ">".join(headings)
        description = fix_whitespaces(description)
        text = "HEADINGS: " + description + "\n"
        for j in range(i, min(i + OVER_LAPPING, len(top_layer_divs))):
            text += "PARAGRAPH: " + top_layer_divs[j].text.strip() + "\n"
        text = fix_whitespaces(text)

        document = Document(
            page_content=text,
            metadata={"source": url, "description": description, "title": title, "text": description + "\n" + text}
        )
        print(description + "\n" + text)
        documents.append(document)
    return documents



#if __name__ == '__main__':
#    files = [f for f in listdir(PATH) if isfile(join(PATH, f))]
#    for file in files:
#        with open(f"{PATH}/{file}", "r") as f:
#            website = f.read()
#            save_website(website, file)
    





