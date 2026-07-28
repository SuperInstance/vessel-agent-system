#!/usr/bin/env python3
"""AELMA Deployment Tests

Tests the deployment scripts and service management.
Validates installation, startup, shutdown, and status checking.

Usage:
    pytest tests/deployment.test.py -v
    python tests/deployment.test.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


class TestDeploymentScripts:
    """Test deployment scripts and service management."""

    @property
    def aelma_dir(self) -> Path:
        """Get AELMA directory path."""
        return Path(__file__).parent.parent

    @property
    def scripts_dir(self) -> Path:
        """Get scripts directory path."""
        return self.aelma_dir / "scripts"

    @property
    def venv_dir(self) -> Path:
        """Get virtual environment path."""
        return self.aelma_dir / ".venv"

    @property
    def pid_dir(self) -> Path:
        """Get PID directory path."""
        return self.aelma_dir / "logs" / "pids"

    @property
    def log_dir(self) -> Path:
        """Get log directory path."""
        return self.aelma_dir / "logs"

    def run_command(self, command: List[str], cwd: Path = None) -> subprocess.CompletedProcess:
        """Run a command and return the result."""
        if cwd is None:
            cwd = self.aelma_dir

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result

    def test_script_files_exist(self) -> None:
        """Test that all deployment scripts exist."""
        scripts = [
            "install.sh",
            "install.ps1",
            "start.sh",
            "start.ps1",
            "stop.sh",
            "stop.ps1",
            "status.sh",
            "status.ps1"
        ]

        for script in scripts:
            script_path = self.scripts_dir / script
            assert script_path.exists(), f"Script {script} not found"
            assert script_path.is_file(), f"Script {script} is not a file"

        print("✓ All deployment scripts exist")

    def test_script_permissions(self) -> None:
        """Test that shell scripts are executable (Unix)."""
        if sys.platform == "win32":
            print("⊘ Skipping permission tests on Windows")
            return

        shell_scripts = [
            "install.sh",
            "start.sh",
            "stop.sh",
            "status.sh"
        ]

        for script in shell_scripts:
            script_path = self.scripts_dir / script
            if script_path.exists():
                is_executable = os.access(script_path, os.X_OK)
                assert is_executable, f"Script {script} is not executable"
                print(f"✓ {script} is executable")

    def test_systemd_service_files(self) -> None:
        """Test that systemd service files exist and are valid."""
        if sys.platform == "win32":
            print("⊘ Skipping systemd tests on Windows")
            return

        systemd_dir = self.scripts_dir / "systemd"
        services = [
            "aelma-bridge.service",
            "aelma-twin.service",
            "aelma-viewer.service",
            "aelma-simulator.service"
        ]

        assert systemd_dir.exists(), "Systemd directory not found"

        for service in services:
            service_path = systemd_dir / service
            assert service_path.exists(), f"Service file {service} not found"

            # Read and validate service file
            content = service_path.read_text()

            # Check for required sections
            assert "[Unit]" in content, f"{service} missing [Unit] section"
            assert "[Service]" in content, f"{service} missing [Service] section"
            assert "[Install]" in content, f"{service} missing [Install] section"

            # Check for required fields
            assert "Description=" in content, f"{service} missing Description"
            assert "ExecStart=" in content, f"{service} missing ExecStart"
            assert "User=" in content, f"{service} missing User"

            print(f"✓ {service} is valid")

    def test_virtual_environment_setup(self) -> None:
        """Test virtual environment can be created."""
        # Skip if venv already exists
        if self.venv_dir.exists():
            print("⊘ Virtual environment already exists")
            return

        # Try to create venv
        python = sys.executable

        result = self.run_command([
            python, "-m", "venv", str(self.venv_dir)
        ])

        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"
        assert self.venv_dir.exists(), "Virtual environment directory not created"

        # Check python executable
        if sys.platform == "win32":
            python_bin = self.venv_dir / "Scripts" / "python.exe"
        else:
            python_bin = self.venv_dir / "bin" / "python"

        assert python_bin.exists(), "Python executable not found in venv"

        print("✓ Virtual environment setup works")

    def test_log_directory_creation(self) -> None:
        """Test that log directories can be created."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pid_dir.mkdir(parents=True, exist_ok=True)

        assert self.log_dir.exists(), "Log directory not created"
        assert self.pid_dir.exists(), "PID directory not created"

        print("✓ Log directories can be created")

    def test_component_import(self) -> None:
        """Test that component modules can be imported."""
        components = [
            "bridge",
            "twin"
        ]

        for component in components:
            try:
                # Try importing the module
                __import__(component)
                print(f"✓ {component} can be imported")
            except ImportError as e:
                print(f"✗ {component} import failed: {e}")
                if self.venv_dir.exists():
                    # Only fail if venv exists (should have dependencies)
                    raise

    def test_port_availability_check(self) -> None:
        """Test port availability checking."""
        ports = [8000, 8001, 8080, 8090]

        for port in ports:
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()

                if result == 0:
                    print(f"⊘ Port {port} is in use")
                else:
                    print(f"✓ Port {port} is available")
            except Exception as e:
                print(f"✗ Port {port} check failed: {e}")

    def test_environment_file_template(self) -> None:
        """Test that environment file can be created."""
        env_file = self.aelma_dir / ".env"

        # Create test environment file
        test_content = """# AELMA Configuration
MODE=development
PLATFORM=linux
VENV_DIR=/opt/aelma/.venv

# Bridge
BRIDGE_TCP_PORT=8001
BRIDGE_WS_PORT=8000

# Twin
TWIN_BRIDGE_URL=ws://localhost:8000
TWIN_VIEWER_PORT=8090
"""

        try:
            env_file.write_text(test_content)
            assert env_file.exists(), "Environment file not created"

            # Read and validate
            content = env_file.read_text()
            assert "BRIDGE_TCP_PORT" in content, "Missing BRIDGE_TCP_PORT"
            assert "TWIN_VIEWER_PORT" in content, "Missing TWIN_VIEWER_PORT"

            print("✓ Environment file template works")

            # Clean up
            env_file.unlink(missing_ok=True)
        except Exception as e:
            print(f"✗ Environment file creation failed: {e}")
            raise

    def test_help_commands(self) -> None:
        """Test that components respond to help requests."""
        if not self.venv_dir.exists():
            print("⊘ Skipping help tests (no venv)")
            return

        # Test bridge help
        try:
            result = self.run_command([
                str(self.venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else self.venv_dir / "bin" / "python"),
                "-m", "bridge", "--help"
            ])

            if result.returncode == 0:
                print("✓ Bridge help command works")
            else:
                print(f"✗ Bridge help failed: {result.stderr}")
        except Exception as e:
            print(f"⊘ Bridge help test failed: {e}")

    def test_bathymetry_file(self) -> None:
        """Test that bathymetry file exists or can be created."""
        bathymetry_file = self.aelma_dir / "bathymetry.json"

        if bathymetry_file.exists():
            print("✓ Bathymetry file exists")
        else:
            # Create default bathymetry
            import json
            default_data = {
                "type": "FeatureCollection",
                "features": []
            }

            bathymetry_file.write_text(json.dumps(default_data, indent=2))
            print("✓ Default bathymetry file created")

    def run_all_tests(self) -> bool:
        """Run all deployment tests."""
        tests = [
            self.test_script_files_exist,
            self.test_script_permissions,
            self.test_systemd_service_files,
            self.test_virtual_environment_setup,
            self.test_log_directory_creation,
            self.test_component_import,
            self.test_port_availability_check,
            self.test_environment_file_template,
            self.test_help_commands,
            self.test_bathymetry_file
        ]

        print("\n" + "=" * 60)
        print("AELMA Deployment Tests")
        print("=" * 60 + "\n")

        failed = []

        for test in tests:
            test_name = test.__name__
            print(f"\nRunning {test_name}...")
            try:
                test()
            except AssertionError as e:
                print(f"✗ {test_name} failed: {e}")
                failed.append((test_name, str(e)))
            except Exception as e:
                print(f"✗ {test_name} error: {e}")
                failed.append((test_name, str(e)))

        print("\n" + "=" * 60)
        if failed:
            print(f"FAILED: {len(failed)} tests failed")
            for test_name, error in failed:
                print(f"  - {test_name}: {error}")
            return False
        else:
            print("SUCCESS: All deployment tests passed!")
            return True


def main():
    """Main entry point."""
    tests = TestDeploymentScripts()
    success = tests.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
