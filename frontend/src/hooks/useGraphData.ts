import { useState, useEffect } from 'react';
import type { GraphData } from '../types';

export function useGraphData(filters?: Record<string, string>) {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
  }, [filterKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error };
}
