"""
Seeds a demo telecom product/datasheet catalog so BOQ generation has
something to match against. Run inside the backend container:

  docker compose exec backend python scripts/seed_catalog.py <tenant_id>
"""
import sys
sys.path.insert(0, "/app")

from app.database import SessionLocal
from app import models

SAMPLE_PRODUCTS = [
    dict(sku="NET-SW-CORE-48P", name="48-Port Enterprise Core Switch", category="Networking & Infrastructure",
         spec_json={"ports": "48", "protocol": "10G Ethernet"}, unit_cost=6800, unit_price=0, lead_time_days=21),
    dict(sku="NET-WIFI6-AP", name="Wi-Fi 6 Enterprise Access Point", category="Networking & Infrastructure",
         spec_json={"standard": "Wi-Fi 6", "coverage": "indoor"}, unit_cost=850, unit_price=0, lead_time_days=14),
    dict(sku="SEC-CCTV-4K-IP", name="4K IP CCTV Camera (fixed dome)", category="Smart Connected Facilities",
         spec_json={"resolution": "4K", "protocol": "ONVIF"}, unit_cost=650, unit_price=0, lead_time_days=14),
    dict(sku="SEC-ACS-DOOR", name="Access Control Door Controller", category="Smart Connected Facilities",
         spec_json={"doors": "1", "protocol": "Wiegand"}, unit_cost=420, unit_price=0, lead_time_days=14),
    dict(sku="SEC-BMS-IOT-HUB", name="Building Management System IoT Hub", category="Smart Connected Facilities",
         spec_json={"protocol": "BACnet/IP"}, unit_cost=9500, unit_price=0, lead_time_days=30),
    dict(sku="CYB-NGFW-5G", name="5G-Throughput Next-Gen Firewall", category="Cybersecurity",
         spec_json={"throughput": "5G", "protocol": "NGFW"}, unit_cost=13500, unit_price=0, lead_time_days=21),
    dict(sku="CYB-SOC-MDR-Y1", name="Managed Detection & Response — Year 1", category="Cybersecurity",
         spec_json={}, unit_cost=28000, unit_price=0, lead_time_days=0),
    dict(sku="UC-IPPBX-500U", name="IP-PBX Unified Communications Platform (500 users)", category="Integrated Communications",
         spec_json={"users": "500", "protocol": "SIP"}, unit_cost=32000, unit_price=0, lead_time_days=30),
    dict(sku="UC-CC-OMNI-50AGT", name="Omnichannel Contact Centre Platform (50 agents)", category="Integrated Communications",
         spec_json={"agents": "50", "channels": "voice, chat, email"}, unit_cost=45000, unit_price=0, lead_time_days=45),
    dict(sku="DX-ERP-LIC-100U", name="Cloud ERP Licenses (100 users)", category="Digital Transformation",
         spec_json={"users": "100", "deployment": "cloud"}, unit_cost=52000, unit_price=0, lead_time_days=60),
    dict(sku="DX-CRM-LIC-50U", name="CRM Platform Licenses (50 users)", category="Digital Transformation",
         spec_json={"users": "50", "deployment": "cloud"}, unit_cost=18000, unit_price=0, lead_time_days=30),
    dict(sku="AV-BOARDROOM-KIT", name="Boardroom AV & Video Conferencing Kit", category="Audio Visual",
         spec_json={"room_size": "medium"}, unit_cost=15500, unit_price=0, lead_time_days=21),
    dict(sku="SVC-PROJ-MGMT", name="Project Management & Commissioning Services", category="Managed Services",
         spec_json={}, unit_cost=8000, unit_price=0, lead_time_days=0),
    dict(sku="SVC-AMC-Y1", name="Annual Maintenance Contract — Year 1", category="Managed Services",
         spec_json={}, unit_cost=12000, unit_price=0, lead_time_days=0),
]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_catalog.py <tenant_id>")
        sys.exit(1)

    tenant_id = sys.argv[1]
    db = SessionLocal()
    for p in SAMPLE_PRODUCTS:
        db.add(models.Product(tenant_id=tenant_id, **p))
    db.commit()
    print(f"Seeded {len(SAMPLE_PRODUCTS)} products for tenant {tenant_id}")
