"""Pydantic data models for all entity types in the telemetry graph."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MalwareFile(BaseModel):
    sha256: str
    file_name: str
    file_path: str
    file_type: str  # "PE32", "script", "document"
    file_size: int
    signature_status: str  # "unsigned", "invalid", "revoked"
    first_seen: datetime
    last_seen: datetime
    parent_process: Optional[str] = None
    dropped_by: Optional[str] = None  # sha256 of parent dropper


class Host(BaseModel):
    device_id: str
    hostname: str
    os_family: str  # "Windows", "Linux", "macOS"
    device_type: str  # "server", "desktop", "laptop", "VM"
    environment: str  # "enterprise_workstation", "terminal_server", "mail_server", "cloud_vm", "developer_box"
    country: str  # ISO 3166-1 alpha-2
    tenant_id: str
    user: str
    security_posture: list[str]  # e.g. ["edr_enabled", "mail_filtering_high"]


class Email(BaseModel):
    message_id: str
    sender: str
    sender_domain: str
    reply_to: Optional[str] = None
    subject: str
    attachment_name: str
    attachment_type: str  # "xlsx", "docm", "zip", "iso"
    delivery_time: datetime
    recipient_user: str
    recipient_tenant: str
    spf: str  # "pass", "fail", "none"
    dkim: str
    dmarc: str
    campaign_id: str


class NetworkInfra(BaseModel):
    url: str
    domain: str
    ip: str
    asn: str
    hosting_provider: str
    protocol: str  # "https", "http", "ftp"
    port: int
    uri_path: str
    ssl_cert_fingerprint: Optional[str] = None
    ip_country: str


class ExecutionEvent(BaseModel):
    event_id: str
    host_device_id: str
    file_sha256: str
    process_name: str
    persistence_type: Optional[str] = None  # "registry_run_key", "scheduled_task", "cron", "startup_folder"
    script_interpreter: Optional[str] = None  # "powershell", "cmd", "bash", "wscript"
    external_connection: Optional[str] = None  # domain connected to after execution
    follow_on_payload: Optional[str] = None  # sha256 of downloaded payload
    behavior_flags: list[str] = []  # e.g. ["credential_theft", "recon", "beaconing"]
    timestamp: datetime


class Campaign(BaseModel):
    cluster_id: str
    region_variant: str  # e.g. "NA-english", "EU-german", "APAC-japanese"
    lure_family: str  # e.g. "invoice", "shipping", "legal"
    time_window_start: datetime
    time_window_end: datetime
    infra_reuse_cluster: str  # groups campaigns sharing infrastructure
    sender_domains: list[str]
    target_countries: list[str]


class GraphNode(BaseModel):
    id: str
    type: str  # "file", "host", "email", "domain", "ip", "user", "country", "tenant", "campaign", "process", "url"
    label: str
    properties: dict


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # relationship type
    properties: dict = {}
