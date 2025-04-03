# backend/app.py
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import requests
import json
import threading
from database import get_db, Chat, Message
from datetime import datetime

# Создаем экземпляр приложения Flask
app = Flask(__name__)

# Настраиваем CORS: разрешаем запросы с любого источника (*)
# В реальном приложении лучше указать конкретный адрес фронтенда
CORS(app)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:12b"

# Словарь для хранения активных запросов
active_requests = {}

def generate_stream(prompt, request_id):
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": True
            },
            stream=True
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line and request_id in active_requests:
                json_response = json.loads(line)
                if 'response' in json_response:
                    yield json_response['response']
                
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        yield "Извините, произошла ошибка при обработке вашего запроса."
    finally:
        if request_id in active_requests:
            del active_requests[request_id]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    request_id = data.get('request_id')
    chat_id = data.get('chat_id')  # Добавим параметр chat_id
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
        
    db = next(get_db())
    
    # Если chat_id не передан, создаем новый чат
    # Если передан, используем существующий
    if chat_id:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
    else:
        chat = Chat()
        db.add(chat)
        db.commit()
    
    # Сохраняем сообщение пользователя
    user_message = Message(
        chat_id=chat.id,
        text=message,
        sender='user',
        timestamp=datetime.utcnow()
    )
    db.add(user_message)
    db.commit()
    
    # Получаем историю сообщений для этого чата
    chat_history = db.query(Message).filter(
        Message.chat_id == chat.id
    ).order_by(Message.timestamp).all()
    
    # Формируем контекст из предыдущих сообщений
    context = ""
    for msg in chat_history[:-1]:  # Исключаем последнее сообщение, так как это текущий вопрос
        context += f"{'Пользователь' if msg.sender == 'user' else 'Ассистент'}: {msg.text}\n"
    
    # Формируем промпт с контекстом
    full_prompt = f"""История диалога:
{context}
Пользователь: {message}
Ассистент:"""
    
    active_requests[request_id] = True
    
    def generate_stream():
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": full_prompt,
                    "stream": True
                },
                stream=True
            )
            
            accumulated_text = ""
            for line in response.iter_lines():
                if line and request_id in active_requests:
                    json_response = json.loads(line)
                    if 'response' in json_response:
                        chunk = json_response['response']
                        accumulated_text += chunk
                        yield chunk
                        
            # Сохраняем ответ бота
            if accumulated_text:
                bot_message = Message(
                    chat_id=chat.id,
                    text=accumulated_text,
                    sender='bot',
                    timestamp=datetime.utcnow()
                )
                db.add(bot_message)
                db.commit()
                
        except Exception as e:
            print(f"Error: {e}")
            
        finally:
            if request_id in active_requests:
                del active_requests[request_id]
                
    return Response(stream_with_context(generate_stream()), content_type='text/plain')

@app.route('/api/stop', methods=['POST'])
def stop_generation():
    try:
        data = request.get_json()
        request_id = data.get('request_id', '')
        
        if request_id in active_requests:
            del active_requests[request_id]
            return jsonify({"status": "success"})
        
        return jsonify({"status": "not_found"}), 404
    
    except Exception as e:
        print(f"Error in stop endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/edit', methods=['POST'])
def edit():
    try:
        data = request.get_json()
        text = data.get('text', '')
        prompt = data.get('prompt', '')
        
        if not text or not prompt:
            return jsonify({"error": "Text and prompt are required"}), 400

        # Формируем промпт для редактирования
        edit_prompt = f"""Измени следующий текст согласно инструкции. Сохрани стиль и форматирование, измени только смысл согласно запросу.

Текст для изменения:
{text}

Инструкция по изменению:
{prompt}

Измени только указанный текст, сохранив его стиль и форматирование."""

        # Получаем ответ от модели
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": edit_prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        
        return jsonify({"response": response.json()["response"]})
    
    except Exception as e:
        print(f"Error in edit endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Добавим новый эндпоинт для получения истории чатов
@app.route('/api/chats', methods=['GET'])
def get_chats():
    db = next(get_db())
    chats = db.query(Chat).all()
    
    chat_list = []
    for chat in chats:
        messages = []
        for message in chat.messages:
            messages.append({
                'id': message.id,
                'text': message.text,
                'sender': message.sender,
                'timestamp': message.timestamp.isoformat()
            })
        chat_list.append({
            'id': chat.id,
            'created_at': chat.created_at.isoformat(),
            'messages': messages
        })
    
    return jsonify(chat_list)

# Запускаем сервер для разработки
if __name__ == '__main__':
    # debug=True включает автоматическую перезагрузку при изменениях
    # host='0.0.0.0' делает сервер доступным в локальной сети (не только с localhost)
    app.run(debug=True, host='0.0.0.0', port=5000) # Используем порт 5000 (или любой другой)