import React from 'react';
import './Timeline.css';

function Timeline({ timesteps, currentTimestep, setCurrentTimestep, isPlaying, onPlayPause }) {
  if (!timesteps || timesteps.length === 0) return null;
  
  const currentTime = timesteps[currentTimestep]?.time || 0;
  const maxTime = timesteps[timesteps.length - 1]?.time || 1;
  
  return (
    <div className="timeline">
      <button className="play-button" onClick={onPlayPause}>
        {isPlaying ? '||' : '▶'}
      </button>
      
      <div className="timeline-slider">
        <input
          type="range"
          min={0}
          max={timesteps.length - 1}
          value={currentTimestep}
          onChange={(e) => setCurrentTimestep(Number(e.target.value))}
        />
        <div className="timeline-labels">
          <span>0 min</span>
          <span>{currentTime.toFixed(1)} min</span>
          <span>{maxTime.toFixed(0)} min</span>
        </div>
      </div>
      
      <div className="timeline-info">
        Frame {currentTimestep + 1} / {timesteps.length}
      </div>
    </div>
  );
}

export default Timeline;

