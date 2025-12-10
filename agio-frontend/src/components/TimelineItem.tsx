import React from 'react';

interface TimelineItemProps {
  type: 'user' | 'assistant' | 'tool' | 'error' | 'nested' | 'workflow' | 'parallel_nested';
  children: React.ReactNode;
  isLast?: boolean;
  depth?: number;  // For nested events indentation
}

export function TimelineItem({ type, children, isLast = false, depth = 0 }: TimelineItemProps) {
  const getDotColor = () => {
    switch (type) {
      case 'user':
        return 'bg-primary-500 ring-primary-500/30';
      case 'assistant':
        return 'bg-blue-500 ring-blue-500/30';
      case 'tool':
        return 'bg-purple-500 ring-purple-500/30';
      case 'nested':
        return 'bg-amber-500 ring-amber-500/30';
      case 'parallel_nested':
        return 'bg-amber-500 ring-amber-500/30';
      case 'workflow':
        return 'bg-cyan-500 ring-cyan-500/30';
      case 'error':
        return 'bg-red-500 ring-red-500/30';
      default:
        return 'bg-gray-500 ring-gray-500/30';
    }
  };

  // Calculate left padding based on depth
  const paddingLeft = 20 + depth * 16;  // Base 20px + 16px per depth level

  // Dot: 6px (w-1.5 h-1.5), positioned at left-[2px]
  // Dot center X = 2px + 3px = 5px, so line should be at left-[4.5px] (centered on 1px line)
  // Dot top = 1.05rem ≈ 17px, dot bottom = 17 + 6 = 23px ≈ 1.45rem
  
  return (
    <div className="relative pt-3 group" style={{ paddingLeft }}>
      {/* Vertical Line - from below this dot to next dot */}
      {!isLast && (
        <div className="absolute top-[1.45rem] bottom-[-1rem] w-px bg-border group-hover:bg-gray-700 transition-colors" style={{ left: 4.5 + depth * 16 }} />
      )}

      {/* Dot Marker - vertically centered with first line text */}
      <div 
        className={`absolute top-[1.05rem] w-1.5 h-1.5 rounded-full ${getDotColor()} ring-1 transition-all duration-300 z-10`}
        style={{ left: 2 + depth * 16 }}
      />

      {/* Content */}
      <div className="min-w-0">
        {children}
      </div>
    </div>
  );
}
