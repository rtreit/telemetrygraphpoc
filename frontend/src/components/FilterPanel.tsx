import { useState, useEffect } from 'react';
import { NODE_TYPE_CONFIG, COUNTRY_COLORS } from '../config';

interface FilterState {
  types: Set<string>;
  countries: Set<string>;
  campaign: string;
}

interface SummaryData {
  node_types: Record<string, number>;
  countries: string[];
  campaigns: string[];
}

interface FilterPanelProps {
  onFiltersChange: (filters: Record<string, string>) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function FilterPanel({ onFiltersChange, isOpen, onToggle: _onToggle }: FilterPanelProps) {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [filterState, setFilterState] = useState<FilterState>({
    types: new Set(),
    countries: new Set(),
    campaign: '',
  });

  useEffect(() => {
    fetch('/api/graph/summary')
      .then(r => r.json())
      .then(setSummary)
      .catch(console.error);
  }, []);

  const applyFilters = (state: FilterState) => {
    const filters: Record<string, string> = {};
    if (state.types.size > 0) filters.type = Array.from(state.types).join(',');
    if (state.countries.size > 0) filters.country = Array.from(state.countries).join(',');
    if (state.campaign) filters.campaign = state.campaign;
    onFiltersChange(filters);
  };

  const toggleType = (type: string) => {
    setFilterState(prev => {
      const next = { ...prev, types: new Set(prev.types) };
      if (next.types.has(type)) next.types.delete(type);
      else next.types.add(type);
      applyFilters(next);
      return next;
    });
  };

  const toggleCountry = (code: string) => {
    setFilterState(prev => {
      const next = { ...prev, countries: new Set(prev.countries) };
      if (next.countries.has(code)) next.countries.delete(code);
      else next.countries.add(code);
      applyFilters(next);
      return next;
    });
  };

  const setCampaign = (id: string) => {
    setFilterState(prev => {
      const next = { ...prev, campaign: id };
      applyFilters(next);
      return next;
    });
  };

  const clearAll = () => {
    const cleared = { types: new Set<string>(), countries: new Set<string>(), campaign: '' };
    setFilterState(cleared);
    onFiltersChange({});
  };

  if (!isOpen) return null;

  return (
    <div className="w-72 bg-gray-900/95 border-r border-gray-700 flex flex-col h-full overflow-y-auto">
      <div className="p-4 border-b border-gray-700 flex justify-between items-center">
        <h2 className="text-sm font-bold uppercase tracking-wider text-gray-400">Filters</h2>
        <button onClick={clearAll} className="text-xs text-blue-400 hover:text-blue-300">Clear All</button>
      </div>

      {/* Node Types */}
      <div className="p-4 border-b border-gray-800">
        <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Node Types</h3>
        <div className="space-y-1">
          {summary && Object.entries(summary.node_types).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
            <label key={type} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-800 rounded px-1 py-0.5">
              <input
                type="checkbox"
                checked={filterState.types.size === 0 || filterState.types.has(type)}
                onChange={() => toggleType(type)}
                className="rounded border-gray-600"
              />
              <span 
                className="w-2.5 h-2.5 rounded-full" 
                style={{ backgroundColor: NODE_TYPE_CONFIG[type]?.color || '#888' }}
              />
              <span className="text-gray-300 flex-1">{type}</span>
              <span className="text-gray-500 text-xs">{count}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Countries */}
      <div className="p-4 border-b border-gray-800">
        <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Countries</h3>
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {summary?.countries.map(code => (
            <label key={code} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-800 rounded px-1 py-0.5">
              <input
                type="checkbox"
                checked={filterState.countries.size === 0 || filterState.countries.has(code)}
                onChange={() => toggleCountry(code)}
                className="rounded border-gray-600"
              />
              <span 
                className="w-2.5 h-2.5 rounded-full" 
                style={{ backgroundColor: COUNTRY_COLORS[code] || '#555' }}
              />
              <span className="text-gray-300">{code}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Campaigns */}
      <div className="p-4">
        <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Campaign</h3>
        <select
          value={filterState.campaign}
          onChange={(e) => setCampaign(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300"
        >
          <option value="">All Campaigns</option>
          {summary?.campaigns.map(id => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
