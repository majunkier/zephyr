# Copyright (c) 2024 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
import fnmatch
from collections import defaultdict

import scl

logger = logging.getLogger('twister')


# Handles test scripting configurations.
class Scripting:
    def __init__(self, scripting_files: list[Path | str], scripting_schema: dict) -> None:
        self.scripting = ScriptingData()
        self.scripting_files = scripting_files or []
        self.scripting_schema = scripting_schema
        self.load_and_validate_files()

    def __post_init__(self):
        """Called after __init__, validate and deduplicate the scripting elements"""
        self.validate_and_deduplicate()
        self.print_scripting_elements()


    # def validate_and_deduplicate(self):
    #     """
    #     Validate and deduplicate the scripting elements.
    #     Rules:
    #     - For each (scenario, platform) key:
    #         - If one element → use it
    #         - If multiple:
    #             - If exactly one has override_script=True → use it
    #             - If none or more than one have override=True → error
    #     - At the end, include each element only once, even if it matched multiple keys.
    #     """
    #     key_to_elements = {}

    #     # Group elements by (scenario, platform) pairs
    #     for elem in self.scripting.elements:
    #         for scenario in elem.scenarios:
    #             for platform in elem.platforms:
    #                 key = (scenario, platform)
    #                 key_to_elements.setdefault(key, []).append(elem)

    #     selected_elements = set()  # store unique selected elements

    #     for key, elements in key_to_elements.items():
    #         logger.info(f"Processing {key}: {len(elements)} elements found")

    #         unique_elements = list(set(elements))  # de-duplicate same element appearing multiple times

    #         if len(unique_elements) == 1:
    #             selected_elements.add(unique_elements[0])
    #         else:
    #             override_elements = [e for e in unique_elements if self.has_override_script(e)]
    #             if len(override_elements) == 1:
    #                 selected_elements.add(override_elements[0])
    #                 self.update_element_with_preference(key, override_elements[0])
    #             elif len(override_elements) > 1:
    #                 logger.error(f"Error: More than one override script for {key}")
    #                 sys.exit(1)
    #             else:
    #                 logger.error(f"Error: No override script for {key}")
    #                 sys.exit(1)

    #     final_list = list(selected_elements)
    #     logger.info(f"Updating scripting elements with {len(final_list)} valid elements")
    #     self.scripting.elements = final_list


    def get_selected_script_path(self, scenario: str, platform: str, script_type: str = "pre_script") -> str | None:
        def matches_scenario(defined_scenario: str, input_scenario: str) -> bool:
            if defined_scenario.endswith(".*"):
                base = defined_scenario[:-2]
                return input_scenario == base or input_scenario.startswith(base + ".")
            return defined_scenario == input_scenario

        def get_script(elem):
            return getattr(elem, script_type, None)

        matching_elements = []
        for elem in self.scripting.elements:
            if platform not in elem.platforms:
                continue

            for defined_scenario in elem.scenarios:
                if matches_scenario(defined_scenario, scenario):
                    matching_elements.append(elem)
                    break  # Avoid duplicates if multiple scenarios match

        key = (scenario, platform)
        logger.info(f"Matching scripting elements for {key}: {len(matching_elements)} found")

        if not matching_elements:
            logger.warning(f"No scripting elements found for {key}")
            return None

        # Check for override script definitions and group by script_type
        override_elements = [
            elem for elem in matching_elements
            if get_script(elem) and get_script(elem).override_script
        ]

        if len(override_elements) > 1:
            logger.error(f"Multiple override {script_type} definitions found for {key}")
            # Log each element involved for debugging
            for elem in override_elements:
                logger.error(f"Override found in: {elem}")
            return None
        elif override_elements:
            selected_elem = override_elements[0]
        else:
            selected_elem = matching_elements[0]
            logger.warning(f"No override {script_type} for {key}, selecting first available")

        script = get_script(selected_elem)
        if not script:
            logger.warning(f"No {script_type} defined in selected element for {key}")
            return None

        logger.info(f"Selected {script_type} for {key}: {script.path}")
        return script.path



    def has_override_script(self, elem: ScriptingElement) -> bool:
        """Check if any of the scripts in the element have `override_script=True`"""
        return (
            (elem.pre_script and elem.pre_script.override_script) or
            (elem.post_flash_script and elem.post_flash_script.override_script) or
            (elem.post_script and elem.post_script.override_script)
        )

    def update_element_with_preference(self, key: tuple[str, str], selected_elem: ScriptingElement) -> None:
        """Log and update the element selection (can add more complex logic here)"""
        logger.info(f"Selected script for {key}: {selected_elem}")




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

    def print_scripting_elements(self):
        if not self.scripting.elements:
            logger.info("No scripting elements loaded.")
            return

        for i, elem in enumerate(self.scripting.elements, 1):
            logger.info(f"Scripting Element #{i}")
            logger.info(f"  Scenarios: {elem.scenarios}")
            logger.info(f"  Platforms: {elem.platforms}")
            if elem.pre_script:
                logger.info(f"  Pre-script: {elem.pre_script.path} (override: {elem.pre_script.override_script})")
            if elem.post_flash_script:
                logger.info(f"  Post-flash-script: {elem.post_flash_script.path} (override: {elem.post_flash_script.override_script})")
            if elem.post_script:
                logger.info(f"  Post-script: {elem.post_script.path} (override: {elem.post_script.override_script})")
            logger.info(f"  Comment: {elem.comment}")





@dataclass
class Script:
    path: str | None = None
    timeout: int | None = None

    def __eq__(self, other):
        if isinstance(other, Script):
            return (self.path == other.path and
                    self.timeout == other.timeout)
        return False

    def __hash__(self):
        return hash((self.path, self.timeout))

    def __repr__(self):
        return f"Script(path={self.path}, timeout={self.timeout})"


@dataclass
# Represents a single scripting element with associated scripts and metadata.
class ScriptingElement:
    scenarios: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    override_script: bool = False
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

    def __eq__(self, other):
        # Check equality based on the attributes that uniquely identify the element
        return (self.scenarios == other.scenarios and
                self.platforms == other.platforms and
                self.override_script == other.override_script and
                self.pre_script == other.pre_script and
                self.post_flash_script == other.post_flash_script and
                self.post_script == other.post_script and
                self.comment == other.comment)

    def __hash__(self):
        # Use the tuple of relevant attributes to create a hash
        return hash((
            tuple(self.scenarios),
            tuple(self.platforms),
            self.override_script,
            self.pre_script,
            self.post_flash_script,
            self.post_script,
            self.comment
        ))

    def __repr__(self):
        return f"ScriptingElement(scenarios={self.scenarios}, platforms={self.platforms}, override_script={self.override_script}, comment={self.comment})"

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
    def find_matching_scripting(self, scenario: str, platform: str) -> 'ScriptingElement | None':
        matched_elements = []

        for element in self.elements:
            scenario_match = _matches_element(scenario, element.scenarios) if element.scenarios else True
            platform_match = _matches_element(platform, element.platforms) if element.platforms else True

            if scenario_match and platform_match:
                matched_elements.append(element)

        override_scripts = get_override_scripts(matched_elements)

        if len(override_scripts) > 1:
            logger.error("Multiple override script definitions found for matching scenario/platform")
            sys.exit(1)
        elif len(override_scripts) == 1:
            logger.debug("Found override script match.")
            return override_scripts[0]
        elif matched_elements:
            logger.debug("Found regular match (no override).")
            return matched_elements[0]

        return None


# Checks if the given element matches any of the provided patterns.
def _matches_element(element: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(element, pattern) for pattern in patterns)

def get_override_scripts(elements):
    return [
        elem for elem in elements if (
            (elem.pre_script and elem.pre_script.override_script) or
            (elem.post_flash_script and elem.post_flash_script.override_script) or
            (elem.post_script and elem.post_script.override_script)
        )
    ]


