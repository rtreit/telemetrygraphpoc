import type { GraphNode, GraphEdge } from '../types';
import { NODE_TYPE_CONFIG } from '../config';

interface NodePanelProps {
  node: GraphNode;
  connectedEdges: GraphEdge[];
  onClose: () => void;
  onExpandNode: (node: GraphNode) => void;
  onNavigateToNode: (nodeId: string) => void;
}

export function NodePanel({ node, connectedEdges, onClose, onExpandNode, onNavigateToNode }: NodePanelProps) {
  const typeConfig = NODE_TYPE_CONFIG[node.type];
  
  const outgoing = connectedEdges.filter(e => e.source === node.id);
  const incoming = connectedEdges.filter(e => e.target === node.id);

  return (
    <div className="w-96 bg-gray-900/95 border-l border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex justify-between items-start mb-2">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-bold truncate" title={node.label}>{node.label}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span 
                className="inline-block w-3 h-3 rounded-full" 
                style={{ backgroundColor: typeConfig?.color || '#888' }}
              />
              <span className="text-xs text-gray-400 uppercase tracking-wider">{node.type}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white ml-2 text-lg">✕</button>
        </div>
        <div className="text-xs text-gray-500 font-mono break-all mt-2">{node.id}</div>
        <button 
          onClick={() => onExpandNode(node)}
          className="mt-3 w-full px-3 py-1.5 bg-blue-600/20 text-blue-400 border border-blue-600/30 rounded text-sm hover:bg-blue-600/30 transition"
        >
          Expand Neighborhood
        </button>
      </div>

      {/* Properties */}
      <div className="flex-1 overflow-y-auto p-4">
        <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Properties</h3>
        <div className="space-y-1.5 mb-6">
          {Object.entries(node.properties).map(([key, value]) => (
            <div key={key} className="text-sm">
              <span className="text-gray-500">{key}: </span>
              <span className="text-gray-200 break-all">
                {Array.isArray(value) 
                  ? value.join(', ') 
                  : typeof value === 'object' && value !== null
                    ? JSON.stringify(value)
                    : String(value)}
              </span>
            </div>
          ))}
        </div>

        {outgoing.length > 0 && (
          <>
            <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">
              Outgoing ({outgoing.length})
            </h3>
            <div className="space-y-1 mb-4">
              {outgoing.slice(0, 20).map((edge, i) => (
                <div 
                  key={i} 
                  className="text-xs flex items-center gap-1 hover:bg-gray-800 rounded px-1 py-0.5 cursor-pointer"
                  onClick={() => onNavigateToNode(edge.target)}
                >
                  <span className="text-yellow-500">→</span>
                  <span className="text-gray-400">{edge.type}</span>
                  <span className="text-gray-300 truncate">{edge.target}</span>
                </div>
              ))}
              {outgoing.length > 20 && (
                <div className="text-xs text-gray-500">...and {outgoing.length - 20} more</div>
              )}
            </div>
          </>
        )}

        {incoming.length > 0 && (
          <>
            <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">
              Incoming ({incoming.length})
            </h3>
            <div className="space-y-1 mb-4">
              {incoming.slice(0, 20).map((edge, i) => (
                <div 
                  key={i} 
                  className="text-xs flex items-center gap-1 hover:bg-gray-800 rounded px-1 py-0.5 cursor-pointer"
                  onClick={() => onNavigateToNode(edge.source)}
                >
                  <span className="text-blue-500">←</span>
                  <span className="text-gray-400">{edge.type}</span>
                  <span className="text-gray-300 truncate">{edge.source}</span>
                </div>
              ))}
              {incoming.length > 20 && (
                <div className="text-xs text-gray-500">...and {incoming.length - 20} more</div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
