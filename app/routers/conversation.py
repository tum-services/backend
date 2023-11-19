from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from ..models import Message, Conversation, ConversationSummary, Wizard
from langchain.memory import ConversationSummaryMemory, ChatMessageHistory
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from .wizard import wizards


router = APIRouter(
    prefix="/conversation",
    tags=["conversation"],
    responses={404: {"description": "Not found"}},
)

prompt = """Summarize the following conversation between an user and the assistant:
            Focus on the needs of the user.
            {conversation}
            SUMMARY:
        """

prompt_name = """Summarize the following conversation between an user and the assistant into a title of a conversation:
            {conversation}
            TITLE:
        """

class MessageInput(BaseModel):
    content: str
    author: str # User or Bot
    created: str | None
  

class ConversationInput(BaseModel):
    conversation: list[MessageInput]
    wizard_id: int | None
    wizard_anwsers: list[str] | None




@router.post("/", response_model=None)
async def new_conv(conv: ConversationInput) -> dict:
    sumconv = ""
    # c = Conversation()
    # c.conversation = conv.conversation
    for message in conv.conversation:
        sumconv += f"{'Assistant' if message.author == 'bot' else 'User'}: {message.content}\n:"


    
    chain = LLMChain(llm=OpenAI(), prompt=PromptTemplate.from_template(prompt))
    summary = chain.run(sumconv)

    chain = LLMChain(llm=OpenAI(), prompt=PromptTemplate.from_template(prompt_name))
    title = chain.run(sumconv)

    con_summary = ConversationSummary()
    con_summary.summary = summary
    con_summary.title = title
    if conv.wizard_id is not None: 
        if wizards[conv.wizard_id] is None:
            raise HTTPException(status_code=404, detail="Wizard not found")
        if len(wizards[conv.wizard_id]) != len(conv.wizard_anwsers):
            raise HTTPException(status_code=404, detail="Wizard length not matching")
        con_summary.wizard = []
        for i in range(len(conv.wizard_anwsers)):
            wiz_obj = wizards[conv.wizard_id][i]
            wiz = Wizard()
            if wiz_obj["type"] == "text":
                wiz.question = wiz_obj["question"]
                wiz.answer = conv.wizard_anwsers[i]
            else:
                wiz.question = wiz_obj["question"]
                wiz.answer = wiz_obj["options"][int(conv.wizard_anwsers[i])]
            con_summary.wizard.append(wiz)
    # c.save()
    con_summary.save()
    return con_summary.to_dict()


@router.get("/")
async def get_convs():
    cs =  ConversationSummary.collection.fetch()
    return [c.to_dict() for c in cs]