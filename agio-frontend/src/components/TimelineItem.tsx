import React from 'react';

interface TimelineItemProps {
  type: 'user' | 'assistant' | 'tool' | 'error' | 'nested' | 'parallel_nested';
  children: React.ReactNode;
  isLast?: boolean;
  depth?: number;  // For nested events indentation
}

export function TimelineItem({ type, children, isLast = false, depth = 0 }: TimelineItemProps) {
  const getDotColor = () => {
    switch (type) {
      case 'user':
        return 'bg-primary-500 shadow-[0_0_8px_rgba(249,115,22,0.5)]';
      case 'assistant':
        return 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]';
      case 'tool':
        return 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)]';
      case 'nested':
        return 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]';
      case 'parallel_nested':
        return 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]';
      case 'error':
        return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]';
      default:
        return 'bg-gray-500';
    }
  };

  const paddingLeft = 24 + depth * 20;

  return (
    <div className="relative pt-4 group animate-in fade-in slide-in-from-left-2 duration-500" style={{ paddingLeft }}>
      {/* Vertical Line */}
      {!isLast && (
        <div 
          className="absolute top-[1.8rem] bottom-[-1rem] w-px bg-white/5 group-hover:bg-white/10 transition-colors" 
          style={{ left: 9.5 + depth * 20 }} 
        />
      )}

      {/* Dot Marker */}
      <div 
        className={`absolute top-[1.35rem] w-1.5 h-1.5 rounded-full ${getDotColor()} transition-all duration-300 z-10 border border-black/50`}
        style={{ left: 7 + depth * 20 }}
      />

      {/* Content */}
      <div className="min-w-0 pb-2">
        {children}
      </div>
    </div>
  );
}
