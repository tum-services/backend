from langchain.document_loaders import WebBaseLoader
from bs4 import BeautifulSoup
import re
import os
from langchain.vectorstores import Pinecone
from langchain.embeddings import OpenAIEmbeddings

if os.environ.get("PINECONE_API_KEY", None) is None:
    raise Exception("Missing `PINECONE_API_KEY` environment variable.")

if os.environ.get("PINECONE_ENVIRONMENT", None) is None:
    raise Exception("Missing `PINECONE_ENVIRONMENT` environment variable.")

PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX", "langchain-test")

def save_documents(documents):
    vectorstore = Pinecone.from_documents(
        documents=documents, embedding=OpenAIEmbeddings(), index_name=PINECONE_INDEX_NAME
    )
    retriever = vectorstore.as_retriever()
    return retriever

def save_website(website, url):
    soup = BeautifulSoup(website, 'html.parser')
    documents = []
    paragraphs = soup.find_all("p")
    title = soup.find("title").text.strip()
    for paragraph in paragraphs:
        heading = paragraph.find_previous(re.compile('^h[1-6]$'))
        paragraph = paragraph.text.strip()
        if heading is not None:
            heading = heading.text.strip()
        document = Pinecone.Document(
            description=heading,
            source=url,
            text=paragraph,
            title=title
        )
        documents.append(document)
    return save_documents(documents)











