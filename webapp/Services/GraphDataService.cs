using System.Text.Json;
using System.Text.Json.Serialization;

namespace webapp.Services;

public class GraphNode
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";
    [JsonPropertyName("label")]
    public string Label { get; set; } = "";
    [JsonPropertyName("properties")]
    public Dictionary<string, JsonElement> Properties { get; set; } = new();
}

public class GraphEdge
{
    [JsonPropertyName("source")]
    public string Source { get; set; } = "";
    [JsonPropertyName("target")]
    public string Target { get; set; } = "";
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";
    [JsonPropertyName("properties")]
    public Dictionary<string, JsonElement> Properties { get; set; } = new();
}

public class GraphDataService
{
    private List<GraphNode> _nodes = new();
    private List<GraphEdge> _edges = new();
    private Dictionary<string, GraphNode> _nodesById = new();
    private Dictionary<string, List<GraphEdge>> _edgesBySource = new();
    private Dictionary<string, List<GraphEdge>> _edgesByTarget = new();

    public void LoadData()
    {
        // Try data/graph first, fall back to data/sample
        var basePath = AppContext.BaseDirectory;
        var graphDir = Path.Combine(basePath, "data", "graph");
        var sampleDir = Path.Combine(basePath, "data", "sample");

        var dataDir = Directory.Exists(graphDir) && File.Exists(Path.Combine(graphDir, "nodes.json"))
            ? graphDir
            : sampleDir;

        var nodesPath = Path.Combine(dataDir, "nodes.json");
        var edgesPath = Path.Combine(dataDir, "edges.json");

        if (File.Exists(nodesPath))
        {
            var json = File.ReadAllText(nodesPath);
            _nodes = JsonSerializer.Deserialize<List<GraphNode>>(json) ?? new();
        }
        if (File.Exists(edgesPath))
        {
            var json = File.ReadAllText(edgesPath);
            _edges = JsonSerializer.Deserialize<List<GraphEdge>>(json) ?? new();
        }

        // Build indexes
        _nodesById = _nodes.ToDictionary(n => n.Id, n => n);
        _edgesBySource = _edges.GroupBy(e => e.Source).ToDictionary(g => g.Key, g => g.ToList());
        _edgesByTarget = _edges.GroupBy(e => e.Target).ToDictionary(g => g.Key, g => g.ToList());

        Console.WriteLine($"Loaded {_nodes.Count} nodes and {_edges.Count} edges from {dataDir}");
    }

    public (List<GraphNode> Nodes, List<GraphEdge> Edges) GetGraph(
        string? type = null, string? country = null, string? campaign = null,
        string? timeStart = null, string? timeEnd = null)
    {
        var nodes = _nodes.AsEnumerable();

        if (!string.IsNullOrEmpty(type))
        {
            var types = type.Split(',').Select(t => t.Trim()).ToHashSet(StringComparer.OrdinalIgnoreCase);
            nodes = nodes.Where(n => types.Contains(n.Type));
        }

        if (!string.IsNullOrEmpty(country))
        {
            var codes = country.Split(',').Select(c => c.Trim().ToUpperInvariant()).ToHashSet();
            nodes = nodes.Where(n =>
            {
                var cc = GetStringProp(n, "country_code") ?? GetStringProp(n, "country") ?? "";
                return codes.Contains(cc.ToUpperInvariant()) ||
                       (n.Type == "country" && codes.Contains(n.Id.ToUpperInvariant()));
            });
        }

        if (!string.IsNullOrEmpty(campaign))
        {
            var campaigns = campaign.Split(',').Select(c => c.Trim()).ToHashSet();
            nodes = nodes.Where(n =>
            {
                var cid = GetStringProp(n, "campaign_id") ?? GetStringProp(n, "cluster_id") ?? "";
                return campaigns.Contains(cid) ||
                       (n.Type == "campaign" && campaigns.Contains(n.Id));
            });
        }

        // Time filtering
        if (!string.IsNullOrEmpty(timeStart) || !string.IsNullOrEmpty(timeEnd))
        {
            nodes = nodes.Where(n =>
            {
                var ts = GetStringProp(n, "timestamp") ?? GetStringProp(n, "delivery_time") ?? GetStringProp(n, "first_seen");
                if (ts == null) return true;
                if (!string.IsNullOrEmpty(timeStart) && string.Compare(ts, timeStart, StringComparison.Ordinal) < 0) return false;
                if (!string.IsNullOrEmpty(timeEnd) && string.Compare(ts, timeEnd, StringComparison.Ordinal) > 0) return false;
                return true;
            });
        }

        var filteredNodes = nodes.ToList();
        var nodeIds = filteredNodes.Select(n => n.Id).ToHashSet();
        var filteredEdges = _edges.Where(e => nodeIds.Contains(e.Source) && nodeIds.Contains(e.Target)).ToList();

        return (filteredNodes, filteredEdges);
    }

    public object GetSummary()
    {
        var nodeTypeCounts = _nodes.GroupBy(n => n.Type).ToDictionary(g => g.Key, g => g.Count());
        var edgeTypeCounts = _edges.GroupBy(e => e.Type).ToDictionary(g => g.Key, g => g.Count());

        var countries = new HashSet<string>();
        var campaigns = new HashSet<string>();
        var tenants = new HashSet<string>();

        foreach (var n in _nodes)
        {
            var cc = GetStringProp(n, "country_code");
            if (!string.IsNullOrEmpty(cc)) countries.Add(cc);
            if (n.Type == "country") countries.Add(n.Id);

            var cid = GetStringProp(n, "campaign_id") ?? GetStringProp(n, "cluster_id");
            if (!string.IsNullOrEmpty(cid)) campaigns.Add(cid);
            if (n.Type == "campaign") campaigns.Add(n.Id);

            var tid = GetStringProp(n, "tenant_id");
            if (!string.IsNullOrEmpty(tid)) tenants.Add(tid);
            if (n.Type == "tenant") tenants.Add(n.Id);
        }

        return new
        {
            total_nodes = _nodes.Count,
            total_edges = _edges.Count,
            node_types = nodeTypeCounts,
            edge_types = edgeTypeCounts,
            countries = countries.OrderBy(c => c).ToList(),
            campaigns = campaigns.OrderBy(c => c).ToList(),
            tenants = tenants.OrderBy(t => t).ToList(),
        };
    }

    public GraphNode? GetNode(string nodeId) => _nodesById.GetValueOrDefault(nodeId);

    public List<GraphEdge> GetConnectedEdges(string nodeId)
    {
        var fromSource = _edgesBySource.GetValueOrDefault(nodeId, new());
        var fromTarget = _edgesByTarget.GetValueOrDefault(nodeId, new());
        return fromSource.Concat(fromTarget).ToList();
    }

    public (List<GraphNode> Nodes, List<GraphEdge> Edges) GetNeighbors(string nodeId)
    {
        var node = GetNode(nodeId);
        if (node == null) return (new(), new());

        var connectedEdges = GetConnectedEdges(nodeId);
        var neighborIds = new HashSet<string>();
        foreach (var e in connectedEdges)
        {
            neighborIds.Add(e.Source);
            neighborIds.Add(e.Target);
        }
        neighborIds.Remove(nodeId);

        var neighbors = neighborIds.Where(id => _nodesById.ContainsKey(id)).Select(id => _nodesById[id]).ToList();
        return (new List<GraphNode> { node }.Concat(neighbors).ToList(), connectedEdges);
    }

    public List<GraphNode> Search(string query, int limit = 50)
    {
        var q = query.ToLowerInvariant();
        var results = new List<GraphNode>();

        foreach (var node in _nodes)
        {
            if (results.Count >= limit) break;

            if (node.Label.Contains(q, StringComparison.OrdinalIgnoreCase) ||
                node.Id.Contains(q, StringComparison.OrdinalIgnoreCase))
            {
                results.Add(node);
                continue;
            }

            // Search all string properties
            bool matched = false;
            foreach (var (key, val) in node.Properties)
            {
                if (val.ValueKind == JsonValueKind.String)
                {
                    var sv = val.GetString();
                    if (sv != null && sv.Contains(q, StringComparison.OrdinalIgnoreCase))
                    {
                        results.Add(node);
                        matched = true;
                        break;
                    }
                }
                else if (val.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in val.EnumerateArray())
                    {
                        if (item.ValueKind == JsonValueKind.String)
                        {
                            var sv = item.GetString();
                            if (sv != null && sv.Contains(q, StringComparison.OrdinalIgnoreCase))
                            {
                                results.Add(node);
                                matched = true;
                                break;
                            }
                        }
                    }
                    if (matched) break;
                }
            }
        }

        return results;
    }

    private static string? GetStringProp(GraphNode node, string key)
    {
        if (node.Properties.TryGetValue(key, out var val) && val.ValueKind == JsonValueKind.String)
            return val.GetString();
        return null;
    }
}
