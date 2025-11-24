#!/usr/bin/env python3
"""
Test runner script for LoLalytics-Helper
Provides convenient commands for running different test suites.
"""

import sys
import subprocess
from pathlib import Path


def run_all_tests():
    """Run all tests with coverage report."""
    print("Running all tests with coverage...")
    cmd = [
        sys.executable, "-m", "pytest",
        "test_suite.py",
        "--cov=lobby_manager",
        "--cov-report=term-missing",
        "--cov-report=html",
        "-v"
    ]
    return subprocess.call(cmd)


def run_unit_tests():
    """Run only unit tests."""
    print("Running unit tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "test_suite.py",
        "-m", "unit",
        "-v"
    ]
    return subprocess.call(cmd)


def run_integration_tests():
    """Run only integration tests."""
    print("Running integration tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "test_suite.py",
        "-m", "integration",
        "-v"
    ]
    return subprocess.call(cmd)


def run_lcu_tests():
    """Run LCU-related tests."""
    print("Running LCU tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "test_suite.py",
        "-k", "lcu or snapshot or lane",
        "-v"
    ]
    return subprocess.call(cmd)


def run_quick_tests():
    """Run tests quickly without coverage."""
    print("Running quick tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "test_suite.py",
        "-x",  # Stop on first failure
        "--tb=short",
        "-v"
    ]
    return subprocess.call(cmd)


def run_with_replay():
    """Run tests and then replay test with actual snapshots."""
    print("Running tests and snapshot replay...")
    # First run the test suite
    result = run_all_tests()
    
    if result == 0:
        print("\n" + "="*60)
        print("All tests passed! Now running snapshot replay...")
        print("="*60 + "\n")
        
        # Run the existing test_lcu_logic.py
        cmd = [sys.executable, "test_lcu_logic.py"]
        return subprocess.call(cmd)
    else:
        print("\nTests failed. Skipping snapshot replay.")
        return result


def print_usage():
    """Print usage information."""
    print("""
LoLalytics-Helper Test Runner

Usage: python run_tests.py [command]

Commands:
    all         Run all tests with coverage (default)
    unit        Run only unit tests
    integration Run only integration tests
    lcu         Run LCU-related tests
    quick       Run tests quickly (stop on first failure)
    replay      Run tests then replay snapshots
    help        Show this help message

Examples:
    python run_tests.py
    python run_tests.py all
    python run_tests.py quick
    python run_tests.py lcu
    """)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
    else:
        command = "all"
    
    commands = {
        "all": run_all_tests,
        "unit": run_unit_tests,
        "integration": run_integration_tests,
        "lcu": run_lcu_tests,
        "quick": run_quick_tests,
        "replay": run_with_replay,
        "help": print_usage,
        "-h": print_usage,
        "--help": print_usage,
    }
    
    if command in commands:
        if command in ["help", "-h", "--help"]:
            commands[command]()
            return 0
        else:
            return commands[command]()
    else:
        print(f"Unknown command: {command}")
        print_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())
