import ForceGraph3D from '3d-force-graph';
import type { ForceGraph3DInstance } from '3d-force-graph';
import SpriteText from 'three-spritetext';
import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import { COUNTRY_COLORS, NODE_TYPE_CONFIG } from '../config';
import type { GraphNode, GraphEdge } from '../types';

interface Graph3DProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  onNodeDoubleClick?: (node: GraphNode) => void;
  highlightNodes?: Set<string>;
  highlightEdges?: Set<string>;
  selectedNodeId?: string | null;
}

export interface Graph3DHandle {
  focusOnNode: (nodeId: string) => void;
}

interface GraphNodeObject {
  id: string;
  type: string;
  label: string;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
}

export const Graph3D = forwardRef<Graph3DHandle, Graph3DProps>(
  ({ nodes, edges, onNodeClick, onNodeDoubleClick, highlightNodes, highlightEdges, selectedNodeId }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const graphRef = useRef<ForceGraph3DInstance | null>(null);
    const highlightNodesRef = useRef(highlightNodes);
    const highlightEdgesRef = useRef(highlightEdges);
    const selectedNodeIdRef = useRef(selectedNodeId);

    // Keep refs in sync
    useEffect(() => { highlightNodesRef.current = highlightNodes; }, [highlightNodes]);
    useEffect(() => { highlightEdgesRef.current = highlightEdges; }, [highlightEdges]);
    useEffect(() => { selectedNodeIdRef.current = selectedNodeId; }, [selectedNodeId]);

    useImperativeHandle(ref, () => ({
      focusOnNode: (nodeId: string) => {
        if (!graphRef.current) return;
        const node = (graphRef.current.graphData() as unknown as { nodes: GraphNodeObject[] }).nodes.find((n) => n.id === nodeId);
        if (node) {
          graphRef.current.cameraPosition(
            { x: node.x! + 100, y: node.y! + 100, z: node.z! + 100 },
            { x: node.x!, y: node.y!, z: node.z! },
            1500
          );
        }
      },
    }));

    useEffect(() => {
      if (!containerRef.current) return;

      const graph = new ForceGraph3D(containerRef.current)
        .backgroundColor('#0a0a0f')
        .nodeLabel((obj) => {
          const node = obj as unknown as GraphNodeObject;
          const cc = (node.properties?.country_code || node.properties?.country || '') as string;

          let details = '';
          if (node.type === 'file') {
            const names = node.properties?.file_names;
            const paths = node.properties?.file_paths;
            if (Array.isArray(names) && names.length > 0) {
              details += `<br/><span style="color:#ccc">File: ${names[0]}</span>`;
            }
            if (Array.isArray(paths) && paths.length > 0) {
              details += `<br/><span style="color:#999;font-size:11px">${paths[0]}</span>`;
            }
          }

          return `<div style="color:#fff;background:rgba(0,0,0,0.85);padding:6px 10px;border-radius:6px;font-size:12px;max-width:400px;">
            <b>${node.label}</b>
            <br/><span style="color:#999">${node.type}</span>${cc ? ` · <span style="color:#aaa">${cc}</span>` : ''}
            ${details}
          </div>`;
        })
        .nodeColor((obj) => {
          const node = obj as unknown as GraphNodeObject;
          const hl = highlightNodesRef.current;
          if (hl && hl.size > 0 && !hl.has(node.id)) {
            return '#1a1a1a';
          }
          if (node.id === selectedNodeIdRef.current) {
            return '#ffffff';
          }
          // Color by country_code (all nodes have this now)
          const countryCode = (node.properties?.country_code || node.properties?.country) as string;
          if (countryCode && COUNTRY_COLORS[countryCode]) {
            return COUNTRY_COLORS[countryCode];
          }
          return NODE_TYPE_CONFIG[node.type]?.color || '#888888';
        })
        .nodeVal((obj) => {
          const node = obj as unknown as GraphNodeObject;
          if (node.id === selectedNodeIdRef.current) {
            return (NODE_TYPE_CONFIG[node.type]?.size || 3) * 2;
          }
          return NODE_TYPE_CONFIG[node.type]?.size || 3;
        })
        .nodeOpacity(0.9)
        .linkOpacity(1.0)
        .linkColor((link: any) => {
          const hl = highlightEdgesRef.current;
          if (hl && hl.size > 0) {
            const key = `${typeof link.source === 'object' ? link.source.id : link.source}->${typeof link.target === 'object' ? link.target.id : link.target}`;
            const reverseKey = `${typeof link.target === 'object' ? link.target.id : link.target}->${typeof link.source === 'object' ? link.source.id : link.source}`;
            if (hl.has(key) || hl.has(reverseKey)) {
              return 'rgba(255,255,255,0.6)';
            }
            return 'rgba(255,255,255,0.08)';
          }
          return 'rgba(255,255,255,0.35)';
        })
        .linkWidth((link: any) => {
          const hl = highlightEdgesRef.current;
          if (hl && hl.size > 0) {
            const key = `${typeof link.source === 'object' ? link.source.id : link.source}->${typeof link.target === 'object' ? link.target.id : link.target}`;
            const reverseKey = `${typeof link.target === 'object' ? link.target.id : link.target}->${typeof link.source === 'object' ? link.source.id : link.source}`;
            if (hl.has(key) || hl.has(reverseKey)) return 1.5;
          }
          return 0.8;
        })
        .linkDirectionalParticles((link: any) => {
          const hl = highlightEdgesRef.current;
          if (hl && hl.size > 0) {
            const key = `${typeof link.source === 'object' ? link.source.id : link.source}->${typeof link.target === 'object' ? link.target.id : link.target}`;
            const reverseKey = `${typeof link.target === 'object' ? link.target.id : link.target}->${typeof link.source === 'object' ? link.source.id : link.source}`;
            if (hl.has(key) || hl.has(reverseKey)) return 2;
          }
          return 0;
        })
        .linkDirectionalParticleWidth(1.2)
        .linkThreeObjectExtend(true)
        .linkThreeObject((link: any) => {
          const hl = highlightEdgesRef.current;
          if (!hl || hl.size === 0) return null as any;
          const srcId = typeof link.source === 'object' ? link.source.id : link.source;
          const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
          const key = `${srcId}->${tgtId}`;
          const reverseKey = `${tgtId}->${srcId}`;
          if (!hl.has(key) && !hl.has(reverseKey)) return null as any;

          const sprite = new SpriteText(link.type || '', 2.5, 'rgba(255,255,255,0.8)');
          sprite.backgroundColor = 'rgba(0,0,0,0.6)';
          sprite.padding = 1.5;
          sprite.borderRadius = 2;
          return sprite;
        })
        .linkPositionUpdate((sprite: any, { start, end }: any) => {
          if (!sprite || !start || !end) return false;
          const mid = {
            x: (start.x + end.x) / 2,
            y: (start.y + end.y) / 2,
            z: (start.z + end.z) / 2,
          };
          Object.assign(sprite.position, mid);
          return true;
        })
        .onNodeClick((obj) => {
          if (onNodeClick) onNodeClick(obj as unknown as GraphNode);
        })
        .onNodeRightClick((obj) => {
          if (onNodeDoubleClick) onNodeDoubleClick(obj as unknown as GraphNode);
        })
        .graphData({
          nodes: nodes.map(n => ({ ...n })),
          links: edges.map(e => ({ source: e.source, target: e.target, type: e.type })),
        });

      graph.d3Force('charge')?.strength(-20);
      graph.d3Force('link')?.distance(40);

      graphRef.current = graph;

      const handleResize = () => {
        if (containerRef.current) {
          graph.width(containerRef.current.clientWidth);
          graph.height(containerRef.current.clientHeight);
        }
      };
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        graph._destructor();
      };
    }, [nodes, edges]); // Only re-create on data change

    // Refresh visual properties when highlight/selection changes
    useEffect(() => {
      if (graphRef.current) {
        graphRef.current.nodeColor(graphRef.current.nodeColor());
        graphRef.current.nodeVal(graphRef.current.nodeVal());
        graphRef.current.linkColor(graphRef.current.linkColor());
        graphRef.current.linkWidth(graphRef.current.linkWidth());
        graphRef.current.linkDirectionalParticles(graphRef.current.linkDirectionalParticles());
        // Re-evaluate edge labels when selection changes
        graphRef.current.linkThreeObject(graphRef.current.linkThreeObject());
      }
    }, [highlightNodes, highlightEdges, selectedNodeId]);

    return <div ref={containerRef} className="w-full h-full" />;
  }
);

Graph3D.displayName = 'Graph3D';
