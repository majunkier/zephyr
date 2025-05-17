# Copyright (c) 2024 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
import os

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



    def print_scripting_elements(self):
        logger.info("Printing scripting elements:")

        # Iterate over each scripting element
        for elem in self.scripting.elements:
            logger.info(f"Scenario(s): {elem.scenarios}")
            logger.info(f"Platform(s): {elem.platforms}")
            logger.info(f"Override Script: {elem.override_script}")

            # Print script details if they exist
            if elem.pre_script:
                logger.info(f"  Pre-script: {elem.pre_script.path}, Timeout: {elem.pre_script.timeout}")
            if elem.post_flash_script:
                logger.info(f"  Post-flash script: {elem.post_flash_script.path}, Timeout: {elem.post_flash_script.timeout}")
            if elem.post_script:
                logger.info(f"  Post-script: {elem.post_script.path}, Timeout: {elem.post_script.timeout}")

            logger.info("-" * 50)

    def check_for_conflicts(self, structured_data):
        wildcard_scripts = []
        exact_scripts = []

        # Step 1: Split scripts
        for entry in structured_data:
            scenarios = entry.get("scenario", [])
            if any("*" in s for s in scenarios):
                wildcard_scripts.append(entry)
            else:
                exact_scripts.append(entry)

        # Step 2: Compare wildcard to exact
        for wildcard_entry in wildcard_scripts:
            wildcard_scenarios = wildcard_entry["scenario"]
            wildcard_override = wildcard_entry.get("override_script", False)

            for wildcard_scenario in wildcard_scenarios:
                if "*" not in wildcard_scenario:
                    continue
                wildcard_prefix = wildcard_scenario.split("*")[0]

                # Step 3: Look for matching exact scripts
                for exact_entry in exact_scripts:
                    for exact_scenario in exact_entry["scenario"]:
                        if exact_scenario.startswith(wildcard_prefix):
                            exact_override = exact_entry.get("override_script", False)

                            # Step 4: Apply comparison rules
                            if wildcard_override and exact_override:
                                logger.error(f"Conflict: Both wildcard '{wildcard_scenario}' and exact '{exact_scenario}' have override_script=True")
                                sys.exit(1)
                            elif not wildcard_override and not exact_override:
                                logger.error(f"Conflict: Both wildcard '{wildcard_scenario}' and exact '{exact_scenario}' have override_script=False")
                                sys.exit(1)
                            elif wildcard_override and not exact_override:
                                logger.error(f"Conflict: wildcard '{wildcard_scenario}' override=True but exact '{exact_scenario}' override=False")
                                sys.exit(1)
                            # If wildcard=False and exact=True — OK, do nothing



        #  for entry in structured_data:

    def check_for_duplicates_and_conflicts(self, structured_data):
        self.check_for_conflicts(structured_data)
        """
        Check for conflicts and duplicates based on the following rules:
        1. If a scenario 'kernel.*' and a specific scenario (e.g., 'kernel.semaphore') exist for the same platform, raise an error.
        2. If 'kernel.*' is used but a specific scenario like 'kernel.semaphore' is missing for a platform, raise an error.
        3. If two identical entries exist with conflicting 'Override Script' values, raise an error.
        """
        scenario_platform_map = {}

        for entry in structured_data:
            scenario = entry["scenario"][0]  # First item in the list
            platform = entry["platform"][0]  # First item in the list
            override_script = entry["override_script"]
            key = (scenario, platform)

            # If a wildcard scenario exists, check for conflicts with specific scenarios
            if "*" in scenario:
                for s, p in scenario_platform_map.keys():
                    # Check if a specific scenario conflicts with the wildcard scenario
                    if s != scenario and scenario.endswith("*") and s.startswith(scenario[:-2]):
                        logger.error(f"Scenario wildcard conflict detected for Scenario: {scenario} on Platform: {platform}")
                        raise ValueError(f"Scenario wildcard conflict detected for Scenario: {scenario} on Platform: {platform}")
            else:
                if (scenario, platform) in scenario_platform_map:
                    # Check for conflicts based on 'Override Script' values
                    existing_entry = scenario_platform_map[(scenario, platform)]
                    if existing_entry["override_script"] != override_script:
                        logger.error(f"Conflict detected for Scenario: {scenario}, Platform: {platform} due to different 'Override Script' values.")
                        raise ValueError(f"Conflict detected for Scenario: {scenario}, Platform: {platform} due to different 'Override Script' values.")
                # Store this scenario-platform pair
                scenario_platform_map[(scenario, platform)] = entry

            # Check if any wildcard scenario matches a specific one but is not handled properly
            if scenario.endswith(".*"):
                base_scenario = scenario[:-2]  # Strip the wildcard part
                # Ensure all specific scenarios are used
                for other_scenario, _ in scenario_platform_map.keys():
                    if other_scenario.startswith(base_scenario) and other_scenario != scenario:
                        break
                else:
                    logger.error(f"Scenario '{base_scenario}' is missing in platform '{platform}' where wildcard is used.")
                    raise ValueError(f"Scenario '{base_scenario}' is missing in platform '{platform}' where wildcard is used.")

        # Check if we have duplicate 'Override Script: False' for the same scenario and platform
        for (scenario, platform), entry in scenario_platform_map.items():
            if entry["override_script"] == False:
                for other_scenario, other_platform in scenario_platform_map.keys():
                    if (scenario, platform) != (other_scenario, other_platform):
                        if entry["override_script"] == False:
                            logger.error(f"Duplicate entries with Override Script: False for Scenario: {scenario}, Platform: {platform}")
                            raise ValueError(f"Duplicate entries with Override Script: False for Scenario: {scenario}, Platform: {platform}")

        self.print_scripts_structure(scenario_platform_map)
        return scenario_platform_map


    def remove_duplicates_and_handle_overrides(self, structured_data):
        """
        Removes duplicates for scenario and platform based on the rule:
        - If there are multiple entries for the same scenario and platform,
        only the one with `Override Script: True` should remain.
        - If there are multiple entries with `Override Script: False`, it raises an error.
        - If there are multiple entries with `Override Script: True`, it raises an error.
        """
        seen = {}  # To track (scenario, platform) combinations
        final_data = []

        for entry in structured_data:
            scenario = entry["scenario"][0]  # Extract scenario (first item in the list)
            platform = entry["platform"][0]  # Extract platform (first item in the list)
            key = (scenario, platform)

            # Check if the combination is already seen
            if key in seen:
                # Case 1: Both entries have Override Script: False
                if not seen[key]["override_script"] and not entry["override_script"]:
                    logger.error(f"Duplicate entries with Override Script: False for Scenario: {scenario}, Platform: {platform}")
                    raise ValueError(f"Duplicate entries with Override Script: False for Scenario: {scenario}, Platform: {platform}")

                # Case 2: Both entries have Override Script: True
                if seen[key]["override_script"] and entry["override_script"]:
                    logger.error(f"Duplicate entries with Override Script: True for Scenario: {scenario}, Platform: {platform}")
                    raise ValueError(f"Duplicate entries with Override Script: True for Scenario: {scenario}, Platform: {platform}")

                # Case 3: If one entry has Override Script: False and the other has Override Script: True
                if not seen[key]["override_script"] and entry["override_script"]:
                    # Replace the entry with override script (keep the one with Override Script: True)
                    seen[key] = entry
            else:
                # If it's not seen, add it to the seen dictionary
                seen[key] = entry

        # Collect the final list based on the updated seen dictionary
        for entry in seen.values():
            final_data.append(entry)

        # Print the final data for debug/logging purposes
        self.print_scripts_structure(final_data)

        return final_data



    def print_scripts_structure(self, structured_data):
        """
        Prints the structured data in the desired format for logging.
        """
        for entry in structured_data:
            logger.info(f"Scenario(s): {entry['scenario']}")
            logger.info(f"Platform(s): {entry['platform']}")
            logger.info(f"Override Script: {entry['override_script']}")

            for script in entry['scripts']:
                logger.info(f"   {script['type']}: {script['path']}, Timeout: {script['timeout']}")

            logger.info("-" * 50)


    def get_split_scripts_structure(self):
        """
        Returns a structured list of dictionaries, each representing a unique
        combination of scenario and platform with its script details.
        """
        structured_data = []

        for elem in self.scripting.elements:
            # Iterate over each scenario for the element
            for scenario in elem.scenarios:
                # Iterate over each platform for the element
                for platform in elem.platforms:
                    # Prepare the structure for each combination
                    scenario_platform_data = {
                        "scenario": [scenario],
                        "platform": [platform],
                        "override_script": getattr(elem, "override_script", False),
                        "scripts": []
                    }

                    # Collect the scripts for the current scenario-platform combination
                    for script_type in ["pre_script", "post_flash_script", "post_script"]:
                        script = getattr(elem, script_type, None)
                        if script and getattr(script, "path", None):
                            scenario_platform_data["scripts"].append({
                                "type": script_type,
                                "path": script.path,
                                "timeout": script.timeout
                            })

                    # Add the current scenario-platform structure to the final list
                    structured_data.append(scenario_platform_data)

        # Return the structured data
        return structured_data


    def split_and_print_scripts(self):
        """
        Splits and prints the scripting information for each combination of scenario and platform.
        Each scenario-platform combination will be printed with its own set of script details.
        """
        for elem in self.scripting.elements:
            # Iterate over each scenario for the element
            for scenario in elem.scenarios:
                # Iterate over each platform for the element
                for platform in elem.platforms:
                    logger.info(f"Scenario(s): [{scenario}]")
                    logger.info(f"Platform(s): [{platform}]")
                    logger.info(f"Override Script: {getattr(elem, 'override_script', False)}")

                    # Print the scripts for the current scenario-platform combination
                    for script_type in ["pre_script", "post_flash_script", "post_script"]:
                        script = getattr(elem, script_type, None)
                        if script and getattr(script, "path", None):
                            logger.info(f"  {script_type.replace('_', ' ').capitalize()}: {script.path}, Timeout: {script.timeout}")

                    # Print a separator for clarity
                    logger.info("--------------------------------------------------")




    def get_scripts_per_platform(self) -> dict[str, dict[str, dict[str, str | int]]]:
        """
        Returns a dictionary of scripts per platform, checking for duplicates and structure.
        Prints the collected structure before returning it.

        Returns:
            A dictionary where the key is the platform name and the value is another dictionary
            containing script types and their paths with timeouts.
        """
        scripts_per_platform = {}

        # Loop through all scripting elements
        for elem in self.scripting.elements:
            for platform in elem.platforms:
                if platform not in scripts_per_platform:
                    scripts_per_platform[platform] = {}

                # For each script type, check if it exists and if it's a duplicate
                for script_type in ["pre_script", "post_flash_script", "post_script"]:
                    script = getattr(elem, script_type, None)

                    if script and getattr(script, "path", None):
                        script_key = f"{script_type}_{script.path}"

                        # Check for duplicates in the scripts
                        if script_key in scripts_per_platform[platform]:
                            logger.error(f"Duplicate script found for platform {platform} and script {script_type}: {script.path}")
                        else:
                            # Add the script to the platform structure
                            scripts_per_platform[platform][script_key] = {
                                "path": script.path,
                                "timeout": script.timeout
                            }

        # Print the collected scripts structure per platform
        logger.info("Collected scripts structure per platform:")
        for platform, scripts in scripts_per_platform.items():
            logger.info(f"Platform: {platform}")
            for script_key, script_data in scripts.items():
                logger.info(f"  {script_key}: {script_data}")

        return scripts_per_platform



    def get_selected_scripts(self, scenario: str, platform: str) -> tuple[dict, ScriptingElement] | None:
        def matches_scenario(defined_scenario: str, input_scenario: str) -> bool:
            if defined_scenario.endswith(".*"):
                base = defined_scenario[:-2]
                return input_scenario == base or input_scenario.startswith(base + ".")
            return defined_scenario == input_scenario

        matching_elements = []
        for elem in self.scripting.elements:
            if platform not in elem.platforms:
                continue
            for defined_scenario in elem.scenarios:
                if matches_scenario(defined_scenario, scenario):
                    matching_elements.append(elem)
                    break

        key = (scenario, platform)
        # logger.debug(f"Matching scripting elements for {key}: {len(matching_elements)} found")

        if not matching_elements:
            # logger.debug(f"No scripting elements found for {key}")
            return {}, None  # Return empty dict and None when no elements found

        override_elements = [e for e in matching_elements if e.override_script]
        if len(override_elements) > 1:
            logger.error(f"Multiple override_script definitions found for {key}")
            for elem in override_elements:
                logger.error(f"Override found in: {elem}")
            sys.exit(1)

        selected_elem = override_elements[0] if override_elements else matching_elements[0]

        result: dict[str] = {}
        for script_type in ["pre_script", "post_script", "post_flash_script"]:
            script = getattr(selected_elem, script_type, None)
            if script and getattr(script, "path", None):
                timeout = getattr(script, "timeout", None)
                result[script_type] = {
                    "path": script.path,
                    "timeout": timeout
                }
            else:
                logger.debug("")


        return result, selected_elem


    def validate_script_paths(self, script_dict: dict[str, dict[str, str | int]]) -> None:
        for script_type, data in script_dict.items():
            path = data.get("path")
            if not os.path.isfile(path):
                logger.error(f"{script_type} file does not exist at path: {path}")
                sys.exit(f"Error: {script_type} file not found at {path}")
            else:
                logger.debug(f"{script_type} file exists: {path}")

    def load_and_validate_files(self):
        for scripting_file in self.scripting_files:
            self.scripting.extend(
                ScriptingData.load_from_yaml(scripting_file, self.scripting_schema)
            )


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
