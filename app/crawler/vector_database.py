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


def save_chunks(documents):
    vectorstore = Pinecone.from_documents(
        documents=documents, embedding=OpenAIEmbeddings(), index_name=PINECONE_INDEX_NAME
    )
    retriever = vectorstore.as_retriever()
    return retriever


def get_chunk(website, url):
    soup = BeautifulSoup(website, 'html.parser')
    documents = []
    paragraphs = soup.find_all("p")

    title = soup.find("title").text.strip()
    for paragraph in paragraphs:
        description = paragraph.find_previous(re.compile('^h[1-6]$'))
        paragraph = paragraph.text.strip()
        if description is not None:
            description = description.text.strip()
        else:
            description = title
        document = Document(
            page_content=website,
            metadata={"source": url, "description": description, "title": title, "text": paragraph}
        )
        documents.append(document)
    return documents

#if __name__ == '__main__':
#    files = [f for f in listdir(PATH) if isfile(join(PATH, f))]
#    for file in files:
#        with open(f"{PATH}/{file}", "r") as f:
#            website = f.read()
#            save_website(website, file)
    





