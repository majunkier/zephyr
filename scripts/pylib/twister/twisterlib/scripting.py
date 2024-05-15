# Copyright (c) 2024 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import scl

logger = logging.getLogger('twister')


# Handles test scripting configurations.
class Scripting:
    def __init__(self, scripting_files: list[Path | str], scripting_schema: dict) -> None:
        self.scripting = ScriptingData()
        self.scripting_files = scripting_files or []
        self.scripting_schema = scripting_schema
        self.load_and_validate_files()

    # Finds and returns the scripting element that matches the given test name and platform.
    def get_matched_scripting(self, testname: str, platform: str) -> ScriptingElement | None:
        matched_scripting = self.scripting.find_matching_scripting(testname, platform)
        if matched_scripting:
            logger.info(
                f"'{testname}' on '{platform}' device handler scripts '{str(matched_scripting)}'"
            )
            return matched_scripting
        return None

    def load_and_validate_files(self):
        for scripting_file in self.scripting_files:
            self.scripting.extend(
                ScriptingData.load_from_yaml(scripting_file, self.scripting_schema)
            )


@dataclass
class Script:
    path: str | None = None
    timeout: int | None = None
    override_script: bool = False


@dataclass
# Represents a single scripting element with associated scripts and metadata.
class ScriptingElement:
    scenarios: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    pre_script: Script | None = None
    post_flash_script: Script | None = None
    post_script: Script | None = None
    comment: str = 'NA'

    # Ensures all required scripts are present and validates the element.
    def __post_init__(self):
        if not any([self.pre_script, self.post_flash_script, self.post_script]):
            logger.error("At least one of the scripts must be specified")
            sys.exit(1)
        self.pre_script = self._convert_to_script(self.pre_script)
        self.post_flash_script = self._convert_to_script(self.post_flash_script)
        self.post_script = self._convert_to_script(self.post_script)

    # Converts a dictionary to a Script instance if necessary.
    def _convert_to_script(self, script: dict | Script | None) -> Script | None:
        if isinstance(script, dict):
            return Script(**script)
        return script


@dataclass
# Holds a collection of scripting elements.
class ScriptingData:
    elements: list[ScriptingElement] = field(default_factory=list)

    # Ensures all elements are ScriptingElement instances.
    def __post_init__(self):
        self.elements = [
            elem if isinstance(elem, ScriptingElement) else ScriptingElement(**elem)
            for elem in self.elements
        ]

    @classmethod
    # Loads scripting data from a YAML file.
    def load_from_yaml(cls, filename: Path | str, schema: dict) -> ScriptingData:
        try:
            raw_data = scl.yaml_load_verify(filename, schema) or []
            return cls(raw_data)
        except scl.EmptyYamlFileException:
            logger.error(f'Scripting file {filename} is empty')
            sys.exit(1)
        except FileNotFoundError:
            logger.error(f'Scripting file {filename} not found')
            sys.exit(1)
        except Exception as e:
            logger.error(f'Error loading {filename}: {e}')
            sys.exit(1)

    # Extends the current scripting data with another set of scripting data.
    def extend(self, other: ScriptingData) -> None:
        self.elements.extend(other.elements)

    # Finds a scripting element that matches the given scenario and platform.
    def find_matching_scripting(self, scenario: str, platform: str) -> ScriptingElement | None:
        matched_elements = []

        for element in self.elements:
            if element.scenarios and not _matches_element(scenario, element.scenarios):
                continue
            if element.platforms and not _matches_element(platform, element.platforms):
                continue
            matched_elements.append(element)

        # Check for override_script
        override_scripts = [
            elem
            for elem in matched_elements
            if (
                (elem.pre_script and elem.pre_script.override_script)
                or (elem.post_flash_script and elem.post_flash_script.override_script)
                or (elem.post_script and elem.post_script.override_script)
            )
        ]

        if len(override_scripts) > 1:
            logger.error("Multiple override definition for scripts found")
            sys.exit(1)
        elif len(override_scripts) == 1:
            return override_scripts[0]
        elif matched_elements:
            return matched_elements[0]

        return None


# Checks if the given element matches any of the provided patterns.
def _matches_element(element: str, patterns: list[str]) -> bool:
    return any(pattern == element for pattern in patterns)
