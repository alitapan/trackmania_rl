import gymnasium as gym
from gymnasium import spaces
import numpy as np
import time
from bridge.bridge import TelemetryBridge
from core.instance import TrackmaniaGameInstance
from shared.schemas import Telemetry

TELEMETRY_PORT = 5000
TELEMETRY_HOST = "127.0.0.1"
EPISODE_DURATION = 60
speed_weight = 0.1
checkpoint_weight = 1.0


class TrackmaniaEnv(gym.Env):
    def __init__(self):
        super().__init__()

        # Action space: [steer, throttle, brake]
        self.action_space = spaces.Box(low=np.array([-1, 0, 0]),
                                       high=np.array([1, 1, 1]),
                                       dtype=np.float32)

        # Observation space
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(15,), dtype=np.float32)

        # Setup the telemetry bridge
        self.telemetry_bridge = TelemetryBridge(host=TELEMETRY_HOST, port=TELEMETRY_PORT)
        self.telemetry_bridge.start()

        # Launch Trackmania
        self.game_instance = TrackmaniaGameInstance(telemetry_bridge=self.telemetry_bridge)

        self.max_episode_duration = EPISODE_DURATION
        self.episode_start_time = None
        self.last_checkpoint_progress = 0.0
        self.first_reset_done = False


    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        self.episode_start_time = time.time()
        self.last_checkpoint_progress = 0.0
        self.last_speed = 0.0

        if not self.first_reset_done:
            print("[TrackmaniaEnv] First reset: waiting 15s to skip ghost prompt...")
            time.sleep(15)
            self.game_instance.press_key("enter")
            self.first_reset_done = True

        # Restart the race
        self.game_instance.press_key("backspace")
        time.sleep(1)

        obs = self._get_obs()
        return obs, {}

    def step(self, action):
        steer, throttle, brake = action
        self._send_control(steer, throttle, brake)

        time.sleep(0.05)  # simulate ~20Hz control loop

        obs = self._get_obs()
        reward = self._compute_reward(obs)
        done = self._check_done(obs)

        return obs, reward, done, False, {}


    def _get_obs(self):
        telemetry = self.telemetry_bridge.get_latest_telemetry()
        return self._process_telemetry(telemetry)

    def _process_telemetry(self, telemetry: Telemetry) -> np.ndarray:
        if telemetry is None:
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        def norm(x, min_val, max_val):
            return (x - min_val) / (max_val - min_val) if max_val > min_val else 0.0

        wheel_rot = np.mean([
            telemetry.wheel_states["front_left"].rotation,
            telemetry.wheel_states["front_right"].rotation,
            telemetry.wheel_states["rear_left"].rotation,
            telemetry.wheel_states["rear_right"].rotation,
        ])
        wheel_slip = np.mean([
            telemetry.wheel_states["front_left"].slip_coef,
            telemetry.wheel_states["front_right"].slip_coef,
            telemetry.wheel_states["rear_left"].slip_coef,
            telemetry.wheel_states["rear_right"].slip_coef,
        ])

        obs = np.array([
            norm(telemetry.rpm or 0, 0, 10000),
            norm(wheel_rot, 0, 3000),
            norm(wheel_slip, 0, 1),
            float(telemetry.on_ground),
            float(telemetry.finished),
            *(telemetry.orientation if telemetry.orientation else [0.0, 0.0, 0.0]),
            norm(telemetry.side_speed or 0, -100, 100),
            *(telemetry.velocity if telemetry.velocity else [0.0, 0.0, 0.0]),
            float(telemetry.is_turbo),
            norm(telemetry.speed or 0, 0, 300),
            telemetry.checkpoints.progress if telemetry.checkpoints else 0.0
        ], dtype=np.float32)

        return obs

    def _send_control(self, steer, throttle, brake):        
        if steer < -0.5:
            self.game_instance.press_key("left")
        elif steer > 0.5:
            self.game_instance.press_key("right")

        if throttle > 0.5:
            self.game_instance.press_key("up")

        if brake > 0.5:
            self.game_instance.press_key("down")

    def _compute_reward(self, obs):
        current_speed = obs[11]
        progress = obs[-2]

        # Reward for high speed
        speed_delta = max(0.0, current_speed - self.last_speed)
        speed_reward = speed_delta * 0.5
        
        self.last_speed = current_speed
        # Reward for checkpoint progress
        checkpoint_reward = max(0.0, progress - self.last_checkpoint_progress)
        self.last_checkpoint_progress = progress    

        total_reward = speed_reward + checkpoint_reward
        return total_reward
    
    def _check_done(self, obs):
        # Check if agent finished the track
        finished = obs[-1] == 1.0

        # Check time limit
        exceeded_time = (time.time() - self.episode_start_time) > self.max_episode_duration

        if exceeded_time:
            print("[TrackmaniaEnv] Episode timed out.")

        return finished or exceeded_time
