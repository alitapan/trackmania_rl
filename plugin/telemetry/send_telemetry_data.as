[Plugin]
Name="Telemetry Bridge"
Description="Sends vehicle telemetry data to a configurable endpoint"
Author="Ali Tapan"
Version="1.0"

// Constants
const string CONFIG_FILENAME = "Plugins/TelemetryConfig.json";
const string DEFAULT_BRIDGE_URL = "http://127.0.0.1:5000/telemetry";
const uint SEND_INTERVAL_MS = 100;  // 10Hz telemetry
const uint CONFIG_CHECK_INTERVAL = 5000; // Check for config changes every 5 seconds
const float MIN_VELOCITY_FOR_ORIENTATION = 0.1f;

// Configurable settings
string BridgeURL = DEFAULT_BRIDGE_URL;

// Race state tracking
uint totalCheckpoints = 0;
uint currentCheckpointIndex = 0;
vec3 lastCheckpointPos = vec3();
float cpTriggerDistance = 8.0f;
array<vec3> checkpointPositions;

bool finishedRace = false;
uint preCheckpointIndex = uint(-1);
uint currentCheckpointCount = 0;
uint maxCheckpointCount = 0;
string lastMapId = "";

enum WheelType { FL, FR, RL, RR }

// --------------------------
// Configuration Management
// --------------------------

void LoadConfig() {
    try {
        if (IO::FileExists(CONFIG_FILENAME)) {
            string json = IO::File::Read(CONFIG_FILENAME);
            auto config = Json::Parse(json);
            
            if (config.GetType() == Json::Type::Object) {
                // Read URL setting
                if (config.HasKey("bridge_url") && config["bridge_url"].GetType() == Json::Type::String) {
                    BridgeURL = config["bridge_url"];
                    trace("Loaded Bridge URL from config: " + BridgeURL);
                }
            }
        } else {
            // Create default config file if it doesn't exist
            CreateDefaultConfig();
        }
    } catch {
        warn("Failed to load config file, using defaults");
        BridgeURL = DEFAULT_BRIDGE_URL;
    }
}

void CreateDefaultConfig() {
    try {
        auto config = Json::Object();
        config["bridge_url"] = DEFAULT_BRIDGE_URL;
        config["send_interval_ms"] = SEND_INTERVAL_MS;
        config["debug_mode"] = false;
        
        string json = Json::Write(config, true); // pretty-print
        IO::File::Write(CONFIG_FILENAME, json);
        trace("Created default config file");
    } catch {
        error("Failed to create default config file");
    }
}

// --------------------------
// Helper Functions
// --------------------------

Json::Value CreateCheckpointJson(uint maxCount, uint currentCount) {
    auto checkpointJson = Json::Object();
    checkpointJson["total"] = maxCount;
    checkpointJson["passed"] = currentCount;
    checkpointJson["progress"] = maxCount > 0 ? float(currentCount) / float(maxCount) : 0.0;
    return checkpointJson;
}

Json::Array Vec3ToJsonArray(vec3 vec) {
    auto arr = Json::Array();
    arr.Add(vec.x); arr.Add(vec.y); arr.Add(vec.z);
    return arr;
}

bool IsVehicleOnGround(CSceneVehicleVisState@ vis) {
    if (vis is null) return false;
    return (VehicleState::GetWheelFalling(vis, 0) >= 2 ||
            VehicleState::GetWheelFalling(vis, 1) >= 2 ||
            VehicleState::GetWheelFalling(vis, 2) >= 2 ||
            VehicleState::GetWheelFalling(vis, 3) >= 2);
}

Json::Value CreateWheelStatesJson(CSceneVehicleVisState@ vis) {
    if (vis is null) return Json::Object();
    
    auto wheelStates = Json::Object();
    wheelStates["front_left"] = GetWheelJson(vis, 0, WheelType::FL);
    wheelStates["front_right"] = GetWheelJson(vis, 1, WheelType::FR);
    wheelStates["rear_left"] = GetWheelJson(vis, 2, WheelType::RL);
    wheelStates["rear_right"] = GetWheelJson(vis, 3, WheelType::RR);
    return wheelStates;
}

// --------------------------
// Core Telemetry Functions
// --------------------------

void UpdateCheckpointProgress(CSmPlayer@ player, CSmArenaClient@ playground) {
    if (player is null || playground is null) return;
    
    MwFastBuffer<CGameScriptMapLandmark@> landmarks = playground.Arena.MapLandmarks;

    // If we changed maps, recalculate maxCheckpointCount
    auto map = cast<CGameCtnChallenge>(GetApp().RootMap);
    if (map !is null && map.IdName != lastMapId) {
        lastMapId = map.IdName;
        maxCheckpointCount = 0;
        array<int> links;

        for (uint i = 0; i < landmarks.Length; i++) {
            auto lm = landmarks[i];
            if (lm.Waypoint is null || lm.Waypoint.IsFinish || lm.Waypoint.IsMultiLap)
                continue;

            if (lm.Tag == "Checkpoint") {
                maxCheckpointCount++;
            } else if (lm.Tag == "LinkedCheckpoint") {
                if (links.Find(lm.Order) < 0) {
                    links.InsertLast(lm.Order);
                    maxCheckpointCount++;
                }
            } else {
                maxCheckpointCount++;
            }
        }

        currentCheckpointCount = 0;
        preCheckpointIndex = uint(-1);
    }

    uint cpIndex = player.CurrentLaunchedRespawnLandmarkIndex;

    if (cpIndex != preCheckpointIndex && cpIndex < landmarks.Length) {
        preCheckpointIndex = cpIndex;
        auto lm = landmarks[cpIndex];
        finishedRace = (lm.Waypoint !is null && lm.Waypoint.IsFinish);
        
        if (lm.Waypoint is null || lm.Waypoint.IsFinish || lm.Waypoint.IsMultiLap) {
            currentCheckpointCount = 0;
        } else {
            currentCheckpointCount++;
        }
    }
}

bool IsInRaceMode() {
    auto app = cast<CTrackMania>(GetApp());
    if (app is null || app.RootMap is null || app.CurrentPlayground is null) return false;

    auto playground = cast<CSmArenaClient>(app.CurrentPlayground);
    if (playground is null || playground.GameTerminals.Length == 0) return false;

    auto terminal = playground.GameTerminals[0];
    return terminal !is null && terminal.ControlledPlayer !is null;
}

string GetTurboLevelName(int level) {
    switch(level) {
        case 0: return "None";
        case 1: return "Normal";
        case 2: return "Super";
        case 3: return "RouletteNormal";
        case 4: return "RouletteSuper";
        case 5: return "RouletteUltra";
        default: return "Unknown";
    }
}

string GetFallingStateName(int state) {
    switch(state) {
        case 0: return "FallingAir";
        case 1: return "FallingWater";
        case 2: return "RestingGround";
        case 3: return "RestingWater";
        case 4: return "GlidingGround";
        default: return "Unknown";
    }
}

string GetVehicleTypeName(int type) {
    switch(type) {
        case 0: return "CharacterPilot";
        case 1: return "CarSport";
        case 2: return "CarSnow";
        case 3: return "CarRally";
        case 4: return "CarDesert";
        default: return "Unknown";
    }
}

string GetReactorBoostLvlName(ESceneVehicleVisReactorBoostLvl lvl) {
    switch (lvl) {
        case ESceneVehicleVisReactorBoostLvl::None: return "None";
        case ESceneVehicleVisReactorBoostLvl::Lvl1: return "Lvl1";
        case ESceneVehicleVisReactorBoostLvl::Lvl2: return "Lvl2";
        default: return "Unknown";
    }
}

string GetReactorBoostTypeName(ESceneVehicleVisReactorBoostType type) {
    switch (type) {
        case ESceneVehicleVisReactorBoostType::None: return "None";
        case ESceneVehicleVisReactorBoostType::Up: return "Up";
        case ESceneVehicleVisReactorBoostType::Down: return "Down";
        case ESceneVehicleVisReactorBoostType::UpAndDown: return "UpAndDown";
        default: return "Unknown";
    }
}

Json::Value GetWheelJson(CSceneVehicleVisState@ vis, int index, WheelType type) {
    if (vis is null) return Json::Object();

    auto wheel = Json::Object();

    switch (type) {
        case WheelType::FL:
            wheel["steer_angle"] = vis.FLSteerAngle;
            wheel["rotation"] = vis.FLWheelRot;
            wheel["slip_coef"] = vis.FLSlipCoef;
            wheel["dirt"] = VehicleState::GetWheelDirt(vis, index);
            wheel["brake_coef"] = vis.FLBreakNormedCoef;
            wheel["tire_wear"] = vis.FLTireWear01;
            wheel["icing"] = vis.FLIcing01;
            wheel["ground_material"] = GetGroundMaterialName(vis.FLGroundContactMaterial);
            wheel["falling_state"] = GetFallingStateName(VehicleState::GetWheelFalling(vis, 0));
            break;
        case WheelType::FR:
            wheel["steer_angle"] = vis.FRSteerAngle;
            wheel["rotation"] = vis.FRWheelRot;
            wheel["slip_coef"] = vis.FRSlipCoef;
            wheel["dirt"] = VehicleState::GetWheelDirt(vis, index);
            wheel["brake_coef"] = vis.FRBreakNormedCoef;
            wheel["tire_wear"] = vis.FRTireWear01;
            wheel["icing"] = vis.FRIcing01;
            wheel["ground_material"] = GetGroundMaterialName(vis.FRGroundContactMaterial);
            wheel["falling_state"] = GetFallingStateName(VehicleState::GetWheelFalling(vis, 1));
            break;
        case WheelType::RL:
            wheel["steer_angle"] = vis.RLSteerAngle;
            wheel["rotation"] = vis.RLWheelRot;
            wheel["slip_coef"] = vis.RLSlipCoef;
            wheel["dirt"] = VehicleState::GetWheelDirt(vis, index);
            wheel["brake_coef"] = vis.RLBreakNormedCoef;
            wheel["tire_wear"] = vis.RLTireWear01;
            wheel["icing"] = vis.RLIcing01;
            wheel["ground_material"] = GetGroundMaterialName(vis.RLGroundContactMaterial);
            wheel["falling_state"] = GetFallingStateName(VehicleState::GetWheelFalling(vis, 2));
            break;
        case WheelType::RR:
            wheel["steer_angle"] = vis.RRSteerAngle;
            wheel["rotation"] = vis.RRWheelRot;
            wheel["slip_coef"] = vis.RRSlipCoef;
            wheel["dirt"] = VehicleState::GetWheelDirt(vis, index);
            wheel["brake_coef"] = vis.RRBreakNormedCoef;
            wheel["tire_wear"] = vis.RRTireWear01;
            wheel["icing"] = vis.RRIcing01;
            wheel["ground_material"] = GetGroundMaterialName(vis.RRGroundContactMaterial);
            wheel["falling_state"] = GetFallingStateName(VehicleState::GetWheelFalling(vis, 3));
            break;
    }

    wheel["wetness"] = vis.WetnessValue01;
    return wheel;
}

void PostTelemetry(const string &in json) {
    if (BridgeURL.Length == 0) return;
    
    try {
        auto req = Net::HttpRequest();
        req.Method = Net::HttpMethod::Post;
        req.Url = BridgeURL;
        req.Headers["Content-Type"] = "application/json";
        req.Body = json;
        req.Start();
        
        while (!req.Finished()) {
            yield();
        }
    } catch {
        warn("Failed to send telemetry to " + BridgeURL);
    }
}

// --------------------------
// Main Plugin Loop
// --------------------------

void Main() {
    // Load configuration first
    LoadConfig();
    
    uint lastSendTime = Time::Now;
    uint lastConfigCheckTime = Time::Now;
    Json::Value telemetry = Json::Object();
            
    while (true) {
        uint now = Time::Now;
        
        // Check for config updates periodically
        if (now - lastConfigCheckTime >= CONFIG_CHECK_INTERVAL) {
            LoadConfig();
            lastConfigCheckTime = now;
        }
        
        // Send telemetry at configured interval
        if (now - lastSendTime >= SEND_INTERVAL_MS) {
            lastSendTime = now;
            auto app = cast<CTrackMania>(GetApp());
            bool inMainMenu = app is null || app.RootMap is null;

            if (!IsInRaceMode()) {
                if (inMainMenu) {
                    telemetry["in_main_menu"] = inMainMenu;
                    PostTelemetry(Json::Write(telemetry));
                }
                yield(); continue;
            }

            auto playground = cast<CSmArenaClient>(app.CurrentPlayground);
            if (playground is null || playground.GameTerminals.Length == 0) { yield(); continue; }

            auto terminal = playground.GameTerminals[0];
            if (terminal is null || terminal.ControlledPlayer is null) { yield(); continue; }

            auto player = cast<CSmPlayer>(terminal.ControlledPlayer);
            if (player is null) { yield(); continue; }

            CSceneVehicleVisState@ vis = VehicleState::ViewingPlayerState();
            if (vis is null) { yield(); continue; }

            UpdateCheckpointProgress(player, playground);
            
            // Prepare telemetry data
            telemetry["checkpoints"] = CreateCheckpointJson(maxCheckpointCount, currentCheckpointCount);
            telemetry["position"] = Vec3ToJsonArray(vis.Position);
            telemetry["velocity"] = Vec3ToJsonArray(vis.WorldVel);
            telemetry["orientation"] = Vec3ToJsonArray(vis.WorldVel.Length() > MIN_VELOCITY_FOR_ORIENTATION ? vis.WorldVel.Normalized() : vec3(1, 0, 0));
            
            // Vehicle state
            telemetry["speed"] = vis.FrontSpeed;
            telemetry["side_speed"] = VehicleState::GetSideSpeed(vis);
            telemetry["rpm"] = VehicleState::GetRPM(vis);
            telemetry["vehicle_type"] = GetVehicleTypeName(VehicleState::GetVehicleType(vis));
            telemetry["gear"] = vis.CurGear;
            telemetry["engine_on"] = vis.EngineOn;
            telemetry["is_turbo"] = vis.IsTurbo;
            telemetry["turbo_time"] = vis.TurboTime;
            
            // Reactor state
            telemetry["reactor_ground_mode"] = vis.IsReactorGroundMode;
            telemetry["reactor_inputs_x"] = vis.ReactorInputsX;
            telemetry["reactor_air_control"] = Vec3ToJsonArray(vis.ReactorAirControl);
            telemetry["reactor_boost_lvl"] = GetReactorBoostLvlName(vis.ReactorBoostLvl);
            telemetry["reactor_boost_type"] = GetReactorBoostTypeName(vis.ReactorBoostType);
            
            // General state
            telemetry["in_main_menu"] = inMainMenu;
            telemetry["on_ground"] = IsVehicleOnGround(vis);
            telemetry["wheel_states"] = CreateWheelStatesJson(vis);
            telemetry["finished"] = finishedRace;
            
            PostTelemetry(Json::Write(telemetry));
        }
        yield();
    }
}