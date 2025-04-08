# Чат с ИИ

Приложение чата с интеграцией различных моделей ИИ. Проект состоит из бэкенда на Flask и фронтенда на React.

## Требования для запуска

### Бэкенд (Python)

1. Python 3.8+ 
2. Библиотеки Python:
   - flask==3.0.2
   - flask-cors==4.0.0
   - requests==2.31.0
   - werkzeug==3.0.1
   - python-docx==0.8.11 (для обработки Word документов)
   - psycopg2-binary
   - SQLAlchemy

### Фронтенд (React) 

1. Node.js (рекомендуется 14+ или более новая)
2. npm или yarn
3. Зависимости:
   - React 19.1.0
   - lucide-react (установка с --legacy-peer-deps)

### Модели ИИ 

Для запуска требуется хотя бы одна из этих моделей:

1. **Ollama** (локальная модель):
   - Установить Ollama: https://ollama.com/download
   - Скачать модель: `ollama pull gemma3:12b`

2. **Внешние API** (настроены, но требуют рабочего интернет-подключения):
   - DeepSeek V3
   - Gemini 2.5 Pro
   - Claude 3.7 Sonnet

## Инструкции по установке

### Бэкенд:

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Фронтенд:

```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

## Особенности

- Конвертация Word документов в текст перед отправкой моделям
- Поддержка различных моделей ИИ
- Сохранение истории чатов в базе данных

## Устранение неполадок

1. При проблемах с библиотекой lucide-react:
   ```bash
   npm uninstall lucide-react
   npm install --save lucide-react --legacy-peer-deps
   ```

2. Если возникают проблемы с компиляцией фронтенда:
   ```bash
   npm cache clean --force
   npm rebuild
   npm start
   ``` 