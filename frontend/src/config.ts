export const COUNTRY_COLORS: Record<string, string> = {
  US: '#4285F4', UK: '#EA4335', DE: '#FBBC04', JP: '#34A853',
  CA: '#FF6D01', AU: '#46BDC6', FR: '#7B61FF', BR: '#00C853',
  IN: '#FF7043', KR: '#AB47BC', NL: '#FF8F00', SE: '#00ACC1',
  IT: '#E53935', ES: '#F4511E', MX: '#8D6E63', ZA: '#78909C',
  SA: '#26A69A', AE: '#5C6BC0', SG: '#66BB6A', PH: '#FFCA28',
  TH: '#EC407A', NG: '#8BC34A', KE: '#FF5722', CO: '#29B6F6',
  CL: '#FFA726', PL: '#9CCC65', CZ: '#EF5350', IL: '#42A5F5',
};

export const DEFAULT_COUNTRY_COLOR = '#555555';

export const NODE_TYPE_CONFIG: Record<string, { color: string; shape: string; size: number }> = {
  file:     { color: '#ff4444', shape: 'sphere', size: 4 },
  host:     { color: '#4488ff', shape: 'sphere', size: 5 },
  email:    { color: '#ffaa00', shape: 'sphere', size: 3 },
  domain:   { color: '#00ccaa', shape: 'sphere', size: 6 },
  ip:       { color: '#aa44ff', shape: 'sphere', size: 5 },
  user:     { color: '#44aaff', shape: 'sphere', size: 3 },
  country:  { color: '#ffcc00', shape: 'sphere', size: 8 },
  tenant:   { color: '#ff6600', shape: 'sphere', size: 7 },
  campaign: { color: '#ff0066', shape: 'sphere', size: 9 },
  url:      { color: '#00aacc', shape: 'sphere', size: 3 },
  process:  { color: '#cc4400', shape: 'sphere', size: 3 },
};
