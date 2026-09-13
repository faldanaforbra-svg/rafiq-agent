"""
RAFIQ (رفيق) — Nokia CAMARA / GSMA Open Gateway Network API Client
Handles Device Location, Quality on Demand (QoD), Carrier SMS, and Device Status.
Includes global state registration for Command Center integration.
"""

from datetime import datetime
import random
import streamlit as st

# Shared Global Stores across Streamlit sessions/tabs
@st.cache_resource
def get_global_sms_log():
    return []

@st.cache_resource
def get_global_qos_registry():
    return {}

@st.cache_resource
def get_global_user_locations():
    return {}

@st.cache_resource
def get_global_zone_overrides():
    return {}


# Predefined demo zones around Masjid al-Haram — zone 0 matches the original
# default exactly, so anyone without an explicit override behaves exactly as
# before. Names line up with the landmarks already named in the agent's own
# navigation persona (Gate 79, Ajyad, Clock Tower, Safa/Marwah).
HAJJ_ZONES = [
    {"zone": "Masjid al-Haram Courtyard (Mataf)", "nearest_landmark": "Gate 79 (King Fahd Gate)", "latitude": 21.4225, "longitude": 39.8262},
    {"zone": "Safa-Marwah Gallery", "nearest_landmark": "Safa Hill", "latitude": 21.4234, "longitude": 39.8270},
    {"zone": "Clock Tower Concourse", "nearest_landmark": "Abraj Al Bait Clock Tower", "latitude": 21.4187, "longitude": 39.8258},
    {"zone": "Ajyad Gate Area", "nearest_landmark": "Ajyad Gate", "latitude": 21.4200, "longitude": 39.8245},
]


class NokiaCAMARAClient:
    def __init__(self):
        # Global SOS Incident Feed accessible by Command Center
        self.alerts = get_global_sms_log()
        # Track active 5G QoS boosts globally per phone number
        self.qos_registry = get_global_qos_registry()
        # Persist simulated GPS locations
        self.user_locations = get_global_user_locations()
        # Demo control: pins a phone number to a specific HAJJ_ZONES index
        self.zone_overrides = get_global_zone_overrides()

    def register_incident(self, phone_number: str, reason: str, profile_data: dict,
                           location_data: dict = None, incident_type: str = "SELF",
                           subject: str = None) -> dict:
        """
        Registers an emergency incident in the central registry so it appears in the Command Center.
        Called automatically whenever the AI Agent triggers an SOS or Emergency SMS tool.

        incident_type: "SELF" (default, unchanged behavior) means the pilgrim
        who owns phone_number is themselves the person at risk. "THIRD_PARTY"
        means the pilgrim reported someone else (a companion/friend/family
        member) is the one needing help — dispatchers should look for the
        person named in `subject`, not necessarily the pilgrim's own location.
        subject: free-text description of who the incident concerns, e.g.
        "Pilgrim's brother — Mohamed". Defaults to the pilgrim's own name for
        SELF incidents.
        """
        if not location_data:
            location_data = self.get_device_location(phone_number)

        if subject is None:
            subject = profile_data.get("name", "Pilgrim") if incident_type == "SELF" else "Unnamed companion"

        # Check if active incident already exists for this number AND this
        # incident_type — a THIRD_PARTY report about a companion should not
        # silently overwrite (or be overwritten by) an active SELF incident
        # for the same pilgrim; they describe different people at risk.
        existing = next(
            (a for a in self.alerts
             if a["phone_number"] == phone_number
             and a["status"] == "ACTIVE"
             and a.get("incident_type", "SELF") == incident_type),
            None
        )
        if existing:
            existing["reason"] = reason
            existing["subject"] = subject
            existing["timestamp"] = datetime.now().strftime("%H:%M:%S")
            return existing

        incident_id = str(len(self.alerts) + 101)
        incident = {
            "id": incident_id,
            "phone_number": phone_number,
            "status": "ACTIVE",
            "incident_type": incident_type,
            "subject": subject,
            "reason": reason,
            "location": location_data,
            "profile": profile_data,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.alerts.append(incident)
        return incident

    def resolve_incident(self, phone_number: str, note: str = "Resolved", incident_type: str = None) -> dict:
        """
        Marks active incidents for this phone number as resolved and restores
        standard network priority. Used by both the manual SOS-cancel button and
        the AI agent's autonomous stand-down tool, so both behave identically.

        incident_type: if None (default, unchanged behavior), resolves ALL
        active incidents for this phone number regardless of type. Pass
        "SELF" or "THIRD_PARTY" to resolve only that type — e.g. a pilgrim
        confirming *they* are safe should not automatically also close out an
        active THIRD_PARTY report about an injured companion who may still
        need help.
        """
        resolved_ids = []
        for alert in self.alerts:
            matches_type = incident_type is None or alert.get("incident_type", "SELF") == incident_type
            if alert.get("status") == "ACTIVE" and alert.get("phone_number") == phone_number and matches_type:
                alert["status"] = "RESOLVED"
                alert["resolution_note"] = note
                resolved_ids.append(alert["id"])
        qos_res = self.deactivate_qos_boost(phone_number)
        return {
            "phone_number": phone_number,
            "resolved_incident_ids": resolved_ids,
            "qos_status": qos_res,
        }

    def get_device_location(self, phone_number: str) -> dict:
        """Nokia Location Verification API. Defaults to HAJJ_ZONES[0] (identical
        to the original fixed location) unless a demo override has been set via
        set_simulated_zone()."""
        zone_idx = self.zone_overrides.get(phone_number, 0)
        cached = self.user_locations.get(phone_number)

        if not cached or cached.get("zone_idx") != zone_idx:
            zone = HAJJ_ZONES[zone_idx]
            self.user_locations[phone_number] = {
                "zone_idx": zone_idx,
                "latitude": zone["latitude"] + random.uniform(-0.0008, 0.0008),
                "longitude": zone["longitude"] + random.uniform(-0.0008, 0.0008),
                "zone": zone["zone"],
                "nearest_landmark": zone["nearest_landmark"]
            }

        loc = self.user_locations[phone_number]
        return {
            "phone_number": phone_number,
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "nearest_landmark": loc["nearest_landmark"],
            "zone": loc["zone"],
            "accuracy_radius_m": 25,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def set_simulated_zone(self, phone_number: str, zone_index: int) -> dict:
        """Demo control: pins a pilgrim's simulated location to one of the
        predefined HAJJ_ZONES, so navigation/directions can be showcased from
        different starting points without waiting for real movement."""
        zone_index = max(0, min(int(zone_index), len(HAJJ_ZONES) - 1))
        self.zone_overrides[phone_number] = zone_index
        return self.get_device_location(phone_number)

    def request_qos_boost(self, phone_number: str, duration_minutes: int = 30, reason: str = "Priority Request") -> dict:
        """Nokia QoD API: Dynamically provisions 5G network slice."""
        self.qos_registry[phone_number] = {
            "status": "ACTIVE",
            "activated_at": datetime.now().strftime("%H:%M:%S")
        }
        return {
            "status": "SUCCESS",
            "qos_profile": "QoS_ELEVATED_EMERGENCY",
            "phone_number": phone_number,
            "allocated_bandwidth_mbps": 100,
            "latency_ms": 12,
            "duration_minutes": duration_minutes,
            "reason": reason,
            "activated_at": self.qos_registry[phone_number]["activated_at"]
        }

    def deactivate_qos_boost(self, phone_number: str) -> dict:
        """Deactivates 5G priority slice."""
        if phone_number in self.qos_registry:
            self.qos_registry[phone_number]["status"] = "INACTIVE"
        return {
            "status": "DEACTIVATED",
            "phone_number": phone_number,
            "restored_profile": "QoS_STANDARD_BEST_EFFORT"
        }

    def check_qos_status(self, phone_number: str) -> bool:
        """Checks if 5G boost is active globally."""
        return self.qos_registry.get(phone_number, {}).get("status") == "ACTIVE"

    def get_zone_incident_clusters(self, min_incidents: int = 2) -> list:
        """
        Groups currently ACTIVE incidents by zone (using each incident's own
        logged location) and returns zones whose active-incident count meets
        or exceeds min_incidents. This is real aggregation over the live
        alerts list, not a canned/simulated result — it will correctly return
        an empty list if no zone actually has that many active incidents.

        Returns a list of dicts: {"zone": str, "count": int, "incident_ids": [...]}
        sorted by count descending.
        """
        zone_map = {}
        for alert in self.alerts:
            if alert.get("status") != "ACTIVE":
                continue
            zone_name = alert.get("location", {}).get("zone", "Unknown Zone")
            zone_map.setdefault(zone_name, []).append(alert["id"])

        clusters = [
            {"zone": zone, "count": len(ids), "incident_ids": ids}
            for zone, ids in zone_map.items()
            if len(ids) >= min_incidents
        ]
        clusters.sort(key=lambda c: c["count"], reverse=True)
        return clusters

    def get_zone_summary(self) -> list:
        """
        Real-data summary per HAJJ_ZONES entry: how many known pilgrims
        (distinct phone numbers with a cached location) are currently in each
        zone, and how many active incidents (any type) are in that zone.
        Computed fresh from user_locations and alerts each call.
        """
        summary = []
        for zone in HAJJ_ZONES:
            zone_name = zone["zone"]
            pilgrim_count = sum(
                1 for loc in self.user_locations.values() if loc.get("zone") == zone_name
            )
            active_incidents = [
                a for a in self.alerts
                if a.get("status") == "ACTIVE" and a.get("location", {}).get("zone") == zone_name
            ]
            summary.append({
                "zone": zone_name,
                "nearest_landmark": zone["nearest_landmark"],
                "pilgrim_count": pilgrim_count,
                "active_incident_count": len(active_incidents),
                "active_incident_ids": [a["id"] for a in active_incidents],
            })
        return summary

    def send_sms_alert(self, recipients: list, message: str) -> dict:
        """Nokia Carrier SMS API."""
        dispatched = []
        for phone in recipients:
            if phone:
                dispatched.append({
                    "to": phone,
                    "status": "DELIVERED",
                    "carrier_message_id": f"MSG-NOKIA-{hash(str(phone) + str(message)) % 1000000}"
                })
        return {
            "dispatched_count": len(dispatched),
            "messages": dispatched,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    def get_device_status(self, phone_number: str) -> dict:
        """Nokia Device Status API."""
        return {
            "phone_number": phone_number,
            "reachability": "CONNECTED",
            "connectivity_type": "5G_NR_SA",
            "roaming_status": "ROAMING_LOCAL_SAUDI_HOST",
            "battery_network_indicator": "NORMAL",
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_simulated_weather(self) -> dict:
        """
        NOT a real weather API call — this is fixed, clearly-labeled DEMO DATA
        for the Command Center dashboard. There is no live weather integration
        in this build. Callers/UI must display the is_simulated flag so this
        is never mistaken for a real reading.
        """
        return {
            "location": "Makkah, Saudi Arabia",
            "temperature_c": 41,
            "condition": "Sunny / Clear",
            "humidity_pct": 18,
            "heat_advisory": True,
            "is_simulated": True,
            "source": "DEMO DATA — not a live weather feed",
        }