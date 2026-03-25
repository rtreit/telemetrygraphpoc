using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace webapp.Services;

public class CampaignGenerator
{
    // Weighted country distribution
    private static readonly (string Code, double Weight)[] Countries =
    [
        ("US", 0.20), ("UK", 0.08), ("DE", 0.07), ("JP", 0.05), ("FR", 0.05),
        ("CA", 0.04), ("AU", 0.04), ("BR", 0.04), ("IN", 0.04), ("KR", 0.03),
        ("NL", 0.03), ("IT", 0.03), ("ES", 0.03), ("SE", 0.03), ("MX", 0.03),
        ("SG", 0.02), ("CH", 0.02), ("PL", 0.02), ("ZA", 0.02), ("NO", 0.02),
        ("IL", 0.02), ("TW", 0.02), ("NZ", 0.01), ("IE", 0.01), ("FI", 0.01),
        ("BE", 0.01), ("AT", 0.01), ("CZ", 0.01), ("DK", 0.01), ("PT", 0.01),
    ];

    private static readonly string[] TenantNames =
        ["Contoso", "Fabrikam", "Woodgrove", "Northwind", "AdventureWorks",
         "TailspinToys", "WideWorldImporters", "LitwareInc", "Proseware", "Coho"];

    private static readonly string[] DropperFileNames =
        ["Invoice_2024.exe", "ShippingLabel.exe", "Document_Viewer.exe",
         "Receipt_Details.exe", "PurchaseOrder.exe", "PaymentConfirmation.exe",
         "Tracking_Update.exe", "DeliveryNotice.exe", "Statement_Q4.exe", "TaxForm_2024.exe"];

    private static readonly string[] C2Domains =
        ["xk3j29.top", "q8vbn2m.xyz", "r4kf7p.buzz", "m2xn9w.click", "j7hv3q.top",
         "z5nt8c.xyz", "w9pd2k.buzz", "f6yg4r.click", "b3em7x.top", "v8ck5n.xyz"];

    private static readonly string[] EmailSubjects =
        ["Invoice #INV-{0} Attached", "Your Shipment #{0} Has Shipped",
         "Legal Notice - Case #{0}", "Payment Confirmation #{0}",
         "Action Required: Document #{0}", "Delivery Notification #{0}",
         "Purchase Order PO-{0}", "Updated Statement #{0}",
         "Urgent: Account Verification #{0}", "Tax Document #{0} Ready"];

    private static readonly string[] SenderDomains =
        ["invoices-portal.com", "shipping-alerts.net", "legal-notices.org",
         "payment-confirm.com", "docs-delivery.net", "secure-notify.org",
         "accounts-update.com", "order-tracking.net"];

    private static readonly string[] FirstNames =
        ["james", "mary", "john", "emma", "robert", "sarah", "david", "lisa",
         "michael", "anna", "william", "jennifer", "richard", "karen", "thomas",
         "susan", "mark", "nancy", "steven", "betty"];

    private static readonly string[] LastNames =
        ["smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
         "davis", "martinez", "anderson", "taylor", "thomas", "wilson", "moore",
         "jackson", "martin", "lee", "white", "harris", "clark"];

    private static readonly string[] FollowOnPayloadNames =
        ["svchost_update.dll", "winlogon_helper.dll", "chrome_update.exe",
         "system32_patch.dll", "taskeng_service.exe"];

    private static readonly string[] ProcessNames =
        ["cmd.exe", "powershell.exe", "wscript.exe", "mshta.exe", "rundll32.exe"];

    private static readonly string[] CampaignIds =
        ["CAMP-ALPHA", "CAMP-BRAVO", "CAMP-CHARLIE"];

    public (List<GraphNode> Nodes, List<GraphEdge> Edges) Generate(int seed, int nodeCount = 100)
    {
        var rng = new Random(seed);
        var nodes = new List<GraphNode>();
        var edges = new List<GraphEdge>();
        var nodeIds = new HashSet<string>();

        // Deterministic seed IOC SHA-256
        var seedIocSha256 = ComputeSha256($"seed-ioc-{seed}");

        // Scale parameters
        int tenantCount = Math.Max(3, nodeCount / 25);
        tenantCount = Math.Min(tenantCount, TenantNames.Length);

        // C2 infrastructure (shared across all hosts)
        int c2DomainCount = Math.Min(3 + rng.Next(3), C2Domains.Length);
        int ipCount = 3 + rng.Next(3);
        int urlCount = 5 + rng.Next(4);
        int followOnCount = 2 + rng.Next(2);

        // Build campaign node
        var campaignId = CampaignIds[rng.Next(CampaignIds.Length)];
        AddNode(nodes, nodeIds, campaignId, "campaign", campaignId, new Dictionary<string, object>
        {
            ["cluster_id"] = campaignId,
            ["lure_family"] = "invoice_shipping",
            ["first_seen"] = $"2024-01-{10 + rng.Next(20):D2}T08:00:00Z",
            ["region_variants"] = new[] { "NA", "EU", "APAC" },
        });

        // Build tenants
        var tenants = new List<(string Id, string Name, string Country)>();
        for (int t = 0; t < tenantCount; t++)
        {
            var name = TenantNames[t];
            var tenantId = $"tenant:{name.ToLowerInvariant()}";
            var country = PickWeightedCountry(rng);
            tenants.Add((tenantId, name, country));

            AddNode(nodes, nodeIds, tenantId, "tenant", name, new Dictionary<string, object>
            {
                ["tenant_name"] = name,
                ["country_code"] = country,
                ["industry"] = PickIndustry(rng),
            });
        }

        // Distribute hosts across tenants
        int totalHosts = Math.Max(tenantCount * 2, nodeCount / 8);
        var hostsByTenant = DistributeAmongTenants(rng, totalHosts, tenantCount);

        // Build C2 domains
        var activeDomains = new List<string>();
        for (int d = 0; d < c2DomainCount; d++)
        {
            var domainName = C2Domains[d];
            var domainId = $"domain:{domainName}";
            var domainCountry = PickWeightedCountry(rng);
            activeDomains.Add(domainId);

            AddNode(nodes, nodeIds, domainId, "domain", domainName, new Dictionary<string, object>
            {
                ["domain_name"] = domainName,
                ["registrar"] = "NameCheap Inc.",
                ["registered_date"] = $"2024-01-{1 + rng.Next(28):D2}",
                ["country_code"] = domainCountry,
                ["campaign_id"] = campaignId,
            });
        }

        // Build IPs
        var activeIps = new List<string>();
        for (int i = 0; i < ipCount; i++)
        {
            var ipAddr = $"{45 + rng.Next(200)}.{rng.Next(256)}.{rng.Next(256)}.{rng.Next(256)}";
            var ipId = $"ip:{ipAddr}";
            var ipCountry = PickWeightedCountry(rng);
            activeIps.Add(ipId);

            AddNode(nodes, nodeIds, ipId, "ip", ipAddr, new Dictionary<string, object>
            {
                ["ip_address"] = ipAddr,
                ["asn"] = $"AS{10000 + rng.Next(50000)}",
                ["country_code"] = ipCountry,
            });
        }

        // Domain -> IP edges
        foreach (var domainId in activeDomains)
        {
            var targetIp = activeIps[rng.Next(activeIps.Count)];
            edges.Add(MakeEdge(domainId, targetIp, "resolves_to"));
        }

        // Build URLs
        var activeUrls = new List<string>();
        for (int u = 0; u < urlCount; u++)
        {
            var domainId = activeDomains[rng.Next(activeDomains.Count)];
            var domainLabel = domainId["domain:".Length..];
            var path = $"/dl/{RandomHex(rng, 8)}/{DropperFileNames[rng.Next(DropperFileNames.Length)]}";
            var fullUrl = $"https://{domainLabel}{path}";
            var urlId = $"url:{RandomHex(rng, 12)}";
            activeUrls.Add(urlId);

            AddNode(nodes, nodeIds, urlId, "url", fullUrl, new Dictionary<string, object>
            {
                ["full_url"] = fullUrl,
                ["domain"] = domainLabel,
                ["path"] = path,
                ["country_code"] = GetPropString(nodes, domainId, "country_code"),
            });

            edges.Add(MakeEdge(urlId, domainId, "hosted_on"));
        }

        // Build follow-on payloads (unique file hashes)
        var followOnFiles = new List<(string Sha256, string FileName)>();
        for (int f = 0; f < followOnCount; f++)
        {
            var sha = ComputeSha256($"followon-{seed}-{f}");
            var fname = FollowOnPayloadNames[f % FollowOnPayloadNames.Length];
            followOnFiles.Add((sha, fname));
        }

        // Per-tenant: create hosts, users, emails, files, processes
        int hostIndex = 0;
        for (int t = 0; t < tenantCount; t++)
        {
            var (tenantId, tenantName, tenantCountry) = tenants[t];
            int hostsForTenant = hostsByTenant[t];

            for (int h = 0; h < hostsForTenant; h++)
            {
                hostIndex++;
                var country = rng.NextDouble() < 0.6 ? tenantCountry : PickWeightedCountry(rng);
                var os = PickOS(rng);
                var firstName = FirstNames[rng.Next(FirstNames.Length)];
                var lastName = LastNames[rng.Next(LastNames.Length)];
                var username = $"{firstName}.{lastName}";
                var hostname = $"{tenantName.ToUpperInvariant()[..3]}-{os[..3].ToUpperInvariant()}-{hostIndex:D4}";
                var deviceId = $"device:{Guid.NewGuid().ToString("N")[..16]}";
                var machineGuid = Guid.NewGuid().ToString();

                // Host node
                AddNode(nodes, nodeIds, deviceId, "host", hostname, new Dictionary<string, object>
                {
                    ["hostname"] = hostname,
                    ["device_id"] = deviceId,
                    ["machine_guid"] = machineGuid,
                    ["os"] = os,
                    ["device_type"] = os == "macOS" ? "laptop" : (rng.NextDouble() < 0.5 ? "desktop" : "laptop"),
                    ["country_code"] = country,
                    ["tenant_id"] = tenantId,
                    ["tenant_name"] = tenantName,
                    ["environment"] = rng.NextDouble() < 0.8 ? "corporate" : "remote",
                    ["security_posture"] = rng.NextDouble() < 0.7 ? "managed" : "unmanaged",
                    ["campaign_id"] = campaignId,
                });

                // Host -> Tenant edge
                edges.Add(MakeEdge(deviceId, tenantId, "belongs_to"));

                // User node
                var userId = $"{tenantId}/{username}";
                if (nodeIds.Add(userId))
                {
                    AddNodeDirect(nodes, userId, "user", $"{firstName} {lastName} ({tenantName})", new Dictionary<string, object>
                    {
                        ["username"] = username,
                        ["display_name"] = $"{char.ToUpper(firstName[0])}{firstName[1..]} {char.ToUpper(lastName[0])}{lastName[1..]}",
                        ["email_address"] = $"{username}@{tenantName.ToLowerInvariant()}.com",
                        ["tenant_id"] = tenantId,
                        ["country_code"] = country,
                        ["campaign_id"] = campaignId,
                    });
                }

                // User -> Host edge
                edges.Add(MakeEdge(userId, deviceId, "uses"));

                // Email node
                var emailId = $"email:{RandomHex(rng, 16)}";
                var subjectTemplate = EmailSubjects[rng.Next(EmailSubjects.Length)];
                var subject = string.Format(subjectTemplate, 100000 + rng.Next(900000));
                var senderDomain = SenderDomains[rng.Next(SenderDomains.Length)];
                var sender = $"noreply@{senderDomain}";
                var deliveryDay = rng.Next(1, 29);
                var deliveryHour = rng.Next(6, 22);
                var deliveryTime = $"2024-01-{deliveryDay:D2}T{deliveryHour:D2}:{rng.Next(60):D2}:00Z";
                var dropperFileName = DropperFileNames[rng.Next(DropperFileNames.Length)];

                AddNode(nodes, nodeIds, emailId, "email", subject, new Dictionary<string, object>
                {
                    ["message_id"] = $"<{RandomHex(rng, 20)}@{senderDomain}>",
                    ["sender"] = sender,
                    ["recipient"] = $"{username}@{tenantName.ToLowerInvariant()}.com",
                    ["subject"] = subject,
                    ["attachment_name"] = dropperFileName,
                    ["delivery_time"] = deliveryTime,
                    ["spf_result"] = rng.NextDouble() < 0.3 ? "pass" : "fail",
                    ["dkim_result"] = rng.NextDouble() < 0.2 ? "pass" : "fail",
                    ["dmarc_result"] = "fail",
                    ["country_code"] = country,
                    ["tenant_id"] = tenantId,
                    ["campaign_id"] = campaignId,
                });

                // Campaign -> Email edge
                edges.Add(MakeEdge(campaignId, emailId, "launches"));

                // Email -> User edge
                edges.Add(MakeEdge(emailId, userId, "delivered_to"));

                // File (seed IOC instance per host)
                var filePath = BuildFilePath(os, username, dropperFileName);
                var pathHash = ComputeSha256(filePath)[..8];
                var fileId = $"file:{seedIocSha256[..12]}:{pathHash}";

                AddNode(nodes, nodeIds, fileId, "file", dropperFileName, new Dictionary<string, object>
                {
                    ["sha256"] = seedIocSha256,
                    ["file_name"] = dropperFileName,
                    ["file_path"] = filePath,
                    ["file_size"] = 245760 + rng.Next(102400),
                    ["file_type"] = "PE32 executable",
                    ["is_seed_ioc"] = true,
                    ["first_seen"] = deliveryTime,
                    ["country_code"] = country,
                    ["tenant_id"] = tenantId,
                    ["device_id"] = deviceId,
                    ["campaign_id"] = campaignId,
                    ["signatures"] = new[] { "Trojan.GenericKD", "Mal/Dropper-A" },
                });

                // Email -> File edge (contains attachment)
                edges.Add(MakeEdge(emailId, fileId, "contains"));

                // File -> Host edge (dropped on)
                edges.Add(MakeEdge(fileId, deviceId, "dropped_on"));

                // ~30% of hosts get process execution
                if (rng.NextDouble() < 0.30)
                {
                    var processName = ProcessNames[rng.Next(ProcessNames.Length)];
                    var eventId = RandomHex(rng, 8);
                    var processId = $"{deviceId}/{processName}/{eventId}";
                    var execTime = $"2024-01-{deliveryDay:D2}T{Math.Min(deliveryHour + 1, 23):D2}:{rng.Next(60):D2}:00Z";

                    AddNode(nodes, nodeIds, processId, "process", $"{processName} on {hostname}", new Dictionary<string, object>
                    {
                        ["process_name"] = processName,
                        ["command_line"] = $"{processName} /c \"{filePath}\"",
                        ["pid"] = 1000 + rng.Next(60000),
                        ["parent_process"] = "explorer.exe",
                        ["execution_time"] = execTime,
                        ["country_code"] = country,
                        ["device_id"] = deviceId,
                        ["tenant_id"] = tenantId,
                        ["campaign_id"] = campaignId,
                    });

                    // Process -> File edge (executes)
                    edges.Add(MakeEdge(processId, fileId, "executes"));
                    // Process -> Host edge (runs on)
                    edges.Add(MakeEdge(processId, deviceId, "runs_on"));

                    // Process -> C2 domain
                    var c2Domain = activeDomains[rng.Next(activeDomains.Count)];
                    edges.Add(MakeEdge(processId, c2Domain, "connects_to"));

                    // ~10% of executing processes download follow-on payload (roughly 1/3 of 30%)
                    if (rng.NextDouble() < 0.33)
                    {
                        var (foSha, foName) = followOnFiles[rng.Next(followOnFiles.Count)];
                        var foPath = BuildFilePath(os, username, foName);
                        var foPathHash = ComputeSha256(foPath)[..8];
                        var foFileId = $"file:{foSha[..12]}:{foPathHash}";

                        if (nodeIds.Add(foFileId))
                        {
                            AddNodeDirect(nodes, foFileId, "file", foName, new Dictionary<string, object>
                            {
                                ["sha256"] = foSha,
                                ["file_name"] = foName,
                                ["file_path"] = foPath,
                                ["file_size"] = 102400 + rng.Next(204800),
                                ["file_type"] = foName.EndsWith(".dll") ? "PE32 DLL" : "PE32 executable",
                                ["is_follow_on"] = true,
                                ["first_seen"] = execTime,
                                ["country_code"] = country,
                                ["tenant_id"] = tenantId,
                                ["device_id"] = deviceId,
                                ["campaign_id"] = campaignId,
                                ["signatures"] = new[] { "Trojan.Agent", "Backdoor.Generic" },
                            });
                        }

                        edges.Add(MakeEdge(processId, foFileId, "downloads"));
                    }
                }
            }
        }

        return (nodes, edges);
    }

    private static void AddNode(List<GraphNode> nodes, HashSet<string> ids, string id, string type, string label, Dictionary<string, object> props)
    {
        if (!ids.Add(id)) return;
        AddNodeDirect(nodes, id, type, label, props);
    }

    private static void AddNodeDirect(List<GraphNode> nodes, string id, string type, string label, Dictionary<string, object> props)
    {
        nodes.Add(new GraphNode
        {
            Id = id,
            Type = type,
            Label = label,
            Properties = props.ToDictionary(kv => kv.Key, kv => JsonSerializer.SerializeToElement(kv.Value)),
        });
    }

    private static GraphEdge MakeEdge(string source, string target, string type, Dictionary<string, object>? props = null)
    {
        return new GraphEdge
        {
            Source = source,
            Target = target,
            Type = type,
            Properties = props?.ToDictionary(kv => kv.Key, kv => JsonSerializer.SerializeToElement(kv.Value)) ?? new(),
        };
    }

    private static string PickWeightedCountry(Random rng)
    {
        var roll = rng.NextDouble();
        double cumulative = 0;
        foreach (var (code, weight) in Countries)
        {
            cumulative += weight;
            if (roll < cumulative) return code;
        }
        return Countries[^1].Code;
    }

    private static string PickOS(Random rng)
    {
        var roll = rng.NextDouble();
        if (roll < 0.70) return "Windows";
        if (roll < 0.90) return "Linux";
        return "macOS";
    }

    private static string PickIndustry(Random rng)
    {
        string[] industries = ["Technology", "Finance", "Healthcare", "Manufacturing", "Retail", "Energy", "Government", "Education"];
        return industries[rng.Next(industries.Length)];
    }

    private static string BuildFilePath(string os, string username, string fileName)
    {
        return os switch
        {
            "Windows" => $@"C:\Users\{username}\AppData\Local\Temp\{fileName}",
            "macOS" => $"/Users/{username}/Downloads/{fileName}",
            _ => $"/tmp/{fileName}",
        };
    }

    private static string ComputeSha256(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexStringLower(bytes);
    }

    private static string RandomHex(Random rng, int length)
    {
        var sb = new StringBuilder(length);
        for (int i = 0; i < length; i++)
            sb.Append("0123456789abcdef"[rng.Next(16)]);
        return sb.ToString();
    }

    private static int[] DistributeAmongTenants(Random rng, int total, int tenantCount)
    {
        var result = new int[tenantCount];
        // Give each tenant at least 2 hosts
        int remaining = total - tenantCount * 2;
        for (int i = 0; i < tenantCount; i++)
            result[i] = 2;

        // Distribute remaining randomly
        for (int i = 0; i < Math.Max(0, remaining); i++)
            result[rng.Next(tenantCount)]++;

        return result;
    }

    private static string GetPropString(List<GraphNode> nodes, string nodeId, string key)
    {
        var node = nodes.FirstOrDefault(n => n.Id == nodeId);
        if (node != null && node.Properties.TryGetValue(key, out var val) && val.ValueKind == JsonValueKind.String)
            return val.GetString() ?? "";
        return "";
    }
}
