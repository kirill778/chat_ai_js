# backend/app.py
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import requests
import json
import threading
from database import get_db, Chat, Message, Command
from datetime import datetime, timedelta
import re
from typing import Optional, List, Dict
import subprocess
import sys
import aiohttp
import os
import tempfile
from werkzeug.utils import secure_filename
import docx  # Import for Word document handling

# Создаем экземпляр приложения Flask
app = Flask(__name__)

# Настраиваем CORS: разрешаем запросы с любого источника (*)
# В реальном приложении лучше указать конкретный адрес фронтенда
CORS(app)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:12b"

# Словарь для хранения активных запросов
active_requests = {}

# Глобальная переменная для хранения системного промпта
SYSTEM_PROMPT = """"""

# Список доступных моделей
AVAILABLE_MODELS = {
    "gemma3:12b": {
        "name": "Gemma 3 12B",
        "provider": "ollama",
        "endpoint": "http://localhost:11434/api/generate",
        "max_tokens": 4096
    },
    "deepseek-v3": {
        "name": "DeepSeek V3",
        "provider": "hyperbolic",
        "endpoint": "https://api.hyperbolic.xyz/v1/chat/completions",
        "model_id": "deepseek-ai/DeepSeek-V3-0324",
        "max_tokens": 512,
        "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJraW5nMjI4NjY2QGdtYWlsLmNvbSIsImlhdCI6MTczMTUyMDIzM30.nQLMovda2N0X5U1dH2yJ_sJaYczHIMIzyte1onDdNm8"
    },
    "gemini-2.5-pro-preview-03-25": {
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "endpoint": "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-pro-preview-03-25:generateContent",
        "model_id": "gemini-2.5-pro-preview-03-25",
        "max_tokens": 2048,
        "api_key": "AIzaSyBM8dCaUfXBE3Yz8R263kslnFz9GfAoiFM"
    },
    "gemini-2.0-pro": {
        "name": "Gemini 2.0 Pro",
        "provider": "google",
        "endpoint": "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-pro:generateContent",
        "model_id": "gemini-2.0-pro",
        "max_tokens": 2048,
        "api_key": "AIzaSyBM8dCaUfXBE3Yz8R263kslnFz9GfAoiFM"
    },
    "claude-3-7-sonnet": {
        "name": "Claude 3.7 Sonnet",
        "provider": "langdock",
        "endpoint": "https://api.langdock.com/anthropic/eu/v1/messages",
        "model_id": "claude-3-7-sonnet-20250219",
        "max_tokens": 4096,
        "api_key": "sk-dC2KBHGN_2vWk7SVpIZVpq81X3vwMzt7iCFzZjpA_o4OMPQ_RUjAqjOVi1vDW2Zhit1nf1ekfmWB0F983QcLKg"
    }
}

# Функция для конвертации Word документа в текст
def convert_docx_to_text(filepath):
    """Convert a Word document to text."""
    try:
        doc = docx.Document(filepath)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        print(f"Error converting Word document: {str(e)}")
        return None

# Функция для определения типа файла и его обработки
def process_file(filepath, filename):
    """Process a file based on its extension and return its text content."""
    file_extension = os.path.splitext(filename)[1].lower()
    
    if file_extension == '.docx':
        return convert_docx_to_text(filepath)
    elif file_extension == '.txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    else:
        # Для других типов файлов можно добавить дополнительные обработчики
        return None

def execute_command(command: Command, args: Optional[str] = None) -> str:
    """Выполняет команду в зависимости от её типа."""
    print(f"Executing command: {command.trigger}, type: {command.action_type}")
    
    if not command.is_active:
        return "Эта команда отключена."

    try:
        if command.action_type == "notification":
            # Для уведомлений возвращаем специальный формат
            return json.dumps({
                "type": "notification",
                "content": command.action_data.format(args=args if args else "")
            })
        elif command.action_type == "script":
            # Для скриптов выполняем код Python
            if command.trigger.lower() == "открой редактор письма":
                print("Executing 'Открой редактор письма' command")
                result = json.dumps({
                    "type": "write_letter",
                    "content": "Открываю редактор для написания письма"
                })
                print(f"Command result: {result}")
                return result
            else:
                local_vars = {"args": args}
                exec(command.action_data, globals(), local_vars)
                return json.dumps({
                    "type": "script_result",
                    "content": local_vars.get("result", "Скрипт выполнен успешно")
                })
        else:
            return json.dumps({
                "type": "error",
                "content": f"Неизвестный тип команды: {command.action_type}"
            })
    except Exception as e:
        return json.dumps({
            "type": "error",
            "content": f"Ошибка при выполнении команды: {str(e)}"
        })

def check_for_commands(message: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Проверяет, является ли сообщение командой."""
    db = next(get_db())
    commands = db.query(Command).filter(Command.is_active == True).all()
    
    for command in commands:
        if message.lower() == command.trigger.lower():
            return True, command.trigger, None
        elif message.lower().startswith(command.trigger.lower()):
            args = message[len(command.trigger):].strip()
            return True, command.trigger, args
    
    return False, None, None

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    model = data.get('model', 'gemma3:12b')
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
        
    db = next(get_db())
    
    # Проверяем, является ли сообщение командой
    is_command, trigger, args = check_for_commands(message)
    
    # Создаем или получаем чат
    if data.get('chat_id'):
        chat = db.query(Chat).filter(Chat.id == data['chat_id']).first()
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
    
    # Если это команда, выполняем её
    if is_command and trigger:
        command = db.query(Command).filter(Command.trigger == trigger).first()
        if command:
            result = execute_command(command, args)
            
            # Сохраняем результат команды как сообщение бота
            bot_message = Message(
                chat_id=chat.id,
                text=result,
                sender='bot',
                timestamp=datetime.utcnow()
            )
            db.add(bot_message)
            db.commit()
            
            return jsonify({
                'chat_id': chat.id,
                'content': result
            })
    
    # Получаем историю сообщений для контекста
    chat_messages = db.query(Message).filter(
        Message.chat_id == chat.id
    ).order_by(Message.timestamp.asc()).all()
    
    # Формируем историю сообщений для API
    messages_history = []
    for msg in chat_messages:
        messages_history.append({
            'role': 'user' if msg.sender == 'user' else 'assistant',
            'content': msg.text
        })
    
    # Добавляем текущее сообщение
    messages_history.append({
        'role': 'user',
        'content': message
    })
    
    # Получаем конфигурацию модели
    model_config = AVAILABLE_MODELS.get(model)
    if not model_config:
        return jsonify({'error': 'Model not found'}), 404
    
    try:
        if model_config['provider'] == 'hyperbolic':
            # Формируем запрос для Hyperbolic API
            api_data = {
                'messages': messages_history,
                'model': model_config['model_id'],
                'max_tokens': model_config['max_tokens'],
                'temperature': 0.1,
                'top_p': 0.9
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {model_config["api_key"]}'
            }
            
            print(f"Sending request to Hyperbolic API: {json.dumps(api_data)}")
            
            response = requests.post(
                model_config['endpoint'],
                headers=headers,
                json=api_data,
                timeout=30
            )
            
            print(f"Hyperbolic API response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Hyperbolic API error response: {response.text}")
                return jsonify({'error': f'API request failed with status {response.status_code}: {response.text}'}), 500
                
            response_data = response.json()
            print(f"Hyperbolic API response data: {json.dumps(response_data)}")
            
            bot_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not bot_response:
                return jsonify({'error': 'Empty response from API'}), 500
            
        elif model_config['provider'] == 'langdock':
            # Формируем запрос для Langdock API (Claude)
            api_data = {
                'model': model_config['model_id'],
                'messages': messages_history,
                'max_tokens': model_config['max_tokens'],
                'temperature': 0.7,
                'stream': False
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {model_config["api_key"]}'
            }
            
            print(f"Sending request to Langdock API: {json.dumps(api_data)}")
            
            response = requests.post(
                model_config['endpoint'],
                headers=headers,
                json=api_data,
                timeout=60
            )
            
            print(f"Langdock API response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Langdock API error response: {response.text}")
                return jsonify({'error': f'API request failed with status {response.status_code}: {response.text}'}), 500
                
            response_data = response.json()
            print(f"Langdock API response data: {json.dumps(response_data)}")
            
            bot_response = response_data.get('content', [{}])[0].get('text', '')
            if not bot_response:
                return jsonify({'error': 'Empty response from API'}), 500
            
        else:
            # Формируем единый текст с историей сообщений и системным промптом
            full_prompt = SYSTEM_PROMPT + "\n\nИстория сообщений:\n"
            
            # Добавляем всю историю сообщений в текстовом формате
            for msg in chat_messages:
                sender = "Пользователь" if msg.sender == "user" else "Ассистент"
                full_prompt += f"{sender}: {msg.text}\n"
            
            # Добавляем текущее сообщение
            full_prompt += f"\nПользователь: {message}\n\nАссистент:"
            
            # Отправляем запрос к модели с полным контекстом
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "num_ctx": 4096,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 2048
                    }
                }
            )
            
            if response.status_code != 200:
                return jsonify({'error': 'API request failed'}), 500
                
            response_data = response.json()
            bot_response = response_data.get('response', '')
            
        # Сохраняем ответ бота
        bot_message = Message(
            chat_id=chat.id,
            text=bot_response,
            sender='bot',
            timestamp=datetime.utcnow()
        )
        db.add(bot_message)
        db.commit()
        
        return jsonify({
            'chat_id': chat.id,
            'content': bot_response
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")  # Добавляем логирование ошибки
        return jsonify({'error': str(e)}), 500

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
    try:
        db = next(get_db())
        chats = db.query(Chat).all()
        
        chat_list = []
        for chat in chats:
            # Получаем сообщения, сортируя их по timestamp
            messages = db.query(Message).filter(
                Message.chat_id == chat.id
            ).order_by(Message.timestamp.asc()).all()
            
            messages_list = []
            for message in messages:
                messages_list.append({
                    'id': message.id,
                    'text': message.text,
                    'sender': message.sender,
                    'timestamp': message.timestamp.isoformat()
                })
            
            chat_data = {
                'id': chat.id,
                'title': chat.title,
                'created_at': chat.created_at.isoformat(),
                'messages': messages_list
            }
            chat_list.append(chat_data)
        
        return jsonify(chat_list)
    except Exception as e:
        print(f"Error getting chats: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API для управления командами
@app.route('/api/commands', methods=['GET'])
def get_commands():
    """Получить список всех команд"""
    db = next(get_db())
    commands = db.query(Command).all()
    return jsonify([{
        'id': cmd.id,
        'trigger': cmd.trigger,
        'description': cmd.description,
        'action_type': cmd.action_type,
        'action_data': cmd.action_data,
        'is_active': cmd.is_active,
        'created_at': cmd.created_at.isoformat(),
        'updated_at': cmd.updated_at.isoformat()
    } for cmd in commands])

@app.route('/api/commands', methods=['POST'])
def create_command():
    """Создать новую команду"""
    data = request.json
    if not all(k in data for k in ['trigger', 'action_type', 'action_data']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    db = next(get_db())
    command = Command(
        trigger=data['trigger'],
        description=data.get('description'),
        action_type=data['action_type'],
        action_data=data['action_data'],
        is_active=data.get('is_active', True)
    )
    
    try:
        db.add(command)
        db.commit()
        db.refresh(command)
        return jsonify({
            'id': command.id,
            'trigger': command.trigger,
            'description': command.description,
            'action_type': command.action_type,
            'action_data': command.action_data,
            'is_active': command.is_active,
            'created_at': command.created_at.isoformat(),
            'updated_at': command.updated_at.isoformat()
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/commands/<int:command_id>', methods=['PUT'])
def update_command(command_id):
    """Обновить существующую команду"""
    data = request.json
    db = next(get_db())
    command = db.query(Command).filter(Command.id == command_id).first()
    
    if not command:
        return jsonify({'error': 'Command not found'}), 404
    
    for key in ['trigger', 'description', 'action_type', 'action_data', 'is_active']:
        if key in data:
            setattr(command, key, data[key])
    
    try:
        db.commit()
        return jsonify({
            'id': command.id,
            'trigger': command.trigger,
            'description': command.description,
            'action_type': command.action_type,
            'action_data': command.action_data,
            'is_active': command.is_active,
            'created_at': command.created_at.isoformat(),
            'updated_at': command.updated_at.isoformat()
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/commands/<int:command_id>', methods=['DELETE'])
def delete_command(command_id):
    """Удалить команду"""
    db = next(get_db())
    command = db.query(Command).filter(Command.id == command_id).first()
    
    if not command:
        return jsonify({'error': 'Command not found'}), 404
    
    try:
        db.delete(command)
        db.commit()
        return jsonify({'message': 'Command deleted successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/chats', methods=['POST'])
def create_chat():
    try:
        db = next(get_db())
        data = request.get_json(force=True, silent=True) or {}
        title = data.get('title', 'Новый чат')
        
        chat = Chat(title=title)
        db.add(chat)
        db.commit()
        
        return jsonify({
            'id': chat.id,
            'title': chat.title,
            'created_at': chat.created_at.isoformat(),
            'messages': []
        })
    except Exception as e:
        print(f"Error creating chat: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/chats/<int:chat_id>', methods=['PUT'])
def update_chat(chat_id):
    try:
        db = next(get_db())
        data = request.get_json(force=True, silent=True) or {}
        
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
            
        if 'title' in data:
            chat.title = data['title']
            db.commit()
            
        return jsonify({
            'id': chat.id,
            'title': chat.title,
            'created_at': chat.created_at.isoformat(),
            'messages': []
        })
    except Exception as e:
        print(f"Error updating chat: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/chats/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    try:
        db = next(get_db())
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
            
        db.delete(chat)
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting chat: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/system-prompt', methods=['GET'])
def get_system_prompt():
    """Получить текущий системный промпт"""
    return jsonify({'prompt': SYSTEM_PROMPT})

@app.route('/api/system-prompt', methods=['POST'])
def update_system_prompt():
    """Обновить системный промпт"""
    global SYSTEM_PROMPT
    data = request.get_json()
    if 'prompt' not in data:
        return jsonify({'error': 'No prompt provided'}), 400
    
    SYSTEM_PROMPT = data['prompt']
    return jsonify({'success': True})

@app.route('/api/init-commands', methods=['POST'])
def init_commands():
    """Инициализация команд в базе данных"""
    db = next(get_db())
    
    # Список команд для инициализации
    commands = [
        Command(
            trigger="help",
            description="Показать список доступных команд",
            action_type="script",
            action_data="result = 'Доступные команды:\\n' + '\\n'.join([f'- {cmd.trigger}: {cmd.description}' for cmd in db.query(Command).all()])",
            is_active=True
        ),
        Command(
            trigger="Открой редактор письма",
            description="Открывает редактор для написания письма",
            action_type="script",
            action_data="result = 'Открываю редактор для написания письма'",
            is_active=True
        )
    ]
    
    # Удаляем старые команды и добавляем новые
    db.query(Command).delete()
    for command in commands:
        db.add(command)
    db.commit()
    
    return jsonify({"status": "success"})

@app.route('/api/generate-letter', methods=['POST'])
def generate_letter():
    """Генерация письма с помощью модели"""
    data = request.get_json()
    letter_type = data.get('type', 'business')
    content = data.get('content', '')

    # Формируем промпт для генерации письма
    letter_prompts = {
        'business': """Напиши деловое письмо, используя следующие требования:
1. Официальный стиль
2. Четкая структура
3. Профессиональная лексика
4. Вежливое обращение и заключение

Контекст или описание: {content}""",

        'personal': """Напиши личное письмо, используя следующие требования:
1. Дружелюбный тон
2. Неформальный стиль
3. Эмоциональность
4. Личные детали и воспоминания

Контекст или описание: {content}""",

        'complaint': """Напиши письмо-жалобу, используя следующие требования:
1. Конструктивный тон
2. Четкое описание проблемы
3. Конкретные факты
4. Ясные требования или просьбы

Контекст или описание: {content}""",

        'gratitude': """Напиши благодарственное письмо, используя следующие требования:
1. Искренний тон
2. Конкретные причины благодарности
3. Теплые пожелания
4. Выражение признательности

Контекст или описание: {content}""",

        'invitation': """Напиши письмо-приглашение, используя следующие требования:
1. Приветливый тон
2. Четкие детали мероприятия
3. Информация о времени и месте
4. RSVP (просьба ответить)

Контекст или описание: {content}"""
    }

    prompt = letter_prompts.get(letter_type, letter_prompts['business']).format(content=content)

    try:
        # Отправляем запрос к модели
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 2048
                }
            }
        )
        
        result = response.json()
        generated_text = result.get('response', '')
        
        return jsonify({
            'text': generated_text,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error generating letter: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    return jsonify({
        "models": [
            {
                "id": model_id,
                "name": config["name"],
                "max_tokens": config["max_tokens"]
            }
            for model_id, config in AVAILABLE_MODELS.items()
        ]
    })

@app.route('/api/check-commands', methods=['GET'])
def check_commands():
    """Проверка доступных команд"""
    db = next(get_db())
    commands = db.query(Command).all()
    return jsonify([{
        'id': cmd.id,
        'trigger': cmd.trigger,
        'description': cmd.description,
        'action_type': cmd.action_type,
        'action_data': cmd.action_data,
        'is_active': cmd.is_active
    } for cmd in commands])

@app.route('/api/process-document', methods=['POST'])
def process_document():
    """Process an uploaded document along with a prompt."""
    if 'document' not in request.files:
        return jsonify({'error': 'No document provided'}), 400
    
    file = request.files['document']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    # Get prompt and model from the form data
    prompt = request.form.get('prompt', '')
    model = request.form.get('model', 'gemma3:12b')
    chat_id = request.form.get('chat_id')
    
    # Save the file temporarily
    temp_dir = tempfile.gettempdir()
    filename = secure_filename(file.filename)
    filepath = os.path.join(temp_dir, filename)
    file.save(filepath)
    
    db = next(get_db())
    
    # Create or get chat
    if chat_id:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
    else:
        chat = Chat()
        db.add(chat)
        db.commit()
    
    try:
        # Process the file based on its type
        file_content = process_file(filepath, filename)
        
        if file_content is None:
            return jsonify({'error': 'Unsupported file format or error processing file'}), 400
        
        # Create combined message with document content and prompt
        combined_message = f"Document: {filename}\n\n{file_content}\n\nPrompt: {prompt}"
        
        # Save user message (just the prompt part)
        user_message = Message(
            chat_id=chat.id,
            text=f"[Document: {filename}] {prompt}",
            sender='user',
            timestamp=datetime.utcnow()
        )
        db.add(user_message)
        db.commit()
        
        # Get model configuration
        model_config = AVAILABLE_MODELS.get(model)
        if not model_config:
            return jsonify({'error': 'Model not found'}), 404
        
        # Get the response from the model (reuse existing model handling code)
        # Create a simplified context with just this message
        messages_history = [{
            'role': 'user',
            'content': combined_message
        }]
        
        # Process with model using the same approach as in chat endpoint
        if model_config['provider'] == 'hyperbolic':
            # Use Hyperbolic API
            api_data = {
                'messages': messages_history,
                'model': model_config['model_id'],
                'max_tokens': model_config['max_tokens'],
                'temperature': 0.1,
                'top_p': 0.9
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {model_config["api_key"]}'
            }
            
            response = requests.post(
                model_config['endpoint'],
                headers=headers,
                json=api_data,
                timeout=60  # Increased timeout for document processing
            )
            
            if response.status_code != 200:
                return jsonify({'error': f'API request failed with status {response.status_code}: {response.text}'}), 500
                
            response_data = response.json()
            bot_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
        elif model_config['provider'] == 'langdock':
            # Use Langdock API (Claude)
            api_data = {
                'model': model_config['model_id'],
                'messages': messages_history,
                'max_tokens': model_config['max_tokens']
            }
            
            headers = {
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01',
                'x-api-key': model_config['api_key']
            }
            
            response = requests.post(
                model_config['endpoint'],
                headers=headers,
                json=api_data,
                timeout=60
            )
            
            if response.status_code != 200:
                return jsonify({'error': f'API request failed with status {response.status_code}: {response.text}'}), 500
                
            response_data = response.json()
            bot_response = response_data.get('content', [{}])[0].get('text', '')
            
        elif model_config['provider'] == 'google':
            # Use Google Gemini API
            api_data = {
                'contents': [{'parts': [{'text': combined_message}]}],
                'generationConfig': {
                    'temperature': 0.1,
                    'topK': 1,
                    'topP': 0.9,
                    'maxOutputTokens': model_config['max_tokens'],
                }
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{model_config['endpoint']}?key={model_config['api_key']}",
                headers=headers,
                json=api_data,
                timeout=60
            )
            
            if response.status_code != 200:
                return jsonify({'error': f'API request failed with status {response.status_code}: {response.text}'}), 500
                
            response_data = response.json()
            bot_response = response_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            
        elif model_config['provider'] == 'ollama':
            # Use Ollama API
            api_data = {
                'model': model,
                'prompt': combined_message,
                'stream': False,
                'temperature': 0.1,
                'top_p': 0.9
            }
            
            response = requests.post(
                model_config['endpoint'],
                json=api_data,
                timeout=60
            )
            
            if response.status_code != 200:
                return jsonify({'error': f'API request failed with status {response.status_code}: {response.text}'}), 500
                
            response_data = response.json()
            bot_response = response_data.get('response', '')
        
        else:
            return jsonify({'error': f'Unsupported model provider: {model_config["provider"]}'}), 500
        
        # Save bot response
        if bot_response:
            bot_message = Message(
                chat_id=chat.id,
                text=bot_response,
                sender='bot',
                timestamp=datetime.utcnow()
            )
            db.add(bot_message)
            db.commit()
        
        return jsonify({
            'chat_id': chat.id,
            'response': bot_response
        })
    
    except Exception as e:
        return jsonify({'error': f'Error processing document: {str(e)}'}), 500
    
    finally:
        # Clean up the temporary file
        if os.path.exists(filepath):
            os.remove(filepath)

# Запускаем сервер для разработки
if __name__ == '__main__':
    # Создаем базовую команду для уведомлений при первом запуске
    db = next(get_db())
    if not db.query(Command).filter(Command.trigger == "Уведомление").first():
        notification_command = Command(
            trigger="Уведомление",
            description="Отправляет уведомление с указанным текстом",
            action_type="notification",
            action_data="{args}",
            is_active=True
        )
        db.add(notification_command)
        db.commit()
    
    # debug=True включает автоматическую перезагрузку при изменениях
    # host='0.0.0.0' делает сервер доступным в локальной сети (не только с localhost)
    app.run(debug=True, host='0.0.0.0', port=5000) # Используем порт 5000 (или любой другой)