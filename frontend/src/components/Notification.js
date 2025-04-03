import React, { useEffect, useState } from 'react';
import './Notification.css';

const Notification = ({ message, timestamp }) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
    }, 4700); // Устанавливаем таймер на 4.7 секунды

    return () => clearTimeout(timer);
  }, []);

  return (
    <div className={`notification ${!isVisible ? 'fade-out' : ''}`}>
      <div className="notification-content">{message}</div>
      <div className="notification-timestamp">{timestamp}</div>
    </div>
  );
};

export default Notification; 