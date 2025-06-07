import pytest
import numpy as np
from gym_trackmania.trackmania_env import TrackmaniaEnv
from gym_trackmania.shared.schemas import Telemetry, WheelState

class DummyBridge:
    def get_latest_telemetry(self):
        return Telemetry(
            rpm=3000,
            velocity=[5.0, 0.0, 0.0],
            orientation=[0.0, 1.0, 0.0],
            speed=150.0,
            side_speed=10.0,
            wheel_states={
                "front_left": WheelState(0, 1000, 0.1, 0, 0, 0, 0, "", "", 0),
                "front_right": WheelState(0, 1000, 0.1, 0, 0, 0, 0, "", "", 0),
                "rear_left": WheelState(0, 1000, 0.1, 0, 0, 0, 0, "", "", 0),
                "rear_right": WheelState(0, 1000, 0.1, 0, 0, 0, 0, "", "", 0),
            },
            in_main_menu=False,
            finished=False
        )

def test_process_telemetry_vector_shape(monkeypatch):
    env = TrackmaniaEnv()
    env.telemetry_bridge = DummyBridge()
    obs = env._get_obs()
    assert isinstance(obs, np.ndarray)
    assert obs.shape == env.observation_space.shape