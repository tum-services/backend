from fastapi import FastAPI, UploadFile
from fastapi.responses import RedirectResponse
from langserve import add_routes
from rag_conversation import chain as rag_conversation_chain
from langserve.client import RemoteRunnable
from fastapi.middleware.cors import CORSMiddleware
from .routers import conversation, file, wizard

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs") 

app.include_router(file.router)
app.include_router(conversation.router)
app.include_router(wizard.router)


# Edit this to add the chain you want to add
add_routes(app, rag_conversation_chain, path="/rag-conversation")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
