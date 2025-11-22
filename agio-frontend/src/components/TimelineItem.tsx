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

  return (
    <div className="relative pl-8 py-2 group">
      {/* Vertical Line */}
      {!isLast && (
        <div className="absolute left-[11px] top-8 bottom-0 w-px bg-border group-hover:bg-gray-700 transition-colors" />
      )}

      {/* Dot Marker */}
      <div className={`absolute left-1 top-3 w-5 h-5 rounded-full border-4 border-background ${getDotColor()} ring-2 transition-all duration-300 z-10`} />

      {/* Content */}
      <div className="min-w-0 flex-1">
        {children}
      </div>
    </div>
  );
}
