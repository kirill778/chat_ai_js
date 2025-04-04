import React, { useState, useRef, useEffect } from 'react';
import './Chat.css';
import Notification from './Notification';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
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

  // Загрузка истории чатов при монтировании
  useEffect(() => {
    fetchChats();
  }, []);

  const fetchChats = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/chats');
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
    e.preventDefault(); // Предотвращаем перезагрузку страницы
    if (currentRequestId) {
      try {
        await fetch('http://localhost:5000/api/stop', {
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
    
    // Сохраняем текущее сообщение в истории
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
      
      // Позиционируем кнопку редактирования
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
      const response = await fetch('http://localhost:5000/api/edit', {
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
      
      // Обновляем сообщение с новым текстом
      setMessages(prev => prev.map((msg, index) => {
        if (index === editingMessage) {
          const newText = msg.text.replace(selectedText, data.response);
          return { ...msg, text: newText };
        }
        return msg;
      }));

      // Сбрасываем состояние редактирования
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    const userMessage = {
      text: inputMessage,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setCurrentStreamingMessage('');
    
    abortControllerRef.current = new AbortController();
    const requestId = Date.now().toString();
    setCurrentRequestId(requestId);

    try {
      const response = await fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: inputMessage,
          request_id: requestId,
          chat_id: currentChatId
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const contentType = response.headers.get('content-type');
      
      // Если это JSON - значит это результат выполнения команды
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        
        switch (data.type) {
          case 'notification':
            // Показываем уведомление
            setNotification({
              message: data.content,
              timestamp: new Date().toLocaleTimeString()
            });
            setTimeout(() => setNotification(null), 5000);
            break;
            
          case 'script_result':
            // Добавляем результат скрипта в чат
            const scriptMessage = {
              text: data.content,
              sender: 'bot',
              timestamp: new Date().toLocaleTimeString()
            };
            setMessages(prev => [...prev, scriptMessage]);
            break;
            
          case 'error':
            // Показываем ошибку в чате
            const errorMessage = {
              text: data.content,
              sender: 'bot',
              timestamp: new Date().toLocaleTimeString(),
              isError: true
            };
            setMessages(prev => [...prev, errorMessage]);
            break;
        }
        return;
      }

      // Если это не JSON - это обычный ответ от модели
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        accumulatedText += text;
        setCurrentStreamingMessage(accumulatedText);
      }

      const botMessage = {
        text: accumulatedText.trim(),
        sender: 'bot',
        timestamp: new Date().toLocaleTimeString()
      };

      setMessages(prev => [...prev, botMessage]);
      setCurrentStreamingMessage('');
      
      // Обновляем список чатов после каждого сообщения
      fetchChats();
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Request was aborted');
        return;
      }
      console.error('Error:', error);
      const errorMessage = {
        text: 'Извините, произошла ошибка. Попробуйте еще раз.',
        sender: 'bot',
        timestamp: new Date().toLocaleTimeString(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setCurrentRequestId('');
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  };

  const handleKeyDown = (e) => {
    // Отправка сообщения по Enter (Shift+Enter для новой строки)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const createNewChat = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/chats', {
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
    setMessages(chat.messages || []);
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
              <div className="chat-title">{chat.title}</div>
              <div className="chat-date">
                {new Date(chat.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="chat-container">
        <div className="messages">
          {messages.map((message, index) => (
            <div 
              key={index} 
              className={`message ${message.sender}`}
              onMouseUp={(e) => handleTextSelection(e, index)}
            >
              <div className="message-content">
                {message.text}
              </div>
              <div className="message-timestamp">
                {message.timestamp}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                {currentStreamingMessage}
                <span className="typing-indicator">▋</span>
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
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Введите сообщение..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Остановить' : 'Отправить'}
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
    </div>
  );
};

export default Chat; 