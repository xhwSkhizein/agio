import React from 'react';

interface TimelineItemProps {
  type: 'user' | 'assistant' | 'tool' | 'error';
  children: React.ReactNode;
  isLast?: boolean;
}

export function TimelineItem({ type, children, isLast = false }: TimelineItemProps) {
  const getDotColor = () => {
    switch (type) {
      case 'user':
        return 'bg-primary-500 ring-primary-500/30';
      case 'assistant':
        return 'bg-blue-500 ring-blue-500/30';
      case 'tool':
        return 'bg-purple-500 ring-purple-500/30';
      case 'error':
        return 'bg-red-500 ring-red-500/30';
      default:
        return 'bg-gray-500 ring-gray-500/30';
    }
  };

  // Dot: 6px (w-1.5 h-1.5), positioned at left-[2px]
  // Dot center X = 2px + 3px = 5px, so line should be at left-[4.5px] (centered on 1px line)
  // Dot top = 1.05rem ≈ 17px, dot bottom = 17 + 6 = 23px ≈ 1.45rem
  
  return (
    <div className="relative pl-5 pt-3 group">
      {/* Vertical Line - from below this dot to next dot */}
      {!isLast && (
        <div className="absolute left-[4.5px] top-[1.45rem] bottom-[-1rem] w-px bg-border group-hover:bg-gray-700 transition-colors" />
      )}

      {/* Dot Marker - vertically centered with first line text */}
      <div className={`absolute left-[2px] top-[1.05rem] w-1.5 h-1.5 rounded-full ${getDotColor()} ring-1 transition-all duration-300 z-10`} />

      {/* Content */}
      <div className="min-w-0">
        {children}
      </div>
    </div>
  );
}
