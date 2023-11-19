import datetime
import json
import os
import requests
from operator import itemgetter
from typing import List, Tuple
import regex as re
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
# print(data)


# # Split

from langchain.text_splitter import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
all_splits = text_splitter.split_documents(data)

# # Add to vectorDB
# vectorstore = Pinecone.from_documents(
#    documents=all_splits, embedding=OpenAIEmbeddings(), index_name=PINECONE_INDEX_NAME
# )
# retriever = vectorstore.as_retriever()

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

get_context_chain = (
    PromptTemplate.from_template(
        template="""You are a preprocessor for prompts to another GPT. You need to figure out, what the prompt is about. 
        Pick exactly one of the following options that describes the main idea based on the input prompt you will receive the best:
1: A meal served in the Mensa at a certain date
2: Study rooms
0: Something else

Answer with only with 0, 1 or 2. This is the prompt:".
        Input: {question}
        Answer:"""
    )
)

mensa_prompt = """This is the following meal plan for the next week:
<meal plan>
    {context}
</meal plan>
Current Day: {day}
"""

room_prompt = """Keep everything between <> exactly the same. This is current data about the availability of rooms:
<rooms>
    {context}
</rooms>
"""


def create_date_string(weeks, max_dishes=4):
    days = []
    for week in weeks:
        for day in week["days"]:
            days.append(day)
    ret = ""
    for day in days:
        if day["date"] >= datetime.datetime.today().strftime("%Y-%m-%d"):
            reduced = ""
            count = 0
            for dish in day["dishes"]:
                if count < max_dishes:
                    reduced += dish["name"] + ", "
                count += 1
            ret += f"{day['date']}: {reduced[:-2]}\n\n"
    print(ret)
    return ret

def create_room_data_string(room_data, max=15):
    ret = ""
    for room in room_data:
        if "Weihenstephan" not in room["gebaeude_name"]:
            ret += f"<{room['raum_nr_architekt']}>: {room['gebaeude_name']}({room['raum_name']})\n\n"
    return ret


mensa_data = json.loads(requests.get(
    "https://menu.tum.sexy/_next/data/b6k1mCvyQ9LCiKmF_t8Nd/de/mensa-garching.json?locale=de&id=mensa-garching").text)[
    "pageProps"]["foodPlaceMenu"]["weeks"]
mensa_data_str = json.dumps(create_date_string(mensa_data), indent=4)

datetime.datetime.today().strftime("%Y-%m-%d")

room_data = json.loads(requests.get("https://iris.asta.tum.de/api/").text)["raeume"]
room_data_str = json.dumps(create_room_data_string(room_data), indent=4)

PATTERN_MENSA = "mensa|essen|food|meal|lunch|dinner|breakfast|frühstück|mittagessen|abendessen|essen|kantine|cafeteria|restaurant|essen"
PATTERN_ROOM = "room|räume"

def get_mensa(text):
    if not re.search(PATTERN_MENSA, text, re.IGNORECASE):
        return None
    return mensa_prompt.format(context=mensa_data_str, day=datetime.datetime.today().strftime("%d.%m.%Y"))

def get_room(text):
    if not re.search(PATTERN_ROOM, text, re.IGNORECASE):
        return None
    return room_prompt.format(context=room_data_str)

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
        | ChatOpenAI(temperature=0, model="gpt-3.5-turbo-16k")
        | StrOutputParser(),
    ),
    # Else, we have no chat history, so just pass through the question
    RunnableLambda(itemgetter("question")),
)

def regex_content(text):
    mensa = get_mensa(text)
    if mensa is not None:
        return mensa
    room = get_room(text)
    if room is not None:
        return room
    return None

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
                RunnableLambda(lambda x: regex_content(x["question"]) is not None),
                RunnableLambda(lambda x: regex_content(x["question"]))),
            _search_query | retriever | _combine_documents
        ),
    }
).with_types(input_type=ChatHistory)


chain = _inputs | ANSWER_PROMPT | ChatOpenAI() | StrOutputParser()
