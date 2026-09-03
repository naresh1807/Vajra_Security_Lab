import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { DiscoveredEndpoint } from "../../types";

interface Props {
  projectId: number;
  endpoints: DiscoveredEndpoint[];
  onSelectHost: (host: string) => void;
}

interface NodePoint { x: number; y: number; endpoint: DiscoveredEndpoint }

export function AttackSurfaceMap({ projectId, endpoints, onSelectHost }: Props) {
  const navigate = useNavigate();
  const graph = useMemo(() => {
    const grouped = new Map<string, DiscoveredEndpoint[]>();
    for (const endpoint of endpoints) grouped.set(endpoint.hostname, [...(grouped.get(endpoint.hostname) ?? []), endpoint]);
    const hosts = [...grouped.entries()].sort((a, b) => b[1].length - a[1].length).slice(0, 10);
    return hosts.map(([hostname, items], index) => {
      const angle = (index / Math.max(hosts.length, 1)) * Math.PI * 2 - Math.PI / 2;
      const host = { x: 450 + Math.cos(angle) * 225, y: 260 + Math.sin(angle) * 165 };
      const shown = items.slice(0, 7).map((endpoint, childIndex): NodePoint => {
        const spread = angle + (childIndex - Math.min(items.length, 7) / 2) * 0.12;
        const distance = 75 + (childIndex % 2) * 20;
        return { x: host.x + Math.cos(spread) * distance, y: host.y + Math.sin(spread) * distance, endpoint };
      });
      return { hostname, host, shown, hidden: Math.max(0, items.length - shown.length) };
    });
  }, [endpoints]);

  if (endpoints.length === 0) return <div className="flex h-72 items-center justify-center text-sm text-slate-600">No endpoints match the current filters.</div>;
  return <div><div className="overflow-x-auto"><svg viewBox="0 0 900 520" className="min-w-[720px]" role="img" aria-label="Interactive attack surface graph">
    <g stroke="#334155" strokeWidth="1">{graph.map((group) => <g key={`edges-${group.hostname}`}><line x1="450" y1="260" x2={group.host.x} y2={group.host.y} />{group.shown.map((node) => <line key={node.endpoint.id} x1={group.host.x} y1={group.host.y} x2={node.x} y2={node.y} />)}</g>)}</g>
    <g><circle cx="450" cy="260" r="48" fill="#6d28d9" opacity=".9" /><text x="450" y="256" textAnchor="middle" fill="white" fontSize="13" fontWeight="600">PROJECT</text><text x="450" y="274" textAnchor="middle" fill="#ddd6fe" fontSize="10">{endpoints.length} endpoints</text></g>
    {graph.map((group) => <g key={group.hostname}><g className="cursor-pointer" onClick={() => onSelectHost(group.hostname)}><circle cx={group.host.x} cy={group.host.y} r="34" fill="#172554" stroke="#3b82f6" strokeWidth="2" /><text x={group.host.x} y={group.host.y - 2} textAnchor="middle" fill="#bfdbfe" fontSize="10">{shorten(group.hostname, 19)}</text><text x={group.host.x} y={group.host.y + 14} textAnchor="middle" fill="#64748b" fontSize="9">{group.shown.length + group.hidden} routes</text></g>{group.shown.map((node) => <g key={node.endpoint.id} className="cursor-pointer" onClick={() => navigate(`/projects/${projectId}/http?endpointId=${node.endpoint.id}`)}><circle cx={node.x} cy={node.y} r="11" fill={node.endpoint.deprecated ? "#78350f" : securityNames(node.endpoint).length ? "#164e63" : "#1e293b"} stroke={node.endpoint.parameter_details.length ? "#a78bfa" : "#475569"} /><title>{node.endpoint.method} {node.endpoint.url}</title><text x={node.x} y={node.y + 24} textAnchor="middle" fill="#94a3b8" fontSize="8">{shorten(node.endpoint.path, 18)}</text></g>)}</g>)}
  </svg></div><div className="flex flex-wrap gap-4 border-t border-vajra-border pt-3 text-[11px] text-slate-500"><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-violet-400" />Has parameters</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-cyan-900" />Authentication declared</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-900" />Deprecated</span><span>Click a host to filter · click a route to inspect</span>{graph.length < new Set(endpoints.map((item) => item.hostname)).size && <span className="text-amber-400">Showing the 10 busiest hosts</span>}</div></div>;
}

function securityNames(endpoint: DiscoveredEndpoint): string[] { return [...new Set(endpoint.security_requirements.flatMap((item) => Object.keys(item)))]; }
function shorten(value: string, length: number): string { return value.length <= length ? value : `${value.slice(0, length - 1)}…`; }
