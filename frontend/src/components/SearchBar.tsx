import { useState, useRef, useEffect, useCallback } from 'react';
import { NODE_TYPE_CONFIG } from '../config';
import type { GraphNode } from '../types';

interface SearchBarProps {
  onSelectResult: (node: GraphNode) => void;
}

export function SearchBar({ onSelectResult }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GraphNode[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  const doSearch = useCallback((q: string) => {
    if (q.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    setLoading(true);
    fetch(`/api/search?q=${encodeURIComponent(q)}`)
      .then(r => r.json())
      .then(data => {
        setResults(data.results || []);
        setIsOpen(true);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 300);
  };

  const handleSelect = (node: GraphNode) => {
    onSelectResult(node);
    setIsOpen(false);
    setQuery(node.label);
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center bg-gray-800/90 border border-gray-600 rounded-lg overflow-hidden">
        <span className="pl-3 text-gray-400">🔍</span>
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          placeholder="Search hash, hostname, domain, IP..."
          className="w-64 bg-transparent px-3 py-2 text-sm text-gray-200 placeholder-gray-500 outline-none"
        />
        {loading && <span className="pr-3 text-gray-400 animate-spin">⟳</span>}
      </div>

      {isOpen && results.length > 0 && (
        <div className="absolute top-full mt-1 w-full bg-gray-800 border border-gray-600 rounded-lg shadow-xl max-h-72 overflow-y-auto z-50">
          {results.map((node) => (
            <button
              key={node.id}
              onClick={() => handleSelect(node)}
              className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-700 text-left"
            >
              <span 
                className="w-2.5 h-2.5 rounded-full flex-shrink-0" 
                style={{ backgroundColor: NODE_TYPE_CONFIG[node.type]?.color || '#888' }}
              />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-gray-200 truncate">{node.label}</div>
                <div className="text-xs text-gray-500">{node.type} · {node.id.substring(0, 30)}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {isOpen && query.length >= 2 && results.length === 0 && !loading && (
        <div className="absolute top-full mt-1 w-full bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-3 z-50">
          <div className="text-sm text-gray-400 text-center">No results found</div>
        </div>
      )}
    </div>
  );
}
