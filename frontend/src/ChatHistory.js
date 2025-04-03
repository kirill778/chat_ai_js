import React, { useState, useEffect } from 'react';
import './ChatHistory.css';

const ChatHistory = ({ onSelectChat }) => {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchChats();
  }, []);

  const fetchChats = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/chats');
      const data = await response.json();
      setChats(data);
    } catch (error) {
      console.error('Error fetching chats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Loading chat history...</div>;
  }

  return (
    <div className="chat-history">
      <h2>История чатов</h2>
      <div className="chat-list">
        {chats.map(chat => (
          <div 
            key={chat.id} 
            className="chat-item"
            onClick={() => onSelectChat(chat)}
          >
            <div className="chat-preview">
              <span className="chat-date">
                {new Date(chat.created_at).toLocaleDateString()}
              </span>
              <p className="chat-snippet">
                {chat.messages[0]?.text.substring(0, 50)}...
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChatHistory;
