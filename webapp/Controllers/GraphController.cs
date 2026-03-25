using Microsoft.AspNetCore.Mvc;
using webapp.Services;

namespace webapp.Controllers;

[ApiController]
[Route("api")]
public class GraphController : ControllerBase
{
    private readonly GraphDataService _graphData;
    private readonly CampaignGenerator _generator;

    public GraphController(GraphDataService graphData, CampaignGenerator generator)
    {
        _graphData = graphData;
        _generator = generator;
    }

    [HttpGet("graph")]
    public IActionResult GetGraph(
        [FromQuery] string? type = null,
        [FromQuery] string? country = null,
        [FromQuery] string? campaign = null,
        [FromQuery] string? time_start = null,
        [FromQuery] string? time_end = null)
    {
        var (nodes, edges) = _graphData.GetGraph(type, country, campaign, time_start, time_end);
        return Ok(new { nodes, edges });
    }

    [HttpGet("graph/summary")]
    public IActionResult GetSummary()
    {
        return Ok(_graphData.GetSummary());
    }

    [HttpGet("nodes/{**nodeId}")]
    public IActionResult GetNode(string nodeId)
    {
        // Check if this is a neighbors request
        if (nodeId.EndsWith("/neighbors"))
        {
            var actualId = nodeId[..^"/neighbors".Length];
            return GetNeighbors(actualId);
        }

        var node = _graphData.GetNode(nodeId);
        if (node == null)
            return NotFound(new { detail = $"Node '{nodeId}' not found" });

        var edges = _graphData.GetConnectedEdges(nodeId);
        return Ok(new { node, edges });
    }

    private IActionResult GetNeighbors(string nodeId)
    {
        var node = _graphData.GetNode(nodeId);
        if (node == null)
            return NotFound(new { detail = $"Node '{nodeId}' not found" });

        var (nodes, edges) = _graphData.GetNeighbors(nodeId);
        return Ok(new { nodes, edges });
    }

    [HttpPost("generate")]
    public IActionResult Generate([FromQuery] int? seed = null, [FromQuery] int nodes = 100)
    {
        var actualSeed = seed ?? Random.Shared.Next(1, 999999);
        var (newNodes, newEdges) = _generator.Generate(actualSeed, nodes);

        _graphData.ReplaceData(newNodes, newEdges);

        return Ok(new
        {
            seed = actualSeed,
            total_nodes = newNodes.Count,
            total_edges = newEdges.Count,
        });
    }

    [HttpGet("search")]
    public IActionResult Search([FromQuery] string q)
    {
        if (string.IsNullOrEmpty(q))
            return BadRequest(new { detail = "Query parameter 'q' is required" });

        var results = _graphData.Search(q);
        return Ok(new { results, total = results.Count, query = q });
    }
}
