import { useState, useCallback, useMemo, useRef } from 'react';
import { Graph3D, type Graph3DHandle } from './components/Graph3D';
import { NodePanel } from './components/NodePanel';
import { FilterPanel } from './components/FilterPanel';
import { SearchBar } from './components/SearchBar';
import { Legend } from './components/Legend';
import { useGraphData } from './hooks/useGraphData';
import { EU_COUNTRIES } from './config';
import type { GraphNode } from './types';

function App() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const { data, loading, error } = useGraphData(filters);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [highlightEU, setHighlightEU] = useState(false);
  const graphRef = useRef<Graph3DHandle>(null);

  const connectedEdges = useMemo(() => {
    if (!selectedNode || !data) return [];
    return data.edges.filter(
      e => e.source === selectedNode.id || e.target === selectedNode.id
    );
  }, [selectedNode, data]);

  const highlightNodes = useMemo(() => {
    if (selectedNode && data) {
      // Selection takes priority
      const connected = new Set<string>([selectedNode.id]);
      data.edges.forEach(e => {
        if (e.source === selectedNode.id) connected.add(e.target);
        if (e.target === selectedNode.id) connected.add(e.source);
      });
      return connected;
    }
    if (highlightEU && data) {
      return new Set(
        data.nodes
          .filter(n => {
            const cc = (n.properties?.country_code || n.properties?.country) as string;
            return cc && EU_COUNTRIES.has(cc);
          })
          .map(n => n.id)
      );
    }
    return new Set<string>();
  }, [selectedNode, data, highlightEU]);

  const highlightEdges = useMemo(() => {
    if (!selectedNode || !data) return new Set<string>();
    const edgeKeys = new Set<string>();
    data.edges.forEach(e => {
      if (e.source === selectedNode.id || e.target === selectedNode.id) {
        edgeKeys.add(`${e.source}->${e.target}`);
      }
    });
    return edgeKeys;
  }, [selectedNode, data]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(prev => prev?.id === node.id ? null : node);
  }, []);

  const handleExpandNode = useCallback((node: GraphNode) => {
    graphRef.current?.focusOnNode(node.id);
  }, []);

  const handleNavigateToNode = useCallback((nodeId: string) => {
    if (!data) return;
    const node = data.nodes.find(n => n.id === nodeId);
    if (node) {
      setSelectedNode(node);
      graphRef.current?.focusOnNode(nodeId);
    }
  }, [data]);

  const handleSearchSelect = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    graphRef.current?.focusOnNode(node.id);
  }, []);

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0f] text-gray-100 flex items-center justify-center">
      <div className="text-center">
        <div className="text-xl animate-pulse mb-2">Loading graph data...</div>
        <div className="text-sm text-gray-500">Fetching nodes and edges</div>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-[#0a0a0f] text-red-400 flex items-center justify-center">
      <div className="text-center">
        <div className="text-xl mb-2">Failed to load graph</div>
        <div className="text-sm text-red-300">{error}</div>
        <div className="text-sm text-gray-500 mt-2">Make sure the API server is running on port 8000</div>
      </div>
    </div>
  );

  return (
    <div className="h-screen w-screen bg-[#0a0a0f] text-gray-100 flex overflow-hidden">
      {/* Filter panel (left side) */}
      <FilterPanel
        isOpen={showFilters}
        onToggle={() => setShowFilters(!showFilters)}
        onFiltersChange={setFilters}
      />

      {/* Main graph area */}
      <div className="flex-1 relative">
        {data && (
          <Graph3D
            ref={graphRef}
            nodes={data.nodes}
            edges={data.edges}
            onNodeClick={handleNodeClick}
            highlightNodes={highlightNodes}
            highlightEdges={highlightEdges}
            selectedNodeId={selectedNode?.id}
          />
        )}

        {/* Top bar overlays */}
        <div className="absolute top-4 left-4 right-4 flex items-start justify-between pointer-events-none">
          {/* Left: controls */}
          <div className="flex flex-col gap-2 pointer-events-auto">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${
                showFilters 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-black/60 backdrop-blur-sm text-gray-300 hover:text-white'
              }`}
            >
              ☰ Filters
            </button>
            <button
              onClick={() => setHighlightEU(!highlightEU)}
              className={`px-3 py-1.5 rounded-lg text-sm transition ${
                highlightEU 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-black/60 backdrop-blur-sm text-gray-300 hover:text-white'
              }`}
            >
              🇪🇺 EU
            </button>
            <div className="bg-black/60 backdrop-blur-sm rounded-lg px-3 py-1.5 text-sm">
              <span className="text-gray-400">Nodes:</span> {data?.nodes.length ?? 0}
              <span className="text-gray-400 ml-3">Edges:</span> {data?.edges.length ?? 0}
            </div>
            <Legend />
          </div>

          {/* Center: search */}
          <div className="pointer-events-auto">
            <SearchBar onSelectResult={handleSearchSelect} />
          </div>

          {/* Right: spacer */}
          <div className="w-20" />
        </div>
      </div>

      {/* Node details panel (right side) */}
      {selectedNode && (
        <NodePanel
          node={selectedNode}
          connectedEdges={connectedEdges}
          onClose={() => setSelectedNode(null)}
          onExpandNode={handleExpandNode}
          onNavigateToNode={handleNavigateToNode}
        />
      )}
    </div>
  );
}

export default App;
