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


class NokiaCAMARAClient:
    def __init__(self):
        # Global SOS Incident Feed accessible by Command Center
        self.alerts = get_global_sms_log()
        # Track active 5G QoS boosts globally per phone number
        self.qos_registry = get_global_qos_registry()
        # Persist simulated GPS locations
        self.user_locations = get_global_user_locations()

    def register_incident(self, phone_number: str, reason: str, profile_data: dict, location_data: dict = None) -> dict:
        """
        Registers an emergency incident in the central registry so it appears in the Command Center.
        Called automatically whenever the AI Agent triggers an SOS or Emergency SMS tool.
        """
        if not location_data:
            location_data = self.get_device_location(phone_number)

        # Check if active incident already exists for this number
        existing = next((a for a in self.alerts if a["phone_number"] == phone_number and a["status"] == "ACTIVE"), None)
        if existing:
            existing["reason"] = reason
            existing["timestamp"] = datetime.now().strftime("%H:%M:%S")
            return existing

        incident_id = str(len(self.alerts) + 101)
        incident = {
            "id": incident_id,
            "phone_number": phone_number,
            "status": "ACTIVE",
            "reason": reason,
            "location": location_data,
            "profile": profile_data,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.alerts.append(incident)
        return incident

    def get_device_location(self, phone_number: str) -> dict:
        """Nokia Location Verification API."""
        if phone_number not in self.user_locations:
            self.user_locations[phone_number] = {
                "latitude": 21.4225 + random.uniform(-0.0008, 0.0008),
                "longitude": 39.8262 + random.uniform(-0.0008, 0.0008),
                "zone": "Masjid al-Haram Courtyard",
                "nearest_landmark": "Gate 79 (King Fahd Gate)"
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