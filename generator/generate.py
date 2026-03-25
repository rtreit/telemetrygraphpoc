"""Synthetic telemetry generator for the Global Malware IOC Telemetry Graph POC.

Usage:
    python -m generator.generate --seed 42 --nodes 5000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import string
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

FILE_TYPES_DROPPED = [
    ("PE32", ".exe"), ("PE32", ".dll"), ("script", ".ps1"),
    ("script", ".vbs"), ("script", ".bat"), ("script", ".sh"),
    ("document", ".docm"), ("document", ".xlsx"),
]

BENIGN_NAMES = [
    "svchost_helper.exe", "update_service.dll", "system_config.ps1",
    "maintenance.bat", "health_check.vbs", "cleanup_temp.sh",
    "win_diag.exe", "netmon_svc.dll",
]


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


def _scale(base: int, nodes: int, ref: int = 5000) -> int:
    """Scale a count proportionally to --nodes."""
    return max(1, round(base * nodes / ref))


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class TelemetryGenerator:
    def __init__(self, seed: int = 42, nodes: int = 5000) -> None:
        self.seed = seed
        self.nodes = nodes
        self.rng = random.Random(seed)
        self.fake = Faker()
        Faker.seed(seed)

        # Derived counts (scaled proportionally)
        self.n_campaigns = max(3, _scale(4, nodes))
        self.n_tenants = max(5, _scale(18, nodes))
        self.n_hosts = _scale(1000, nodes)
        self.n_domains = _scale(40, nodes)
        self.n_ips = _scale(50, nodes)
        self.n_urls = _scale(65, nodes)

        # Seed IOC
        self.seed_ioc = _sha256_from_seed(f"seed-ioc-{seed}")

        # Storage
        self.campaigns: list[Campaign] = []
        self.tenants: list[dict] = []
        self.hosts: list[Host] = []
        self.emails: list[Email] = []
        self.files: list[MalwareFile] = []
        self.executions: list[ExecutionEvent] = []
        self.network: list[NetworkInfra] = []

        # Internal lookup structures
        self._domains: list[str] = []
        self._ips: list[str] = []
        self._domain_ip_map: dict[str, str] = {}
        self._campaign_sender_domains: dict[str, list[str]] = {}

    # ----- campaigns --------------------------------------------------------

    def _generate_campaigns(self) -> None:
        base_start = datetime(2024, 10, 7, tzinfo=timezone.utc)
        infra_clusters = [f"INFRA-{chr(65 + i)}" for i in range(max(2, self.n_campaigns - 1))]

        used_variants: list[str] = []
        used_lures: list[str] = []

        for i in range(self.n_campaigns):
            cluster_id = f"CAMP-{i+1:03d}"
            variant = self.rng.choice([v for v in REGION_VARIANTS if v not in used_variants] or REGION_VARIANTS)
            used_variants.append(variant)
            lure = self.rng.choice([l for l in LURE_FAMILIES if l not in used_lures] or LURE_FAMILIES)
            used_lures.append(lure)

            offset_days = i * self.rng.randint(2, 5)
            start = base_start + timedelta(days=offset_days)
            end = start + timedelta(days=self.rng.randint(10, 18))

            sender_domains = self.rng.sample(SENDER_DOMAIN_POOL, k=min(self.rng.randint(3, 5), len(SENDER_DOMAIN_POOL)))
            self._campaign_sender_domains[cluster_id] = sender_domains

            region_key = variant.split("-")[0]
            target = REGION_TO_COUNTRIES.get(region_key, COUNTRIES[:5])
            extra = self.rng.sample([c for c in COUNTRIES if c not in target], k=min(3, len(COUNTRIES) - len(target)))
            target_countries = list(target) + extra

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
            self.tenants.append({"tenant_id": tid, "name": f"{name}-{region}", "countries": countries})

    # ----- hosts ------------------------------------------------------------

    def _generate_hosts(self) -> None:
        host_counter: dict[str, int] = {}
        for i in range(self.n_hosts):
            country = self.rng.choices(COUNTRIES, weights=WEIGHTS, k=1)[0]
            tenant = self.rng.choice([t for t in self.tenants if country in t["countries"]]
                                     or self.tenants)
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

    # ----- network infra ----------------------------------------------------

    def _generate_network(self) -> None:
        all_domains = list(DGA_DOMAINS) + list(TYPOSQUAT_DOMAINS) + list(LEGIT_LOOKING_DOMAINS)
        self.rng.shuffle(all_domains)
        self._domains = all_domains[: self.n_domains]

        # Generate IPs
        seen_ips: set[str] = set()
        while len(self._ips) < self.n_ips:
            ip = _make_ip(self.rng)
            if ip not in seen_ips:
                seen_ips.add(ip)
                self._ips.append(ip)

        # Map domains -> IPs (some share IPs for infra reuse)
        for d in self._domains:
            self._domain_ip_map[d] = self.rng.choice(self._ips)

        uri_paths = [
            "/update/check", "/api/v2/beacon", "/gate.php", "/submit",
            "/cdn/loader.js", "/static/payload.bin", "/config.json",
            "/panel/login", "/drop/stage2", "/health",
        ]

        for d in self._domains:
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

        # Generate extra URL variants for remaining budget
        extra_urls = self.n_urls - len(self.network)
        for _ in range(max(0, extra_urls)):
            d = self.rng.choice(self._domains)
            ip = self._domain_ip_map[d]
            protocol = self.rng.choice(["https", "http"])
            port = 443 if protocol == "https" else 80
            uri = self.rng.choice(uri_paths) + f"/{self.rng.randint(1,9999)}"
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

    # ----- emails -----------------------------------------------------------

    def _generate_emails(self) -> None:
        email_hosts = self.rng.sample(self.hosts, k=int(len(self.hosts) * 0.70))

        for host in email_hosts:
            campaign = self.rng.choice(self.campaigns)
            sender_domain = self.rng.choice(self._campaign_sender_domains[campaign.cluster_id])
            sender_user = self.fake.user_name()
            sender = f"{sender_user}@{sender_domain}"

            lure = campaign.lure_family
            templates = SUBJECT_TEMPLATES[lure]
            subj_template = self.rng.choice(templates)
            num = f"{self.rng.randint(1000, 9999)}"
            subject = subj_template.format(
                num=num,
                date=self.fake.date_between(start_date=campaign.time_window_start, end_date=campaign.time_window_end).strftime("%Y-%m-%d"),
                tracking=f"TRK{self.rng.randint(100000, 999999)}",
                company=self.fake.company(),
                sender=sender_user,
                quarter=self.rng.randint(1, 4),
            )

            att_templates = ATTACHMENT_TEMPLATES[lure]
            att_name_template, att_type = self.rng.choice(att_templates)
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

            self.emails.append(Email(
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
            ))

    # ----- files ------------------------------------------------------------

    def _generate_files(self) -> None:
        base_time = datetime(2024, 10, 5, tzinfo=timezone.utc)

        # Seed IOC dropper — appears on many hosts with different names/paths
        dropper_names = [
            "Invoice_2024.exe", "ShippingLabel.exe", "Document_Viewer.exe",
            "update_svc.exe", "acrobat_reader.exe", "winhelper.exe",
        ]
        for host in self.hosts[:min(50, len(self.hosts))]:
            fname = self.rng.choice(dropper_names)
            fpath = self._os_path(host.os_family, host.user, fname)
            seen = base_time + timedelta(hours=self.rng.randint(0, 72))
            self.files.append(MalwareFile(
                sha256=self.seed_ioc,
                file_name=fname,
                file_path=fpath,
                file_type="PE32",
                file_size=self.rng.randint(180_000, 350_000),
                signature_status=self.rng.choice(["unsigned", "invalid", "revoked"]),
                first_seen=seen,
                last_seen=seen + timedelta(hours=self.rng.randint(1, 48)),
            ))

        # Additional dropped/related files for executing hosts (~30-40% of hosts)
        executing_hosts = self.rng.sample(self.hosts, k=int(len(self.hosts) * 0.35))
        for host in executing_hosts:
            n_dropped = self.rng.randint(2, 6)
            for j in range(n_dropped):
                ft, ext = self.rng.choice(FILE_TYPES_DROPPED)
                if self.rng.random() < 0.15:
                    fname = self.rng.choice(BENIGN_NAMES)
                else:
                    fname = f"{self.fake.lexify('??????')}{ext}"
                fpath = self._os_path(host.os_family, host.user, fname)
                sha = _sha256_from_seed(f"dropped-{host.device_id}-{j}-{self.seed}")
                seen = base_time + timedelta(hours=self.rng.randint(0, 120))
                self.files.append(MalwareFile(
                    sha256=sha,
                    file_name=fname,
                    file_path=fpath,
                    file_type=ft,
                    file_size=self.rng.randint(5_000, 500_000),
                    signature_status=self.rng.choice(["unsigned", "invalid"]),
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
        # ~30% of hosts that received the dropper
        email_host_ids = {e.recipient_user for e in self.emails}
        candidate_hosts = [h for h in self.hosts if h.user in email_host_ids]
        executing = self.rng.sample(candidate_hosts, k=max(1, int(len(candidate_hosts) * 0.30)))

        follow_on_hashes = [_sha256_from_seed(f"payload-{i}-{self.seed}") for i in range(10)]

        for host in executing:
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

            ext_conn = self.rng.choice(self._domains) if self.rng.random() < 0.6 else None
            payload = self.rng.choice(follow_on_hashes) if self.rng.random() < 0.10 else None

            n_flags = self.rng.randint(1, 3)
            flags = self.rng.sample(BEHAVIOR_FLAGS, k=min(n_flags, len(BEHAVIOR_FLAGS)))

            ts = datetime(2024, 10, 8, tzinfo=timezone.utc) + timedelta(
                hours=self.rng.randint(0, 14 * 24)
            )

            eid = f"exec-{uuid.UUID(int=self.rng.getrandbits(128), version=4)}"

            # If there's a follow-on payload, also create a file entry for it
            if payload:
                pay_name = self.rng.choice(["stage2.dll", "beacon.exe", "mimikatz.exe",
                                            "recon.ps1", "loader.sh", "implant.bin"])
                pay_path = self._os_path(os_fam, host.user, pay_name)
                seen = ts + timedelta(minutes=self.rng.randint(1, 60))
                self.files.append(MalwareFile(
                    sha256=payload,
                    file_name=pay_name,
                    file_path=pay_path,
                    file_type="PE32" if pay_name.endswith((".exe", ".dll", ".bin")) else "script",
                    file_size=self.rng.randint(20_000, 800_000),
                    signature_status="unsigned",
                    first_seen=seen,
                    last_seen=seen + timedelta(hours=self.rng.randint(1, 24)),
                    parent_process=proc,
                    dropped_by=self.seed_ioc,
                ))

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
        self._generate_network()
        self._generate_emails()
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
    parser.add_argument("--nodes", type=int, default=5000, help="Target node count (default: 5000)")
    args = parser.parse_args()

    gen = TelemetryGenerator(seed=args.seed, nodes=args.nodes)
    counts = gen.generate_all()
    gen.write()

    total = sum(counts.values())
    print(f"\n{'='*50}")
    print(f"  Telemetry generated  (seed={args.seed}, target={args.nodes})")
    print(f"{'='*50}")
    for entity, count in counts.items():
        print(f"  {entity:<15} {count:>6}")
    print(f"  {'—'*22}")
    print(f"  {'total':<15} {total:>6}")
    print(f"  seed IOC: {gen.seed_ioc[:16]}...")
    print(f"  output:   {OUTPUT_DIR.resolve()}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
