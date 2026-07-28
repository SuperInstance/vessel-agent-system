# ReportGenerator Component Documentation

## Component Overview

The **ReportGenerator** is a comprehensive reporting system for the AELMA marine digital twin that provides regulatory compliance reporting, operational analysis, and fleet management capabilities. It integrates with all TwinCore data sources to generate professional reports in multiple formats.

### Purpose

- **Regulatory Compliance**: Generate reports required by fisheries management agencies
- **Operational Analysis**: Analyze vessel performance, catch patterns, and crew activities
- **Fleet Management**: Multi-vessel reporting and comparative analytics
- **Record Keeping**: Maintain comprehensive digital records of all vessel activities

### Use Cases

1. **Trip Reports**: Complete fishing trip summary for regulatory submission
2. **Catch Logs**: Species catch details for quota tracking and fisheries management
3. **Daily Operations**: 24-hour summaries for shift handoff and performance tracking
4. **Performance Analysis**: Fuel efficiency, catch rates, and operational metrics
5. **Equipment Monitoring**: Gear usage, maintenance tracking, and failure analysis
6. **Compliance Monitoring**: Permit status, quota utilization, and regulatory adherence
7. **Fleet Analytics**: Multi-vessel comparison and best practice identification

### Integration

The ReportGenerator integrates with:

- **TwinCore**: Core vessel digital twin system
- **Telemetry System**: Position, engine, sensor data
- **A2A Log**: Agent-to-agent action history
- **OpLog**: Crew operations and catch logging
- **Bathymetry System**: Depth and seafloor data
- **Vessel State**: Current vessel status and configuration
- **External Systems**: Email (SMTP), webhooks, regulatory APIs

## Architecture

### Component Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ReportGenerator                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Data Gathering Layer                       │  │
│  │  • Telemetry Query Callback                                   │  │
│  │  • A2A Log Query Callback                                     │  │
│  │  • OpLog Query Callback                                      │  │
│  │  • Bathymetry Query Callback                                 │  │
│  │  • Vessel State Query Callback                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                   ↓                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Statistics Computation                     │  │
│  │  • Record Counts                                              │  │
│  │  • Position Statistics                                        │  │
│  │  • Catch Statistics                                          │  │
│  │  • Telemetry Statistics                                       │  │
│  │  • Action Statistics                                         │  │
│  │  • Operation Statistics                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                   ↓                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Report Rendering Layer                     │  │
│  │  • HTML Renderer                                              │  │
│  │  • PDF Renderer                                               │  │
│  │  • JSON Renderer                                              │  │
│  │  • CSV Renderer                                               │  │
│  │  • XML Renderer                                               │  │
│  │  • Markdown Renderer                                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                   ↓                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Delivery & Storage                          │  │
│  │  • File Storage (reports/)                                    │  │
│  │  • Email Delivery (SMTP)                                      │  │
│  │  • Webhook Notifications                                      │  │
│  │  • In-Memory Return                                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                   ↓                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Scheduling System                           │  │
│  │  • Cron-based Scheduling                                      │  │
│  │  • Schedule Persistence                                       │  │
│  │  • Automated Generation                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Structures

#### ReportSpec

```python
@dataclass
class ReportSpec:
    """Specification for report generation."""

    # Required fields
    report_type: str           # Type of report (trip, daily, catch, etc.)
    title: str                 # Report title for display
    start_time: Any            # Time window start (datetime, epoch, or ISO string)
    end_time: Any              # Time window end (datetime, epoch, or ISO string)

    # Optional fields
    format: str = "html"       # Export format (pdf, html, json, csv, xml, md)
    vessel_id: str | None = None           # Vessel identifier
    crew_filter: set[str] | None = None     # Filter by crew members
    include_charts: bool = True             # Include charts (HTML/PDF)
    include_maps: bool = True               # Include maps (HTML/PDF)
    include_raw_data: bool = False          # Include raw data appendix
    recipient_emails: list[str] | None = None  # Auto-delivery recipients
```

**Validation Rules:**
- `format` must be one of: pdf, html, json, csv, xml, md
- `report_type` must be one of: trip, daily, catch, equipment, crew, weather, performance, compliance, maintenance, fleet
- `end_time` must be after `start_time`
- `start_time` and `end_time` accept: None (now), datetime, epoch seconds, or ISO string

#### ReportResult

```python
@dataclass
class ReportResult:
    """Result of report generation."""

    report_id: str             # Unique identifier (UUID4)
    spec: ReportSpec           # Original report specification
    generated_at: datetime     # Generation timestamp (UTC)
    file_path: str | None      # Path to generated file
    content: str | None        # Report content (for JSON, CSV, XML, MD)
    status: str                # pending, generating, complete, failed
    error_message: str | None  # Error message if failed
    size_bytes: int | None     # Size of generated report
```

**Status Flow:**
```
pending → generating → complete
                    ↘ failed
```

#### ScheduleSpec

```python
@dataclass
class ScheduleSpec:
    """Specification for scheduled report generation."""

    schedule_id: str            # Unique identifier (UUID4)
    spec: ReportSpec            # Report specification to generate
    cron_expression: str       # Cron schedule expression
    enabled: bool = True        # Schedule active status
    last_run: datetime | None = None      # Last generation time
    next_run: datetime | None = None      # Next scheduled run
```

### Storage Architecture

#### File System

```
reports/
├── trip_20260728_20260728_a1b2c3d4.html
├── daily_20260728_20260728_e5f6g7h8.pdf
├── catch_20260720_20260728_i9j0k1l2.json
└── ...
```

**File Naming Pattern:**
```
{report_type}_{start_date}_{end_date}_{report_id[:8]}{extension}
```

#### In-Memory Storage

```python
_reports: dict[str, ReportResult] = {}        # report_id -> result
_schedules: dict[str, ScheduleSpec] = {}      # schedule_id -> spec
_webhooks: dict[str, list[str]] = {}          # report_type -> [urls]
```

### Template System

The ReportGenerator uses Python format strings for templating:

```python
# Default template location
template_path = "twin/templates/"

# Template naming convention
{report_type}_report.html

# Example templates
trip_report.html
daily_report.html
catch_report.html
equipment_report.html
crew_report.html
weather_report.html
performance_report.html
compliance_report.html
maintenance_report.html
fleet_report.html
```

## Report Types

### 1. Trip Reports

**Purpose**: Complete fishing trip summary for regulatory compliance and trip analysis.

**Data Includes**:
- Trip duration and timeline
- Total catch by species with weights
- Position track with map
- Depth profile chart
- Weather conditions encountered
- Crew actions and activities
- Equipment usage summary
- Performance metrics (fuel efficiency, catch rates)

**Telemetry Channels**:
```python
{
    "speed_kn", "heading_deg", "depth_m",
    "fuel_level", "engine_hours"
}
```

**Use Cases**:
- Regulatory submission to fisheries agencies
- Trip performance analysis
- Historical record keeping
- Crew payroll verification

**Example**:
```python
spec = ReportSpec(
    report_type="trip",
    title="Trip Report - TRIP-2026-07-28",
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="pdf",
    vessel_id="US-AK-FVEILEEN-51",
    include_charts=True,
    include_maps=True,
)
```

### 2. Daily Reports

**Purpose**: 24-hour operational summary for daily review and shift handoff.

**Data Includes**:
- Timeline of events and activities
- Position track
- Catch summary
- Fuel consumption
- Engine hours
- Weather conditions
- Crew fatigue indicators

**Telemetry Channels**:
```python
{
    "speed_kn", "heading_deg", "depth_m",
    "fuel_level", "engine_hours"
}
```

**Use Cases**:
- Daily operations review
- Shift handoff documentation
- Performance tracking
- Safety monitoring

**Example**:
```python
spec = ReportSpec(
    report_type="daily",
    title="Daily Report - 2026-07-28",
    start_time="2026-07-28T00:00:00Z",
    end_time="2026-07-28T23:59:59Z",
    format="html",
)
```

### 3. Catch Reports

**Purpose**: Species breakdown and analysis for fisheries management.

**Data Includes**:
- Species breakdown with weights and counts
- Size distribution analysis
- Bycatch analysis and discard reasons
- CPUE (catch per unit effort) calculations
- Location heatmaps
- Time distribution of catches

**Telemetry Channels**:
```python
{"depth_m", "sea_surface_temp", "speed_kn"}
```

**Use Cases**:
- Fisheries management data
- Quota tracking
- Scientific analysis
- Catch optimization

**Example**:
```python
spec = ReportSpec(
    report_type="catch",
    title="Catch Report - Week 30",
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="csv",
    include_raw_data=True,
)
```

### 4. Equipment Reports

**Purpose**: Gear usage and maintenance tracking.

**Data Includes**:
- Gear deployment/retrieval log
- Equipment runtime statistics
- Maintenance events history
- Failure analysis
- Predictive maintenance alerts
- Equipment cost tracking

**Telemetry Channels**:
```python
{"engine_hours", "hydraulic_pressure", "winch_speed"}
```

**Use Cases**:
- Maintenance planning
- Cost management
- Reliability analysis
- Equipment optimization

**Example**:
```python
spec = ReportSpec(
    report_type="equipment",
    title="Equipment Status Report",
    start_time="2026-07-01T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="json",
)
```

### 5. Crew Reports

**Purpose**: Crew activity, hours, and fatigue monitoring.

**Data Includes**:
- Hours worked per crew member
- Fatigue analysis
- Actions performed by crew
- Watch schedule compliance
- Training records

**Telemetry Channels**:
```python
{"speed_kn", "heading_deg"}
```

**Use Cases**:
- Crew management
- Compliance monitoring
- Safety analysis
- Payroll verification

**Example**:
```python
spec = ReportSpec(
    report_type="crew",
    title="Crew Activity Report",
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="html",
    crew_filter={"captain", "crewman"},
)
```

### 6. Weather Reports

**Purpose**: Weather conditions encountered and forecast accuracy.

**Data Includes**:
- Weather conditions summary
- Forecast vs actual comparison
- Impact on operations
- Sea state statistics
- Visibility conditions

**Telemetry Channels**:
```python
{
    "wind_speed", "wind_dir", "air_temp",
    "sea_surface_temp", "barometer"
}
```

**Use Cases**:
- Trip planning
- Safety analysis
- Operational optimization
- Weather service validation

**Example**:
```python
spec = ReportSpec(
    report_type="weather",
    title="Weather Impact Report",
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="html",
)
```

### 7. Performance Reports

**Purpose**: Vessel performance metrics and optimization analysis.

**Data Includes**:
- Fuel efficiency analysis
- Speed profiles
- Catch rates
- Engine performance
- Operational costs
- Benchmark comparisons

**Telemetry Channels**:
```python
{"speed_kn", "fuel_rate", "engine_rpm", "depth_m"}
```

**Use Cases**:
- Performance optimization
- Cost reduction
- Fleet benchmarking
- Operational efficiency

**Example**:
```python
spec = ReportSpec(
    report_type="performance",
    title="Performance Analysis - July 2026",
    start_time="2026-07-01T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="pdf",
    include_charts=True,
)
```

### 8. Compliance Reports

**Purpose**: Regulatory compliance status and risk management.

**Data Includes**:
- Permit status
- Quota utilization
- Catch limit compliance
- Reporting deadline tracking
- Area restrictions monitoring
- Observer requirements

**Telemetry Channels**:
```python
{"position.lat", "position.lon", "speed_kn"}
```

**Use Cases**:
- Regulatory compliance
- Audit preparation
- Risk management
- Permit maintenance

**Example**:
```python
spec = ReportSpec(
    report_type="compliance",
    title="Compliance Status - Q3 2026",
    start_time="2026-07-01T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="xml",  # For regulatory submission
)
```

### 9. Maintenance Reports

**Purpose**: Equipment status and maintenance planning.

**Data Includes**:
- Current equipment status
- Upcoming maintenance requirements
- Maintenance history
- Spare parts inventory
- Maintenance cost analysis

**Telemetry Channels**:
```python
{"engine_hours", "hydraulic_pressure", "temperature"}
```

**Use Cases**:
- Maintenance planning
- Budgeting
- Downtime minimization
- Equipment lifecycle management

**Example**:
```python
spec = ReportSpec(
    report_type="maintenance",
    title="Maintenance Schedule - August 2026",
    start_time="2026-07-01T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="html",
)
```

### 10. Fleet Reports

**Purpose**: Multi-vessel analytics and comparative analysis.

**Data Includes**:
- Fleet position overview
- Relative performance analysis
- Best practice identification
- Fleet utilization metrics
- Cross-vessel comparisons

**Telemetry Channels**:
```python
{"speed_kn", "heading_deg", "fuel_level"}
```

**Use Cases**:
- Fleet management
- Strategic planning
- Best practice sharing
- Resource allocation

**Example**:
```python
spec = ReportSpec(
    report_type="fleet",
    title="Fleet Performance - July 2026",
    start_time="2026-07-01T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="html",
    include_charts=True,
    include_maps=True,
)
```

## Export Formats

### PDF

**Purpose**: Professional formatted reports for official submissions and printing.

**Features**:
- Tables and charts
- Position track maps
- Depth profile charts
- Professional formatting
- Page numbers and headers/footers

**Implementation**: Currently falls back to HTML (requires PDF library like weasyprint or reportlab)

**Best For**: Official submissions, printing, archival

**Example**:
```python
result = await generator.generate_report(
    ReportSpec(
        report_type="trip",
        title="Official Trip Report",
        start_time=start,
        end_time=end,
        format="pdf",
    )
)
# Note: Currently saves as HTML with .pdf extension warning
# Production: Use weasyprint or reportlab for true PDF generation
```

### HTML

**Purpose**: Interactive web reports for viewing and analysis.

**Features**:
- Responsive design
- Styled tables
- Chart placeholders (for Chart.js/Plotly integration)
- Map placeholders (for Leaflet integration)
- Print-friendly CSS
- Drill-down capabilities

**Best For**: Web viewing, dashboards, interactive analysis

**Structure**:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{spec[title]}</title>
    <style>
        /* Professional styling */
    </style>
</head>
<body>
    <h1>{spec[title]}</h1>
    <div class="summary">
        <!-- Report metadata -->
    </div>

    <h2>Statistics</h2>
    <!-- Statistical summaries -->

    <h2>Catch Records</h2>
    <table>
        <!-- Data tables -->
    </table>

    <h2>Operations Log</h2>
    <table>
        <!-- Operations data -->
    </table>

    <h2>Actions Log</h2>
    <table>
        <!-- Actions data -->
    </table>
</body>
</html>
```

**Example**:
```python
result = await generator.generate_report(
    ReportSpec(
        report_type="daily",
        title="Daily Operations",
        start_time=start,
        end_time=end,
        format="html",
        include_charts=True,
        include_maps=True,
    )
)
```

### JSON

**Purpose**: Machine-readable structured data for API integration and processing.

**Features**:
- Complete data structure
- Schema-validated
- Easy to parse and process
- Include raw data option
- ISO 8601 timestamps

**Best For**: API integration, data processing, custom applications

**Structure**:
```json
{
    "spec": {
        "report_type": "trip",
        "title": "Trip Report",
        "start_time": "2026-07-20T00:00:00+00:00",
        "end_time": "2026-07-28T00:00:00+00:00",
        "vessel_id": "US-AK-FVEILEEN-51"
    },
    "positions": [
        {"channel": "position.lat", "value": 59.5, "timestamp_ns": 1234567890000000000}
    ],
    "telemetry": {},
    "actions": [],
    "operations": [],
    "catch": [],
    "bathymetry": null,
    "vessel_state": null,
    "statistics": {
        "record_count": {},
        "time_range": {},
        "position": {},
        "catch": {},
        "telemetry": {},
        "actions": {},
        "operations": {}
    }
}
```

**Example**:
```python
result = await generator.generate_report(
    ReportSpec(
        report_type="catch",
        title="Catch Data Export",
        start_time=start,
        end_time=end,
        format="json",
        include_raw_data=True,
    )
)

# Parse and process
data = json.loads(result.content)
catch_data = data["catch"]
```

### CSV

**Purpose**: Spreadsheet-compatible data for analysis and import.

**Features**:
- Multiple sections (metadata, statistics, records)
- Raw data export
- Excel/Google Sheets compatible
- Easy statistical analysis

**Best For**: Spreadsheet analysis, data import/export, custom calculations

**Structure**:
```csv
Report Metadata
Report Type,catch
Title,Catch Report
Start Time,2026-07-20T00:00:00+00:00
End Time,2026-07-28T00:00:00+00:00
Generated,2026-07-28T12:00:00+00:00

Statistics
Record Counts
Category,Count
positions,1500
actions,25
operations,100
catch,50

Catch Statistics
Total Weight (kg),5000

Catch Records
Time,Crew,Species,Weight (kg),Notes
2026-07-21T10:00:00+00:00,crewman,cod,250,
2026-07-21T14:00:00+00:00,captain,pollock,300,

Operations Log
Time,Type,Crew,Message
2026-07-21T08:00:00+00:00,gear_deployed,captain,Deployed cod pot gear
2026-07-21T16:00:00+00:00,gear_retrieved,crewman,Retrieved gear

Actions Log
Time,Action,Source,Priority,Reason
2026-07-21T10:30:00+00:00,raise_alert,watcher,0.85,depth=1.40m
2026-07-21T11:00:00+00:00,mode_morph,llm,0.50,Entering fishing grounds
```

**Example**:
```python
result = await generator.generate_report(
    ReportSpec(
        report_type="catch",
        title="Catch Data for Analysis",
        start_time=start,
        end_time=end,
        format="csv",
    )
)

# Import to spreadsheet
import pandas as pd
from io import StringIO

df = pd.read_csv(StringIO(result.content), skiprows=1)
```

### XML

**Purpose**: Regulatory submission format compatible with e-logbook systems.

**Features**:
- e-logbook compatible
- Namespace handling
- Schema validation
- Compliance with regulatory formats
- Pretty-printed output

**Best For**: Regulatory submissions, EDI integration, official reporting

**Structure**:
```xml
<?xml version="1.0" ?>
<Report type="trip" generated="2026-07-28T12:00:00+00:00">
    <Metadata>
        <Title>Trip Report</Title>
        <StartTime>2026-07-20T00:00:00+00:00</StartTime>
        <EndTime>2026-07-28T00:00:00+00:00</EndTime>
        <VesselID>US-AK-FVEILEEN-51</VesselID>
    </Metadata>

    <Statistics>
        <RecordCounts>
            <Count type="positions">1500</Count>
            <Count type="actions">25</Count>
            <Count type="operations">100</Count>
            <Count type="catch">50</Count>
        </RecordCounts>
        <Catch>
            <TotalWeightKg>5000</TotalWeightKg>
            <SpeciesBreakdown>
                <Species name="cod">30</Species>
                <Species name="pollock">20</Species>
            </SpeciesBreakdown>
        </Catch>
    </Statistics>

    <CatchRecords>
        <Catch timestamp="2026-07-21T10:00:00+00:00" crew="crewman">
            <Species>cod</Species>
            <WeightKg>250</WeightKg>
        </Catch>
    </CatchRecords>

    <Operations>
        <Operation timestamp="2026-07-21T08:00:00+00:00">
            <Type>gear_deployed</Type>
            <Crew>captain</Crew>
            <Message>Deployed cod pot gear</Message>
        </Operation>
    </Operations>

    <Actions>
        <Action timestamp="2026-07-21T10:30:00+00:00">
            <Name>raise_alert</Name>
            <Source>watcher</Source>
            <Priority>0.85</Priority>
            <Reason>depth=1.40m</Reason>
        </Action>
    </Actions>
</Report>
```

**Example**:
```python
result = await generator.generate_report(
    ReportSpec(
        report_type="compliance",
        title="Regulatory Submission",
        start_time=start,
        end_time=end,
        format="xml",
    )
)

# Submit to regulatory system
import requests
response = requests.post(
    "https://regulatory-agency.gov/api/submissions",
    data=result.content,
    headers={"Content-Type": "application/xml"}
)
```

### Markdown

**Purpose**: Documentation and email-friendly reports.

**Features**:
- Clean text format
- Email-friendly
- Easy to version control
- GitHub-compatible
- Simple table formatting

**Best For**: Email reports, documentation, version control

**Structure**:
```markdown
# Trip Report

**Vessel:** US-AK-FVEILEEN-51
**Period:** 2026-07-20 00:00 to 2026-07-28 00:00
**Generated:** 2026-07-28 12:00:00 UTC

## Statistics

### Record Counts

- **Positions:** 1500
- **Actions:** 25
- **Operations:** 100
- **Catch:** 50

### Catch Summary

- **Total Weight:** 5000 kg
- **Total Records:** 50

#### Species Breakdown

| Species | Count |
|---------|-------|
| cod | 30 |
| pollock | 20 |

## Catch Records

| Time | Crew | Species | Weight (kg) |
|------|------|---------|-------------|
| 2026-07-21T10:00:00+00:00 | crewman | cod | 250 |
| 2026-07-21T14:00:00+00:00 | captain | pollock | 300 |

## Operations Log

| Time | Type | Crew | Message |
|------|------|------|---------|
| 2026-07-21T08:00:00+00:00 | gear_deployed | captain | Deployed cod pot gear |
| 2026-07-21T16:00:00+00:00 | gear_retrieved | crewman | Retrieved gear |

## Actions Log

| Time | Action | Source | Priority | Reason |
|------|--------|--------|----------|--------|
| 2026-07-21T10:30:00+00:00 | raise_alert | watcher | 0.85 | depth=1.40m |
| 2026-07-21T11:00:00+00:00 | mode_morph | llm | 0.50 | Entering fishing grounds |
```

**Example**:
```python
result = await generator.generate_report(
    ReportSpec(
        report_type="daily",
        title="Daily Summary",
        start_time=start,
        end_time=end,
        format="md",
    )
)

# Email the report
await send_email(
    to="manager@example.com",
    subject=result.spec.title,
    body=result.content,
)
```

## API Reference

### Initialization

#### ReportGenerator.__init__()

```python
def __init__(
    self,
    storage_path: str | Path = "reports",
    template_path: str | Path = "twin/templates",
    smtp_host: str | None = None,
    smtp_port: int = 587,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    smtp_from: str | None = None,
) -> None:
    """Initialize report generator.

    Parameters
    ----------
    storage_path : str | Path
        Directory to store generated reports (default: "reports")
    template_path : str | Path
        Directory containing report templates (default: "twin/templates")
    smtp_host : str | None
        SMTP server for email delivery (optional)
    smtp_port : int
        SMTP server port (default: 587)
    smtp_user : str | None
        SMTP username (optional)
    smtp_password : str | None
        SMTP password (optional)
    smtp_from : str | None
        From address for report emails (optional)
    """
```

**Example**:
```python
generator = ReportGenerator(
    storage_path="reports",
    template_path="twin/templates",
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_user="reports@example.com",
    smtp_password="password",
    smtp_from="reports@example.com",
)
```

### Report Generation

#### generate_report()

```python
async def generate_report(self, spec: ReportSpec) -> ReportResult:
    """Generate a report from specification.

    Parameters
    ----------
    spec : ReportSpec
        Report specification

    Returns
    -------
    ReportResult
        Result of report generation with status, file_path, and content

    Raises
    ------
    ValueError
        If spec validation fails
    Exception
        If generation fails (status = "failed")
    """
```

**Example**:
```python
spec = ReportSpec(
    report_type="trip",
    title="Trip Report",
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="html",
)

result = await generator.generate_report(spec)

if result.status == "complete":
    print(f"Report saved to: {result.file_path}")
    print(f"Size: {result.size_bytes} bytes")
elif result.status == "failed":
    print(f"Generation failed: {result.error_message}")
```

#### generate_trip_report()

```python
async def generate_trip_report(
    self,
    trip_id: str,
    start_time: Any,
    end_time: Any,
    format: str = "pdf"
) -> ReportResult:
    """Generate a trip report.

    Parameters
    ----------
    trip_id : str
        Trip identifier
    start_time : Any
        Trip start time (datetime, epoch seconds, or ISO string)
    end_time : Any
        Trip end time (datetime, epoch seconds, or ISO string)
    format : str
        Export format (default: "pdf")

    Returns
    -------
    ReportResult
        Trip report result
    """
```

**Example**:
```python
result = await generator.generate_trip_report(
    trip_id="TRIP-2026-07-28",
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="pdf",
)
```

#### generate_daily_report()

```python
async def generate_daily_report(
    self,
    date: datetime,
    format: str = "pdf"
) -> ReportResult:
    """Generate a daily report.

    Parameters
    ----------
    date : datetime
        Date for report (will use day portion)
    format : str
        Export format (default: "pdf")

    Returns
    -------
    ReportResult
        Daily report result spanning full day (00:00:00 to 23:59:59)
    """
```

**Example**:
```python
date = datetime(2026, 7, 28, tzinfo=timezone.utc)
result = await generator.generate_daily_report(date=date, format="html")

# Report spans full day
assert result.spec.start_dt.hour == 0
assert result.spec.start_dt.minute == 0
assert result.spec.end_dt.hour == 23
assert result.spec.end_dt.minute == 59
```

#### generate_catch_report()

```python
async def generate_catch_report(
    self,
    start_time: Any,
    end_time: Any,
    format: str = "pdf"
) -> ReportResult:
    """Generate a catch report.

    Parameters
    ----------
    start_time : Any
        Report start time (datetime, epoch seconds, or ISO string)
    end_time : Any
        Report end time (datetime, epoch seconds, or ISO string)
    format : str
        Export format (default: "pdf")

    Returns
    -------
    ReportResult
        Catch report result
    """
```

**Example**:
```python
result = await generator.generate_catch_report(
    start_time="2026-07-20T00:00:00Z",
    end_time="2026-07-28T00:00:00Z",
    format="csv",
)
```

### Report Management

#### list_reports()

```python
def list_reports(
    self,
    report_type: str | None = None,
    limit: int = 100
) -> list[ReportResult]:
    """List reports with optional filter.

    Parameters
    ----------
    report_type : str | None
        Filter by report type (None = all types)
    limit : int
        Maximum number of reports to return (default: 100)

    Returns
    -------
    list[ReportResult]
        List of reports, newest first (sorted by generated_at)
    """
```

**Example**:
```python
# List all trip reports
trip_reports = generator.list_reports(report_type="trip", limit=10)

for report in trip_reports:
    print(f"{report.spec.title}: {report.status} ({report.generated_at})")

# List all reports
all_reports = generator.list_reports(limit=50)
```

#### get_report()

```python
def get_report(self, report_id: str) -> ReportResult | None:
    """Get a report by ID.

    Parameters
    ----------
    report_id : str
        Report identifier (UUID4)

    Returns
    -------
    ReportResult | None
        Report result or None if not found
    """
```

**Example**:
```python
result = generator.get_report("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

if result:
    print(f"Report: {result.spec.title}")
    print(f"Status: {result.status}")
    print(f"File: {result.file_path}")
else:
    print("Report not found")
```

#### delete_report()

```python
def delete_report(self, report_id: str) -> bool:
    """Delete a report.

    Parameters
    ----------
    report_id : str
        Report identifier

    Returns
    -------
    bool
        True if deleted, False if not found

    Notes
    -----
    Also deletes the report file from disk if it exists
    """
```

**Example**:
```python
deleted = generator.delete_report("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

if deleted:
    print("Report deleted successfully")
else:
    print("Report not found")
```

### Scheduling

#### schedule_report()

```python
def schedule_report(
    self,
    spec: ReportSpec,
    cron_expression: str
) -> str:
    """Schedule a report for automatic generation.

    Parameters
    ----------
    spec : ReportSpec
        Report specification to generate on schedule
    cron_expression : str
        Cron expression (e.g., "0 6 * * *" for daily at 6am)

    Returns
    -------
    str
        Schedule ID (UUID4)

    Notes
    -----
    Scheduled reports are persisted in _schedules dictionary
    """
```

**Example**:
```python
spec = ReportSpec(
    report_type="daily",
    title="Daily Operations Report",
    start_time=datetime.now(timezone.utc),
    end_time=datetime.now(timezone.utc) + timedelta(days=30),
    format="pdf",
    recipient_emails=["manager@example.com"],
)

schedule_id = generator.schedule_report(spec, "0 6 * * *")  # Daily at 6 AM
print(f"Scheduled: {schedule_id}")
```

#### get_scheduled_reports()

```python
def get_scheduled_reports(self) -> list[dict[str, Any]]:
    """Get all scheduled reports.

    Returns
    -------
    list[dict]
        List of schedule specifications with keys:
        - schedule_id: str
        - spec: dict (report_type, title, format)
        - cron_expression: str
        - enabled: bool
        - last_run: str | None (ISO format)
        - next_run: str | None (ISO format)
    """
```

**Example**:
```python
schedules = generator.get_scheduled_reports()

for schedule in schedules:
    print(f"Schedule: {schedule['schedule_id']}")
    print(f"  Title: {schedule['spec']['title']}")
    print(f"  Cron: {schedule['cron_expression']}")
    print(f"  Enabled: {schedule['enabled']}")
    print(f"  Last Run: {schedule['last_run']}")
    print(f"  Next Run: {schedule['next_run']}")
```

#### cancel_schedule()

```python
def cancel_schedule(self, schedule_id: str) -> bool:
    """Cancel a scheduled report.

    Parameters
    ----------
    schedule_id : str
        Schedule ID to cancel

    Returns
    -------
    bool
        True if cancelled, False if not found
    """
```

**Example**:
```python
cancelled = generator.cancel_schedule("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

if cancelled:
    print("Schedule cancelled successfully")
else:
    print("Schedule not found")
```

### Delivery

#### send_report_email()

```python
async def _send_report_email(
    self,
    result: ReportResult,
    recipients: list[str]
) -> None:
    """Send report via email (internal method).

    Parameters
    ----------
    result : ReportResult
        Report result with file to attach
    recipients : list[str]
        List of recipient email addresses

    Notes
    -----
    - Requires SMTP configuration
    - Attaches report file if available
    - Logs errors but doesn't raise exceptions
    - Called automatically if recipient_emails specified in ReportSpec
    """
```

**Example**:
```python
# Automatic delivery via ReportSpec
spec = ReportSpec(
    report_type="daily",
    title="Daily Report",
    start_time=start,
    end_time=end,
    format="pdf",
    recipient_emails=["captain@example.com", "office@example.com"],
)

result = await generator.generate_report(spec)
# Email sent automatically to recipients
```

#### register_webhook()

```python
def register_webhook(
    self,
    url: str,
    report_types: list[str]
) -> None:
    """Register webhook for report notifications.

    Parameters
    ----------
    url : str
        Webhook URL to POST report result to
    report_types : list[str]
        List of report types to trigger on (e.g., ["trip", "catch", "daily"])

    Notes
    -----
    Webhooks receive POST request with JSON payload of ReportResult.to_dict()
    """
```

**Example**:
```python
# Register webhook for multiple report types
generator.register_webhook(
    url="https://your-system.com/webhooks/reports",
    report_types=["trip", "catch", "daily"],
)

# When any of these report types are generated, webhook is called
# POST https://your-system.com/webhooks/reports
# Content-Type: application/json
# {
#   "report_id": "...",
#   "spec": {...},
#   "generated_at": "...",
#   "file_path": "...",
#   "status": "complete",
#   ...
# }
```

### Template Management

#### register_template()

```python
def register_template(
    self,
    template_name: str,
    template_path: str
) -> None:
    """Register a report template.

    Parameters
    ----------
    template_name : str
        Template identifier (e.g., "trip_report")
    template_path : str
        Path to source template file

    Notes
    -----
    Template is copied to template_path/{template_name}.html
    """
```

**Example**:
```python
# Register custom template
generator.register_template(
    template_name="custom_trip",
    template_path="path/to/custom_trip_template.html",
)

# Use custom template
spec = ReportSpec(
    report_type="trip",
    title="Custom Trip Report",
    start_time=start,
    end_time=end,
    format="html",
)

result = await generator.generate_report(spec)
# Uses custom_trip.html template
```

#### get_template()

```python
def get_template(self, template_name: str) -> str | None:
    """Get a template by name.

    Parameters
    ----------
    template_name : str
        Template identifier

    Returns
    -------
    str | None
        Template content or None if not found
    """
```

**Example**:
```python
template = generator.get_template("trip_report")

if template:
    print("Template found:")
    print(template)
else:
    print("Template not found, will use default")
```

### Data Source Registration

#### register_telemetry_query()

```python
def register_telemetry_query(self, callback: Callable[..., Any]) -> None:
    """Register telemetry query callback from TwinCore.

    Parameters
    ----------
    callback : Callable[..., Any]
        Async callback with signature:
        async query(channels: set[str], start_time: datetime, end_time: datetime) -> list[dict]

    Notes
    -----
    Called by _gather_report_data() to query telemetry channels
    """
```

**Example**:
```python
async def telemetry_callback(channels, start_time, end_time):
    # Query telemetry storage
    results = []
    for channel in channels:
        data = await telemetry_db.query(
            channel=channel,
            start=start_time,
            end=end_time,
        )
        results.extend(data)
    return results

generator.register_telemetry_query(telemetry_callback)
```

#### register_a2a_query()

```python
def register_a2a_query(self, callback: Callable[..., Any]) -> None:
    """Register A2A log query callback from TwinCore.

    Parameters
    ----------
    callback : Callable[..., Any]
        Async callback with signature:
        async query(start_time: datetime, end_time: datetime) -> list[dict]

    Notes
    -----
    Called by _gather_report_data() to query agent actions
    """
```

**Example**:
```python
async def a2a_callback(start_time, end_time):
    return await a2a_log.query(
        start=start_time,
        end=end_time,
    )

generator.register_a2a_query(a2a_callback)
```

#### register_oplog_query()

```python
def register_oplog_query(self, callback: Callable[..., Any]) -> None:
    """Register OpLog query callback from TwinCore.

    Parameters
    ----------
    callback : Callable[..., Any]
        Async callback with signature:
        async query(start_time: datetime, end_time: datetime) -> list[dict]

    Notes
    -----
    Called by _gather_report_data() to query operations and catch records
    """
```

**Example**:
```python
async def oplog_callback(start_time, end_time):
    return await oplog.query(
        start=start_time,
        end=end_time,
    )

generator.register_oplog_query(oplog_callback)
```

#### register_bathymetry()

```python
def register_bathymetry(self, callback: Callable[..., Any]) -> None:
    """Register bathymetry query callback from TwinCore.

    Parameters
    ----------
    callback : Callable[..., Any]
        Async callback with signature:
        async query() -> dict

    Notes
    -----
    Called by _gather_report_data() for trip and daily reports
    """
```

**Example**:
```python
async def bathymetry_callback():
    return await bathymetry_system.get_data()

generator.register_bathymetry(bathymetry_callback)
```

#### register_vessel_state()

```python
def register_vessel_state(self, callback: Callable[..., Any]) -> None:
    """Register vessel state callback from TwinCore.

    Parameters
    ----------
    callback : Callable[..., Any]
        Async callback with signature:
        async query() -> dict

    Notes
    -----
    Called by _gather_report_data() to get current vessel state
    """
```

**Example**:
```python
async def vessel_state_callback():
    return await twin.get_vessel_state()

generator.register_vessel_state(vessel_state_callback)
```

### Status

#### stats()

```python
async def stats(self) -> dict[str, Any]:
    """Get system statistics.

    Returns
    -------
    dict
        System status with keys:
        - storage_path: str
        - template_path: str
        - total_reports: int
        - total_schedules: int
        - total_webhooks: int
        - email_configured: bool
    """
```

**Example**:
```python
stats = await generator.stats()

print(f"Storage: {stats['storage_path']}")
print(f"Reports: {stats['total_reports']}")
print(f"Schedules: {stats['total_schedules']}")
print(f"Webhooks: {stats['total_webhooks']}")
print(f"Email: {stats['email_configured']}")
```

## Scheduling System

### Cron Expression Format

Reports are scheduled using standard cron expressions:

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-6, 0=Sunday)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Common Schedules

```python
# Daily at 6 AM
"0 6 * * *"

# Daily at midnight
"0 0 * * *"

# Weekly on Monday at 8 AM
"0 8 * * 1"

# Monthly on the 1st at 9 AM
"0 9 1 * *"

# Every 6 hours
"0 */6 * * *"

# Every hour
"0 * * * *"

# Every 30 minutes
"*/30 * * * *"

# Weekdays at 9 AM
"0 9 * * 1-5"

# Weekend at midnight
"0 0 * * 0,6"
```

### Schedule Persistence

Schedules are stored in-memory in the `_schedules` dictionary:

```python
_schedules: dict[str, ScheduleSpec] = {}
```

For production use, schedules should be persisted to disk or database:

```python
# Save schedules to file
import json

schedules_data = {
    schedule_id: schedule.to_dict()
    for schedule_id, schedule in generator._schedules.items()
}

with open("schedules.json", "w") as f:
    json.dump(schedules_data, f, indent=2)

# Load schedules from file
with open("schedules.json", "r") as f:
    schedules_data = json.load(f)

for schedule_id, schedule_dict in schedules_data.items():
    generator._schedules[schedule_id] = ScheduleSpec(**schedule_dict)
```

### Automated Generation

To implement automated report generation, you need a scheduler:

```python
import asyncio
from croniter import croniter

async def report_scheduler(generator: ReportGenerator):
    """Run scheduled reports."""
    while True:
        now = datetime.now(timezone.utc)

        for schedule_id, schedule in generator._schedules.items():
            if not schedule.enabled:
                continue

            # Calculate next run if not set
            if schedule.next_run is None:
                cron = croniter(schedule.cron_expression, now)
                schedule.next_run = cron.get_next(datetime)

            # Check if it's time to run
            if now >= schedule.next_run:
                print(f"Running scheduled report: {schedule_id}")

                # Generate report
                result = await generator.generate_report(schedule.spec)

                # Update schedule
                schedule.last_run = now
                cron = croniter(schedule.cron_expression, now)
                schedule.next_run = cron.get_next(datetime)

        # Wait before next check
        await asyncio.sleep(60)

# Run scheduler
asyncio.create_task(report_scheduler(generator))
```

### Schedule Management

```python
# Create schedule
spec = ReportSpec(
    report_type="daily",
    title="Daily Operations",
    start_time=datetime.now(timezone.utc),
    end_time=datetime.now(timezone.utc) + timedelta(days=30),
    format="pdf",
)
schedule_id = generator.schedule_report(spec, "0 6 * * *")

# List all schedules
schedules = generator.get_scheduled_reports()

# Enable/disable schedule
generator._schedules[schedule_id].enabled = False

# Cancel schedule
generator.cancel_schedule(schedule_id)
```

## Template System

### Template Location

Templates are stored in the `twin/templates/` directory:

```
twin/templates/
├── trip_report.html
├── daily_report.html
├── catch_report.html
├── equipment_report.html
├── crew_report.html
├── weather_report.html
├── performance_report.html
├── compliance_report.html
├── maintenance_report.html
└── fleet_report.html
```

### Template Syntax

Templates use Python format string syntax with dictionary access:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{spec[title]}</title>
</head>
<body>
    <h1>{spec[title]}</h1>

    <!-- Access nested data -->
    <p>Period: {spec[start_time]} to {spec[end_time]}</p>

    <!-- Statistics -->
    <p>Total Catch: {statistics[catch][total_weight_kg]} kg</p>

    <!-- Tables would require loop logic (not supported by format strings) -->
    <table>
        <!-- Manual table or use template engine -->
    </table>
</body>
</html>
```

**Note**: Python format strings don't support loops. For complex templates, consider using Jinja2:

```python
from jinja2 import Template

template_str = """
<h1>{{ spec.title }}</h1>
<table>
{% for record in operations %}
<tr>
    <td>{{ record.ts }}</td>
    <td>{{ record.entry_type }}</td>
</tr>
{% endfor %}
</table>
"""

template = Template(template_str)
html = template.render(spec=spec, operations=operations)
```

### Custom Templates

To create a custom template:

1. Create HTML file with format string placeholders:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{spec[title]}</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        h1 { color: #2c3e50; }
        .summary { background: #ecf0f1; padding: 20px; }
    </style>
</head>
<body>
    <h1>{spec[title]}</h1>
    <div class="summary">
        <p>Vessel: {spec[vessel_id]}</p>
        <p>Period: {spec[start_time]} to {spec[end_time]}</p>
    </div>

    <h2>Statistics</h2>
    <p>Total Catch: {statistics[catch][total_weight_kg]} kg</p>
    <p>Duration: {statistics[time_range][duration_hours]:.1f} hours</p>
</body>
</html>
```

2. Register the template:

```python
generator.register_template(
    template_name="my_custom_trip",
    template_path="path/to/my_custom_trip.html",
)
```

3. Use the template:

```python
spec = ReportSpec(
    report_type="trip",  # Maps to trip_report.html
    title="Custom Trip Report",
    start_time=start,
    end_time=end,
    format="html",
)

result = await generator.generate_report(spec)
```

### Available Data in Templates

Templates have access to the following data structure:

```python
{
    "spec": {
        "report_type": str,
        "title": str,
        "start_time": str,  # ISO format
        "end_time": str,    # ISO format
        "vessel_id": str | None,
    },
    "positions": [
        {
            "channel": str,
            "value": float,
            "timestamp_ns": int,
            "quality": str,
        }
    ],
    "telemetry": {
        "channel_name": [
            {
                "channel": str,
                "value": float,
                "timestamp_ns": int,
                "quality": str,
            }
        ]
    },
    "actions": [
        {
            "kind": str,
            "action": str,
            "payload": dict,
            "source": str,
            "reason": str,
            "priority": float,
            "ts": str,
        }
    ],
    "operations": [
        {
            "kind": str,
            "entry_type": str,
            "crew": str,
            "message": str,
            "metadata": dict,
            "ts": str,
        }
    ],
    "catch": [
        {
            "kind": str,
            "entry_type": str,
            "crew": str,
            "message": str,
            "metadata": {
                "species": str,
                "weight_kg": float,
                "length_cm": float,
            },
            "ts": str,
        }
    ],
    "bathymetry": dict | None,
    "vessel_state": dict | None,
    "statistics": {
        "record_count": {
            "positions": int,
            "actions": int,
            "operations": int,
            "catch": int,
        },
        "time_range": {
            "start": str,
            "end": str,
            "duration_hours": float,
        },
        "position": {
            "lat_range": {"min": float, "max": float},
            "lon_range": {"min": float, "max": float},
        },
        "catch": {
            "total_weight_kg": float,
            "species_breakdown": {str: int},
            "total_records": int,
        },
        "telemetry": {
            "channel_name": {
                "count": int,
                "mean": float,
                "min": float,
                "max": float,
            }
        },
        "actions": {
            "total": int,
            "by_type": {str: int},
            "by_source": {str: int},
        },
        "operations": {
            "total": int,
            "by_entry_type": {str: int},
            "by_crew": {str: int},
        },
    },
}
```

## Usage Examples

### Example 1: Generate Trip Report (PDF)

```python
from twin.report_generator import ReportGenerator, ReportSpec
from datetime import datetime, timedelta, timezone

# Initialize generator
generator = ReportGenerator(
    storage_path="reports",
    template_path="twin/templates",
)

# Register data source callbacks (from TwinCore)
generator.register_telemetry_query(twin._query_telemetry)
generator.register_a2a_query(twin._query_a2a_log)
generator.register_oplog_query(twin._query_oplog)
generator.register_bathymetry(twin._get_bathymetry_data)
generator.register_vessel_state(twin._get_vessel_state)

# Generate trip report
start_time = datetime.now(timezone.utc) - timedelta(days=7)
end_time = datetime.now(timezone.utc)

spec = ReportSpec(
    report_type="trip",
    title="Trip Report - TRIP-2026-07-28",
    start_time=start_time,
    end_time=end_time,
    format="pdf",
    vessel_id="US-AK-FVEILEEN-51",
    include_charts=True,
    include_maps=True,
)

result = await generator.generate_report(spec)

if result.status == "complete":
    print(f"Trip report generated: {result.file_path}")
    print(f"Size: {result.size_bytes} bytes")
elif result.status == "failed":
    print(f"Generation failed: {result.error_message}")
```

### Example 2: Generate Catch Report (CSV)

```python
# Generate catch report for spreadsheet analysis
start_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
end_time = datetime(2026, 7, 31, tzinfo=timezone.utc)

result = await generator.generate_catch_report(
    start_time=start_time,
    end_time=end_time,
    format="csv",
)

if result.status == "complete":
    # Import to pandas
    import pandas as pd
    from io import StringIO

    df = pd.read_csv(StringIO(result.content))
    print(f"Catch records: {len(df)}")
    print(df.head())
```

### Example 3: Schedule Daily Reports

```python
# Schedule daily report at 6 AM with email delivery
spec = ReportSpec(
    report_type="daily",
    title="Daily Operations Report",
    start_time=datetime.now(timezone.utc),
    end_time=datetime.now(timezone.utc) + timedelta(days=30),
    format="pdf",
    recipient_emails=["captain@example.com", "office@example.com"],
)

schedule_id = generator.schedule_report(spec, "0 6 * * *")

print(f"Daily report scheduled: {schedule_id}")

# View all scheduled reports
schedules = generator.get_scheduled_reports()
for schedule in schedules:
    print(f"{schedule['spec']['title']}: {schedule['cron_expression']}")
```

### Example 4: Custom Template Usage

```python
# Register custom template
generator.register_template(
    template_name="company_branded",
    template_path="templates/company_trip_report.html",
)

# Generate report with custom template
spec = ReportSpec(
    report_type="trip",
    title="Company Branded Trip Report",
    start_time=start_time,
    end_time=end_time,
    format="html",
)

result = await generator.generate_report(spec)
```

### Example 5: Email Delivery

```python
# Configure SMTP
generator = ReportGenerator(
    storage_path="reports",
    template_path="twin/templates",
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_user="reports@example.com",
    smtp_password="app_password",
    smtp_from="reports@example.com",
)

# Generate report with automatic email delivery
spec = ReportSpec(
    report_type="trip",
    title="Trip Report with Email Delivery",
    start_time=start_time,
    end_time=end_time,
    format="pdf",
    recipient_emails=["captain@example.com", "office@example.com"],
)

result = await generator.generate_report(spec)
# Email sent automatically to recipients
```

### Example 6: Webhook Integration

```python
# Register webhook for report notifications
generator.register_webhook(
    url="https://your-system.com/webhooks/reports",
    report_types=["trip", "catch", "daily"],
)

# Generate report (webhook called automatically)
result = await generator.generate_report(spec)

# Webhook receives POST with:
# {
#   "report_id": "...",
#   "spec": {...},
#   "generated_at": "...",
#   "file_path": "...",
#   "status": "complete",
#   ...
# }
```

### Example 7: Report Management

```python
# List all trip reports
trip_reports = generator.list_reports(report_type="trip", limit=10)

for report in trip_reports:
    print(f"{report.spec.title}: {report.status} ({report.generated_at})")
    print(f"  File: {report.file_path}")
    print(f"  Size: {report.size_bytes} bytes")

# Get specific report
report = generator.get_report(report_id)

# Delete old reports
for report in trip_reports:
    if report.generated_at < datetime.now(timezone.utc) - timedelta(days=90):
        generator.delete_report(report.report_id)
        print(f"Deleted old report: {report.report_id}")
```

### Example 8: Fleet Report (Multi-Vessel)

```python
# Generate fleet-wide comparison report
spec = ReportSpec(
    report_type="fleet",
    title="Fleet Performance Comparison - Q3 2026",
    start_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
    end_time=datetime(2026, 9, 30, tzinfo=timezone.utc),
    format="html",
    include_charts=True,
    include_maps=True,
)

result = await generator.generate_report(spec)

if result.status == "complete":
    print(f"Fleet report generated: {result.file_path}")
```

## Testing

### Test Coverage

The ReportGenerator has comprehensive test coverage in `twin/tests/test_report_generator.py`:

#### 40+ Test Areas

1. **ReportSpec Validation** (5 tests)
   - Valid specification
   - Invalid format
   - Invalid report type
   - End time before start time
   - Crew filter

2. **Timestamp Coercion** (6 tests)
   - None returns current UTC
   - Datetime pass-through
   - Naive datetime adds UTC
   - Epoch seconds conversion
   - ISO string parsing
   - Invalid string/type handling

3. **Initialization** (3 tests)
   - Basic initialization
   - Directory creation
   - SMTP configuration

4. **Callback Registration** (1 test)
   - All data source callbacks

5. **Report Generation** (6 tests)
   - HTML format
   - JSON format
   - CSV format
   - XML format
   - Markdown format
   - PDF fallback

6. **Convenience Methods** (3 tests)
   - generate_trip_report()
   - generate_daily_report()
   - generate_catch_report()

7. **Data Gathering** (3 tests)
   - With registered callbacks
   - Empty data statistics
   - Catch data statistics

8. **Scheduling** (4 tests)
   - Schedule report
   - Cancel schedule
   - Cancel nonexistent
   - Get scheduled reports

9. **Report Management** (6 tests)
   - Get report
   - Get nonexistent
   - List all
   - List filtered
   - List with limit
   - Delete report

10. **Webhooks** (2 tests)
    - Register webhook
    - Register multiple webhooks

11. **Templates** (2 tests)
    - Get nonexistent template
    - Register template

12. **Stats** (1 test)
    - System statistics

13. **Integration** (1 test)
    - Full workflow

### Running Tests

```bash
# Run all report generator tests
pytest twin/tests/test_report_generator.py -v

# Run specific test
pytest twin/tests/test_report_generator.py::test_generate_report_html -v

# Run with coverage
pytest twin/tests/test_report_generator.py --cov=twin/report_generator --cov-report=html

# Run async tests only
pytest twin/tests/test_report_generator.py -k "async" -v
```

### Test Fixtures

```python
@pytest.fixture
def mock_generator(temp_storage: Path, temp_templates: Path) -> ReportGenerator:
    """Create ReportGenerator with mocked dependencies."""
    generator = ReportGenerator(
        storage_path=temp_storage,
        template_path=temp_templates,
    )

    # Register mock callbacks
    generator.register_telemetry_query(AsyncMock(return_value=[]))
    generator.register_a2a_query(AsyncMock(return_value=[]))
    generator.register_oplog_query(AsyncMock(return_value=[]))
    generator.register_bathymetry(AsyncMock(return_value={}))
    generator.register_vessel_state(AsyncMock(return_value={}))

    return generator
```

### Sample Test Data

```python
@pytest.fixture
def sample_telemetry_data() -> list[dict]:
    """Sample telemetry data for testing."""
    return [
        {"channel": "position.lat", "value": 59.5, "timestamp_ns": 1234567890000000000, "quality": "good"},
        {"channel": "position.lon", "value": -152.3, "timestamp_ns": 1234567890000000000, "quality": "good"},
        {"channel": "speed_kn", "value": 8.5, "timestamp_ns": 1234567891000000000, "quality": "good"},
        {"channel": "depth_m", "value": 45.2, "timestamp_ns": 1234567892000000000, "quality": "good"},
    ]

@pytest.fixture
def sample_actions_data() -> list[dict]:
    """Sample A2A actions data for testing."""
    return [
        {
            "kind": "action",
            "action": "raise_alert",
            "payload": {"kind": "shallow_water", "depth": 1.4},
            "source": "watcher",
            "reason": "depth=1.40m",
            "priority": 0.85,
            "ts": "2026-07-28T10:30:00.000000+00:00",
            "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
            "_seq": 42,
        },
        {
            "kind": "action",
            "action": "mode_morph",
            "payload": {"mode": "fishing"},
            "source": "llm",
            "reason": "Entering fishing grounds",
            "priority": 0.5,
            "ts": "2026-07-28T11:00:00.000000+00:00",
            "_loggedAt": "2026-07-28T11:00:00.123456+00:00",
            "_seq": 43,
        },
    ]

@pytest.fixture
def sample_operations_data() -> list[dict]:
    """Sample operations log data for testing."""
    return [
        {
            "kind": "oplog_entry",
            "entry_type": "gear_deployed",
            "crew": "captain",
            "message": "Deployed cod pot gear",
            "metadata": {"gear_type": "cod_pot", "count": 50, "lat": 59.5, "lon": -152.3},
            "ts": "2026-07-28T10:00:00.000000+00:00",
            "_loggedAt": "2026-07-28T10:00:00.123456+00:00",
            "_seq": 10,
        },
        {
            "kind": "oplog_entry",
            "entry_type": "catch_logged",
            "crew": "crewman",
            "message": "Caught Pacific cod",
            "metadata": {"species": "pacific_cod", "weight_kg": 250, "length_cm": 85},
            "ts": "2026-07-28T14:00:00.000000+00:00",
            "_loggedAt": "2026-07-28T14:00:00.123456+00:00",
            "_seq": 11,
        },
    ]
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_report_generation_workflow(mock_generator: ReportGenerator) -> None:
    """Test complete report generation workflow."""
    # Setup mock callbacks
    mock_generator._telemetry_query_cb = AsyncMock(return_value=[
        {"channel": "position.lat", "value": 59.5, "timestamp_ns": 1234567890000000000},
        {"channel": "position.lon", "value": -152.3, "timestamp_ns": 1234567890000000000},
    ])
    mock_generator._oplog_query_cb = AsyncMock(return_value=[
        {
            "entry_type": "catch_logged",
            "crew": "crewman",
            "message": "Caught fish",
            "metadata": {"species": "cod", "weight_kg": 100},
            "ts": "2026-07-28T10:00:00+00:00",
        },
    ])

    # Generate report
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    result = await mock_generator.generate_trip_report(
        trip_id="TRIP-001",
        start_time=start,
        end_time=end,
        format="json",
    )

    # Verify
    assert result.status == "complete"
    assert result.report_id in mock_generator._reports

    # List reports
    reports = mock_generator.list_reports(report_type="trip")
    assert len(reports) >= 1
    assert result in reports

    # Get report
    retrieved = mock_generator.get_report(result.report_id)
    assert retrieved == result

    # Schedule future report
    schedule_id = mock_generator.schedule_report(
        ReportSpec(
            report_type="daily",
            title="Scheduled Daily",
            start_time=start,
            end_time=end,
        ),
        "0 6 * * *",
    )
    assert schedule_id in mock_generator._schedules
```

## Data Source Integration

### Telemetry Queries

The ReportGenerator queries telemetry channels based on report type:

```python
async def _gather_report_data(self, spec: ReportSpec) -> dict[str, Any]:
    # Query position history for all reports
    if self._telemetry_query_cb:
        positions = await self._telemetry_query_cb(
            channels={"position.lat", "position.lon"},
            start_time=spec.start_dt,
            end_time=spec.end_dt,
        )
        data["positions"] = positions

    # Query report-specific channels
    channels = self._get_channels_for_report_type(spec.report_type)
    if channels and self._telemetry_query_cb:
        telemetry = await self._telemetry_query_cb(
            channels=channels,
            start_time=spec.start_dt,
            end_time=spec.end_dt,
        )
        data["telemetry"] = telemetry
```

**Channel Mapping**:

```python
{
    "trip": {"speed_kn", "heading_deg", "depth_m", "fuel_level", "engine_hours"},
    "daily": {"speed_kn", "heading_deg", "depth_m", "fuel_level", "engine_hours"},
    "catch": {"depth_m", "sea_surface_temp", "speed_kn"},
    "equipment": {"engine_hours", "hydraulic_pressure", "winch_speed"},
    "crew": {"speed_kn", "heading_deg"},
    "weather": {"wind_speed", "wind_dir", "air_temp", "sea_surface_temp", "barometer"},
    "performance": {"speed_kn", "fuel_rate", "engine_rpm", "depth_m"},
    "compliance": {"position.lat", "position.lon", "speed_kn"},
    "maintenance": {"engine_hours", "hydraulic_pressure", "temperature"},
    "fleet": {"speed_kn", "heading_deg", "fuel_level"},
}
```

### A2A Log Queries

Agent actions are queried for all report types:

```python
if self._a2a_query_cb:
    actions = await self._a2a_query_cb(
        start_time=spec.start_dt,
        end_time=spec.end_dt,
    )
    data["actions"] = actions
```

**Expected Data Structure**:

```python
[
    {
        "kind": "action",
        "action": str,           # Action name
        "payload": dict,         # Action parameters
        "source": str,           # Agent name
        "reason": str,           # Reason for action
        "priority": float,       # Action priority
        "ts": str,               # Timestamp (ISO format)
        "_loggedAt": str,        # Log timestamp
        "_seq": int,             # Sequence number
    }
]
```

### OpLog Queries

Operations and catch records are queried:

```python
if self._oplog_query_cb:
    operations = await self._oplog_query_cb(
        start_time=spec.start_dt,
        end_time=spec.end_dt,
    )
    data["operations"] = operations

    # Extract catch data for specific report types
    if spec.report_type in {"catch", "trip", "daily"}:
        data["catch"] = [
            op for op in operations
            if op.get("entry_type") == "catch_logged"
        ]
```

**Expected Data Structure**:

```python
[
    {
        "kind": "oplog_entry",
        "entry_type": str,       # "gear_deployed", "catch_logged", etc.
        "crew": str,             # Crew member name
        "message": str,          # Operation message
        "metadata": dict,        # Additional data
        "ts": str,               # Timestamp (ISO format)
        "_loggedAt": str,        # Log timestamp
        "_seq": int,             # Sequence number
    }
]
```

### Bathymetry Queries

Bathymetry data is queried for trip and daily reports:

```python
if spec.report_type in {"trip", "daily"} and self._bathymetry_cb:
    bathymetry = await self._bathymetry_cb()
    data["bathymetry"] = bathymetry
```

**Expected Data Structure**:

```python
{
    "depth_data": [
        {"lat": float, "lon": float, "depth_m": float}
    ],
    "metadata": dict
}
```

### Vessel State Queries

Current vessel state is queried for all reports:

```python
if self._vessel_state_cb:
    state = await self._vessel_state_cb()
    data["vessel_state"] = state
```

**Expected Data Structure**:

```python
{
    "vessel_id": str,
    "mode": str,               # Current vessel mode
    "position": {"lat": float, "lon": float},
    "status": dict,            # Current status
    "configuration": dict,     # Vessel configuration
}
```

## Performance Considerations

### Report Generation Time

Report generation time varies by:

- **Time window**: Longer windows = more data to process
- **Report type**: Complex reports (trip, fleet) take longer
- **Format**: PDF/HTML with charts take longer than JSON/CSV
- **Data availability**: Missing data sources may timeout

**Typical Generation Times**:
- JSON/CSV/XML: < 1 second
- HTML: 1-3 seconds
- HTML with charts/maps: 3-10 seconds
- PDF: Currently same as HTML (requires library for true PDF)

### Optimization Strategies

1. **Reduce Time Window**:
   ```python
   # Instead of monthly report, use weekly
   spec = ReportSpec(
       report_type="catch",
       title="Weekly Catch",
       start_time=start,
       end_time=end,  # 7 days instead of 30
   )
   ```

2. **Disable Charts/Maps**:
   ```python
   spec = ReportSpec(
       report_type="trip",
       title="Trip Report",
       start_time=start,
       end_time=end,
       format="html",
       include_charts=False,  # Faster generation
       include_maps=False,
   )
   ```

3. **Use Appropriate Format**:
   ```python
   # JSON/CSV faster than HTML/PDF
   spec = ReportSpec(
       report_type="catch",
       title="Catch Data",
       start_time=start,
       end_time=end,
       format="json",  # Fastest
   )
   ```

4. **Schedule During Off-Hours**:
   ```python
   # Schedule large reports for low-usage periods
   schedule_id = generator.schedule_report(
       spec,
       "0 2 * * *",  # 2 AM daily
   )
   ```

### Concurrent Generation

Report generation is locked per generator instance:

```python
self._generation_lock = asyncio.Lock()
```

For concurrent generation, use multiple generator instances:

```python
generator1 = ReportGenerator(storage_path="reports1")
generator2 = ReportGenerator(storage_path="reports2")

# Generate concurrently
result1 = await generator1.generate_report(spec1)
result2 = await generator2.generate_report(spec2)
```

### Memory Usage

Memory usage scales with:

- **Data volume**: More telemetry/operations = more memory
- **Report format**: HTML/PDF with charts use more memory
- **Concurrent reports**: Each report holds data in memory during generation

**Best Practices**:
- Delete old reports regularly
- Use reasonable time windows
- Monitor memory usage
- Consider streaming for very large reports

## Error Handling

### Validation Errors

ReportSpec validation throws ValueError:

```python
try:
    spec = ReportSpec(
        report_type="invalid",  # Invalid type
        title="Test",
        start_time=start,
        end_time=end,
    )
except ValueError as e:
    print(f"Validation error: {e}")
```

### Generation Errors

Report generation handles errors gracefully:

```python
result = await generator.generate_report(spec)

if result.status == "failed":
    print(f"Generation failed: {result.error_message}")
    # Handle error - retry, notify user, etc.
else:
    print(f"Generation successful: {result.file_path}")
```

**Common Errors**:
- **Missing data source callbacks**: Warning logged, report with partial data
- **Template not found**: Falls back to default template
- **Storage write error**: Status = "failed", error_message set
- **SMTP connection error**: Logged, report still saved

### Logging

The ReportGenerator uses Python logging:

```python
import logging

log = logging.getLogger("aelma.twin.report_generator")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Log Messages**:
- `INFO`: Initialization, report generation, scheduling
- `WARNING`: Missing data, template errors, email failures
- `ERROR`: Generation failures, critical errors

### Best Practices

1. **Check Report Status**:
   ```python
   result = await generator.generate_report(spec)
   if result.status != "complete":
       # Handle failure
       pass
   ```

2. **Handle Missing Data**:
   ```python
   # Report generates with available data
   # Warnings logged for missing data sources
   ```

3. **Monitor Email Delivery**:
   ```python
   # Email failures logged but don't affect report generation
   # Check logs for delivery issues
   ```

4. **Validate Before Generation**:
   ```python
   # Validate spec early
   try:
       spec = ReportSpec(**spec_dict)
   except ValueError as e:
       # Handle validation error
       pass
   ```

## Troubleshooting

### Report Generation Stuck at "generating"

**Symptoms**: Report status remains "generating"

**Causes**:
- Data source callback not returning
- Large data volume
- Network timeout

**Solutions**:
- Check data source callbacks are registered
- Verify logs for errors
- Reduce time window
- Add timeout to callbacks

### Template Not Found

**Symptoms**: Default template used instead of custom

**Causes**:
- Template file not in template_path
- Incorrect naming convention
- File permissions

**Solutions**:
- Verify template_path configuration
- Check file naming: `{report_type}_report.html`
- Verify file permissions
- Check template syntax

### Email Not Sending

**Symptoms**: No email received, report still saved

**Causes**:
- SMTP configuration incorrect
- Network connectivity
- Authentication failure

**Solutions**:
- Verify SMTP settings
- Test SMTP connection
- Check authentication credentials
- Check logs for errors

### Large Report Generation Time

**Symptoms**: Report takes >10 seconds to generate

**Causes**:
- Large time window (months of data)
- Complex format (HTML with charts)
- Slow data sources

**Solutions**:
- Reduce time window
- Use simpler format (JSON/CSV)
- Disable charts/maps
- Schedule during off-hours
- Optimize data queries

### Missing Data in Reports

**Symptoms**: Report sections empty or missing

**Causes**:
- Data source callbacks not registered
- No data in time window
- Data log files missing

**Solutions**:
- Verify all callbacks registered
- Check data availability
- Verify time window
- Check data log files exist

### PDF Generation Issues

**Symptoms**: PDF saved as HTML

**Causes**:
- PDF library not installed
- Implementation limitation

**Current Status**: PDF generation falls back to HTML

**Solutions**:
- Install weasyprint or reportlab
- Update `_render_pdf()` implementation
- Use HTML format and convert manually

## Best Practices

### 1. Schedule Reports During Off-Hours

Generate large reports during low-usage periods:

```python
# Schedule daily report at 2 AM
schedule_id = generator.schedule_report(spec, "0 2 * * *")
```

### 2. Use Appropriate Formats

Choose format based on use case:

- **HTML**: Web viewing, dashboards
- **PDF**: Official submissions, printing
- **JSON**: API integration, data processing
- **CSV**: Spreadsheet analysis
- **XML**: Regulatory submission
- **Markdown**: Documentation, email

### 3. Manage Storage

Regularly clean up old reports:

```python
# Delete reports older than 90 days
cutoff = datetime.now(timezone.utc) - timedelta(days=90)
reports = generator.list_reports()

for report in reports:
    if report.generated_at < cutoff:
        generator.delete_report(report.report_id)
```

### 4. Monitor Failed Reports

Check report status and handle errors:

```python
result = await generator.generate_report(spec)

if result.status == "failed":
    # Log error
    log.error(f"Report generation failed: {result.error_message}")

    # Notify admin
    await notify_admin(f"Report failed: {result.error_message}")

    # Retry with different parameters
    retry_spec = ReportSpec(
        report_type=spec.report_type,
        title=spec.title,
        start_time=spec.start_time,
        end_time=spec.end_time,
        format="json",  # Simpler format
    )
    result = await generator.generate_report(retry_spec)
```

### 5. Use Templates for Branding

Custom templates for consistent branding:

```python
# Register company-branded templates
generator.register_template(
    "company_trip",
    "templates/company_trip_report.html",
)
generator.register_template(
    "company_daily",
    "templates/company_daily_report.html",
)
```

### 6. Set Up Webhooks

For real-time notifications:

```python
# Register webhook for automatic notifications
generator.register_webhook(
    url="https://your-system.com/webhooks/reports",
    report_types=["trip", "catch", "daily"],
)
```

### 7. Use Email Recipients

Automatic delivery via ReportSpec:

```python
spec = ReportSpec(
    report_type="daily",
    title="Daily Report",
    start_time=start,
    end_time=end,
    format="pdf",
    recipient_emails=["captain@example.com", "office@example.com"],
)
```

### 8. Time Zones

Always use timezone-aware datetime objects:

```python
from datetime import datetime, timezone

# Correct
start = datetime(2026, 7, 28, tzinfo=timezone.utc)

# Incorrect (naive datetime)
start = datetime(2026, 7, 28)
```

### 9. Validate Specs Early

Validate report specifications before generation:

```python
try:
    spec = ReportSpec(
        report_type=report_type,
        title=title,
        start_time=start_time,
        end_time=end_time,
        format=format,
    )
except ValueError as e:
    # Handle validation error
    return {"error": str(e)}
```

### 10. Monitor System Statistics

Regularly check system status:

```python
stats = await generator.stats()

print(f"Total reports: {stats['total_reports']}")
print(f"Total schedules: {stats['total_schedules']}")
print(f"Email configured: {stats['email_configured']}")

# Alert if email not configured
if not stats['email_configured']:
    await notify_admin("Email not configured for reports")
```

## Future Enhancements

### Planned Improvements

1. **Real-time Report Generation**
   - Streaming report generation
   - Progressive rendering
   - Live updates

2. **Interactive Charts**
   - Chart.js integration
   - Plotly integration
   - D3.js visualizations

3. **Advanced PDF Rendering**
   - weasyprint integration
   - reportlab support
   - Professional layouts

4. **Report Versioning**
   - Version history
   - Change tracking
   - Audit trail

5. **Report Comparison**
   - Compare reports over time
   - Diff visualization
   - Trend analysis

6. **Automated Archival**
   - Age-based archival
   - Cloud storage integration
   - Compression

7. **Advanced Scheduling**
   - Recurrence patterns
   - Holiday schedules
   - Time zone support

8. **Template Marketplace**
   - Shared templates
   - Template gallery
   - Custom template builder

9. **Report Sharing**
   - Shareable links
   - Access controls
   - Collaboration features

10. **Performance Optimization**
    - Caching strategies
    - Incremental generation
    - Parallel processing

### Contributing

To contribute enhancements:

1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Update documentation
5. Submit pull request

## Support

For issues, questions, or contributions:

- **GitHub**: https://github.com/SuperInstance/aelma
- **Documentation**: https://docs.aelma.example.com
- **Email**: support@aelma.example.com
- **Issues**: https://github.com/SuperInstance/aelma/issues

## License

Copyright 2026 AELMA. All rights reserved.

---

**Document Version**: 1.0.0
**Last Updated**: 2026-07-28
**Component Version**: ReportGenerator 1.0.0
