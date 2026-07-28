# Report Generation System

## Overview

The AELMA Report Generation System provides comprehensive reporting capabilities for regulatory compliance, operational analysis, and fleet management. The system integrates seamlessly with the TwinCore to aggregate data from multiple sources and generate reports in various formats.

## Features

- **10 Report Types**: Trip, Daily, Catch, Equipment, Crew, Weather, Performance, Compliance, Maintenance, Fleet
- **6 Export Formats**: PDF, HTML, JSON, CSV, XML, Markdown
- **Automated Scheduling**: Cron-based scheduled report generation
- **Multiple Delivery Methods**: Email, webhook, file storage
- **Template System**: Customizable HTML templates
- **Data Aggregation**: Integrates telemetry, A2A log, operations log, and bathymetry data

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TwinCore                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    ReportGenerator                         │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │ │
│  │  │  Data      │  │  Report    │  │  Delivery          │ │ │
│  │  │  Gathering │→ │  Rendering │→ │  System           │ │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│           ↓           ↓           ↓           ↓                │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Telemetry   │ │A2A Log   │ │OpLog     │ │Bathymetry│       │
│  └────────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Report Types

### 1. Trip Reports

Complete fishing trip summary including:
- Trip duration and timeline
- Total catch by species
- Position track map
- Depth profile chart
- Weather conditions summary
- Crew actions log
- Equipment usage summary
- Performance metrics (fuel efficiency, catch rates)

**Use Cases**: Regulatory compliance, trip analysis, record keeping

### 2. Daily Reports

24-hour operational summary including:
- Timeline of events
- Position track
- Catch summary
- Fuel consumption
- Engine hours
- Weather conditions
- Crew fatigue indicators

**Use Cases**: Daily operations review, shift handoff, performance tracking

### 3. Catch Reports

Species breakdown and analysis:
- Species breakdown with weights and counts
- Size distribution analysis
- Bycatch analysis and discard reasons
- CPUE (catch per unit effort) calculations
- Location heatmaps
- Time distribution of catches

**Use Cases**: Fisheries management, quota tracking, scientific analysis

### 4. Equipment Reports

Gear usage and maintenance tracking:
- Gear deployment/retrieval log
- Equipment runtime statistics
- Maintenance events history
- Failure analysis
- Predictive maintenance alerts
- Equipment cost tracking

**Use Cases**: Maintenance planning, cost management, reliability analysis

### 5. Crew Reports

Crew activity and analysis:
- Hours worked per crew member
- Fatigue analysis
- Actions performed by crew
- Watch schedule compliance
- Training records

**Use Cases**: Crew management, compliance, safety monitoring

### 6. Weather Reports

Conditions encountered and forecast accuracy:
- Weather conditions summary
- Forecast vs actual comparison
- Impact on operations
- Sea state statistics
- Visibility conditions

**Use Cases**: Trip planning, safety analysis, operational optimization

### 7. Performance Reports

Vessel performance metrics:
- Fuel efficiency analysis
- Speed profiles
- Catch rates
- Engine performance
- Operational costs
- Benchmark comparisons

**Use Cases**: Performance optimization, cost reduction, fleet benchmarking

### 8. Compliance Reports

Regulatory compliance status:
- Permit status
- Quota utilization
- Catch limit compliance
- Reporting deadline tracking
- Area restrictions monitoring
- Observer requirements

**Use Cases**: Regulatory compliance, audit preparation, risk management

### 9. Maintenance Reports

Equipment status and maintenance planning:
- Current equipment status
- Upcoming maintenance requirements
- Maintenance history
- Spare parts inventory
- Maintenance cost analysis

**Use Cases**: Maintenance planning, budgeting, downtime minimization

### 10. Fleet Reports

Multi-vessel analytics and comparison:
- Fleet position overview
- Relative performance analysis
- Best practice identification
- Fleet utilization metrics
- Cross-vessel comparisons

**Use Cases**: Fleet management, strategic planning, best practice sharing

## Export Formats

### PDF

Professional formatted reports with:
- Tables and charts
- Position track maps
- Depth profile charts
- Professional formatting
- Page numbers and headers/footers

**Best For**: Official submissions, printing, archival

### HTML

Interactive web reports with:
- Responsive design
- Interactive charts (Chart.js/Plotly)
- Leaflet maps for position tracks
- Drill-down capabilities
- Print-friendly CSS

**Best For**: Web viewing, dashboards, interactive analysis

### JSON

Machine-readable structured data:
- Complete data structure
- Schema-validated
- Easy to parse and process
- Include raw data option

**Best For**: API integration, data processing, custom applications

### CSV

Spreadsheet-compatible data:
- Multiple sheets/sections
- Raw data export
- Compatible with Excel, Google Sheets
- Easy statistical analysis

**Best For**: Spreadsheet analysis, data import/export, custom calculations

### XML

Regulatory submission format:
- e-logbook compatible
- Namespace handling
- Schema validation
- Compliance with regulatory formats

**Best For**: Regulatory submissions, EDI integration, official reporting

### Markdown

Documentation and email reports:
- Clean text format
- Email-friendly
- Easy to version control
- GitHub-compatible

**Best For**: Email reports, documentation, version control

## Usage

### Basic Report Generation

```python
from twin.core import TwinCore
from datetime import datetime, timedelta, timezone

# Initialize twin core
twin = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    report_storage_path="reports",
    smtp_host="smtp.example.com",
    smtp_from="reports@example.com",
)

# Generate a trip report
start_time = datetime.now(timezone.utc) - timedelta(days=7)
end_time = datetime.now(timezone.utc)

result = await twin.generate_trip_report(
    trip_id="TRIP-2026-07-28",
    start_time=start_time,
    end_time=end_time,
    format="pdf",
)

print(f"Report generated: {result.report_id}")
print(f"Status: {result.status}")
print(f"File: {result.file_path}")
```

### Daily Report Generation

```python
# Generate daily report for a specific date
date = datetime(2026, 7, 28, tzinfo=timezone.utc)

result = await twin.generate_daily_report(
    date=date,
    format="html",
)
```

### Catch Report with Email Delivery

```python
# Generate catch report and email to recipients
result = await twin.generate_catch_report(
    start_time=start_time,
    end_time=end_time,
    format="pdf",
    recipient_emails=["captain@example.com", "office@example.com"],
)
```

### Scheduled Reports

```python
# Schedule daily report at 6 AM
schedule_id = twin.schedule_report(
    report_type="daily",
    title="Daily Operations Report",
    start_time=datetime.now(timezone.utc),
    end_time=datetime.now(timezone.utc) + timedelta(days=30),
    cron_expression="0 6 * * *",  # Daily at 6 AM
    format="pdf",
    recipient_emails=["manager@example.com"],
)

print(f"Scheduled: {schedule_id}")
```

### Report Management

```python
# List all trip reports
reports = twin.list_reports(report_type="trip", limit=10)

for report in reports:
    print(f"{report.spec.title}: {report.status}")

# Get specific report
report = twin.get_report(report_id)

# Delete old report
twin.delete_report(report_id)
```

### Webhook Integration

```python
# Register webhook for automatic notifications
twin.register_webhook(
    url="https://your-system.com/webhooks/reports",
    report_types=["trip", "catch", "daily"],
)
```

## Scheduling

### Cron Expression Format

Reports can be scheduled using standard cron expressions:

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
```

### Managing Schedules

```python
# Get all scheduled reports
schedules = twin.get_scheduled_reports()

for schedule in schedules:
    print(f"{schedule['title']}: {schedule['cron_expression']}")

# Cancel a schedule
twin.cancel_schedule(schedule_id)
```

## Customization

### Custom Report Templates

```python
# Register a custom template
twin.reports.register_template(
    template_name="custom_trip",
    template_path="path/to/custom_template.html",
)
```

### Template Structure

HTML templates use Python format string syntax:

```html
<!DOCTYPE html>
<html>
<head>
    <title>{spec[title]}</title>
</head>
<body>
    <h1>{spec[title]}</h1>
    <p>Period: {spec[start_time]} to {spec[end_time]}</p>

    <h2>Statistics</h2>
    <p>Total Catch: {statistics[catch][total_weight_kg]} kg</p>

    <!-- Access nested data -->
    <table>
        {% for record in operations %}
        <tr>
            <td>{record[ts]}</td>
            <td>{record[entry_type]}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
```

### Custom Report Types

To add a custom report type:

1. Define the report type in `ReportSpec` validation
2. Add data gathering logic in `_gather_report_data()`
3. Add rendering logic or create a template
4. Update `_get_channels_for_report_type()` if needed

## Integration with TwinCore

### Data Sources

The report generator integrates with TwinCore data sources:

```python
# Registered callbacks
twin.reports.register_vessel_state(twin._get_vessel_state)
twin.reports.register_bathymetry(twin._get_bathymetry_data)
twin.reports.register_a2a_query(twin._query_a2a_log)
twin.reports.register_oplog_query(twin._query_oplog)
twin.reports.register_telemetry_query(twin._query_telemetry)
```

### Configuration

Configure reports in TwinCore initialization:

```python
twin = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    report_storage_path="reports",
    report_template_path="twin/templates",
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_user="user@example.com",
    smtp_password="password",
    smtp_from="reports@example.com",
)
```

## API Reference

### ReportGenerator Class

#### Methods

- `generate_report(spec: ReportSpec) -> ReportResult`
  - Generate a report from specification

- `generate_trip_report(trip_id, start_time, end_time, format) -> ReportResult`
  - Generate a trip report

- `generate_daily_report(date, format) -> ReportResult`
  - Generate a daily report

- `generate_catch_report(start_time, end_time, format) -> ReportResult`
  - Generate a catch report

- `schedule_report(spec, cron_expression) -> str`
  - Schedule a report for automatic generation

- `cancel_schedule(schedule_id) -> bool`
  - Cancel a scheduled report

- `get_scheduled_reports() -> List[Dict]`
  - Get all scheduled reports

- `get_report(report_id) -> ReportResult | None`
  - Get a report by ID

- `list_reports(report_type, limit) -> List[ReportResult]`
  - List reports with optional filter

- `delete_report(report_id) -> bool`
  - Delete a report

- `register_webhook(url, report_types) -> None`
  - Register webhook for report notifications

### ReportSpec Dataclass

```python
@dataclass
class ReportSpec:
    report_type: str           # Type of report
    title: str                 # Report title
    start_time: Any            # Time window start
    end_time: Any              # Time window end
    format: str = "html"       # Export format
    vessel_id: str | None = None
    crew_filter: Set[str] | None = None
    include_charts: bool = True
    include_maps: bool = True
    include_raw_data: bool = False
    recipient_emails: List[str] | None = None
```

### ReportResult Dataclass

```python
@dataclass
class ReportResult:
    report_id: str             # Unique identifier
    spec: ReportSpec           # Original specification
    generated_at: datetime     # Generation timestamp
    file_path: str | None      # Path to generated file
    content: str | None        # Report content
    status: str                # pending, generating, complete, failed
    error_message: str | None  # Error if failed
    size_bytes: int | None     # Size in bytes
```

## Error Handling

The report generator handles errors gracefully:

```python
result = await twin.generate_report(spec)

if result.status == "failed":
    print(f"Report generation failed: {result.error_message}")
    # Handle error
else:
    print(f"Report generated successfully")
    # Use result
```

Common errors:
- **Invalid specification**: ValueError thrown during spec validation
- **Missing data**: Warnings logged, report generated with available data
- **Template not found**: Falls back to default template
- **Export error**: Result status = "failed", error_message set
- **Email delivery failure**: Logged, report still saved

## Performance Considerations

- Large reports may take several seconds to generate
- PDF generation requires additional processing time
- Charts and maps increase generation time
- Email delivery is asynchronous
- Webhook timeouts are 30 seconds
- Report generation is locked per generator instance

## Best Practices

1. **Schedule Reports During Off-Hours**: Generate large reports during low-usage periods

2. **Use Appropriate Formats**:
   - HTML for interactive viewing
   - PDF for official submissions
   - JSON for API integration
   - CSV for spreadsheet analysis

3. **Manage Storage**: Regularly clean up old reports using `delete_report()`

4. **Monitor Failed Reports**: Check report status and handle errors appropriately

5. **Use Templates for Branding**: Custom templates for consistent branding

6. **Set Up Webhooks**: For real-time notifications when reports are generated

7. **Email Recipients**: Use recipient_emails for automatic delivery

8. **Time Zones**: Always use timezone-aware datetime objects

## Troubleshooting

### Report Generation Stuck at "generating"

- Check if data source callbacks are properly registered
- Verify logs for errors in data gathering
- Ensure storage path is writable

### Template Not Found

- Verify template_path configuration
- Check template file naming convention: `{report_type}_report.html`
- Check file permissions

### Email Not Sending

- Verify SMTP configuration
- Check SMTP server connectivity
- Verify authentication credentials
- Check recipient email addresses

### Large Report Generation Time

- Reduce time window for reports
- Disable charts/maps if not needed
- Consider scheduled generation instead of on-demand

### Missing Data in Reports

- Verify data source integrations
- Check time window for data availability
- Verify data log files exist and are readable

## Testing

Run the test suite:

```bash
pytest twin/tests/test_report_generator.py -v
```

Test coverage includes:
- Report specification validation
- All report types
- All export formats
- Scheduling system
- Report management
- Email/webhook delivery
- Integration queries
- Error handling

## Examples

See the `examples/` directory for complete examples:
- `basic_report_generation.py` - Simple report generation
- `scheduled_reports.py` - Setting up scheduled reports
- `custom_templates.py` - Using custom templates
- `email_delivery.py` - Email delivery setup
- `webhook_integration.py` - Webhook integration
- `fleet_reports.py` - Multi-vessel fleet reporting

## Future Enhancements

Planned improvements:
- Real-time report generation with streaming
- Interactive chart libraries integration
- More sophisticated PDF rendering
- Report versioning and history
- Report comparison tools
- Automated report archiving
- Cloud storage integration
- Report sharing and collaboration
- Advanced scheduling with recurrence
- Report templates marketplace

## Support

For issues, questions, or contributions:
- GitHub: https://github.com/SuperInstance/aelma
- Documentation: https://docs.aelma.example.com
- Email: support@aelma.example.com

## License

Copyright 2026 AELMA. All rights reserved.
