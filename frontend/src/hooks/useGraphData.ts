import { useState, useEffect, useCallback } from 'react';
import type { GraphData } from '../types';

export function useGraphData(filters?: Record<string, string>) {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const filterKey = JSON.stringify(filters);

  useEffect(() => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
    }
    const qs = params.toString();
    const url = `/api/graph${qs ? '?' + qs : ''}`;

    setLoading(true);
    fetch(url)
      .then(r => r.json())
      .then((d: GraphData) => { setData(d); setError(null); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filterKey, reloadKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const regenerate = useCallback(async (seed?: number, nodes: number = 100) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (seed !== undefined) params.set('seed', String(seed));
      params.set('nodes', String(nodes));
      const qs = params.toString();

      const resp = await fetch(`/api/generate?${qs}`, { method: 'POST' });
      if (!resp.ok) throw new Error(`Generate failed: ${resp.statusText}`);

      // Trigger reload of graph data
      setReloadKey(k => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generate failed');
      setLoading(false);
    }
  }, []);

  return { data, loading, error, regenerate };
}
