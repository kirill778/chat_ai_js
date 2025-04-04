# backend/app.py
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import requests
import json
import threading
from database import get_db, Chat, Message, Command
from datetime import datetime
import re
from typing import Optional
import subprocess
import sys

# Создаем экземпляр приложения Flask
app = Flask(__name__)

# Настраиваем CORS: разрешаем запросы с любого источника (*)
# В реальном приложении лучше указать конкретный адрес фронтенда
CORS(app)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:12b"

# Словарь для хранения активных запросов
active_requests = {}

def execute_command(command: Command, args: Optional[str] = None) -> str:
    """Выполняет команду в зависимости от её типа."""
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
            local_vars = {"args": args}
            exec(command.action_data, {}, local_vars)
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
        if message.lower().startswith(command.trigger.lower()):
            args = message[len(command.trigger):].strip()
            return True, command.trigger, args
    
    return False, None, None

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    request_id = data.get('request_id')
    chat_id = data.get('chat_id')
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
        
    db = next(get_db())
    
    # Проверяем, является ли сообщение командой
    is_command, trigger, args = check_for_commands(message)
    
    # Создаем или получаем чат
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
    
    # Если это команда, выполняем её
    if is_command and trigger:
        command = db.query(Command).filter(Command.trigger == trigger).first()
        if command:
            result = execute_command(command, args)
            
            # Сохраняем результат команды как сообщение бота
            bot_message = Message(
                chat_id=chat.id,
                text=f"Выполнена команда {trigger}: {args if args else ''}",
                sender='bot',
                timestamp=datetime.utcnow()
            )
            db.add(bot_message)
            db.commit()
            
            # Возвращаем результат с правильным Content-Type
            return Response(
                result,
                content_type='application/json'
            )
    
    # Если это не команда или команда не найдена, обрабатываем как обычное сообщение
    active_requests[request_id] = True
    
    def generate_stream():
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": message,
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
    try:
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
            chat_data = {
                'id': chat.id,
                'title': chat.title,
                'created_at': chat.created_at.isoformat(),
                'messages': messages
            }
            print(f"Chat data: {chat_data}")
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