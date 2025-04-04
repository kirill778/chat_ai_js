import React, { useState } from 'react';
import { 
  Bold, 
  Italic, 
  Underline, 
  AlignLeft, 
  AlignCenter, 
  AlignRight, 
  List,
  FileText,
  Save,
  Wand2
} from 'lucide-react';
import './TextEditor.css';

const TextEditor = ({ isOpen, onClose, onSave }) => {
  const [content, setContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleFormat = (command) => {
    document.execCommand(command, false);
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
          type: 'business',
          content: content
        }),
      });
      
      const data = await response.json();
      setContent(data.text);
      // Обновляем содержимое редактируемого div
      const editorDiv = document.querySelector('.editor-content');
      if (editorDiv) {
        editorDiv.innerHTML = data.text;
      }
    } catch (error) {
      console.error('Error generating letter:', error);
    }
    setIsGenerating(false);
  };

  if (!isOpen) return null;

  return (
    <div className="text-editor-overlay">
      <div className="text-editor-container">
        {/* Top Bar */}
        <div className="text-editor-header">
          <div className="header-left">
            <FileText size={24} />
            <h2>Редактор документа</h2>
          </div>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        
        {/* Toolbar */}
        <div className="text-editor-toolbar">
          <button
            onClick={() => handleFormat('bold')}
            className="toolbar-button"
            title="Жирный"
          >
            <Bold size={20} />
          </button>
          <button
            onClick={() => handleFormat('italic')}
            className="toolbar-button"
            title="Курсив"
          >
            <Italic size={20} />
          </button>
          <button
            onClick={() => handleFormat('underline')}
            className="toolbar-button"
            title="Подчёркнутый"
          >
            <Underline size={20} />
          </button>
          
          <div className="toolbar-divider" />
          
          <button
            onClick={() => handleFormat('justifyLeft')}
            className="toolbar-button"
            title="По левому краю"
          >
            <AlignLeft size={20} />
          </button>
          <button
            onClick={() => handleFormat('justifyCenter')}
            className="toolbar-button"
            title="По центру"
          >
            <AlignCenter size={20} />
          </button>
          <button
            onClick={() => handleFormat('justifyRight')}
            className="toolbar-button"
            title="По правому краю"
          >
            <AlignRight size={20} />
          </button>
          
          <div className="toolbar-divider" />
          
          <button
            onClick={() => handleFormat('insertUnorderedList')}
            className="toolbar-button"
            title="Маркированный список"
          >
            <List size={20} />
          </button>

          <div className="toolbar-divider" />

          <button 
            className="generate-button"
            onClick={handleGenerate}
            disabled={isGenerating}
          >
            <Wand2 size={20} />
            {isGenerating ? 'Генерация...' : 'Сгенерировать текст'}
          </button>
        </div>

        {/* Editor Area */}
        <div className="text-editor-content">
          <div
            className="editor-content"
            contentEditable
            onInput={(e) => setContent(e.currentTarget.innerHTML)}
            dangerouslySetInnerHTML={{ __html: content }}
          />
        </div>

        {/* Footer */}
        <div className="text-editor-footer">
          <button className="cancel-button" onClick={onClose}>
            Отмена
          </button>
          <button 
            className="save-button" 
            onClick={() => onSave(content)}
            disabled={!content.trim()}
          >
            <Save size={16} />
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
};

export default TextEditor; 