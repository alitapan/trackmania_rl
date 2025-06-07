import pytest
from gym_trackmania.bridge.bridge import TelemetryBridge
from gym_trackmania.shared.schemas import Telemetry

def test_bridge_receives_and_stores_telemetry(monkeypatch):
    bridge = TelemetryBridge()

    dummy_data = {
        "in_main_menu": True,
        "wheel_states": {
            "front_left": {
                "steer_angle": 0.0, "rotation": 0.0, "slip_coef": 0.0, "dirt": 0.0,
                "brake_coef": 0.0, "tire_wear": 0.0, "icing": 0.0,
                "ground_material": "", "falling_state": "", "wetness": 0.0
            }
        }
    }

    telemetry = Telemetry.from_dict(dummy_data)
    bridge.latest_telemetry = telemetry

    assert bridge.get_latest_telemetry().in_main_menu is True