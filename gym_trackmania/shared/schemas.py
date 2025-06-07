from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CheckpointStatus:
    total: int
    passed: int
    progress: float

    @staticmethod
    def from_dict(d: dict) -> "CheckpointStatus":
        return CheckpointStatus(
            total=d.get("total", 0),
            passed=d.get("passed", 0),
            progress=d.get("progress", 0.0)
        )

@dataclass
class WheelState:
    steer_angle: float
    rotation: float
    slip_coef: float
    dirt: float
    brake_coef: float
    tire_wear: float
    icing: float
    ground_material: str
    falling_state: str
    wetness: float

    @staticmethod
    def from_dict(d: dict) -> "WheelState":
        return WheelState(
            steer_angle=d["steer_angle"],
            rotation=d["rotation"],
            slip_coef=d["slip_coef"],
            dirt=d["dirt"],
            brake_coef=d["brake_coef"],
            tire_wear=d["tire_wear"],
            icing=d["icing"],
            ground_material=d["ground_material"],
            falling_state=d["falling_state"],
            wetness=d["wetness"],
        )


@dataclass
class Telemetry:
    position: Optional[List[float]] = None
    velocity: Optional[List[float]] = None
    orientation: Optional[List[float]] = None
    speed: Optional[float] = None
    side_speed: Optional[float] = None
    rpm: Optional[float] = None
    vehicle_type: Optional[str] = None
    gear: Optional[int] = None
    engine_on: Optional[bool] = None
    is_turbo: Optional[bool] = None
    turbo_time: Optional[float] = None
    reactor_ground_mode: Optional[bool] = None
    reactor_inputs: Optional[bool] = None
    reactor_air_control: Optional[List[float]] = None
    reactor_boost_level: Optional[str] = None
    reactor_boost_type: Optional[str] = None
    on_ground: Optional[bool] = None
    checkpoints: Optional[List[List[float]]] = None
    wheel_states: Optional[dict] = None
    in_main_menu: bool = True
    finished: Optional[bool] = None
    @staticmethod
    def from_dict(d: dict):
        raw_ws = d.get("wheel_states", {})

        # Ensure all 4 wheels exist with fallback default values
        def safe_wheel(k):
            return WheelState.from_dict(raw_ws.get(k, {
                "steer_angle": 0.0, "rotation": 0.0, "slip_coef": 0.0, "dirt": 0.0,
                "brake_coef": 0.0, "tire_wear": 0.0, "icing": 0.0,
                "ground_material": "", "falling_state": "", "wetness": 0.0
            }))

        wheel_states = {
            "front_left": safe_wheel("front_left"),
            "front_right": safe_wheel("front_right"),
            "rear_left": safe_wheel("rear_left"),
            "rear_right": safe_wheel("rear_right"),
        }
        checkpoints_data = d.get("checkpoints")
        checkpoints = CheckpointStatus.from_dict(checkpoints_data) if checkpoints_data else None
        return Telemetry(
            position=d.get("position"),
            velocity=d.get("velocity"),
            orientation=d.get("orientation"),
            speed=d.get("speed"),
            side_speed=d.get("side_speed"),
            rpm=d.get("rpm"),
            vehicle_type=d.get("vehicle_type"),
            gear=d.get("gear"),
            engine_on=d.get("engine_on"),
            is_turbo=d.get("is_turbo"),
            turbo_time=d.get("turbo_time"),
            reactor_ground_mode=d.get("reactor_ground_mode"),
            reactor_inputs=d.get("reactor_inputs"),
            reactor_air_control=d.get("reactor_air_control"),
            reactor_boost_level=d.get("reactor_boost_level"),
            reactor_boost_type=d.get("reactor_boost_type"),
            checkpoints=checkpoints,
            wheel_states=wheel_states,
            on_ground=d.get("on_ground"),
            in_main_menu=d.get("in_main_menu"),
            finished=d.get("finished", False),
        )