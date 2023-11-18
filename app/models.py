from fireo.models import Model
from fireo.typedmodels import TypedModel
from fireo.fields import TextField, DateTime, ListField, IDField, ReferenceField, Field


class FileAttachment(Model):
    content = Field()
    name = TextField()
    created = DateTime(auto=True)
# class FileAttachment(TypedModel):
#     content: str
#     name: str
#     created: str

class Message(Model):
    text = TextField()
    sender = TextField() # User or Employee
    files = ListField(model=ReferenceField(FileAttachment, auto_load=True)) # List of file IDs
    created = DateTime(auto=True)
# class Message(TypedModel):
#     text: str
#     sender:str  # User or Employee
#     files: [str] = [] # List of file IDs
#     created: str

class Conversation(Model):
    employee_id = TextField()
    user_id = TextField()
    conversation = ListField(model=Message)
# class Conversation(TypedModel):
#     employee_id: str
#     user_id: str
#     conversation:[str]

class Wizard(Model):
    question = TextField()
    answer = TextField()

class ConversationSummary(Model):
    summary = TextField()
    wizard = ListField(model=Wizard)


