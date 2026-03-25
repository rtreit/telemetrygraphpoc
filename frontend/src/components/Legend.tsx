import { useState } from 'react';
import { NODE_TYPE_CONFIG } from '../config';

interface LegendProps {
  labelTypes?: Set<string>;
  onToggleLabelType?: (type: string) => void;
}

export function Legend({ labelTypes, onToggleLabelType }: LegendProps) {
  const [isOpen, setIsOpen] = useState(true);
  
  return (
    <div className="bg-black/60 backdrop-blur-sm rounded-lg">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 w-full text-left"
      >
        {isOpen ? '▾' : '▸'} Legend
      </button>
      {isOpen && (
        <div className="px-3 pb-2 grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(NODE_TYPE_CONFIG).map(([type, cfg]) => (
            <div key={type} className="flex items-center gap-1.5 text-xs">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cfg.color }} />
              <span className="text-gray-400">{type}</span>
              <button
                onClick={() => onToggleLabelType?.(type)}
                className={`ml-auto text-[10px] px-1 rounded ${
                  labelTypes?.has(type)
                    ? 'bg-white/20 text-white'
                    : 'text-gray-600 hover:text-gray-400'
                }`}
                title={`Toggle labels for ${type}`}
              >
                Aa
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
