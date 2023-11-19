import datetime
import json
import os
import requests
from operator import itemgetter
from typing import List, Tuple

from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.prompts.prompt import PromptTemplate
from langchain.schema import AIMessage, HumanMessage, format_document
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import (
    RunnableBranch,
    RunnableLambda,
    RunnableMap,
    RunnablePassthrough,
)
from langchain.vectorstores import Pinecone
from pydantic import BaseModel, Field

if os.environ.get("PINECONE_API_KEY", None) is None:
    raise Exception("Missing `PINECONE_API_KEY` environment variable.")

if os.environ.get("PINECONE_ENVIRONMENT", None) is None:
    raise Exception("Missing `PINECONE_ENVIRONMENT` environment variable.")

PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX", "langchain-test")

### Ingest code - you may need to run this the first time
# # Load
from langchain.document_loaders import WebBaseLoader

loader = WebBaseLoader("https://www.cit.tum.de/cit/startseite/")
data = loader.load()
#print(data)


# # Split

from langchain.text_splitter import RecursiveCharacterTextSplitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
all_splits = text_splitter.split_documents(data)

# # Add to vectorDB
#vectorstore = Pinecone.from_documents(
#    documents=all_splits, embedding=OpenAIEmbeddings(), index_name=PINECONE_INDEX_NAME
#)
#retriever = vectorstore.as_retriever()

vectorstore = Pinecone.from_existing_index(PINECONE_INDEX_NAME, OpenAIEmbeddings())
retriever = vectorstore.as_retriever()

# Condense a chat history and follow-up question into a standalone question
_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.
Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""  # noqa: E501
CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(_template)

# RAG answer synthesis prompt
template = """Answer the question only with regard to the Technical University of Munich and based only on the following context:
<context>
{context}
</context>"""
ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{question}"),
    ]
)

# Conversational Retrieval Chain
DEFAULT_DOCUMENT_PROMPT = PromptTemplate.from_template(template="{page_content}")


def _combine_documents(
    docs, document_prompt=DEFAULT_DOCUMENT_PROMPT, document_separator="\n\n"
):
    doc_strings = [format_document(doc, document_prompt) for doc in docs]
    return document_separator.join(doc_strings)


def _format_chat_history(chat_history: List[Tuple[str, str]]) -> List:
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer


# User input
class ChatHistory(BaseModel):
    chat_history: List[Tuple[str, str]] = Field(..., extra={"widget": {"type": "chat"}})
    question: str

# RAG Conversation Chain
# TODO: Add a branch for the case where the input is about the mensa menu of the day
  
is_mensa_chain = (
    PromptTemplate.from_template(
        template="""Given the following input, determine if the input is about the menu in the mensa.
Only answer with "yes" or "no".
Input: {question}
Answer:"""
    )
)

mensa_prompt = """Given the following input, answer the question based only on the following meal plan for the next week and the provided day:
<meal plan>
    {context}
</meal plan>
Current Day: {day}
"""

def create_date_string(weeks):
    days = []
    for week in weeks:
        for day in week["days"]:
            days.append(day)
    ret = ""
    for day in days:
        if day["date"] >= datetime.datetime.today().strftime("%Y-%m-%d"):
            reduced = ""
            for dish in day["dishes"]:
                reduced += dish["name"] + ", "
            ret += f"{day['date']}: {reduced[:-2]}\n\n"
    return ret
     

_search_query = RunnableBranch(
    # If input includes chat_history, we condense it with the follow-up question
    (
        RunnableLambda(lambda x: bool(x.get("chat_history"))).with_config(
            run_name="HasChatHistoryCheck"
        ),  # Condense follow-up question and chat into a standalone_question
        RunnablePassthrough.assign(
            chat_history=lambda x: _format_chat_history(x["chat_history"])
        )
        | CONDENSE_QUESTION_PROMPT
        | ChatOpenAI(temperature=0)
        | StrOutputParser(),
    ),
    # Else, we have no chat history, so just pass through the question
    RunnableLambda(itemgetter("question")),
)

# # If the input is about the mensa menu of the day, we search for the menu
#     (
#         is_mensa_chain
#         | ChatOpenAI(temperature=0)
#         | StrOutputParser()
#         # | RunnableLambda(lambda x: requests.get("https://en4gdf6m924yj.x.pipedream.net/" + x) or x)
#         | RunnableLambda(lambda x: "yes" in x.lower() or "mensa" in x["question"].lower()),
#         RunnableLambda(lambda _: requests.get("https://menu.tum.sexy/_next/data/b6k1mCvyQ9LCiKmF_t8Nd/de/mensa-garching.json?locale=de&id=mensa-garching"))
#         | RunnableLambda(lambda x: json.loads(x.text))
#         | RunnableLambda(lambda x: x["pageProps"]["foodPlaceMenu"]["weeks"])
#         | RunnableLambda(lambda x: create_date_string(x))
#         | RunnableLambda(lambda x: json.dumps(x, indent=4))
#         | RunnableLambda(lambda x: mensa_prompt.format(context=x, day=datetime.datetime.today().strftime("%d.%m.%Y")))
#         | RunnableLambda(lambda x: print(x) or x)
#         | ChatOpenAI(temperature=0)
#         | StrOutputParser(),
#     ),

_inputs = RunnableMap(
    {
        "question": lambda x: x["question"],
        "chat_history": lambda x: _format_chat_history(x["chat_history"]),
        "context": RunnableBranch(
            (
                is_mensa_chain
                | ChatOpenAI(temperature=0)
                | StrOutputParser()
                | RunnableLambda(lambda x: "yes" in x.lower() or "mensa" in x.lower()),
                RunnableLambda(lambda _: requests.get("https://menu.tum.sexy/_next/data/b6k1mCvyQ9LCiKmF_t8Nd/de/mensa-garching.json?locale=de&id=mensa-garching"))
                | RunnableLambda(lambda x: json.loads(x.text))
                | RunnableLambda(lambda x: x["pageProps"]["foodPlaceMenu"]["weeks"])
                | RunnableLambda(lambda x: create_date_string(x))
                | RunnableLambda(lambda x: json.dumps(x, indent=4))
                | RunnableLambda(lambda x: mensa_prompt.format(context=x, day=datetime.datetime.today().strftime("%Y-%m-%d")))
                | RunnableLambda(lambda x: print(x) or x)
            ),
            _search_query | retriever | _combine_documents
        ),
    }
).with_types(input_type=ChatHistory)

chain = _inputs | ANSWER_PROMPT | ChatOpenAI() | StrOutputParser()
