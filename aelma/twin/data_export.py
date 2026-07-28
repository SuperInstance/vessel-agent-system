"""DataExporter: industry-standard data export for the AELMA twin core.

Produces export artifacts from the three twin data sources — telemetry
packets (:mod:`schema/telemetry_packet.schema.json`), the bathymetry
voxel grid (:mod:`twin.bathymetry`), and the trip summary
(:mod:`twin.trip_summary`) — in industry-standard formats:

  * **JSON** — structured data interchange (all sources).
  * **CSV** — spreadsheet-friendly tabular export (telemetry, bathymetry).
  * **GPX** — GPS Exchange Format tracks/waypoints for chart plotters and
    navigation tools (telemetry position fixes, bathymetry soundings).
  * **KML** — Google Earth visualization (telemetry track, bathymetry).
  * **PDF** — printable trip reports via ReportLab when installed;
    falls back to the plain-text report otherwise.

The exporter is feed-based: pump telemetry packets in via
:meth:`DataExporter.add_telemetry` (live or replayed from JSONL logs),
attach a :class:`~twin.bathymetry.BathymetryGrid` and/or a
:class:`~twin.trip_summary.TripSummary`, then call the export methods.
:meth:`DataExporter.export_batch` packages several exports into a single
zip archive.

Stdlib only; ReportLab is an optional dependency used for PDF output.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
import zipfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from xml.sax.saxutils import escape as _xml_escape

log = logging.getLogger("aelma.twin.data_export")

try:  # Optional dependency: real PDF output when ReportLab is installed.
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    REPORTLAB_AVAILABLE = False

# Telemetry channels consumed for track (GPX/KML) generation.
LAT_CHANNEL = "position.lat"
LON_CHANNEL = "position.lon"

# Export formats supported per source kind.
TELEMETRY_FORMATS = ("json", "csv", "gpx", "kml")
BATHYMETRY_FORMATS = ("json", "csv", "gpx", "kml")
REPORT_FORMATS = ("json", "text", "html", "pdf")


def _iso_from_ns(ts_ns: int) -> str:
    """Render epoch nanoseconds as an ISO-8601 UTC timestamp."""
    return datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc).isoformat()


class DataExporter:
    """Export twin data (telemetry, bathymetry, trip reports) to files.

    Parameters
    ----------
    telemetry:
        Optional iterable of telemetry packet dicts to seed the exporter.
    bathymetry:
        Optional :class:`~twin.bathymetry.BathymetryGrid` or iterable of
        voxel dicts (``lat``, ``lon``, ``depth_m``, ``sample_count``,
        ``last_sample_ns``, ``source``).
    trip_summary:
        Optional :class:`~twin.trip_summary.TripSummary` used by
        :meth:`export_trip_report`.
    """

    def __init__(
        self,
        telemetry: Iterable[Mapping[str, Any]] | None = None,
        bathymetry: Any = None,
        trip_summary: Any = None,
    ) -> None:
        """Initialize the exporter with optional data sources."""
        self._packets: list[dict[str, Any]] = []
        self._cells: list[dict[str, Any]] = []
        self._trip_summary: Any = None
        if telemetry is not None:
            for packet in telemetry:
                self.add_telemetry(packet)
        if bathymetry is not None:
            self.set_bathymetry(bathymetry)
        if trip_summary is not None:
            self.set_trip_summary(trip_summary)

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def add_telemetry(self, packet: Mapping[str, Any]) -> None:
        """Add one telemetry packet; malformed packets are skipped."""
        try:
            self._packets.append(
                {
                    "timestamp_ns": int(packet["timestamp_ns"]),
                    "source": str(packet.get("source", "manual")),
                    "channel": str(packet["channel"]),
                    "value": packet.get("value"),
                    "quality": str(packet.get("quality", "good")),
                    "sentence": packet.get("sentence"),
                }
            )
        except (KeyError, TypeError, ValueError):
            log.warning("skipping malformed telemetry packet: %r", packet)

    def set_bathymetry(self, source: Any) -> None:
        """Attach bathymetry data: a BathymetryGrid or voxel dicts."""
        if hasattr(source, "_cells"):  # BathymetryGrid (same package)
            cells = source._cells.values()
        elif isinstance(source, Iterable):
            cells = source
        else:
            raise TypeError(
                "bathymetry must be a BathymetryGrid or an iterable of voxel dicts"
            )
        self._cells = [
            {
                "lat": float(c["lat"]),
                "lon": float(c["lon"]),
                "depth_m": float(c["depth_m"]),
                "sample_count": int(c.get("sample_count", 1)),
                "last_sample_ns": int(c.get("last_sample_ns", 0)),
                "source": str(c.get("source", "sounder")),
            }
            for c in cells
        ]

    def set_trip_summary(self, summary: Any) -> None:
        """Attach a TripSummary (or any object with generate_summary)."""
        if not hasattr(summary, "generate_summary"):
            raise TypeError("trip_summary must provide generate_summary()")
        self._trip_summary = summary

    # ------------------------------------------------------------------
    # Filtering / track building
    # ------------------------------------------------------------------

    def _filter_packets(self, filters: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        """Apply ``filters`` to the telemetry packets.

        Supported keys: ``channels`` (list of channel names), ``sources``,
        ``qualities``, ``start_ns`` / ``end_ns`` (inclusive epoch-ns bounds).
        Unknown keys are ignored.
        """
        if not filters:
            return sorted(self._packets, key=lambda p: p["timestamp_ns"])
        channels = set(filters.get("channels") or [])
        sources = set(filters.get("sources") or [])
        qualities = set(filters.get("qualities") or [])
        start_ns = filters.get("start_ns")
        end_ns = filters.get("end_ns")

        out = []
        for p in self._packets:
            if channels and p["channel"] not in channels:
                continue
            if sources and p["source"] not in sources:
                continue
            if qualities and p["quality"] not in qualities:
                continue
            if start_ns is not None and p["timestamp_ns"] < int(start_ns):
                continue
            if end_ns is not None and p["timestamp_ns"] > int(end_ns):
                continue
            out.append(p)
        out.sort(key=lambda p: p["timestamp_ns"])
        return out

    @staticmethod
    def _position_fixes(packets: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Pair ``position.lat`` / ``position.lon`` packets into fixes.

        A fix is complete when both channels carry the same
        ``timestamp_ns`` (same rule as :class:`~twin.state.VesselState`).
        Returns fixes sorted by time: ``[{timestamp_ns, lat, lon}, ...]``.
        """
        by_ts: dict[int, dict[str, Any]] = {}
        for p in packets:
            if p["channel"] not in (LAT_CHANNEL, LON_CHANNEL):
                continue
            if not isinstance(p["value"], (int, float)) or isinstance(p["value"], bool):
                continue
            entry = by_ts.setdefault(p["timestamp_ns"], {"timestamp_ns": p["timestamp_ns"]})
            entry["lat" if p["channel"] == LAT_CHANNEL else "lon"] = float(p["value"])
        fixes = [f for f in by_ts.values() if "lat" in f and "lon" in f]
        fixes.sort(key=lambda f: f["timestamp_ns"])
        return fixes

    # ------------------------------------------------------------------
    # Telemetry exports
    # ------------------------------------------------------------------

    def export_telemetry(
        self,
        format: str = "json",
        filters: Mapping[str, Any] | None = None,
    ) -> str:
        """Export telemetry packets as ``json``, ``csv``, ``gpx``, or ``kml``.

        ``filters`` restricts the packets (see :meth:`_filter_packets`).
        GPX/KML output is built from paired position fixes only; packets on
        other channels are ignored for those formats.
        """
        format = format.lower()
        if format not in TELEMETRY_FORMATS:
            raise ValueError(
                f"unsupported telemetry format {format!r}; expected one of {TELEMETRY_FORMATS}"
            )
        packets = self._filter_packets(filters)
        if format == "json":
            return json.dumps(packets, indent=2, ensure_ascii=False, default=str)
        if format == "csv":
            return self._telemetry_csv(packets)
        fixes = self._position_fixes(packets)
        if format == "gpx":
            return self._track_gpx(fixes)
        return self._track_kml(fixes)

    @staticmethod
    def _telemetry_csv(packets: list[dict[str, Any]]) -> str:
        """Render telemetry packets as CSV (one row per packet)."""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(
            ["timestamp_ns", "timestamp_utc", "source", "channel", "value", "quality", "sentence"]
        )
        for p in packets:
            writer.writerow(
                [
                    p["timestamp_ns"],
                    _iso_from_ns(p["timestamp_ns"]),
                    p["source"],
                    p["channel"],
                    p["value"],
                    p["quality"],
                    p["sentence"] if p["sentence"] is not None else "",
                ]
            )
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Bathymetry exports
    # ------------------------------------------------------------------

    def export_bathymetry(self, format: str = "json") -> str:
        """Export the bathymetry grid as ``json``, ``csv``, ``gpx``, or ``kml``.

        GPX output uses waypoints (one per sounding cell); KML uses point
        placemarks; both carry depth and confidence metadata.
        """
        format = format.lower()
        if format not in BATHYMETRY_FORMATS:
            raise ValueError(
                f"unsupported bathymetry format {format!r}; expected one of {BATHYMETRY_FORMATS}"
            )
        cells = sorted(self._cells, key=lambda c: (c["lat"], c["lon"]))
        if format == "json":
            return json.dumps({"cells": cells}, indent=2, ensure_ascii=False, default=str)
        if format == "csv":
            return self._bathymetry_csv(cells)
        if format == "gpx":
            return self._bathymetry_gpx(cells)
        return self._bathymetry_kml(cells)

    @staticmethod
    def _bathymetry_csv(cells: list[dict[str, Any]]) -> str:
        """Render bathymetry cells as CSV (one row per voxel)."""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(
            ["lat", "lon", "depth_m", "sample_count", "last_sample_ns", "last_sample_utc", "source"]
        )
        for c in cells:
            writer.writerow(
                [
                    c["lat"],
                    c["lon"],
                    c["depth_m"],
                    c["sample_count"],
                    c["last_sample_ns"],
                    _iso_from_ns(c["last_sample_ns"]) if c["last_sample_ns"] else "",
                    c["source"],
                ]
            )
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Trip report exports
    # ------------------------------------------------------------------

    def export_trip_report(self, format: str = "pdf") -> str | bytes:
        """Export the trip report as ``json``, ``text``, ``html``, or ``pdf``.

        PDF output requires ReportLab; when it is not installed the
        plain-text report is returned instead (text-only fallback). Returns
        ``bytes`` for real PDF output, ``str`` for every other format.
        """
        format = format.lower()
        if format not in REPORT_FORMATS:
            raise ValueError(
                f"unsupported report format {format!r}; expected one of {REPORT_FORMATS}"
            )
        if self._trip_summary is None:
            raise ValueError("no trip summary attached; call set_trip_summary() first")
        summary = self._trip_summary.generate_summary()
        if format == "json":
            return json.dumps(summary, indent=2, ensure_ascii=False, default=str)
        if format == "html":
            return self._trip_summary.export_html(summary)
        if format == "text":
            return self._trip_summary.export_text(summary)
        # PDF
        if REPORTLAB_AVAILABLE:
            return self._report_pdf(summary)
        log.warning("ReportLab not installed; returning text-only trip report")
        return self._trip_summary.export_text(summary)

    @staticmethod
    def _report_pdf(summary: Mapping[str, Any]) -> bytes:
        """Render the trip summary as a PDF report via ReportLab."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            title="AELMA Trip Report",
        )
        styles = getSampleStyleSheet()
        story: list[Any] = [
            Paragraph("AELMA Trip Report", styles["Title"]),
            Spacer(1, 0.25 * inch),
        ]

        def _section(title: str, rows: list[tuple[str, Any]]) -> None:
            story.append(Paragraph(title, styles["Heading2"]))
            data = [[str(k), str(v)] for k, v in rows if v is not None]
            if data:
                table = Table(data, colWidths=[2.5 * inch, 4.0 * inch])
                table.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ]
                    )
                )
                story.append(table)
            story.append(Spacer(1, 0.15 * inch))

        window = summary.get("trip_window") or {}
        distance = summary.get("distance") or {}
        depth = summary.get("depth") or {}
        fishing = summary.get("fishing") or {}
        alerts = summary.get("alerts") or {}
        catch = summary.get("catch") or {}

        _section(
            f"Trip — {summary.get('vessel_id', 'unknown vessel')}",
            [
                ("Start (UTC)", window.get("start")),
                ("End (UTC)", window.get("end")),
                ("Duration (s)", window.get("duration_s")),
                ("Distance (nm)", distance.get("nm")),
                ("Distance (km)", distance.get("km")),
                ("Position fixes", distance.get("position_fixes")),
                ("Max depth (m)", depth.get("max_m")),
                ("Min depth (m)", depth.get("min_m")),
            ],
        )
        _section(
            "Fishing",
            [
                ("Fishing time (s)", fishing.get("time_s")),
                ("Basis", fishing.get("basis")),
                ("Gear deployments", fishing.get("gear_deployments")),
                ("Hauls completed", fishing.get("hauls_completed")),
            ],
        )
        _section(
            "Alerts",
            [("Total", alerts.get("total"))]
            + sorted((str(k), v) for k, v in (alerts.get("by_kind") or {}).items()),
        )
        _section(
            "Catch",
            [(str(k), v) for k, v in catch.items() if not isinstance(v, (list, dict))],
        )
        story.append(
            Paragraph(
                f"Generated {_iso_from_ns(time.time_ns())}",
                styles["Italic"],
            )
        )
        doc.build(story)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # GPX / KML renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _track_gpx(fixes: list[dict[str, Any]]) -> str:
        """Render position fixes as a GPX 1.1 track."""
        e = _xml_escape
        pts = []
        for f in fixes:
            pts.append(
                f'      <trkpt lat="{f["lat"]}" lon="{f["lon"]}">'
                f"<time>{e(_iso_from_ns(f['timestamp_ns']))}</time></trkpt>"
            )
        body = "\n".join(pts)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="AELMA DataExporter"'
            ' xmlns="http://www.topografix.com/GPX/1/1">\n'
            "  <trk>\n    <name>AELMA vessel track</name>\n    <trkseg>\n"
            f"{body}\n"
            "    </trkseg>\n  </trk>\n</gpx>\n"
        )

    @staticmethod
    def _track_kml(fixes: list[dict[str, Any]]) -> str:
        """Render position fixes as a KML LineString track."""
        coords = " ".join(f'{f["lon"]},{f["lat"]},0' for f in fixes)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2">\n  <Document>\n'
            "    <name>AELMA vessel track</name>\n"
            "    <Placemark>\n      <name>Vessel track</name>\n"
            "      <LineString>\n        <tessellate>1</tessellate>\n"
            f"        <coordinates>{coords}</coordinates>\n"
            "      </LineString>\n    </Placemark>\n  </Document>\n</kml>\n"
        )

    @staticmethod
    def _bathymetry_gpx(cells: list[dict[str, Any]]) -> str:
        """Render bathymetry cells as GPX waypoints with depth metadata."""
        e = _xml_escape
        wpts = []
        for c in cells:
            name = f'{c["depth_m"]:.1f} m'
            desc = (
                f'depth_m={c["depth_m"]}; sample_count={c["sample_count"]}; '
                f'source={c["source"]}'
            )
            wpts.append(
                f'  <wpt lat="{c["lat"]}" lon="{c["lon"]}">'
                f"<name>{e(name)}</name><desc>{e(desc)}</desc></wpt>"
            )
        body = "\n".join(wpts)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="AELMA DataExporter"'
            ' xmlns="http://www.topografix.com/GPX/1/1">\n'
            f"{body}\n</gpx>\n"
        )

    @staticmethod
    def _bathymetry_kml(cells: list[dict[str, Any]]) -> str:
        """Render bathymetry cells as KML point placemarks."""
        e = _xml_escape
        marks = []
        for c in cells:
            desc = (
                f'depth_m={c["depth_m"]}; sample_count={c["sample_count"]}; '
                f'source={c["source"]}'
            )
            marks.append(
                "    <Placemark>\n"
                f'      <name>{e(f"{c["depth_m"]:.1f} m")}</name>\n'
                f"      <description>{e(desc)}</description>\n"
                "      <Point>\n"
                f'        <coordinates>{c["lon"]},{c["lat"]},0</coordinates>\n'
                "      </Point>\n"
                "    </Placemark>"
            )
        body = "\n".join(marks)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2">\n  <Document>\n'
            "    <name>AELMA bathymetry</name>\n"
            f"{body}\n  </Document>\n</kml>\n"
        )

    # ------------------------------------------------------------------
    # Batch export
    # ------------------------------------------------------------------

    def export_batch(
        self,
        zip_path: str | Path,
        jobs: Iterable[Mapping[str, Any]] | None = None,
    ) -> Path:
        """Run several exports and package them into one zip archive.

        Each job is a mapping with ``kind`` (``telemetry`` / ``bathymetry``
        / ``trip_report``), ``format``, an optional ``name`` (archive member
        name), and optional ``filters`` (telemetry only). When ``jobs`` is
        omitted, a default set is exported: telemetry JSON/CSV/GPX,
        bathymetry JSON/CSV/KML, and the trip report as JSON + PDF (when a
        trip summary is attached). Returns the zip path.
        """
        if jobs is None:
            jobs = self._default_jobs()
        target = Path(zip_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for job in jobs:
                kind = str(job["kind"])
                fmt = str(job.get("format", "json"))
                if kind == "telemetry":
                    content = self.export_telemetry(fmt, job.get("filters"))
                elif kind == "bathymetry":
                    content = self.export_bathymetry(fmt)
                elif kind == "trip_report":
                    content = self.export_trip_report(fmt)
                else:
                    raise ValueError(f"unknown batch job kind {kind!r}")
                name = str(job.get("name") or self._default_name(kind, fmt, content))
                zf.writestr(name, content)
                log.info("batch export: wrote %s (%d bytes)", name, len(content))
        return target

    @staticmethod
    def _default_name(kind: str, fmt: str, content: str | bytes) -> str:
        """Archive member name for a job without an explicit ``name``."""
        ext = "pdf" if fmt == "pdf" and isinstance(content, bytes) else (
            "txt" if fmt in ("text", "pdf") else fmt
        )
        stem = {"trip_report": "trip_report"}.get(kind, kind)
        return f"{stem}.{ext}"

    def _default_jobs(self) -> list[dict[str, Any]]:
        """Default batch: all telemetry/bathymetry formats + trip report."""
        jobs: list[dict[str, Any]] = [
            {"kind": "telemetry", "format": fmt} for fmt in TELEMETRY_FORMATS
        ]
        jobs += [{"kind": "bathymetry", "format": fmt} for fmt in BATHYMETRY_FORMATS]
        if self._trip_summary is not None:
            jobs += [
                {"kind": "trip_report", "format": "json"},
                {"kind": "trip_report", "format": "pdf"},
            ]
        return jobs
