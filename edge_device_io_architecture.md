# Edge Device IO Architecture - DAW Tracks for Physical/Sensors

**Date:** 2026-07-24
**Status:** Architecture Specification
**Purpose:** ESP32/edge devices as IO endpoints appearing as DAW tracks

---

## Overview

The **Front View (Frontend) is both code and runtime** - a cross-section of physical gauges, camera feeds, sensor arrays, and controllers. Edge devices (ESP32, Raspberry Pi, etc.) connect via Bluetooth/WiFi and appear as **tracks in the DAW** that can:

1. **Read physical inputs** (jog levers, switches, encoders)
2. **Control physical outputs** (servos, lights, actuators)
3. **Stream sensor data** (GPS, tilt, temperature, pressure)
4. **Display camera feeds** (engine room, deck, forward-looking)
5. **Port controllers/screens** anywhere (Reason-style racks, marine dashboards)

---

## Edge Device IO Types

### 1. Physical Input Devices

#### Jog Lever (Critical Lane)
**Device:** ESP32 with analog joystick
**Connection:** Bluetooth or WiFi
**DAW Track:** "Human Override - Jog Lever" (Critical Lane)
**Purpose:** Absolute human veto - preempts all agent control

```typescript
interface JogLeverInput {
  type: "physical_input";
  device: "ESP32_JogLever";
  connection: "bluetooth | wifi";
  lane: "critical";
  timestamp_ns: number;
  location: {
    latitude: number;
    longitude: number;
    h3_index: string;
  };
  input: {
    direction: "port | starboard | center";
    magnitude: number;  // 0.0 to 1.0
    active: boolean;
  };
  metadata: {
    battery_level: number;
    signal_strength: number;
    last_seen: number;
  };
}

// DAW Visualization
// Track: "Human Override - Jog Lever"
// ├── 14:32:15 ◀ Port (0.75 magnitude) - ACTIVE
// ├── 14:32:20 ● Center - inactive
// └── 14:32:25 ▶ Starboard (0.50 magnitude) - ACTIVE

// Envelope Action: Human Veto (Check #1)
// When active: Reject ALL control intents, safe state
```

#### Light Switches
**Device:** ESP32 with switch array
**Connection:** WiFi
**DAW Track:** "Deck Lights" or "Engine Room Lights"

```typescript
interface SwitchInput {
  type: "physical_input";
  device: "ESP32_SwitchArray";
  connection: "wifi";
  timestamp_ns: number;
  input: {
    switch_id: string;
    state: "on | off";
    location: "deck | engine_room | cabin";
  };
  metadata: {
    power_consumption_watts: number;
  };
}

// DAW Track: "Deck Lights"
// ├── 18:00:00 ● ON (sunset)
// ├── 06:00:00 ○ OFF (sunrise)
// └── Manual toggle events logged

// Automation: Agent can query for lighting decisions
```

#### Throttle Encoder
**Device:** ESP32 with rotary encoder + servo
**Connection:** WiFi
**DAW Track:** "Throttle Position" + "Throttle Command"

```typescript
interface ThrottleInput {
  type: "physical_input";
  device: "ESP32_ThrottleEncoder";
  connection: "wifi";
  timestamp_ns: number;
  input: {
    position_pct: number;  // 0 to 100
    delta: number;  // Change from last
    commanded: boolean;
  };
  metadata: {
    rpm: number;
    fuel_flow_gph: number;
  };
}

interface ThrottleOutput {
  type: "physical_output";
  device: "ESP32_ServoThrottle";
  connection: "wifi";
  timestamp_ns: number;
  output: {
    target_position_pct: number;
    current_position_pct: number;
    active: boolean;
  };
  safety: {
    max_rpm_limit: number;
    rate_limit_pct_per_sec: number;
  };
}

// DAW Track: "Throttle Position" (Continuous line)
// ────────────────────────────────── 100%
//             ┌───┐
// ──────────┘   └────────── 50%
//                      ┌───┐
// ─────────────────────┘   └── 0%

// DAW Track: "Throttle Command" (Step events)
// ├── 08:00 ● Command: 50% (trolling mode)
// ├── 12:30 ● Command: 75% (transit)
// └── 16:45 ● Command: 0% (anchored)
```

---

### 2. Sensor Arrays

#### GPS Array (Heading Sensor)
**Device:** ESP32 with multiple GPS modules
**Connection:** WiFi
**DAW Track:** "GPS Array - Heading Computation"

```typescript
interface GPSArrayInput {
  type: "sensor_array";
  device: "ESP32_GPSArray";
  connection: "wifi";
  timestamp_ns: number;
  location: {
    primary_gps: { lat: number; lon: number; hdop: number; sats: number };
    secondary_gps: { lat: number; lon: number; hdop: number; sats: number };
    computed_heading: number;  // Derived from array
    heading_confidence: number;
  };
  metadata: {
    gps_separation_m: number;
    baseline_heading: number;
  };
}

// DAW Track: "GPS Array - Heading" (Continuous line)
// Heading over time with confidence bands
// 360° ──────────────────────────────────
//       ┌─────────┐
// ──────┘         └─────────────── 180°
//                      ┌─────┐
// ─────────────────────┘         └─ 0°
```

#### Tilt Sensor Array
**Device:** ESP32 with IMU (MPU6050)
**Connection:** Bluetooth
**DAW Track:** "Vessel Attitude" (Pitch/Roll)

```typescript
interface TiltSensorInput {
  type: "sensor_array";
  device: "ESP32_IMU";
  connection: "bluetooth";
  timestamp_ns: number;
  orientation: {
    pitch_deg: number;  // -90 to +90
    roll_deg: number;   // -180 to +180
    yaw_deg: number;    // 0 to 360
  };
  motion: {
    acceleration_x: number;
    acceleration_y: number;
    acceleration_z: number;
    gyro_x: number;
    gyro_y: number;
    gyro_z: number;
  };
  metadata: {
    calibration_status: "calibrated | needs_calibration";
    temperature_c: number;
  };
}

// DAW Track: "Vessel Attitude - Pitch/Roll"
// Two continuous lines showing vessel motion over time
// Pitch:  /¯¯\___/¯¯\___ (degrees)
// Roll:   ~~~~~~~~~~~ (degrees)
```

#### Temperature Sensor Array
**Device:** ESP32 with DS18B20 sensors
**Connection:** WiFi
**DAW Track:** "Engine Temperature" or "Refrigeration"

```typescript
interface TemperatureArrayInput {
  type: "sensor_array";
  device: "ESP32_TemperatureArray";
  connection: "wifi";
  timestamp_ns: number;
  sensors: [
    { id: "engine_1", temp_c: 78.2, location: "port engine" },
    { id: "engine_2", temp_c: 76.8, location: "starboard engine" },
    { id: "gearbox_1", temp_c: 65.4, location: "port gearbox" },
    { id: "gearbox_2", temp_c: 64.9, location: "starboard gearbox" },
    { id: "hold", temp_c: 2.1, location: "fish hold" }
  ];
  metadata: {
    alarm_threshold_c: 90.0;
    warning_threshold_c: 85.0;
  };
}

// DAW Track: "Engine Temperatures" (Multi-line)
// Multiple continuous lines, one per sensor
// Engine 1:  ───────────/¯¯\──────
// Engine 2:  ──────────/¯¯¯\─────
// Gearbox 1: ────────────────
// Hold:      ~~~~~~~~~~~~~~~~~~ (steady cold)
```

---

### 3. Camera Feeds

#### Raspberry Pi Camera
**Device:** Raspberry Pi Zero with camera module
**Connection:** WiFi
**DAW Track:** "Camera Feed" (Video thumbnail + events)
**Front View:** Live video overlay

```typescript
interface CameraInput {
  type: "camera_feed";
  device: "RaspberryPi_Camera";
  connection: "wifi";
  timestamp_ns: number;
  stream: {
    url: string;  // RTSP or HTTP stream
    resolution: "640x480 | 1920x1080";
    fps: number;
    codec: "h264 | mjpeg";
  };
  location: {
    name: "engine_room | deck | forward | stern";
    position: { lat: number; lon: number; heading: number };
  };
  analysis: {
    motion_detected: boolean;
    faces_detected: number;
    objects_detected: string[];
  };
  metadata: {
    storage_enabled: boolean;
    retention_hours: number;
    bandwidth_kbps: number;
  };
}

// DAW Track: "Engine Room Camera" (Thumbnails + events)
// ├── 14:32 📹 Motion detected (person in engine room)
// ├── 15:45 📹 Temperature alert (thermal hot spot)
// └── Continuous thumbnail strip

// Front View: Live video overlay with analysis
// ┌─────────────────────────────────────┐
// │  Engine Room - LIVE                │
// │  ┌─────────────────────────────┐   │
// │  │  [Camera Feed]               │   │
// │  │  Motion: YES                │   │
// │  │  People: 1                   │   │
// │  │  Temp: 76°F                 │   │
// │  └─────────────────────────────┘   │
// └─────────────────────────────────────┘

// Ported to Analyzer:
// Agent can analyze video for:
// - Leak detection (water spots)
// - Thermal monitoring (IR camera)
// - Personnel safety (hard hat detection)
// - Equipment status (gauge reading)
```

#### USB Camera
**Device:** Laptop USB camera
**Connection:** Direct USB
**DAW Track:** "Workstation Camera"
**Front View:** Picture-in-picture overlay

```typescript
interface USBCameraInput {
  type: "camera_feed";
  device: "USB_Camera";
  connection: "usb";
  timestamp_ns: number;
  stream: {
    device_id: string;
    resolution: string;
    fps: number;
  };
  location: {
    name: "wheelhouse | cabin | workstation";
  };
  usage: {
    primary: "video_conference | recording | analysis";
    secondary: "gesture_control | presence_detection";
  };
}
```

---

### 4. Display/Controller Devices

#### Portable Controller Screen
**Device:** ESP32 with TFT display + touch
**Connection:** WiFi
**DAW Track:** "Portable Controller" (IO events)
**Front View:** Ported anywhere (Reason-style rack)

```typescript
interface PortableController {
  type: "controller_display";
  device: "ESP32_TFT_Controller";
  connection: "wifi";
  timestamp_ns: number;
  display: {
    resolution: "320x240";
    orientation: "landscape | portrait";
    brightness: number;
  };
  controls: {
    buttons: { id: string; state: boolean }[];
    sliders: { id: string; value: number }[];
    encoders: { id: string; position: number }[];
  };
  metadata: {
    battery_level: number;
    location: "wheelhouse | deck | engine_room | pocket";
  };
}

// Front View: Ported as "Rack" unit (Reason-style)
// ┌─────────────────────────────────┐
// │  Portable Controller #1         │
// │  ┌───┬───┬───┬───┐            │
// │  │ ↑ │ ↓ │ ○ │ ● │  Buttons   │
// │  ├───┼───┼───┼───┤            │
// │  │ 1 │ 2 │ 3 │ 4 │  Encoders  │
// │  └─────────────┘             │
// │  ┌───────────────────┐        │
// │  │     Slider       │        │
// │  └───────────────────┘        │
// └─────────────────────────────────┘

// DAW Track: "Portable Controller #1 - Inputs"
// ├── 14:32:15 ● Button 1 pressed
// ├── 14:32:17 ○ Encoder 2: +5 steps
// └── 14:32:20 ─ Slider 1: 75% position
```

#### Marine Dashboard Display
**Device:** Any tablet/monitor
**Connection:** WiFi
**Front View:** Cross-section of engine gauges
**DAW Track:** "Dashboard Display" (Configuration events)

```typescript
interface MarineDashboard {
  type: "dashboard_display";
  device: "Tablet | Monitor | Phone";
  connection: "wifi";
  timestamp_ns: number;
  layout: {
    style: "marine_dashboard | code_editor | reason_rack";
    gauges: [
      { type: "speedometer", source: "gps_speed" },
      { type: "tachometer", source: "engine_rpm" },
      { type: "fuel_gauge", source: "fuel_level" },
      { type: "temperature_gauge", source: "engine_temp" },
      { type: "voltmeter", source: "battery_voltage" },
      { type: "pressure_gauge", source: "oil_pressure" }
    ];
  };
  location: {
    name: "wheelhouse_main | wheelhouse_secondary | engine_room | cabin";
  };
}

// Front View: Marine Dashboard (Cross-section of engine gauges)
// ┌─────────────────────────────────────────┐
// │  F/V EILEEN - Engine Room Gauges        │
// │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
// │  │ RPM │ │TEMP │ │FUEL │ │VOLT │       │
// │  │2400 │ │178°F│ │ 85% │ │13.2V│       │
// │  └─────┘ └─────┘ └─────┘ └─────┘       │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
// │  │ OIL │ │GEN │ │TRN │ │PMP │       │
// │  │ 45  │ │ ON │ │ FWD │ │ ON  │       │
// │  └─────┘ └─────┘ └─────┘ └─────┘       │
└─────────────────────────────────────────┘

// DAW Track: "Dashboard Configuration"
// ├── 08:00 ● Layout: marine_dashboard
// ├── 12:30 ● Gauge added: oil_pressure_secondary
// └── 14:45 ● Layout changed: code_editor (for debugging)
```

---

## Complete Edge Device Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EDGE DEVICE NETWORK                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    INPUT DEVICES                            ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ││
│  │  │ Jog Lever    │  │ Light Switch │  │ Throttle     │      ││
│  │  │ (Critical)   │  │ Array        │  │ Encoder       │      ││
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      ││
│  │         │                 │                 │              ││
│  └─────────┼─────────────────┼─────────────────┼──────────────┘│
│            │                 │                 │                   │
│            ▼                 ▼                 ▼                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SENSOR ARRAYS                             ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ││
│  │  │ GPS Array    │  │ Tilt Sensor  │  │ Temperature  │      ││
│  │  │ (Heading)    │  │ (IMU)        │  │ Array        │      ││
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      ││
│  │         │                 │                 │              ││
│  └─────────┼─────────────────┼─────────────────┼──────────────┘│
│            │                 │                 │                   │
│            ▼                 ▼                 ▼                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    CAMERA FEEDS                              ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ││
│  │  │ Engine Room  │  │ Deck Camera  │  │ Forward Cam  │      ││
│  │  │ RPi Camera   │  │ USB Camera   │  │ RPi Camera   │      ││
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      ││
│  │         │                 │                 │              ││
│  └─────────┼─────────────────┼─────────────────┼──────────────┘│
│            │                 │                 │                   │
│            ▼                 ▼                 ▼                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              CONTROLLERS & DISPLAYS                           ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      ││
│  │  │ Portable     │  │ Dashboard    │  │ Analyzer     │      ││
│  │  │ Controller   │  │ Display      │  │ Monitor      │      ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘      ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│                           │                                       │
│                           ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    VESSEL AGENT BACKEND                     ││
│  │  • Time/Location/Source anchoring                             ││
│  │  • Device discovery & registration                            ││
│  │  • Data validation & enrichment                               ││
│  │  • Safety envelope enforcement (critical lane)                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## DAW Track Architecture

### All Devices Become Tracks

```
DAW TIMELINE VIEW (24 hours - Multi-Track)
│
├── 00:00 ────────────────────────────────────────────────────── 24:00
│
│   CRITICAL LANE (Top)
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Human Override - Jog Lever                                    │
│   │  14:32:15 ◀ Port (0.75) - ACTIVE - ENVOY PREEMPTS ALL       │
│   │  14:32:20 ● Center - inactive                              │
│   │  14:32:25 ▶ Starboard (0.50) - ACTIVE - ENVOY PREEMPTS ALL  │
│   └─────────────────────────────────────────────────────────────┘
│
│   CONTINUOUS DATA LANES
│   ┌─────────────────────────────────────────────────────────────┐
│   │ NMEA Sensors (GPS, Depth, Engine)                           │
│   │  • Speed Over Ground ────────────────────                    │
│   │  • Depth ─────────────────────────────                        │
│   │  • RPM ────────────────────────────────                       │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Sensor Arrays (Derived from edge devices)                     │
│   │  • Heading (GPS array) ──────────────────                    │
│   │  • Pitch/Roll (IMU) ────────────────────                      │
│   │  • Engine temps (DS18B20 array) ─────────                    │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Weather & Tides (Continuous from laptop APIs)               │
│   │  • Wind Speed ───────────────────────────                     │
│   │  • Water Level ─────────────────────────                     │
│   └─────────────────────────────────────────────────────────────┘
│
│   EVENT LANES
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Physical Inputs (Switches, encoders)                       │
│   │  08:00 ● Deck Lights ON (sunset)                            │
│   │  12:30 ● Throttle: 50% → 75% (transit)                      │
│   │  18:00 ● Deck Lights OFF (sunrise)                          │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Camera Events (Motion detection, alerts)                     │
│   │  14:32 📹 Engine Room: Motion detected (person)              │
│   │  15:45 📹 Engine Room: Temperature alert (hot spot)          │
│   │  16:20 📹 Deck: Net deployment detected                      │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Fleet Intelligence (Voice reports)                          │
│   │  08:32 💬 F/V Osprey reports chum at Point Arden            │
│   │  10:15 💬 VHF chatter: Good marks near Gary's knob          │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ Catch Events (Logged catch data)                            │
│   │  08:15 🐟 King salmon (14.2 lbs)                           │
│   │  09:45 🐟 Chum salmon (8.4 lbs)                             │
│   └─────────────────────────────────────────────────────────────┘
```

---

## Front View (Frontend) as Runtime Dashboard

### Marine Dashboard Mode

```typescript
interface FrontViewDashboard {
  layout: "marine_dashboard";
  timestamp_ns: number;
  gauges: [
    { label: "RPM", value: 2400, unit: "RPM", source: "engine_rpm", status: "normal" },
    { label: "TEMP", value: 178, unit: "°F", source: "engine_temp", status: "normal" },
    { label: "FUEL", value: 85, unit: "%", source: "fuel_level", status: "normal" },
    { label: "OIL", value: 45, unit: "PSI", source: "oil_pressure", status: "normal" },
    { label: "VOLT", value: 13.2, unit: "V", source: "battery_voltage", status: "normal" },
    { label: "PITCH", value: 2.3, unit: "°", source: "imu_pitch", status: "normal" },
    { label: "ROLL", value: -1.8, unit: "°", source: "imu_roll", status: "normal" },
    { label: "HEAD", value: 180, unit: "°", source: "gps_heading", status: "normal" }
  ];
  alerts: [
    { severity: "warning", message: "Engine temp rising", timestamp: "14:32:15" },
    { severity: "info", message: "F/V Osprey reports chum nearby", timestamp: "14:30:00" }
  ];
}

// Rendered as cross-section of physical gauges
// Each gauge updates in real-time from DAW track data
// Red/yellow/green status indicators based on thresholds
```

### Code Editor Mode (Reason-Style Rack)

```typescript
interface FrontViewCodeEditor {
  layout: "code_editor";
  timestamp_ns: number;
  panels: [
    {
      position: "left",
      content: "markdown_editor",
      document: "daily_summary_2026-07-24.md"
    },
    {
      position: "center",
      content: "controller_rack",
      devices: [
        { id: "portable_controller_1", controls: "buttons, encoders, sliders" },
        { id: "throttle_encoder", controls: "encoder, display" }
      ]
    },
    {
      position: "right",
      content: "chatbot_panel",
      context: "markdown_editor"
    }
  ];
}

// Reason-style rack with portable controllers as "rack units"
// Drag-and-drop controller racks anywhere on screen
```

### Camera Monitor Mode

```typescript
interface FrontViewCameraMonitor {
  layout: "camera_monitor";
  timestamp_ns: number;
  feeds: [
    {
      position: "top_left",
      source: "engine_room_camera",
      url: "rtsp://rpi-engine-room:8554/stream",
      analysis: { motion: true, people: 1, temp: 76 }
    },
    {
      position: "top_right",
      source: "deck_camera",
      url: "rtsp://rpi-deck:8554/stream",
      analysis: { motion: true, objects: ["net", "gear"] }
    },
    {
      position: "bottom_left",
      source: "forward_camera",
      url: "rtsp://rpi-forward:8554/stream",
      analysis: { objects: ["buoy", "land"] }
    },
    {
      position: "bottom_right",
      source: "workstation_camera",
      url: "/dev/video0",
      analysis: { people: 1, gesture: "wave" }
    }
  ];
}

// 4-quadrant camera display
// Each ported to analyzer for real-time processing
// Results fed back to DAW as events
```

---

## Device Discovery & Registration

### ESP32 Device Registration

```typescript
interface DeviceRegistration {
  device_id: string;  // Unique MAC-based ID
  device_type: "input" | "output" | "sensor" | "camera" | "controller";
  connection: "bluetooth" | "wifi" | "usb";
  capabilities: string[];
  metadata: {
    name: string;
    manufacturer: string;
    firmware_version: string;
    battery_level: number;
  };
  registration_time: number;
  last_heartbeat: number;
}

// Auto-discovery on network
// Devices announce presence via mDNS/Bonjour
// Backend validates and assigns DAW track
// Track configuration stored in device profile
```

### Track Assignment

```typescript
interface TrackAssignment {
  device_id: string;
  track_name: string;
  track_type: "continuous" | "event" | "critical";
  lane: "critical" | "telemetry" | "narrative";
  update_frequency_hz: number;
  data_source: string;
  display_config: {
    color: string;
    line_style: "solid" | "dashed" | "dotted";
    icon: string;
  };
}

// Example: Jog lever gets critical lane, red color, warning icon
// Example: Temperature sensor gets telemetry lane, green line, thermometer icon
```

---

## Safety-Critical Integration

### Critical Lane Devices

**Jog Lever (Critical Lane):**
```
ESP32_JogLever → CRITICAL LANE → Envelope Check #1
│
├── Human Veto Active?
│   ├── YES: Reject ALL control intents, safe state
│   └── NO: Continue to envelope checks
```

**Watchdog (Critical Lane):**
```
Watchdog_Relay → CRITICAL LANE → Envelope Check #2
│
├── Watchdog Tripped?
│   ├── YES: Reject ALL control intents, buzzer + safe state
│   └── NO: Continue to envelope checks
```

### Safety Envelope Integration

All physical inputs flow through the **same 7-check envelope** as agent intents:

1. **Human Veto** (Jog lever critical lane)
2. **Watchdog** (Heartbeat critical lane)
3. **Dial Ceiling** (Autonomy level)
4. **Sensor Sanity** (All sensor arrays)
5. **Hard Bounds** (From vessel.toml)
6. **Rate Limits** (Throttle, steering)
7. **Context Guards** (Depth, compass swing, shoaling)

---

## Portability & Reason-Style Interface

### Controller Racks

**Inspired by Reason (propellerheads):**

```
Front View (Code Editor / Runtime):
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Portable #1 │  │ Portable #2 │  │ Throttle    │             │
│  │ ┌───┬───┬───┐│  │ ┌───┬───┬───┐│  │ Encoder    │             │
│  │ │ ↑ │ ↓ │ ○ ││  │ │ ● │ ○ │ ■ ││  │ ┌─────┐    │             │
│  │ ├───┼───┼───┤│  │ ├───┼───┼───┤│  │ │ 75% │    │             │
│  │ │ 1 │ 2 │ 3 ││  │ │ 4 │ 5 │ 6 ││  │ └─────┘    │             │
│  │ └───┴───┴───┘│  │ └───┴───┴───┘│  │ [Servo Pos] │             │
│  │ ┌───────────┐│  │ ┌───────────┐│  └─────────────┘             │
│  │ │ Slider    ││  │ │ Display   ││                                │
│  │ └───────────┘│  │ └───────────┘│                                │
│  └─────────────┘  └─────────────┘                                  │
│                                                                   │
│  [Drag controller racks anywhere on screen]                       │
│  [Each rack appears as DAW track]                                 │
│  [All IO logged with time/location/source]                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key Innovation:**
- **Frontend IS the runtime** - not just code display
- **Portable anywhere** - WiFi controllers, tablets, monitors
- **Reason-style racks** - Drag-and-drop UI components
- **All IO logged** - Every switch, encoder, sensor reading

---

## Success Metrics

### Device Performance
- Device discovery: <5s on power-up
- Connection establishment: <2s
- Input latency: <100ms (jog lever critical)
- Camera streaming latency: <500ms
- Sensor polling rate: 1-100Hz (configurable)

### Data Quality
- 100% of IO time/location/source anchored
- 0% critical lane data loss
- 99.9% telemetry uptime
- <1s sync to DAW tracks

### Safety
- Jog lever override: <50ms latency
- Watchdog trip detection: <100ms
- Human veto preemption: 100% reliable
- Fail-safe state on disconnect

---

## Next Steps

1. ✅ **Edge device IO architecture** (This document)
2. 🔄 **Device discovery protocol**
3. 🔄 **DAW track assignment**
4. 🔄 **Front view dashboard layouts**
5. 🔄 **Safety envelope integration**
6. 🔄 **Portable controller UI**

---

**Document Version:** 1.0
**Date:** 2026-07-24
**Status:** Edge Device IO Architecture Complete

---

*"The ocean forgets nothing. The vessel agent remembers everything - including every switch, sensor, and camera feed."*
