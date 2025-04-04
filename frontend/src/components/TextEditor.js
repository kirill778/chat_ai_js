import React, { useState } from 'react';
import './TextEditor.css';

const TextEditor = ({ isOpen, onClose, onSave }) => {
  const [text, setText] = useState('');
  const [letterType, setLetterType] = useState('business');
  const [isGenerating, setIsGenerating] = useState(false);

  const letterTypes = {
    business: 'Деловое письмо',
    personal: 'Личное письмо',
    complaint: 'Жалоба',
    gratitude: 'Благодарственное письмо',
    invitation: 'Приглашение'
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const response = await fetch('http://localhost:5000/api/generate-letter', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: letterType,
          content: text
        }),
      });
      
      const data = await response.json();
      setText(data.text);
    } catch (error) {
      console.error('Error generating letter:', error);
    }
    setIsGenerating(false);
  };

  if (!isOpen) return null;

  return (
    <div className="text-editor-overlay">
      <div className="text-editor-container">
        <div className="text-editor-header">
          <h2>Редактор письма</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        
        <div className="text-editor-controls">
          <select 
            value={letterType}
            onChange={(e) => setLetterType(e.target.value)}
            className="letter-type-select"
          >
            {Object.entries(letterTypes).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          
          <button 
            className="generate-button"
            onClick={handleGenerate}
            disabled={isGenerating}
          >
            {isGenerating ? 'Генерация...' : 'Сгенерировать письмо'}
          </button>
        </div>

        <textarea
          className="text-editor-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Введите текст письма или опишите, что вы хотите написать..."
        />

        <div className="text-editor-footer">
          <button className="cancel-button" onClick={onClose}>Отмена</button>
          <button 
            className="save-button" 
            onClick={() => onSave(text)}
            disabled={!text.trim()}
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
};

export default TextEditor; 