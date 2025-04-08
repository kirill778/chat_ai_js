import React, { useState, useRef, useEffect } from 'react';
import './Chat.css';
import Notification from './Notification';
import TextEditor from './TextEditor';

const API_URL = 'http://localhost:5000';

const DeleteIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M1.75 3.5H12.25M5.25 1.75H8.75M5.25 12.25V6.125M8.75 12.25V6.125" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M2.625 3.5L3.0625 10.5C3.0625 11.4665 3.8585 12.25 4.8125 12.25H9.1875C10.1415 12.25 10.9375 11.4665 10.9375 10.5L11.375 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gpt-3.5-turbo');
  const [availableModels, setAvailableModels] = useState([]);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [editingMessage, setEditingMessage] = useState(null);
  const [editPrompt, setEditPrompt] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [currentRequestId, setCurrentRequestId] = useState('');
  const [currentChatId, setCurrentChatId] = useState(null);
  const [notification, setNotification] = useState(null);
  const [chats, setChats] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const editButtonRef = useRef(null);
  const abortControllerRef = useRef(null);
  const [editingTitle, setEditingTitle] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [showTextEditor, setShowTextEditor] = useState(false);
  const [availableCommands, setAvailableCommands] = useState([]);
  const [showCommands, setShowCommands] = useState(false);

  // Загрузка истории чатов при монтировании
  useEffect(() => {
    fetchChats();
    fetchSystemPrompt();
    checkAvailableCommands();
  }, []);

  // Загрузка доступных моделей при монтировании компонента
  useEffect(() => {
    fetch(`${API_URL}/api/models`)
      .then(response => response.json())
      .then(data => {
        setAvailableModels(data.models);
      })
      .catch(error => console.error('Error loading models:', error));
  }, []);

  const fetchChats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/chats`);
      const data = await response.json();
      setChats(data);
      
      // Если есть чаты, выбираем последний
      if (data.length > 0) {
        const lastChat = data[data.length - 1];
        setCurrentChatId(lastChat.id);
        setMessages(lastChat.messages);
      }
    } catch (error) {
      console.error('Error fetching chats:', error);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  // Фокус на поле ввода при загрузке
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const stopGeneration = async (e) => {
    e.preventDefault();
    if (currentRequestId) {
      try {
        await fetch(`${API_URL}/api/stop`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ request_id: currentRequestId }),
        });
      } catch (error) {
        console.error('Error stopping generation:', error);
      }
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    if (currentStreamingMessage.trim()) {
      const botMessage = {
        text: currentStreamingMessage.trim(),
        sender: 'bot',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, botMessage]);
    }
    
    setIsLoading(false);
    setCurrentStreamingMessage('');
    setCurrentRequestId('');
  };

  const handleTextSelection = (e, messageIndex) => {
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();
    
    if (selectedText) {
      setSelectedText(selectedText);
      setEditingMessage(messageIndex);
      setIsEditing(true);
      
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const button = editButtonRef.current;
      
      if (button) {
        button.style.top = `${rect.top - 40}px`;
        button.style.left = `${rect.left + (rect.width / 2)}px`;
        button.style.display = 'block';
      }
    } else {
      setIsEditing(false);
      if (editButtonRef.current) {
        editButtonRef.current.style.display = 'none';
      }
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editPrompt.trim() || !selectedText) return;

    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/edit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: selectedText,
          prompt: editPrompt
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      setMessages(prev => prev.map((msg, index) => {
        if (index === editingMessage) {
          const newText = msg.text.replace(selectedText, data.response);
          return { ...msg, text: newText };
        }
        return msg;
      }));

      setSelectedText('');
      setEditPrompt('');
      setIsEditing(false);
      if (editButtonRef.current) {
        editButtonRef.current.style.display = 'none';
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Добавляем функцию форматирования времени
  const formatMessageTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = {
        text: input,
        sender: 'user',
        timestamp: new Date().toISOString(),
        id: Date.now()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
        const response = await fetch(`${API_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: input,
                model: selectedModel,
                chat_id: currentChatId
            }),
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }

        // Parse the content if it's a JSON string
        let parsedContent;
        try {
            parsedContent = typeof data.content === 'string' ? JSON.parse(data.content) : data.content;
            console.log('Parsed content:', parsedContent);
        } catch (e) {
            console.error('Error parsing content:', e);
            parsedContent = { type: 'text', content: data.content };
        }

        // Handle different response types
        if (parsedContent.type === 'write_letter') {
            console.log('Opening letter editor');
            handleWriteLetter();
            return;
        }

        const botMessage = {
            text: parsedContent.content,
            sender: 'bot',
            timestamp: new Date().toISOString(),
            id: Date.now()
        };

        setMessages(prev => [...prev, botMessage]);
    } catch (error) {
        console.error('Error:', error);
        const errorMessage = {
            text: `Error: ${error.message}`,
            sender: 'error',
            timestamp: new Date().toISOString(),
            id: Date.now()
        };
        setMessages(prev => [...prev, errorMessage]);
    } finally {
        setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const createNewChat = async () => {
    try {
      const response = await fetch(`${API_URL}/api/chats`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      const newChat = await response.json();
      setChats(prev => [newChat, ...prev]);
      setCurrentChatId(newChat.id);
      setMessages([]);
    } catch (error) {
      console.error('Error creating new chat:', error);
    }
  };

  const handleSelectChat = (chat) => {
    setCurrentChatId(chat.id);
    // Сортируем сообщения по timestamp
    if (chat.messages && chat.messages.length > 0) {
        const sortedMessages = [...chat.messages].sort((a, b) => {
            const timeA = new Date(a.timestamp).getTime();
            const timeB = new Date(b.timestamp).getTime();
            return timeA - timeB;
        });
        setMessages(sortedMessages);
    } else {
        setMessages([]);
    }
  };

  const handleTitleDoubleClick = (chat) => {
    setEditingTitle(chat.id);
    setEditTitle(chat.title);
  };
  
  const handleTitleSave = async (chatId) => {
    try {
      const response = await fetch(`${API_URL}/api/chats/${chatId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: editTitle }),
      });
      
      if (response.ok) {
        const updatedChat = await response.json();
        setChats(chats.map(chat => 
          chat.id === chatId ? { ...chat, title: updatedChat.title } : chat
        ));
      }
    } catch (error) {
      console.error('Error updating chat title:', error);
    }
    setEditingTitle(null);
  };
  
  const handleTitleKeyPress = (e, chatId) => {
    if (e.key === 'Enter') {
      handleTitleSave(chatId);
    } else if (e.key === 'Escape') {
      setEditingTitle(null);
    }
  };

  const handleDeleteChat = async (e, chatId) => {
    e.stopPropagation(); // Предотвращаем всплытие события к родительскому элементу
    
    if (!window.confirm('Вы уверены, что хотите удалить этот чат?')) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/chats/${chatId}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setChats(chats.filter(chat => chat.id !== chatId));
        if (currentChatId === chatId) {
          setCurrentChatId(null);
          setMessages([]);
        }
      }
    } catch (error) {
      console.error('Error deleting chat:', error);
    }
  };

  // Функция для получения системного промпта
  const fetchSystemPrompt = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/system-prompt');
      const data = await response.json();
      setSystemPrompt(data.prompt);
    } catch (error) {
      console.error('Error fetching system prompt:', error);
    }
  };

  // Функция для сохранения системного промпта
  const saveSystemPrompt = async () => {
    try {
      await fetch('http://localhost:5000/api/system-prompt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: systemPrompt }),
      });
      setShowSettingsModal(false);
    } catch (error) {
      console.error('Error saving system prompt:', error);
    }
  };

  // Обработчик команды написания письма
  const handleWriteLetter = () => {
    console.log('handleWriteLetter called, setting showTextEditor to true');
    setShowTextEditor(true);
  };

  // Обработчик сохранения письма
  const handleSaveLetter = (text) => {
    // Устанавливаем текст в поле ввода
    setInput(text);
    // Закрываем редактор
    setShowTextEditor(false);
    // Фокусируемся на поле ввода
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  // Обработчик команд
  const handleCommand = (command) => {
    if (command === 'write_letter') {
      handleWriteLetter();
    }
    // ... обработка других команд ...
  };

  // Функция для проверки доступных команд
  const checkAvailableCommands = async () => {
    try {
      const response = await fetch(`${API_URL}/api/check-commands`);
      if (response.ok) {
        const commands = await response.json();
        console.log('Available commands:', commands);
        setAvailableCommands(commands);
      }
    } catch (error) {
      console.error('Error checking commands:', error);
    }
  };

  // Функция для реинициализации команд
  const reinitializeCommands = async () => {
    try {
      const response = await fetch(`${API_URL}/api/init-commands`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      if (response.ok) {
        console.log('Commands reinitialized successfully');
        checkAvailableCommands(); // Обновляем список команд
      }
    } catch (error) {
      console.error('Error reinitializing commands:', error);
    }
  };

  return (
    <div className="chat-app">
      <div className="chat-sidebar">
        <button className="new-chat-button" onClick={createNewChat}>
          + Новый чат
        </button>
        <div className="chat-list">
          {chats.map(chat => (
            <div 
              key={chat.id} 
              className={`chat-item ${currentChatId === chat.id ? 'active' : ''}`}
              onClick={() => handleSelectChat(chat)}
            >
              <div className="chat-item-content">
                {editingTitle === chat.id ? (
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => handleTitleSave(chat.id)}
                    onKeyDown={(e) => handleTitleKeyPress(e, chat.id)}
                    autoFocus
                    className="chat-title-input"
                  />
                ) : (
                  <div 
                    className="chat-title" 
                    onDoubleClick={() => handleTitleDoubleClick(chat)}
                  >
                    {chat.title || 'Новый чат'}
                  </div>
                )}
                <div className="chat-date">
                  {new Date(chat.created_at).toLocaleDateString()}
                </div>
              </div>
              <button 
                className="delete-chat-button"
                onClick={(e) => handleDeleteChat(e, chat.id)}
                title="Удалить чат"
              >
                <DeleteIcon />
              </button>
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <button 
            className="settings-button"
            onClick={() => setShowSettingsModal(true)}
            title="Настройки системного промпта"
          >
            ⚙️ Настройки промпта
          </button>
        </div>
      </div>
      <div className="chat-container">
        <div className="model-selector">
          <label htmlFor="model-select">Select Model: </label>
          <select
            id="model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {availableModels.map(model => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </div>
        <div className="messages">
          {messages.map((message, index) => (
            <div 
              key={`${message.id || index}-${message.timestamp}`}
              className={`message ${message.sender}`}
              onMouseUp={(e) => handleTextSelection(e, index)}
            >
              <div className="message-content">
                {message.text}
              </div>
              <div className="message-timestamp">
                {formatMessageTime(message.timestamp)}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                <span className="typing-indicator">...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        {isEditing && (
          <form className="edit-form" onSubmit={handleEditSubmit}>
            <input
              type="text"
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              placeholder="Введите инструкцию для редактирования"
            />
            <button type="submit">Применить</button>
          </form>
        )}
        <form className="input-form" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Введите сообщение..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading}>
            Отправить
          </button>
        </form>
      </div>
      {notification && <Notification {...notification} />}
      <button 
        ref={editButtonRef} 
        className="edit-button"
        style={{ display: 'none' }}
        onClick={() => setIsEditing(true)}
      >
        Редактировать
      </button>

      {/* Кнопка для отображения доступных команд */}
      <button 
        className="show-commands-button"
        onClick={() => setShowCommands(!showCommands)}
        style={{ 
          position: 'fixed', 
          bottom: '20px', 
          right: '20px', 
          zIndex: 9999,
          backgroundColor: '#1a73e8',
          color: 'white',
          border: 'none',
          borderRadius: '8px',
          padding: '10px 16px',
          fontSize: '14px',
          fontWeight: '500',
          boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          transition: 'all 0.2s ease'
        }}
        onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#0d62c9'}
        onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#1a73e8'}
      >
        {showCommands ? 'Скрыть команды' : 'Показать команды'}
      </button>

      {/* Отображение доступных команд */}
      {showCommands && availableCommands.length > 0 && (
        <div className="available-commands" style={{ 
          position: 'fixed', 
          bottom: '70px', 
          right: '20px', 
          zIndex: 9999, 
          background: 'white', 
          padding: '15px', 
          border: '1px solid #e0e0e0', 
          borderRadius: '8px', 
          maxHeight: '300px', 
          overflowY: 'auto',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          width: '300px'
        }}>
          <h3 style={{ marginTop: 0, marginBottom: '10px', color: '#1a73e8' }}>Доступные команды:</h3>
          <ul style={{ paddingLeft: '20px', margin: 0 }}>
            {availableCommands.map((cmd, index) => (
              <li key={index} style={{ marginBottom: '8px' }}>
                <strong style={{ color: '#1a73e8' }}>{cmd.trigger}</strong>: {cmd.description} (тип: {cmd.action_type})
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Модальное окно настроек */}
      {showSettingsModal && (
        <div className="settings-modal">
          <div className="settings-modal-content">
            <h2>Настройки системного промпта</h2>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={15}
              className="system-prompt-textarea"
            />
            <div className="settings-modal-buttons">
              <button onClick={() => setShowSettingsModal(false)}>Отмена</button>
              <button onClick={saveSystemPrompt}>Сохранить</button>
            </div>
          </div>
        </div>
      )}

      <TextEditor 
        isOpen={showTextEditor}
        onClose={() => setShowTextEditor(false)}
        onSave={handleSaveLetter}
      />
    </div>
  );
};

export default Chat;