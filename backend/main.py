from fastapi import FastAPI, Depends
from pydantic import BaseModel
from database import SessionLocal, Message
import openai
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime

from dotenv import load_dotenv
import os

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Настройка CORS, чтобы разрешить запросы с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Создание зависимости для подключения к базе данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UserMessage(BaseModel):
    content: str


@app.post("/api/message")
def send_message(msg: UserMessage, db: Session = Depends(get_db)):
    # Сохраняем сообщение пользователя в базу
    new_msg = Message(role="user", content=msg.content, timestamp=datetime.utcnow())
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    # Получаем всю историю из базы данных
    history = db.query(Message).order_by(Message.timestamp).all()
    conversation = [{"role": m.role, "content": m.content} for m in history]

    # Отправляем историю сообщений в OpenAI API
    response = openai.ChatCompletion.create(model="gpt-4o", messages=conversation)

    reply_content = response.choices[0].message.content

    # Сохраняем ответ GPT обратно в базу
    reply_msg = Message(
        role="assistant", content=reply_content, timestamp=datetime.utcnow()
    )
    db.add(reply_msg)
    db.commit()

    return {"reply": reply_content}


@app.get("/api/context")
def get_context(db: Session = Depends(get_db)):
    history = db.query(Message).order_by(Message.timestamp).all()
    conversation = [{"role": m.role, "content": m.content} for m in history]
    return {"context": conversation}


@app.get("/api/history")
def get_history(db: Session = Depends(get_db)):
    history = db.query(Message).order_by(Message.timestamp).all()
    return {
        "history": [
            {"id": m.id, "timestamp": m.timestamp, "role": m.role, "content": m.content}
            for m in history
        ]
    }
