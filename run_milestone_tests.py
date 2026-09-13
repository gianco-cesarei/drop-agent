#!/usr/bin/env python3
"""
Test runner for Milestone 3 & Milestone 4.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tests.test_fingerprinting import TestFingerprinting
from tests.test_exporters import TestExporters
from tests.test_tracklist_extractor import TestTracklistExtractor
from tests.test_metadata_enricher import (
    TestDiscogsClient, TestBeatportClient, TestArtworkManager, TestMetadataEnricher
)
from tests.test_cloud_pipeline import (
    TestR2Uploader, TestSupabaseSyncClient
)
from tests.test_cli_integration import (
    TestDropAgentCLI
)

def run():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    classes = [
        TestFingerprinting,
        TestExporters,
        TestTracklistExtractor,
        TestDiscogsClient,
        TestBeatportClient,
        TestArtworkManager,
        TestMetadataEnricher,
        TestR2Uploader,
        TestSupabaseSyncClient,
        TestDropAgentCLI,
    ]
    
    for c in classes:
        suite.addTests(loader.loadTestsFromTestCase(c))

    print("\n" + "=" * 65)
    print(f" 🧪 DROP AGENT - RUNNING {suite.countTestCases()} TESTS (MILESTONES 1, 2, 3 & 4)")
    print("=" * 65)

    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    print(" 📊 EXECUTION METRICS:")
    print(f"    - Total Tests Run: {result.testsRun}")
    print(f"    - Failures: {len(result.failures)}")
    print(f"    - Errors: {len(result.errors)}")
    print(f"    - Status: {'PASSED (100%)' if result.wasSuccessful() else 'FAILED'}")
    print("=" * 65 + "\n")

    return result.wasSuccessful()

if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
