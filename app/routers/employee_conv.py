from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from ..models import Message, Conversation, ConversationSummary
from langchain.memory import ConversationSummaryMemory, ChatMessageHistory
from langchain.llms import OpenAI
from .wizard import wizards


router = APIRouter(
    prefix="/conversation",
    tags=["conversation"],
    responses={404: {"description": "Not found"}},
)


class MessageInput(BaseModel):
    text: str
    sender: str # User or Employee
    created: str
  

class ConversationInput(BaseModel):
    conversation: list[MessageInput]
    wizard_id: int
    wizard_anwsers: list[str]



@router.post("/", response_model=None)
async def new_conv(conv: ConversationInput) -> dict:
    c = Conversation()
    c.conversation = conv.conversation
    if wizards[conv.wizard_id] is None:
        raise HTTPException(status_code=404, detail="Wizard not found")
    
    if len(wizards[conv.wizard_id]) != len(conv.wizard_anwsers):
        raise HTTPException(status_code=404, detail="Wizard length not matching")

    chat_history = ChatMessageHistory()
    openai = OpenAI()
    for message in conv.conversation:
        if message.sender == "User":
            chat_history.add_user_message(message.text)
        else:
            chat_history.add_ai_message(message.text)

    summary = ConversationSummaryMemory.from_messages(llm=openai, chat_memory=chat_history, return_messages=True)

    con_summary = ConversationSummary()
    con_summary.summary = summary.buffer
    if conv.wizard_id is not None: 
        con_summary.wizard = []
        for i in range(len(conv.wizard_anwsers)):
            wiz_obj = wizards[conv.wizard_id][i]
            wiz = {}
            if wiz_obj["type"] == "text":
                wiz["question"] = wiz_obj["question"]
                wiz["answer"] = conv.wizard_anwsers[i]
            else:
                wiz["question"] = wiz_obj["question"]
                wiz["answer"] = wiz_obj["options"][int(conv.wizard_anwsers[i])]
            con_summary.wizard.append(wiz)

    c.save()
    con_summary.save()
    return con_summary.to_dict()
