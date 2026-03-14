"""JUnit XML Report Generator for test results."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from datetime import datetime


class JUnitTestCase:
    """Represents a single test case in JUnit format."""

    def __init__(
        self,
        name: str,
        classname: str = "TestCase",
        time: float = 0.0,
    ):
        self.name = name
        self.classname = classname
        self.time = time
        self.failure: Optional[tuple[str, str]] = None  # (message, traceback)
        self.skipped: Optional[str] = None  # skip reason
        self.error: Optional[tuple[str, str]] = None  # (message, traceback)

    def to_xml(self) -> ET.Element:
        """Convert to XML element."""
        tc = ET.Element("testcase")
        tc.set("name", self.name)
        tc.set("classname", self.classname)
        tc.set("time", f"{self.time:.6f}")

        if self.error:
            error = ET.SubElement(tc, "error")
            error.set("message", self.error[0])
            error.text = self.error[1]
        elif self.failure:
            failure = ET.SubElement(tc, "failure")
            failure.set("message", self.failure[0])
            failure.text = self.failure[1]
        elif self.skipped is not None:
            skipped = ET.SubElement(tc, "skipped")
            if self.skipped:
                skipped.set("message", self.skipped)

        return tc


class JUnitTestSuite:
    """Represents a test suite in JUnit format."""

    def __init__(self, name: str = "TestSuite"):
        self.name = name
        self.test_cases: list[JUnitTestCase] = []
        self.timestamp = datetime.now().isoformat()

    def add_testcase(self, testcase: JUnitTestCase) -> None:
        """Add a test case to the suite."""
        self.test_cases.append(testcase)

    def to_xml(self) -> ET.Element:
        """Convert to XML element."""
        suite = ET.Element("testsuite")
        suite.set("name", self.name)
        suite.set("tests", str(len(self.test_cases)))

        # Count failures, errors, and skipped
        failures = sum(1 for tc in self.test_cases if tc.failure)
        errors = sum(1 for tc in self.test_cases if tc.error)
        skipped = sum(1 for tc in self.test_cases if tc.skipped is not None)

        suite.set("failures", str(failures))
        suite.set("errors", str(errors))
        suite.set("skipped", str(skipped))

        # Calculate total time
        total_time = sum(tc.time for tc in self.test_cases)
        suite.set("time", f"{total_time:.6f}")
        suite.set("timestamp", self.timestamp)

        # Add test cases
        for testcase in self.test_cases:
            suite.append(testcase.to_xml())

        return suite


class JUnitReport:
    """Generates JUnit XML report."""

    def __init__(self):
        self.test_suites: list[JUnitTestSuite] = []

    def add_testsuite(self, suite: JUnitTestSuite) -> None:
        """Add a test suite to the report."""
        self.test_suites.append(suite)

    def to_xml_string(self) -> str:
        """Generate XML string."""
        root = ET.Element("testsuites")

        # Calculate totals
        total_tests = sum(len(suite.test_cases) for suite in self.test_suites)
        total_failures = sum(sum(1 for tc in suite.test_cases if tc.failure) for suite in self.test_suites)
        total_errors = sum(sum(1 for tc in suite.test_cases if tc.error) for suite in self.test_suites)
        total_skipped = sum(sum(1 for tc in suite.test_cases if tc.skipped is not None) for suite in self.test_suites)
        total_time = sum(sum(tc.time for tc in suite.test_cases) for suite in self.test_suites)

        root.set("tests", str(total_tests))
        root.set("failures", str(total_failures))
        root.set("errors", str(total_errors))
        root.set("skipped", str(total_skipped))
        root.set("time", f"{total_time:.6f}")

        # Add all suites
        for suite in self.test_suites:
            root.append(suite.to_xml())

        # Format XML with proper indentation
        self._indent_element(root)
        xml_str = ET.tostring(root, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'

    @staticmethod
    def _indent_element(elem, level=0):
        """Add pretty-print indentation to XML elements."""
        indent = "\n" + ("  " * level)
        child_indent = "\n" + ("  " * (level + 1))

        # Process children
        if len(elem):
            # Add newline and indentation before first child
            if not elem.text or not elem.text.strip():
                elem.text = child_indent

            # Add newline and indentation after last child
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent

            # Process each child
            for i, child in enumerate(elem):
                JUnitReport._indent_element(child, level + 1)

                # Set proper tail (whitespace after closing tag)
                if i < len(elem) - 1:
                    # Not the last child
                    child.tail = child_indent
                else:
                    # Last child
                    child.tail = indent
        else:
            # Leaf element
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def write_to_file(self, filepath: str | Path) -> None:
        """Write XML report to file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(self.to_xml_string(), encoding="utf-8")
