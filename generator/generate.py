"""Synthetic telemetry generator for the Global Malware IOC Telemetry Graph POC.

Generates attack-campaign-oriented data where the graph tells a story:
  Campaign → Email → User → Host → File (seed IOC) → Process → C2 Domain → IP
                                                        └→ Follow-on Payload

Usage:
    python -m generator.generate --seed 42 --nodes 100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

from generator.models import (
    Campaign,
    Email,
    ExecutionEvent,
    Host,
    MalwareFile,
    NetworkInfra,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("data") / "raw"

COUNTRY_WEIGHTS: list[tuple[str, float]] = [
    ("US", 0.20), ("UK", 0.08), ("DE", 0.07), ("JP", 0.05),
    ("CA", 0.04), ("AU", 0.04), ("FR", 0.04), ("BR", 0.03),
    ("IN", 0.03), ("KR", 0.03), ("NL", 0.02), ("SE", 0.02),
    ("IT", 0.02), ("ES", 0.02), ("MX", 0.02), ("ZA", 0.02),
    ("SA", 0.02), ("AE", 0.02),
    ("SG", 0.01), ("PH", 0.01), ("TH", 0.01), ("NG", 0.01),
    ("KE", 0.01), ("CO", 0.01), ("CL", 0.01), ("PL", 0.01),
    ("CZ", 0.01), ("IL", 0.01),
]

COUNTRIES = [c for c, _ in COUNTRY_WEIGHTS]
WEIGHTS = [w for _, w in COUNTRY_WEIGHTS]

COUNTRY_CITY_CODES: dict[str, list[str]] = {
    "US": ["NYC", "LAX", "CHI", "DAL", "SEA", "MIA", "DEN", "ATL"],
    "UK": ["LON", "MAN", "BRM", "EDI"],
    "DE": ["BER", "MUC", "FRA", "HAM"],
    "JP": ["TKY", "OSA", "NGO"],
    "CA": ["TOR", "VAN", "MTL"],
    "AU": ["SYD", "MEL", "BRI"],
    "FR": ["PAR", "LYO", "MRS"],
    "BR": ["SAO", "RIO", "BSB"],
    "IN": ["MUM", "DEL", "BLR"],
    "KR": ["SEL", "BUS"],
    "NL": ["AMS", "RTD"],
    "SE": ["STO", "GOT"],
    "IT": ["ROM", "MIL"],
    "ES": ["MAD", "BCN"],
    "MX": ["MEX", "GDL"],
    "ZA": ["JNB", "CPT"],
    "SA": ["RUH", "JED"],
    "AE": ["DXB", "AUH"],
    "SG": ["SIN"],
    "PH": ["MNL"],
    "TH": ["BKK"],
    "NG": ["LOS"],
    "KE": ["NBO"],
    "CO": ["BOG"],
    "CL": ["SCL"],
    "PL": ["WAW"],
    "CZ": ["PRG"],
    "IL": ["TLV"],
}

TENANT_TEMPLATES = [
    ("Contoso", "NA"), ("Fabrikam", "EU"), ("Woodgrove", "APAC"),
    ("Northwind", "NA"), ("AdventureWorks", "EU"), ("Litware", "APAC"),
    ("Tailspin", "LATAM"), ("WingTip", "MEA"), ("Proseware", "NA"),
    ("VanArsdel", "EU"), ("Trey", "APAC"), ("Datum", "LATAM"),
    ("Munson", "MEA"), ("Alpineski", "NA"), ("Bellows", "EU"),
    ("Coho", "APAC"), ("Margie", "NA"), ("Grafton", "EU"),
    ("Humongous", "LATAM"), ("Relecloud", "MEA"),
]

REGION_TO_COUNTRIES: dict[str, list[str]] = {
    "NA": ["US", "CA"],
    "EU": ["UK", "DE", "FR", "NL", "SE", "IT", "ES", "PL", "CZ"],
    "APAC": ["JP", "KR", "AU", "SG", "PH", "TH", "IN"],
    "LATAM": ["BR", "MX", "CO", "CL"],
    "MEA": ["ZA", "SA", "AE", "NG", "KE", "IL"],
}

LURE_FAMILIES = ["invoice", "shipping_notification", "legal_notice", "payment_reminder", "document_share"]

REGION_VARIANTS = [
    "NA-english", "EU-german", "EU-french", "LATAM-spanish",
    "APAC-japanese", "MEA-english",
]

OS_WEIGHTS = {"Windows": 0.70, "Linux": 0.20, "macOS": 0.10}
DEVICE_TYPES = {"desktop": 0.40, "laptop": 0.30, "server": 0.20, "VM": 0.10}
ENVIRONMENTS = {
    "enterprise_workstation": 0.50, "terminal_server": 0.10,
    "mail_server": 0.05, "cloud_vm": 0.20, "developer_box": 0.15,
}

SECURITY_POSTURE_OPTIONS = [
    ["edr_enabled"],
    ["edr_enabled", "mail_filtering_high"],
    ["mail_filtering_high"],
    ["internet_facing"],
    ["edr_enabled", "internet_facing"],
    ["edr_enabled", "mail_filtering_high", "dlp_enabled"],
    ["mail_filtering_low"],
    [],
]

SUBJECT_TEMPLATES: dict[str, list[str]] = {
    "invoice": [
        "Invoice #{num} — Payment Due {date}",
        "Overdue Invoice #{num} — Immediate Action Required",
        "Your Invoice #{num} from {company}",
        "Revised Invoice #{num} Attached",
    ],
    "shipping_notification": [
        "Your package {tracking} has shipped",
        "Shipment Update — Tracking #{tracking}",
        "Delivery Notification for Order #{num}",
        "Action Required: Package #{tracking} held at customs",
    ],
    "legal_notice": [
        "Legal Notice — Case #{num}",
        "Important: Legal Document Requiring Your Signature",
        "Court Filing Notification — Reference #{num}",
        "Urgent Legal Matter — Response Required",
    ],
    "payment_reminder": [
        "Payment Reminder — Account #{num}",
        "Final Notice: Payment Overdue #{num}",
        "Automatic Payment Failed — Action Required",
        "Balance Due Notification #{num}",
    ],
    "document_share": [
        "{sender} shared a document with you",
        "New document available for review",
        "Shared File: Q{quarter} Report.xlsx",
        "Action Required: Review and Sign Document",
    ],
}

ATTACHMENT_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "invoice": [
        ("Invoice_2024_{num}.xlsx", "xlsx"),
        ("INV-{num}.docm", "docm"),
        ("Invoice_{num}.zip", "zip"),
    ],
    "shipping_notification": [
        ("Shipping_Doc.zip", "zip"),
        ("Tracking_{num}.xlsx", "xlsx"),
        ("Delivery_Notice.iso", "iso"),
    ],
    "legal_notice": [
        ("Legal_Notice.docm", "docm"),
        ("Court_Filing_{num}.zip", "zip"),
        ("Legal_Document.xlsx", "xlsx"),
    ],
    "payment_reminder": [
        ("Payment_Details_{num}.xlsx", "xlsx"),
        ("Statement_{num}.docm", "docm"),
        ("Account_Summary.zip", "zip"),
    ],
    "document_share": [
        ("SharedDocument.docm", "docm"),
        ("Report_Q{quarter}.xlsx", "xlsx"),
        ("Documents.zip", "zip"),
    ],
}

SENDER_DOMAIN_POOL = [
    "notify-billing.com", "secure-docs-online.com", "e-invoicing-portal.net",
    "legal-filings-svc.com", "shiptrack-global.com", "payment-center.net",
    "docsign-portal.com", "billing-updates.net", "courier-notify.com",
    "file-share-cloud.com", "corp-notices.com", "global-logistics-mail.com",
    "account-services-center.net", "edocs-delivery.com", "finops-mail.com",
]

DGA_DOMAINS = [
    "xk3j29.top", "q8vbn2m.xyz", "zr4t7w.club", "m9xp3k.top",
    "j2hn8v.info", "b7wq4r.top", "f5kd9s.xyz", "p3yn7c.club",
    "t8gx2l.top", "w6jr4m.xyz", "v9qn5b.info", "k3hp8t.top",
    "d7yw2x.club", "n4fc6r.xyz", "s8bm3j.top",
]

TYPOSQUAT_DOMAINS = [
    "micr0soft-update.com", "g00gle-drive-share.com", "0nedrive-files.com",
    "wind0ws-update-svc.com", "0ffice365-portal.com", "azur3-cdn.com",
    "sharepo1nt-docs.com", "0utlook-secure.com", "teams-meeting-link.com",
    "ms-auth-verify.com",
]

LEGIT_LOOKING_DOMAINS = [
    "cdn-static-assets.com", "api-gateway-prod.com", "cloud-storage-eu.com",
    "global-metrics-svc.com", "edge-cache-node.com", "telemetry-ingest.com",
    "analytics-pipeline.com", "content-delivery-net.com", "infra-monitor.com",
    "app-health-check.com",
]

HOSTING_PROVIDERS = [
    "BulletShield Hosting", "DarkFiber Ltd", "CloudVPS Pro",
    "PacketStorm Networks", "AWS", "Azure", "DigitalOcean",
    "OVHcloud", "Hetzner", "Linode", "Vultr",
    "CompromisedRelay-ISP",
]

IP_COUNTRIES = [
    "RU", "UA", "RO", "BG", "CN", "VN", "ID", "MY",
    "NL", "DE", "US", "SE", "SG", "BR",
]

PROCESS_NAMES_WINDOWS = [
    "rundll32.exe", "powershell.exe", "cmd.exe", "wscript.exe",
    "mshta.exe", "regsvr32.exe", "certutil.exe",
]
PROCESS_NAMES_LINUX = ["bash", "python3", "sh", "curl", "wget"]
PROCESS_NAMES_MACOS = ["bash", "python3", "osascript", "curl"]

PERSISTENCE_WINDOWS = ["registry_run_key", "scheduled_task", "startup_folder"]
PERSISTENCE_LINUX = ["cron", "systemd_service", "rc_local"]
PERSISTENCE_MACOS = ["launch_agent", "cron", "login_item"]

BEHAVIOR_FLAGS = [
    "credential_theft", "recon", "beaconing", "lateral_movement",
    "data_exfil", "defense_evasion", "privilege_escalation",
    "process_injection", "discovery",
]

FOLLOW_ON_PAYLOAD_TEMPLATES = [
    ("beacon.dll", "PE32"),
    ("implant.exe", "PE32"),
    ("recon.ps1", "script"),
    ("stealer.exe", "PE32"),
    ("loader.bin", "PE32"),
]

# Map attachment extension to MalwareFile.file_type
_ATTACHMENT_EXT_TO_FILE_TYPE: dict[str, str] = {
    "xlsx": "document",
    "docm": "document",
    "zip": "PE32",
    "iso": "PE32",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_from_seed(seed_str: str) -> str:
    return hashlib.sha256(seed_str.encode()).hexdigest()


def _weighted_choice(rng: random.Random, options: dict[str, float]) -> str:
    keys = list(options.keys())
    vals = list(options.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def _make_ip(rng: random.Random) -> str:
    return f"{rng.randint(1,223)}.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"


def _scale(base: int, nodes: int, ref: int = 100) -> int:
    """Scale a count proportionally to --nodes."""
    return max(1, round(base * nodes / ref))


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class TelemetryGenerator:
    """Generates attack-campaign-oriented synthetic telemetry.

    The graph tells a per-host attack story rather than creating a blob of
    interconnected files.  Every host gets at most one email; ~30 % of
    hosts execute the dropper; ~10 % of executing hosts download a
    follow-on payload.
    """

    def __init__(self, seed: int = 42, nodes: int = 100) -> None:
        self.seed = seed
        self.nodes = nodes
        self.rng = random.Random(seed)
        self.fake = Faker()
        Faker.seed(seed)

        # --- scaled counts (ref = 100 nodes) --------------------------------
        self.n_campaigns = max(2, min(6, _scale(3, nodes)))
        self.n_tenants = max(3, min(len(TENANT_TEMPLATES), _scale(4, nodes)))
        self.n_hosts = max(5, _scale(18, nodes))
        # C2 infra scales sub-linearly to stay shared
        self.n_c2_domains = min(15, max(3, _scale(4, nodes, ref=200)))
        self.n_c2_ips = min(15, max(3, _scale(4, nodes, ref=200)))
        self.n_urls = max(5, _scale(8, nodes))
        self.n_follow_on = min(len(FOLLOW_ON_PAYLOAD_TEMPLATES), max(2, _scale(3, nodes, ref=200)))

        # Seed IOC — the ONE dropper hash at the centre of the graph
        self.seed_ioc = _sha256_from_seed(f"seed-ioc-{seed}")

        # Follow-on payload hashes (small, fixed set shared across hosts)
        self._follow_on_hashes = [
            _sha256_from_seed(f"payload-{i}-{seed}")
            for i in range(self.n_follow_on)
        ]

        # Entity storage
        self.campaigns: list[Campaign] = []
        self.tenants: list[dict] = []
        self.hosts: list[Host] = []
        self.emails: list[Email] = []
        self.files: list[MalwareFile] = []
        self.executions: list[ExecutionEvent] = []
        self.network: list[NetworkInfra] = []

        # Internal lookup structures
        self._c2_domains: list[str] = []
        self._c2_ips: list[str] = []
        self._domain_ip_map: dict[str, str] = {}
        self._campaign_sender_domains: dict[str, list[str]] = {}
        self._host_email: dict[str, Email] = {}  # device_id → Email

    # ----- campaigns --------------------------------------------------------

    def _generate_campaigns(self) -> None:
        base_start = datetime(2024, 10, 7, tzinfo=timezone.utc)
        infra_clusters = [f"INFRA-{chr(65 + i)}" for i in range(max(2, self.n_campaigns - 1))]

        used_variants: list[str] = []
        used_lures: list[str] = []

        for i in range(self.n_campaigns):
            cluster_id = f"CAMP-{i + 1:03d}"
            variant = self.rng.choice(
                [v for v in REGION_VARIANTS if v not in used_variants] or REGION_VARIANTS
            )
            used_variants.append(variant)
            lure = self.rng.choice(
                [l for l in LURE_FAMILIES if l not in used_lures] or LURE_FAMILIES
            )
            used_lures.append(lure)

            offset_days = i * self.rng.randint(2, 5)
            start = base_start + timedelta(days=offset_days)
            end = start + timedelta(days=self.rng.randint(10, 18))

            # Pick sender domains; allow overlap between campaigns for reuse
            n_senders = min(self.rng.randint(2, 4), len(SENDER_DOMAIN_POOL))
            sender_domains = self.rng.sample(SENDER_DOMAIN_POOL, k=n_senders)
            self._campaign_sender_domains[cluster_id] = sender_domains

            region_key = variant.split("-")[0]
            target = list(REGION_TO_COUNTRIES.get(region_key, COUNTRIES[:5]))
            extra = self.rng.sample(
                [c for c in COUNTRIES if c not in target],
                k=min(2, len(COUNTRIES) - len(target)),
            )
            target_countries = target + extra

            self.campaigns.append(Campaign(
                cluster_id=cluster_id,
                region_variant=variant,
                lure_family=lure,
                time_window_start=start,
                time_window_end=end,
                infra_reuse_cluster=self.rng.choice(infra_clusters),
                sender_domains=sender_domains,
                target_countries=target_countries,
            ))

    # ----- tenants ----------------------------------------------------------

    def _generate_tenants(self) -> None:
        templates = list(TENANT_TEMPLATES)
        self.rng.shuffle(templates)
        for i in range(self.n_tenants):
            name, region = templates[i % len(templates)]
            tid = f"tenant-{name.lower()}-{region.lower()}"
            region_countries = REGION_TO_COUNTRIES.get(region, COUNTRIES[:3])
            n_countries = self.rng.randint(1, min(3, len(region_countries)))
            countries = self.rng.sample(region_countries, k=n_countries)
            self.tenants.append({
                "tenant_id": tid,
                "name": f"{name}-{region}",
                "countries": countries,
            })

    # ----- hosts ------------------------------------------------------------

    def _generate_hosts(self) -> None:
        host_counter: dict[str, int] = {}
        for _ in range(self.n_hosts):
            country = self.rng.choices(COUNTRIES, weights=WEIGHTS, k=1)[0]
            tenant = self.rng.choice(
                [t for t in self.tenants if country in t["countries"]] or self.tenants
            )
            os_family = _weighted_choice(self.rng, OS_WEIGHTS)
            dev_type = _weighted_choice(self.rng, DEVICE_TYPES)
            env = _weighted_choice(self.rng, ENVIRONMENTS)

            city_codes = COUNTRY_CITY_CODES.get(country, ["HQ"])
            city = self.rng.choice(city_codes)
            prefix = "SRV" if dev_type == "server" else "WS"
            key = f"{prefix}-{country}-{city}"
            host_counter[key] = host_counter.get(key, 0) + 1
            hostname = f"{key}-{host_counter[key]:04d}"

            device_id = f"dev-{uuid.UUID(int=self.rng.getrandbits(128), version=4)}"
            machine_guid = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
            user = self.fake.user_name()
            posture = self.rng.choice(SECURITY_POSTURE_OPTIONS)

            self.hosts.append(Host(
                device_id=device_id,
                machine_guid=machine_guid,
                hostname=hostname,
                os_family=os_family,
                device_type=dev_type,
                environment=env,
                country=country,
                tenant_id=tenant["tenant_id"],
                user=user,
                security_posture=posture,
            ))

    # ----- emails -----------------------------------------------------------

    def _generate_emails(self) -> None:
        """One email per host — every host in the graph received a phishing email."""
        for host in self.hosts:
            # Pick a campaign whose target countries include this host's country
            matching = [c for c in self.campaigns if host.country in c.target_countries]
            campaign = self.rng.choice(matching) if matching else self.rng.choice(self.campaigns)

            sender_domain = self.rng.choice(self._campaign_sender_domains[campaign.cluster_id])
            sender_user = self.fake.user_name()
            sender = f"{sender_user}@{sender_domain}"

            lure = campaign.lure_family
            subj_template = self.rng.choice(SUBJECT_TEMPLATES[lure])
            num = f"{self.rng.randint(1000, 9999)}"
            subject = subj_template.format(
                num=num,
                date=self.fake.date_between(
                    start_date=campaign.time_window_start,
                    end_date=campaign.time_window_end,
                ).strftime("%Y-%m-%d"),
                tracking=f"TRK{self.rng.randint(100000, 999999)}",
                company=self.fake.company(),
                sender=sender_user,
                quarter=self.rng.randint(1, 4),
            )

            att_name_template, att_type = self.rng.choice(ATTACHMENT_TEMPLATES[lure])
            att_name = att_name_template.format(num=num, quarter=self.rng.randint(1, 4))

            delta = (campaign.time_window_end - campaign.time_window_start).total_seconds()
            delivery = campaign.time_window_start + timedelta(seconds=self.rng.uniform(0, delta))

            spf = self.rng.choices(["pass", "fail", "none"], weights=[0.60, 0.30, 0.10], k=1)[0]
            dkim = self.rng.choices(["pass", "fail", "none"], weights=[0.55, 0.35, 0.10], k=1)[0]
            dmarc = self.rng.choices(["pass", "fail", "none"], weights=[0.50, 0.35, 0.15], k=1)[0]

            message_id = f"<{uuid.UUID(int=self.rng.getrandbits(128), version=4)}@{sender_domain}>"

            reply_to = None
            if self.rng.random() < 0.3:
                reply_to = f"{self.fake.user_name()}@{self.rng.choice(SENDER_DOMAIN_POOL)}"

            email = Email(
                message_id=message_id,
                sender=sender,
                sender_domain=sender_domain,
                reply_to=reply_to,
                subject=subject,
                attachment_name=att_name,
                attachment_type=att_type,
                delivery_time=delivery,
                recipient_user=host.user,
                recipient_tenant=host.tenant_id,
                country=host.country,
                spf=spf,
                dkim=dkim,
                dmarc=dmarc,
                campaign_id=campaign.cluster_id,
            )
            self.emails.append(email)
            self._host_email[host.device_id] = email

    # ----- network infra ----------------------------------------------------

    def _generate_network(self) -> None:
        """Generate C2 domains, IPs and URL entries (shared across campaigns)."""
        all_c2 = list(DGA_DOMAINS) + list(TYPOSQUAT_DOMAINS) + list(LEGIT_LOOKING_DOMAINS)
        self.rng.shuffle(all_c2)
        self._c2_domains = all_c2[: self.n_c2_domains]

        seen_ips: set[str] = set()
        while len(self._c2_ips) < self.n_c2_ips:
            ip = _make_ip(self.rng)
            if ip not in seen_ips:
                seen_ips.add(ip)
                self._c2_ips.append(ip)

        # Map C2 domains → IPs (some share IPs = infrastructure reuse)
        for d in self._c2_domains:
            self._domain_ip_map[d] = self.rng.choice(self._c2_ips)

        uri_paths = [
            "/update/check", "/api/v2/beacon", "/gate.php", "/submit",
            "/cdn/loader.js", "/static/payload.bin", "/config.json",
            "/panel/login", "/drop/stage2", "/health",
        ]

        # One base URL per C2 domain
        for d in self._c2_domains:
            ip = self._domain_ip_map[d]
            protocol = self.rng.choice(["https", "http"])
            port = 443 if protocol == "https" else 80
            uri = self.rng.choice(uri_paths)
            cert = _sha256_from_seed(f"cert-{d}")[:40] if protocol == "https" else None
            ip_country = self.rng.choice(IP_COUNTRIES)
            asn = f"AS{self.rng.randint(10000, 99999)}"
            provider = self.rng.choice(HOSTING_PROVIDERS)

            self.network.append(NetworkInfra(
                url=f"{protocol}://{d}{uri}",
                domain=d,
                ip=ip,
                asn=asn,
                hosting_provider=provider,
                protocol=protocol,
                port=port,
                uri_path=uri,
                ssl_cert_fingerprint=cert,
                ip_country=ip_country,
            ))

        # Extra URL variants on the same C2 domains
        extra_urls = self.n_urls - len(self.network)
        for _ in range(max(0, extra_urls)):
            d = self.rng.choice(self._c2_domains)
            ip = self._domain_ip_map[d]
            protocol = self.rng.choice(["https", "http"])
            port = 443 if protocol == "https" else 80
            uri = self.rng.choice(uri_paths) + f"/{self.rng.randint(1, 9999)}"
            cert = _sha256_from_seed(f"cert-{d}")[:40] if protocol == "https" else None
            ip_country = self.rng.choice(IP_COUNTRIES)
            asn = f"AS{self.rng.randint(10000, 99999)}"
            provider = self.rng.choice(HOSTING_PROVIDERS)

            self.network.append(NetworkInfra(
                url=f"{protocol}://{d}{uri}",
                domain=d,
                ip=ip,
                asn=asn,
                hosting_provider=provider,
                protocol=protocol,
                port=port,
                uri_path=uri,
                ssl_cert_fingerprint=cert,
                ip_country=ip_country,
            ))

    # ----- files ------------------------------------------------------------

    def _generate_files(self) -> None:
        """Generate file entries for the seed IOC dropper and follow-on payloads.

        Dropper: one MalwareFile per host (same sha256, unique file_name/path
        matching the email attachment so the pipeline creates the
        email → contains_attachment → file edge).

        Follow-on payloads: a small fixed set of unique sha256 hashes shared
        across any host that downloads them.
        """
        base_time = datetime(2024, 10, 5, tzinfo=timezone.utc)

        # -- seed IOC dropper instances (one per host) -----------------------
        for host in self.hosts:
            email = self._host_email.get(host.device_id)
            if email is None:
                continue
            # file_name = email attachment_name so pipeline can match them
            fname = email.attachment_name
            fpath = self._os_path(host.os_family, host.user, fname)
            file_type = _ATTACHMENT_EXT_TO_FILE_TYPE.get(email.attachment_type, "PE32")
            seen = base_time + timedelta(hours=self.rng.randint(0, 72))
            self.files.append(MalwareFile(
                sha256=self.seed_ioc,
                file_name=fname,
                file_path=fpath,
                file_type=file_type,
                file_size=self.rng.randint(180_000, 350_000),
                signature_status=self.rng.choice(["unsigned", "invalid", "revoked"]),
                first_seen=seen,
                last_seen=seen + timedelta(hours=self.rng.randint(1, 48)),
            ))

        # -- follow-on payload files (small global set) ----------------------
        templates = list(FOLLOW_ON_PAYLOAD_TEMPLATES)
        self.rng.shuffle(templates)
        for i, sha in enumerate(self._follow_on_hashes):
            pay_name, pay_type = templates[i % len(templates)]
            seen = base_time + timedelta(hours=self.rng.randint(24, 168))
            self.files.append(MalwareFile(
                sha256=sha,
                file_name=pay_name,
                file_path=f"C:\\ProgramData\\{pay_name}",
                file_type=pay_type,
                file_size=self.rng.randint(20_000, 800_000),
                signature_status="unsigned",
                first_seen=seen,
                last_seen=seen + timedelta(hours=self.rng.randint(1, 72)),
                dropped_by=self.seed_ioc,
            ))

    def _os_path(self, os_family: str, user: str, fname: str) -> str:
        if os_family == "Windows":
            bases = [
                f"C:\\Users\\{user}\\AppData\\Local\\Temp\\",
                f"C:\\Users\\{user}\\Downloads\\",
                "C:\\ProgramData\\",
                "C:\\Windows\\Temp\\",
            ]
        elif os_family == "Linux":
            bases = [
                "/tmp/",
                "/var/tmp/",
                f"/home/{user}/.local/share/",
                f"/home/{user}/Downloads/",
            ]
        else:  # macOS
            bases = [
                "/tmp/",
                f"/Users/{user}/Downloads/",
                f"/Users/{user}/Library/Application Support/",
            ]
        return self.rng.choice(bases) + fname

    # ----- executions -------------------------------------------------------

    def _generate_executions(self) -> None:
        """~30 % of hosts execute the dropper; ~10 % of those download a follow-on.

        Each execution event references the seed IOC sha256 and optionally a
        C2 domain (external_connection) and a follow-on payload hash.
        """
        n_executing = max(1, int(len(self.hosts) * 0.30))
        executing_hosts = self.rng.sample(self.hosts, k=n_executing)

        # Guarantee at least one follow-on download when there are enough hosts
        force_follow_on_index = 0 if len(executing_hosts) >= 2 else -1

        for idx, host in enumerate(executing_hosts):
            os_fam = host.os_family
            if os_fam == "Windows":
                proc = self.rng.choice(PROCESS_NAMES_WINDOWS)
                persist = self.rng.choice(PERSISTENCE_WINDOWS) if self.rng.random() < 0.5 else None
                interp = self.rng.choice(["powershell", "cmd", "wscript"]) if self.rng.random() < 0.4 else None
            elif os_fam == "Linux":
                proc = self.rng.choice(PROCESS_NAMES_LINUX)
                persist = self.rng.choice(PERSISTENCE_LINUX) if self.rng.random() < 0.4 else None
                interp = self.rng.choice(["bash", "python3"]) if self.rng.random() < 0.4 else None
            else:
                proc = self.rng.choice(PROCESS_NAMES_MACOS)
                persist = self.rng.choice(PERSISTENCE_MACOS) if self.rng.random() < 0.3 else None
                interp = self.rng.choice(["bash", "osascript"]) if self.rng.random() < 0.3 else None

            # Most executing hosts connect to C2
            ext_conn = self.rng.choice(self._c2_domains) if self.rng.random() < 0.7 else None

            # ~10 % download a follow-on payload (forced for first host)
            if idx == force_follow_on_index:
                payload = self.rng.choice(self._follow_on_hashes)
            elif self.rng.random() < 0.10 and self._follow_on_hashes:
                payload = self.rng.choice(self._follow_on_hashes)
            else:
                payload = None

            n_flags = self.rng.randint(1, 3)
            flags = self.rng.sample(BEHAVIOR_FLAGS, k=min(n_flags, len(BEHAVIOR_FLAGS)))

            ts = datetime(2024, 10, 8, tzinfo=timezone.utc) + timedelta(
                hours=self.rng.randint(0, 14 * 24),
            )

            eid = f"exec-{uuid.UUID(int=self.rng.getrandbits(128), version=4)}"

            self.executions.append(ExecutionEvent(
                event_id=eid,
                host_device_id=host.device_id,
                country=host.country,
                file_sha256=self.seed_ioc,
                process_name=proc,
                persistence_type=persist,
                script_interpreter=interp,
                external_connection=ext_conn,
                follow_on_payload=payload,
                behavior_flags=flags,
                timestamp=ts,
            ))

    # ----- orchestrator -----------------------------------------------------

    def generate_all(self) -> dict[str, int]:
        """Run all generation steps and return entity counts."""
        self._generate_campaigns()
        self._generate_tenants()
        self._generate_hosts()
        self._generate_emails()
        self._generate_network()
        self._generate_files()
        self._generate_executions()

        return {
            "campaigns": len(self.campaigns),
            "tenants": len(self.tenants),
            "hosts": len(self.hosts),
            "emails": len(self.emails),
            "files": len(self.files),
            "executions": len(self.executions),
            "network": len(self.network),
        }

    # ----- serialization ----------------------------------------------------

    def write(self, output_dir: Path | None = None) -> None:
        out = output_dir or OUTPUT_DIR
        out.mkdir(parents=True, exist_ok=True)

        def _dump(name: str, data: list | dict) -> None:
            path = out / name
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

        _dump("campaigns.json", [c.model_dump(mode="json") for c in self.campaigns])
        _dump("tenants.json", self.tenants)
        _dump("hosts.json", [h.model_dump(mode="json") for h in self.hosts])
        _dump("emails.json", [e.model_dump(mode="json") for e in self.emails])
        _dump("files.json", [f.model_dump(mode="json") for f in self.files])
        _dump("executions.json", [e.model_dump(mode="json") for e in self.executions])
        _dump("network.json", [n.model_dump(mode="json") for n in self.network])
        _dump("seed_ioc.json", {
            "sha256": self.seed_ioc,
            "description": "Seed dropper IOC — SHA-256 of the initial malware sample distributed via email campaign",
        })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic malware IOC telemetry data",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--nodes", type=int, default=100, help="Target node count (default: 100)")
    args = parser.parse_args()

    gen = TelemetryGenerator(seed=args.seed, nodes=args.nodes)
    counts = gen.generate_all()
    gen.write()

    unique_file_hashes = len({f.sha256 for f in gen.files})
    total = sum(counts.values())
    print(f"\n{'=' * 50}")
    print(f"  Telemetry generated  (seed={args.seed}, target={args.nodes})")
    print(f"{'=' * 50}")
    for entity, count in counts.items():
        print(f"  {entity:<15} {count:>6}")
    print(f"  {'—' * 22}")
    print(f"  {'total':<15} {total:>6}")
    print(f"  unique file hashes:  {unique_file_hashes}")
    print(f"  seed IOC: {gen.seed_ioc[:16]}...")
    print(f"  output:   {OUTPUT_DIR.resolve()}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
