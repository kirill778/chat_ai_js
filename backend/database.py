from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Создаем базовый класс для моделей
Base = declarative_base()

# Модель для чата
class Chat(Base):
    __tablename__ = 'chats'
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("Message", back_populates="chat")

# Модель для сообщений
class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey('chats.id'))
    text = Column(Text, nullable=False)
    sender = Column(String(10), nullable=False)  # 'user' или 'bot'
    timestamp = Column(DateTime, default=datetime.utcnow)
    chat = relationship("Chat", back_populates="messages")

# Создаем подключение к базе данных
DATABASE_URL = "postgresql://postgres:1234@localhost:5432/chatdb"
engine = create_engine(DATABASE_URL)

# Создаем таблицы
Base.metadata.create_all(engine)

# Создаем сессию
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
