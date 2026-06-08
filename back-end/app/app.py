from fastapi import FastAPI

from app.routes import chat_router, conversation_router, document_router

app = FastAPI(title="IFormante API")

app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(document_router)

@app.get("/")
async def root():
    return {"message": "IFormante API ready"}
