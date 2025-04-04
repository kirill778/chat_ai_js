import React, { useState } from 'react';
import './Chat.css';

const CommandsList = () => {
  const [isOpen, setIsOpen] = useState(false);

  const commands = [
    {
      trigger: 'Уведомление <текст>',
      description: 'Показывает уведомление с указанным текстом'
    },
    {
      trigger: 'Время',
      description: 'Показывает текущее время'
    }
  ];

  const handleCommandClick = (command) => {
    navigator.clipboard.writeText(command.trigger);
    setIsOpen(false);
  };

  return (
    <>
      <button 
        className="commands-list-button"
        onClick={() => setIsOpen(!isOpen)}
      >
        <svg 
          width="24" 
          height="24" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
        >
          <line x1="8" y1="6" x2="21" y2="6"></line>
          <line x1="8" y1="12" x2="21" y2="12"></line>
          <line x1="8" y1="18" x2="21" y2="18"></line>
          <line x1="3" y1="6" x2="3.01" y2="6"></line>
          <line x1="3" y1="12" x2="3.01" y2="12"></line>
          <line x1="3" y1="18" x2="3.01" y2="18"></line>
        </svg>
      </button>

      {isOpen && (
        <div className="commands-dropdown">
          <h3>Доступные команды</h3>
          <ul className="commands-list">
            {commands.map((command, index) => (
              <li 
                key={index} 
                className="command-item"
                onClick={() => handleCommandClick(command)}
              >
                <div className="command-trigger">{command.trigger}</div>
                <div className="command-description">{command.description}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
};

export default CommandsList; 