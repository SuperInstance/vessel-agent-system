"""Comprehensive test suite for ReportGenerator.

Tests report generation, export formats, scheduling, delivery,
and integration with twin data sources.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twin.report_generator import (
    ReportGenerator,
    ReportSpec,
    ReportResult,
    ScheduleSpec,
    _coerce_ts,
)


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Create temporary storage directory."""
    storage = tmp_path / "reports"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


@pytest.fixture
def temp_templates(tmp_path: Path) -> Path:
    """Create temporary templates directory."""
    templates = tmp_path / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    return templates


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


# ======================================================================== #
# ReportSpec tests
# ======================================================================== #
def test_report_spec_validation() -> None:
    """Test ReportSpec validation."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    # Valid spec
    spec = ReportSpec(
        report_type="trip",
        title="Test Trip Report",
        start_time=start,
        end_time=end,
        format="html",
    )
    assert spec.report_type == "trip"
    assert spec.format == "html"
    assert spec.start_dt == start
    assert spec.end_dt == end


def test_report_spec_invalid_format() -> None:
    """Test ReportSpec rejects invalid format."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    with pytest.raises(ValueError, match="format must be one of"):
        ReportSpec(
            report_type="trip",
            title="Test",
            start_time=start,
            end_time=end,
            format="invalid",
        )


def test_report_spec_invalid_type() -> None:
    """Test ReportSpec rejects invalid report type."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    with pytest.raises(ValueError, match="report_type must be one of"):
        ReportSpec(
            report_type="invalid",
            title="Test",
            start_time=start,
            end_time=end,
            format="html",
        )


def test_report_spec_end_before_start() -> None:
    """Test ReportSpec rejects end time before start time."""
    start = datetime.now(timezone.utc)
    end = start - timedelta(hours=1)

    with pytest.raises(ValueError, match="end_time must be after start_time"):
        ReportSpec(
            report_type="trip",
            title="Test",
            start_time=start,
            end_time=end,
        )


def test_report_spec_crew_filter() -> None:
    """Test ReportSpec crew filter."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    spec = ReportSpec(
        report_type="daily",
        title="Test",
        start_time=start,
        end_time=end,
        crew_filter={"captain", "crewman"},
    )
    assert spec.crew_filter == {"captain", "crewman"}


# ======================================================================== #
# Timestamp coercion tests
# ======================================================================== #
def test_coerce_ts_none() -> None:
    """Test _coerce_ts with None returns current UTC time."""
    result = _coerce_ts(None)
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc
    # Should be very recent
    assert (datetime.now(timezone.utc) - result).total_seconds() < 1.0


def test_coerce_ts_datetime() -> None:
    """Test _coerce_ts with datetime."""
    dt = datetime(2026, 7, 28, 10, 30, 0, tzinfo=timezone.utc)
    result = _coerce_ts(dt)
    assert result == dt


def test_coerce_ts_naive_datetime() -> None:
    """Test _coerce_ts with naive datetime adds UTC."""
    dt = datetime(2026, 7, 28, 10, 30, 0)
    result = _coerce_ts(dt)
    assert result == dt.replace(tzinfo=timezone.utc)


def test_coerce_ts_epoch_seconds() -> None:
    """Test _coerce_ts with epoch seconds."""
    epoch = 1722167400  # 2024-07-28 10:30:00 UTC
    result = _coerce_ts(epoch)
    assert result.year == 2024
    assert result.month == 7
    assert result.day == 28


def test_coerce_ts_iso_string() -> None:
    """Test _coerce_ts with ISO string."""
    iso = "2026-07-28T10:30:00+00:00"
    result = _coerce_ts(iso)
    assert result.year == 2026
    assert result.month == 7
    assert result.day == 28
    assert result.hour == 10
    assert result.minute == 30


def test_coerce_ts_invalid_string() -> None:
    """Test _coerce_ts with invalid ISO string raises ValueError."""
    with pytest.raises(ValueError, match="unparseable ts string"):
        _coerce_ts("not-a-date")


def test_coerce_ts_invalid_type() -> None:
    """Test _coerce_ts with unsupported type raises TypeError."""
    with pytest.raises(TypeError, match="unsupported ts type"):
        _coerce_ts([1, 2, 3])


# ======================================================================== #
# ReportGenerator initialization tests
# ======================================================================== #
def test_generator_initialization(temp_storage: Path, temp_templates: Path) -> None:
    """Test ReportGenerator initialization."""
    generator = ReportGenerator(
        storage_path=temp_storage,
        template_path=temp_templates,
    )

    assert generator.storage_path == temp_storage
    assert generator.template_path == temp_templates
    assert generator._reports == {}
    assert generator._schedules == {}
    assert generator._webhooks == {}


def test_generator_creates_directories(temp_storage: Path, temp_templates: Path) -> None:
    """Test ReportGenerator creates storage directories."""
    non_existent = temp_storage / "nonexistent" / "subdir"

    generator = ReportGenerator(
        storage_path=non_existent,
        template_path=temp_templates,
    )

    assert non_existent.exists()
    assert non_existent.is_dir()


def test_generator_smtp_configuration(temp_storage: Path, temp_templates: Path) -> None:
    """Test ReportGenerator SMTP configuration."""
    generator = ReportGenerator(
        storage_path=temp_storage,
        template_path=temp_templates,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password",
        smtp_from="reports@example.com",
    )

    assert generator.smtp_host == "smtp.example.com"
    assert generator.smtp_port == 587
    assert generator.smtp_user == "user@example.com"
    assert generator.smtp_password == "password"
    assert generator.smtp_from == "reports@example.com"


# ======================================================================== #
# Callback registration tests
# ======================================================================== #
def test_register_callbacks(mock_generator: ReportGenerator) -> None:
    """Test registering data source callbacks."""
    async def mock_callback(*args, **kwargs):
        return {}

    mock_generator.register_telemetry_query(mock_callback)
    mock_generator.register_a2a_query(mock_callback)
    mock_generator.register_oplog_query(mock_callback)
    mock_generator.register_bathymetry(mock_callback)
    mock_generator.register_vessel_state(mock_callback)

    assert mock_generator._telemetry_query_cb is mock_callback
    assert mock_generator._a2a_query_cb is mock_callback
    assert mock_generator._oplog_query_cb is mock_callback
    assert mock_generator._bathymetry_cb is mock_callback
    assert mock_generator._vessel_state_cb is mock_callback


# ======================================================================== #
# Report generation tests
# ======================================================================== #
@pytest.mark.asyncio
async def test_generate_report_html(mock_generator: ReportGenerator) -> None:
    """Test generating HTML report."""
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="trip",
        title="Test Trip Report",
        start_time=start,
        end_time=end,
        format="html",
        vessel_id="US-AK-FVEILEEN-51",
    )

    result = await mock_generator.generate_report(spec)

    assert result.report_id
    assert result.status == "complete"
    assert result.spec == spec
    assert result.size_bytes > 0
    assert result.file_path is not None
    assert Path(result.file_path).exists()

    # Read and verify file content
    with open(result.file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "<!DOCTYPE html>" in content
    assert spec.title in content


@pytest.mark.asyncio
async def test_generate_report_json(mock_generator: ReportGenerator) -> None:
    """Test generating JSON report."""
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="daily",
        title="Daily Report",
        start_time=start,
        end_time=end,
        format="json",
    )

    result = await mock_generator.generate_report(spec)

    assert result.status == "complete"
    assert result.content

    # Verify JSON is valid
    data = json.loads(result.content)
    assert "spec" in data
    assert "statistics" in data
    assert data["spec"]["report_type"] == "daily"


@pytest.mark.asyncio
async def test_generate_report_csv(mock_generator: ReportGenerator) -> None:
    """Test generating CSV report."""
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="catch",
        title="Catch Report",
        start_time=start,
        end_time=end,
        format="csv",
    )

    result = await mock_generator.generate_report(spec)

    assert result.status == "complete"
    assert result.content
    assert "Report Metadata" in result.content
    assert "Report Type,catch" in result.content


@pytest.mark.asyncio
async def test_generate_report_xml(mock_generator: ReportGenerator) -> None:
    """Test generating XML report."""
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="compliance",
        title="Compliance Report",
        start_time=start,
        end_time=end,
        format="xml",
    )

    result = await mock_generator.generate_report(spec)

    assert result.status == "complete"
    assert result.content
    assert "<?xml version" in result.content
    assert "<Report" in result.content


@pytest.mark.asyncio
async def test_generate_report_markdown(mock_generator: ReportGenerator) -> None:
    """Test generating Markdown report."""
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="performance",
        title="Performance Report",
        start_time=start,
        end_time=end,
        format="md",
    )

    result = await mock_generator.generate_report(spec)

    assert result.status == "complete"
    assert result.content
    assert "# Performance Report" in result.content
    assert "## Statistics" in result.content


@pytest.mark.asyncio
async def test_generate_report_pdf_fallback(mock_generator: ReportGenerator) -> None:
    """Test PDF generation falls back to HTML."""
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="trip",
        title="Trip Report",
        start_time=start,
        end_time=end,
        format="pdf",
    )

    result = await mock_generator.generate_report(spec)

    # Should complete but save as HTML file
    assert result.status == "complete"
    assert result.file_path is not None
    # PDF is saved as HTML with warning
    assert result.file_path.endswith('.html')

    # Read and verify file content
    with open(result.file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "<!DOCTYPE html>" in content


# ======================================================================== #
# Convenience method tests
# ======================================================================== #
@pytest.mark.asyncio
async def test_generate_trip_report(mock_generator: ReportGenerator) -> None:
    """Test generate_trip_report convenience method."""
    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc)

    result = await mock_generator.generate_trip_report(
        trip_id="TRIP-001",
        start_time=start,
        end_time=end,
        format="json",
    )

    assert result.status == "complete"
    assert result.spec.report_type == "trip"
    assert "TRIP-001" in result.spec.title


@pytest.mark.asyncio
async def test_generate_daily_report(mock_generator: ReportGenerator) -> None:
    """Test generate_daily_report convenience method."""
    date = datetime(2026, 7, 28, tzinfo=timezone.utc)

    result = await mock_generator.generate_daily_report(date=date, format="json")

    assert result.status == "complete"
    assert result.spec.report_type == "daily"
    assert "2026-07-28" in result.spec.title
    # Should span full day
    assert result.spec.start_dt.hour == 0
    assert result.spec.start_dt.minute == 0
    assert result.spec.end_dt.hour == 23
    assert result.spec.end_dt.minute == 59


@pytest.mark.asyncio
async def test_generate_catch_report(mock_generator: ReportGenerator) -> None:
    """Test generate_catch_report convenience method."""
    start = datetime.now(timezone.utc) - timedelta(days=1)
    end = datetime.now(timezone.utc)

    result = await mock_generator.generate_catch_report(
        start_time=start,
        end_time=end,
        format="json",
    )

    assert result.status == "complete"
    assert result.spec.report_type == "catch"


# ======================================================================== #
# Data gathering tests
# ======================================================================== #
@pytest.mark.asyncio
async def test_gather_report_data_with_callbacks(mock_generator: ReportGenerator) -> None:
    """Test data gathering with registered callbacks."""
    # Setup mock callbacks to return data
    mock_generator._telemetry_query_cb = AsyncMock(return_value=[
        {"channel": "position.lat", "value": 59.5, "timestamp_ns": 1234567890000000000},
    ])
    mock_generator._a2a_query_cb = AsyncMock(return_value=[
        {"action": "test", "ts": "2026-07-28T10:00:00+00:00"},
    ])
    mock_generator._oplog_query_cb = AsyncMock(return_value=[
        {"entry_type": "catch_logged", "ts": "2026-07-28T10:00:00+00:00"},
    ])

    start = datetime.now(timezone.utc) - timedelta(hours=24)
    end = datetime.now(timezone.utc)

    spec = ReportSpec(
        report_type="trip",
        title="Test",
        start_time=start,
        end_time=end,
        format="json",
    )

    data = await mock_generator._gather_report_data(spec)

    assert "positions" in data
    assert "actions" in data
    assert "operations" in data
    assert "statistics" in data
    assert len(data["positions"]) == 1
    assert len(data["actions"]) == 1


def test_compute_statistics_empty_data() -> None:
    """Test statistics computation with empty data."""
    generator = ReportGenerator(storage_path="test")
    spec = ReportSpec(
        report_type="daily",
        title="Test",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    data = {
        "positions": [],
        "actions": [],
        "operations": [],
        "catch": [],
    }

    stats = generator._compute_statistics(data, spec)

    assert "record_count" in stats
    assert stats["record_count"]["positions"] == 0
    assert stats["record_count"]["actions"] == 0


def test_compute_statistics_with_catch_data() -> None:
    """Test statistics computation with catch records."""
    generator = ReportGenerator(storage_path="test")
    spec = ReportSpec(
        report_type="catch",
        title="Test",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    data = {
        "catch": [
            {
                "ts": "2026-07-28T10:00:00+00:00",
                "crew": "crewman",
                "metadata": {"species": "cod", "weight_kg": 100},
            },
            {
                "ts": "2026-07-28T11:00:00+00:00",
                "crew": "crewman",
                "metadata": {"species": "pollock", "weight_kg": 150},
            },
        ],
        "positions": [],
        "actions": [],
        "operations": [],
    }

    stats = generator._compute_statistics(data, spec)

    assert "catch" in stats
    assert stats["catch"]["total_weight_kg"] == 250
    assert stats["catch"]["species_breakdown"]["cod"] == 1
    assert stats["catch"]["species_breakdown"]["pollock"] == 1


# ======================================================================== #
# Scheduling tests
# ======================================================================== #
def test_schedule_report(mock_generator: ReportGenerator) -> None:
    """Test scheduling a report."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    spec = ReportSpec(
        report_type="daily",
        title="Daily Report",
        start_time=start,
        end_time=end,
    )

    schedule_id = mock_generator.schedule_report(spec, "0 6 * * *")

    assert schedule_id
    assert schedule_id in mock_generator._schedules
    assert mock_generator._schedules[schedule_id].spec == spec
    assert mock_generator._schedules[schedule_id].cron_expression == "0 6 * * *"


def test_cancel_schedule(mock_generator: ReportGenerator) -> None:
    """Test canceling a scheduled report."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    spec = ReportSpec(
        report_type="daily",
        title="Daily Report",
        start_time=start,
        end_time=end,
    )

    schedule_id = mock_generator.schedule_report(spec, "0 6 * * *")
    assert schedule_id in mock_generator._schedules

    cancelled = mock_generator.cancel_schedule(schedule_id)
    assert cancelled is True
    assert schedule_id not in mock_generator._schedules


def test_cancel_nonexistent_schedule(mock_generator: ReportGenerator) -> None:
    """Test canceling non-existent schedule returns False."""
    cancelled = mock_generator.cancel_schedule("nonexistent-id")
    assert cancelled is False


def test_get_scheduled_reports(mock_generator: ReportGenerator) -> None:
    """Test getting all scheduled reports."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)

    spec1 = ReportSpec(
        report_type="daily",
        title="Daily 1",
        start_time=start,
        end_time=end,
    )
    spec2 = ReportSpec(
        report_type="trip",
        title="Trip 1",
        start_time=start,
        end_time=end,
    )

    mock_generator.schedule_report(spec1, "0 6 * * *")
    mock_generator.schedule_report(spec2, "0 8 * * *")

    schedules = mock_generator.get_scheduled_reports()

    assert len(schedules) == 2
    assert all("schedule_id" in s for s in schedules)
    assert all("cron_expression" in s for s in schedules)


# ======================================================================== #
# Report management tests
# ======================================================================== #
def test_get_report(mock_generator: ReportGenerator) -> None:
    """Test getting a report by ID."""
    result = ReportResult(
        report_id="test-id",
        spec=ReportSpec(
            report_type="daily",
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        generated_at=datetime.now(timezone.utc),
        status="complete",
    )

    mock_generator._reports["test-id"] = result

    retrieved = mock_generator.get_report("test-id")
    assert retrieved is result
    assert retrieved.report_id == "test-id"


def test_get_nonexistent_report(mock_generator: ReportGenerator) -> None:
    """Test getting non-existent report returns None."""
    result = mock_generator.get_report("nonexistent")
    assert result is None


def test_list_reports_all(mock_generator: ReportGenerator) -> None:
    """Test listing all reports."""
    for i in range(5):
        result = ReportResult(
            report_id=f"report-{i}",
            spec=ReportSpec(
                report_type="daily",
                title=f"Report {i}",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
            generated_at=datetime.now(timezone.utc) - timedelta(hours=i),
            status="complete",
        )
        mock_generator._reports[f"report-{i}"] = result

    reports = mock_generator.list_reports()
    assert len(reports) == 5


def test_list_reports_filtered(mock_generator: ReportGenerator) -> None:
    """Test listing reports filtered by type."""
    for i in range(3):
        result = ReportResult(
            report_id=f"daily-{i}",
            spec=ReportSpec(
                report_type="daily",
                title=f"Daily {i}",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
            generated_at=datetime.now(timezone.utc),
            status="complete",
        )
        mock_generator._reports[f"daily-{i}"] = result

    for i in range(2):
        result = ReportResult(
            report_id=f"trip-{i}",
            spec=ReportSpec(
                report_type="trip",
                title=f"Trip {i}",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
            generated_at=datetime.now(timezone.utc),
            status="complete",
        )
        mock_generator._reports[f"trip-{i}"] = result

    daily_reports = mock_generator.list_reports(report_type="daily")
    trip_reports = mock_generator.list_reports(report_type="trip")

    assert len(daily_reports) == 3
    assert len(trip_reports) == 2
    assert all(r.spec.report_type == "daily" for r in daily_reports)
    assert all(r.spec.report_type == "trip" for r in trip_reports)


def test_list_reports_limit(mock_generator: ReportGenerator) -> None:
    """Test listing reports with limit."""
    for i in range(10):
        result = ReportResult(
            report_id=f"report-{i}",
            spec=ReportSpec(
                report_type="daily",
                title=f"Report {i}",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
            generated_at=datetime.now(timezone.utc),
            status="complete",
        )
        mock_generator._reports[f"report-{i}"] = result

    reports = mock_generator.list_reports(limit=5)
    assert len(reports) == 5


def test_delete_report(mock_generator: ReportGenerator, temp_storage: Path) -> None:
    """Test deleting a report."""
    # Create a report file
    report_file = temp_storage / "test_report.html"
    report_file.write_text("test content")

    result = ReportResult(
        report_id="test-id",
        spec=ReportSpec(
            report_type="daily",
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        generated_at=datetime.now(timezone.utc),
        status="complete",
        file_path=str(report_file),
    )

    mock_generator._reports["test-id"] = result

    deleted = mock_generator.delete_report("test-id")
    assert deleted is True
    assert "test-id" not in mock_generator._reports
    assert not report_file.exists()


def test_delete_nonexistent_report(mock_generator: ReportGenerator) -> None:
    """Test deleting non-existent report returns False."""
    deleted = mock_generator.delete_report("nonexistent")
    assert deleted is False


# ======================================================================== #
# Webhook tests
# ======================================================================== #
def test_register_webhook(mock_generator: ReportGenerator) -> None:
    """Test registering webhook."""
    mock_generator.register_webhook("https://example.com/webhook", ["daily", "trip"])

    assert "daily" in mock_generator._webhooks
    assert "trip" in mock_generator._webhooks
    assert "https://example.com/webhook" in mock_generator._webhooks["daily"]
    assert "https://example.com/webhook" in mock_generator._webhooks["trip"]


def test_register_multiple_webhooks(mock_generator: ReportGenerator) -> None:
    """Test registering multiple webhooks for same report type."""
    mock_generator.register_webhook("https://example.com/webhook1", ["daily"])
    mock_generator.register_webhook("https://example.com/webhook2", ["daily"])

    assert len(mock_generator._webhooks["daily"]) == 2


# ======================================================================== #
# Template tests
# ======================================================================== #
def test_get_template_nonexistent(mock_generator: ReportGenerator) -> None:
    """Test getting non-existent template returns None."""
    template = mock_generator.get_template("nonexistent")
    assert template is None


def test_register_template(mock_generator: ReportGenerator, temp_templates: Path) -> None:
    """Test registering a template."""
    # Create source template
    src = temp_templates / "source.html"
    src.write_text("<html>Test Template</html>")

    mock_generator.register_template("custom", str(src))

    # Template should be copied to custom.html
    dst = temp_templates / "custom.html"
    assert dst.exists()

    content = dst.read_text()
    assert "Test Template" in content


# ======================================================================== #
# Stats tests
# ======================================================================== #
@pytest.mark.asyncio
async def test_stats(mock_generator: ReportGenerator) -> None:
    """Test getting system statistics."""
    # Add some data
    mock_generator._reports["test-1"] = ReportResult(
        report_id="test-1",
        spec=ReportSpec(
            report_type="daily",
            title="Test",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        generated_at=datetime.now(timezone.utc),
    )

    mock_generator.schedule_report(
        ReportSpec(
            report_type="daily",
            title="Scheduled",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        "0 6 * * *",
    )

    stats = await mock_generator.stats()

    assert "storage_path" in stats
    assert "total_reports" in stats
    assert "total_schedules" in stats
    assert stats["total_reports"] == 1
    assert stats["total_schedules"] == 1


# ======================================================================== #
# Integration tests
# ======================================================================== #
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
