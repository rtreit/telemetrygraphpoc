import { useState, useCallback, useMemo, useRef } from 'react';
import { Graph3D, type Graph3DHandle } from './components/Graph3D';
import { NodePanel } from './components/NodePanel';
import { FilterPanel } from './components/FilterPanel';
import { SearchBar } from './components/SearchBar';
import { Legend } from './components/Legend';
import { useGraphData } from './hooks/useGraphData';
import { EU_COUNTRIES, NODE_TYPE_CONFIG } from './config';
import type { GraphNode } from './types';

function App() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const { data, loading, error, regenerate } = useGraphData(filters);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [highlightEU, setHighlightEU] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [nodeCount, setNodeCount] = useState(100);
  const [labelTypes, setLabelTypes] = useState<Set<string>>(new Set(Object.keys(NODE_TYPE_CONFIG)));
  const [hopCount, setHopCount] = useState(1);
  const graphRef = useRef<Graph3DHandle>(null);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setSelectedNode(null);
    try {
      await regenerate(undefined, nodeCount);
    } finally {
      setGenerating(false);
    }
  }, [regenerate, nodeCount]);

  const handleToggleLabelType = useCallback((type: string) => {
    setLabelTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const connectedEdges = useMemo(() => {
    if (!selectedNode || !data) return [];
    return data.edges.filter(
      e => e.source === selectedNode.id || e.target === selectedNode.id
    );
  }, [selectedNode, data]);

  const highlightNodes = useMemo(() => {
    if (selectedNode && data) {
      // Multi-hop BFS from selected node
      const connected = new Set<string>([selectedNode.id]);
      let frontier = new Set<string>([selectedNode.id]);
      for (let hop = 0; hop < hopCount; hop++) {
        const nextFrontier = new Set<string>();
        data.edges.forEach(e => {
          if (frontier.has(e.source) && !connected.has(e.target)) {
            nextFrontier.add(e.target);
            connected.add(e.target);
          }
          if (frontier.has(e.target) && !connected.has(e.source)) {
            nextFrontier.add(e.source);
            connected.add(e.source);
          }
        });
        frontier = nextFrontier;
      }
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
  }, [selectedNode, data, highlightEU, hopCount]);

  const highlightEdges = useMemo(() => {
    if (!data || highlightNodes.size === 0) return new Set<string>();
    const edgeKeys = new Set<string>();
    // Highlight edges where BOTH endpoints are in the highlighted set
    data.edges.forEach(e => {
      if (highlightNodes.has(e.source) && highlightNodes.has(e.target)) {
        edgeKeys.add(`${e.source}->${e.target}`);
      }
    });
    return edgeKeys;
  }, [data, highlightNodes]);

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
            labelTypes={labelTypes}
          />
        )}

        {/* Top bar overlays */}
        <div className="absolute top-4 left-4 right-4 flex items-start justify-between pointer-events-none">
          {/* Left: controls */}
          <div className="flex flex-col gap-2 pointer-events-auto">
            <div className="flex items-center gap-2">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className={`px-3 py-1.5 rounded-lg text-sm transition ${
                  generating
                    ? 'bg-green-800 text-green-300 cursor-wait'
                    : 'bg-green-600/80 text-white hover:bg-green-500'
                }`}
              >
                {generating ? '⏳ Generating...' : '⚡ Generate'}
              </button>
              <input
                type="number"
                min={20}
                max={10000}
                value={nodeCount}
                onChange={e => setNodeCount(Math.max(20, Math.min(10000, parseInt(e.target.value) || 100)))}
                className="w-20 px-2 py-1.5 rounded-lg text-sm bg-black/60 backdrop-blur-sm text-gray-300 border border-gray-700 focus:border-blue-500 outline-none"
                title="Node count"
              />
              <span className="text-xs text-gray-500">nodes</span>
            </div>
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
            <div className="bg-black/60 backdrop-blur-sm rounded-lg px-3 py-1.5 text-sm flex items-center gap-3">
              <span><span className="text-gray-400">Nodes:</span> {data?.nodes.length ?? 0}</span>
              <span><span className="text-gray-400">Edges:</span> {data?.edges.length ?? 0}</span>
              <span className="border-l border-gray-700 pl-3 flex items-center gap-1">
                <span className="text-gray-400">Hops:</span>
                {[1,2,3,4].map(h => (
                  <button
                    key={h}
                    onClick={() => setHopCount(h)}
                    className={`w-6 h-6 rounded text-xs font-mono transition ${
                      hopCount === h
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-500 hover:text-gray-300 hover:bg-white/10'
                    }`}
                  >
                    {h}
                  </button>
                ))}
              </span>
            </div>
            <Legend labelTypes={labelTypes} onToggleLabelType={handleToggleLabelType} />
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
