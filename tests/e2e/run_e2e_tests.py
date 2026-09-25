#!/usr/bin/env python3
"""
Master E2E Test Runner for Observatorio LATAM.
Executes all opaque-box tests across Tiers 1-4:
- Tier 1: Feature Coverage (ETL files, Server endpoints, Web portal)
- Tier 2: Boundary & Corner Cases (Malformed requests, Out-of-catalog refusal, SI.POV.NAHC exclusion, Lag warnings)
- Tier 3: Cross-Feature Combinations (Comparator URLs, Scrollytelling parameters, Inline chart URLs, Composite Index)
- Tier 4: Real-World Scenarios (Costa Rica decoupling, Chile/Colombia inequality, Brasil scale impact)

Zero external dependencies — uses Python standard library unittest.
Returns exit code 0 on complete pass, 1 on any failure.
"""

from __future__ import annotations
import os
from pathlib import Path
import sys
import time
import unittest

# Ensure workspace root and tests are in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from tests.e2e.server_manager import get_shared_server, shutdown_shared_server
from tests.e2e.test_tier1_features import TestTier1Features
from tests.e2e.test_tier2_boundaries import TestTier2Boundaries
from tests.e2e.test_tier3_combinations import TestTier3Combinations
from tests.e2e.test_tier4_scenarios import TestTier4Scenarios


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def run_e2e_suite() -> int:
    """Executes all E2E test tiers and prints a comprehensive audit report."""
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 78}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}       OBSERVATORIO LATAM — END-TO-END VERIFICATION SUITE       {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}          Opaque-Box Multi-Tier Test Runner (ADR-001/002/003)         {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 78}{Color.RESET}\n")

    # Start test server
    print(f"{Color.DIM}[SETUP] Initializing background runtime server...{Color.RESET}")
    server = get_shared_server()
    print(f"{Color.GREEN}[OK]{Color.RESET} Server running on {server.base_url} (HTTP 200 ready)\n")

    tier_classes = [
        ("Tier 1: Feature Coverage (ETL, Server, Portal)", TestTier1Features),
        ("Tier 2: Boundary & Corner Cases (Refusals, SI.POV.NAHC, Lag)", TestTier2Boundaries),
        ("Tier 3: Cross-Feature Combinations (URLs, Stories, Composite)", TestTier3Combinations),
        ("Tier 4: Real-World Scenarios (Decoupling, Inequality, Brasil)", TestTier4Scenarios),
    ]

    tier_results = []
    total_all_tests = 0
    total_all_passed = 0
    total_all_failed = 0
    total_all_errors = 0
    start_time_all = time.time()

    for tier_label, test_cls in tier_classes:
        print(f"{Color.BOLD}>>> Running {tier_label}{Color.RESET}")
        print("-" * 78)

        if hasattr(test_cls, "setUpClass"):
            try:
                test_cls.setUpClass()
            except Exception as e:
                print(f"{Color.RED}        ERROR in {test_cls.__name__}.setUpClass(): {e}{Color.RESET}")

        suite = unittest.TestLoader().loadTestsFromTestCase(test_cls)
        suite_tests = list(suite)
        tier_passed = 0
        tier_failed = 0
        tier_errors = 0

        for test in suite_tests:
            test_name = test._testMethodName
            test_doc = (test._testMethodDoc or "").strip().split("\n")[0]
            display_name = f"{test_name}: {test_doc}" if test_doc else test_name

            # Run single test
            result = unittest.TestResult()
            t0 = time.time()
            test.run(result)
            duration = time.time() - t0

            if result.wasSuccessful():
                tier_passed += 1
                status_str = f"{Color.GREEN}[PASS]{Color.RESET}"
            elif result.failures:
                tier_failed += 1
                status_str = f"{Color.RED}[FAIL]{Color.RESET}"
            else:
                tier_errors += 1
                status_str = f"{Color.RED}[ERR]{Color.RESET}"

            print(f"  {status_str} {display_name} {Color.DIM}({duration:.3f}s){Color.RESET}")

            # Print error detail if any
            for _, err in result.failures:
                print(f"{Color.RED}        FAILURE: {err.strip()}{Color.RESET}")
            for _, err in result.errors:
                print(f"{Color.RED}        ERROR: {err.strip()}{Color.RESET}")

        if hasattr(test_cls, "tearDownClass"):
            try:
                test_cls.tearDownClass()
            except Exception:
                pass

        total_tier = len(suite_tests)
        total_all_tests += total_tier
        total_all_passed += tier_passed
        total_all_failed += tier_failed
        total_all_errors += tier_errors

        tier_status = "PASSED" if (tier_failed == 0 and tier_errors == 0) else "FAILED"
        tier_results.append((tier_label, total_tier, tier_passed, tier_failed + tier_errors, tier_status))
        print(f"{Color.DIM}  Tier Summary: {tier_passed}/{total_tier} passed.\n{Color.RESET}")

    total_duration = time.time() - start_time_all

    # Tear down server
    print(f"{Color.DIM}[TEARDOWN] Shutting down test server...{Color.RESET}")
    shutdown_shared_server()
    print(f"{Color.GREEN}[OK]{Color.RESET} Server stopped cleanly.\n")

    # Final summary table
    print(f"{Color.BOLD}{'=' * 78}{Color.RESET}")
    print(f"{Color.BOLD}{'TIER':<48} | {'TESTS':<6} | {'PASS':<5} | {'FAIL':<5} | {'STATUS':<7}{Color.RESET}")
    print(f"{'-' * 78}")
    for label, count, p, f, st in tier_results:
        st_color = Color.GREEN if st == "PASSED" else Color.RED
        print(f"{label:<48} | {count:<6} | {p:<5} | {f:<5} | {st_color}{st:<7}{Color.RESET}")
    print(f"{'-' * 78}")
    overall_color = Color.GREEN if (total_all_failed == 0 and total_all_errors == 0) else Color.RED
    overall_status = "ALL TESTS PASSED" if (total_all_failed == 0 and total_all_errors == 0) else "FAILURES DETECTED"
    print(f"{Color.BOLD}{'TOTAL':<48} | {total_all_tests:<6} | {total_all_passed:<5} | {total_all_failed + total_all_errors:<5} | {overall_color}{overall_status}{Color.RESET}")
    print(f"Total Execution Time: {total_duration:.2f}s")
    print(f"{Color.BOLD}{'=' * 78}{Color.RESET}\n")

    if total_all_failed > 0 or total_all_errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_e2e_suite())
