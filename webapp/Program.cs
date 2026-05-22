using webapp.Services;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();

// Add the graph data service and campaign generator as singletons
builder.Services.AddSingleton<GraphDataService>();
builder.Services.AddSingleton<CampaignGenerator>();

var app = builder.Build();

// Initialize graph data on startup
var graphService = app.Services.GetRequiredService<GraphDataService>();
graphService.LoadData();

app.UseStaticFiles();
app.MapControllers();

// SPA fallback - serve index.html for any unmatched routes
app.MapFallbackToFile("index.html");

app.Run();
