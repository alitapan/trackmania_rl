import pytest
from gym_trackmania.shared.schemas import Telemetry, WheelState

def test_telemetry_from_dict_basic():
    data = {
        "position": [1.0, 2.0, 3.0],
        "velocity": [0.5, 0.0, -0.2],
        "orientation": [0.0, 1.0, 0.0],
        "speed": 150.0,
        "side_speed": 10.0,
        "rpm": 5000,
        "vehicle_type": "car",
        "gear": 3,
        "engine_on": True,
        "is_turbo": False,
        "turbo_time": 1.2,
        "reactor_ground_mode": True,
        "on_ground": True,
        "in_main_menu": False,
        "finished": True,
        "wheel_states": {
            "front_left": {
                "steer_angle": 0.0, "rotation": 1.0, "slip_coef": 0.1, "dirt": 0.0,
                "brake_coef": 0.0, "tire_wear": 0.0, "icing": 0.0,
                "ground_material": "road", "falling_state": "none", "wetness": 0.0
            }
        }
    }
    telemetry = Telemetry.from_dict(data)
    assert telemetry.position == [1.0, 2.0, 3.0]
    assert telemetry.vehicle_type == "car"
    assert telemetry.in_main_menu is False
    assert isinstance(telemetry.wheel_states["front_left"], WheelState)