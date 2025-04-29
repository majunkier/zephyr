#!/usr/bin/env python3
# Copyright (c) 2024 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import mock_open, patch

import pytest
from twisterlib.scripting import (
    Script,
    Scripting,
    ScriptingData,
    ScriptingElement,
    _matches_element,
)


# Group related tests into a class for ScriptingElement
class TestScriptingElement:
    def test_initialization_with_properties(self):
        # Test initialization with all properties set
        element = ScriptingElement(
            scenarios=['scenario1', 'scenario2'],
            platforms=['platform1', 'platform2'],
            pre_script=Script(path='pre_script.sh', timeout=10),
            post_flash_script=Script(path='post_flash_script.sh', timeout=20),
            post_script=Script(path='post_script.sh'),  # No timeout specified
            override_script=True,
            comment='Test comment',
        )

        # Check if the properties are set correctly
        assert element.scenarios == ['scenario1', 'scenario2']
        assert element.platforms == ['platform1', 'platform2']
        assert element.pre_script.path == 'pre_script.sh'
        assert element.post_flash_script.path == 'post_flash_script.sh'
        assert element.post_script.path == 'post_script.sh'
        assert element.comment == 'Test comment'
        assert element.override_script is True
        assert element.pre_script.timeout == 10
        assert element.post_flash_script.timeout == 20
        assert element.post_script.timeout is None

    def test_initialization_with_no_properties(self):
        # Test initialization with no properties set, which should trigger an error
        with pytest.raises(SystemExit) as excinfo:
            ScriptingElement()
        # Check if the correct exit code is set in the SystemExit exception
        assert excinfo.value.code == 1

    def test_initialization_with_empty_properties(self):
        # Test initialization with empty properties, which should trigger an error
        with pytest.raises(SystemExit) as excinfo:
            ScriptingElement(
                scenarios=[],
                platforms=[],
                pre_script=None,
                post_flash_script=None,
                post_script=None,
                comment='',
            )
        # Check if the correct exit code is set in the SystemExit exception
        assert excinfo.value.code == 1


# Group related tests into a class for ScriptingData
class TestScriptingData:
    @pytest.fixture
    def mock_scripting_elements(self):
        return [
            ScriptingElement(
                scenarios=['scenario1'],
                platforms=['platform1'],
                pre_script=Script(path='pre_script1.sh'),
                post_flash_script=Script(path='post_flash_script1.sh'),
                post_script=Script(path='post_script1.sh'),
                comment='Test comment 1',
            ),
            ScriptingElement(
                scenarios=['scenario2'],
                platforms=['platform2'],
                pre_script=Script(path='pre_script2.sh'),
                post_flash_script=Script(path='post_flash_script2.sh'),
                post_script=Script(path='post_script2.sh'),
                comment='Test comment 2',
            ),
        ]

    def test_initialization_with_scripting_elements(self, mock_scripting_elements):
        # Initialize ScriptingData with the list of mock ScriptingElement instances
        scripting_data = ScriptingData(elements=mock_scripting_elements)
        # Check if the elements are stored correctly
        assert len(scripting_data.elements) == 2
        assert all(isinstance(elem, ScriptingElement) for elem in scripting_data.elements)

    def test_load_from_yaml(self):
        # Mock YAML content
        yaml_content = '''
        - scenarios: ['scenario1']
          platforms: ['platform1']
          pre_script:
            path: 'pre_script1.sh'
          post_flash_script:
            path: 'post_flash_script1.sh'
          post_script:
            path: 'post_script1.sh'
          comment: 'Test comment 1'
        - scenarios: ['scenario2']
          platforms: ['platform2']
          pre_script:
            path: 'pre_script2.sh'
          post_flash_script:
            path: 'post_flash_script2.sh'
          post_script:
            path: 'post_script2.sh'
          comment: 'Test comment 2'
        '''
        # Define the schema as provided
        mock_schema = {
            'type': 'seq',
            'matching': 'all',
            'sequence': [
                {
                    'type': 'map',
                    'required': True,
                    'matching': 'all',
                    'mapping': {
                        'scenarios': {
                            'type': 'seq',
                            'required': True,
                            'sequence': [{'type': 'str'}, {'unique': True}],
                        },
                        'platforms': {
                            'required': False,
                            'type': 'seq',
                            'sequence': [{'type': 'str'}, {'unique': True}],
                        },
                        'pre_script': {'type': 'str', 'required': False},
                        'post_flash_script': {'type': 'str', 'required': False},
                        'post_script': {'type': 'str', 'required': False},
                        'comment': {'type': 'str', 'required': True},
                    },
                }
            ],
        }
        # Use mock_open to simulate file reading
        with (
            patch('builtins.open', mock_open(read_data=yaml_content)),
            patch('scl.yaml_load_verify') as mock_yaml_load_verify,
        ):
            # Mock the yaml_load_verify function to return a list of dictionaries
            mock_yaml_load_verify.return_value = [
                {
                    'scenarios': ['scenario1'],
                    'platforms': ['platform1'],
                    'pre_script': {'path': 'pre_script1.sh'},
                    'post_flash_script': {'path': 'post_flash_script1.sh'},
                    'post_script': {'path': 'post_script1.sh'},
                    'comment': 'Test comment 1',
                },
                {
                    'scenarios': ['scenario2'],
                    'platforms': ['platform2'],
                    'pre_script': {'path': 'pre_script2.sh'},
                    'post_flash_script': {'path': 'post_flash_script2.sh'},
                    'post_script': {'path': 'post_script2.sh'},
                    'comment': 'Test comment 2',
                },
            ]
            # Load ScriptingData from a YAML file with the mock schema
            scripting_data = ScriptingData.load_from_yaml('dummy_file.yaml', mock_schema)
            # Check if the data was loaded correctly
            assert len(scripting_data.elements) == 2
            assert all(isinstance(elem, ScriptingElement) for elem in scripting_data.elements)


class TestMatchingFunctionality:
    @pytest.fixture
    def scripting_data_with_elements(self):
        return ScriptingData(
            elements=[
                ScriptingElement(
                    scenarios=['test_scenario1'],
                    platforms=['platform1'],
                    pre_script=Script(path='pre_script1.sh'),
                    comment='Match 1',
                ),
                ScriptingElement(
                    scenarios=['test_scenario2'],
                    platforms=['platform2'],
                    pre_script=Script(path='pre_script2.sh'),
                    comment='Match 2',
                ),
                ScriptingElement(
                    scenarios=['any_scenario'],
                    platforms=['platform3'],
                    pre_script=Script(path='pre_script3.sh'),
                    comment='Wildcard scenario',
                ),
                ScriptingElement(
                    scenarios=['test_scenario3'],
                    platforms=['any_platform'],
                    pre_script=Script(path='pre_script4.sh'),
                    comment='Wildcard platform',
                ),
            ]
        )

    def test_find_matching_scripting_exact_match(self, scripting_data_with_elements):
        """
        Test finding a matching scripting element for a given scenario and platform
        where there is an exact match (not a wildcard).
        """
        scenario = 'test_scenario1'
        platform = 'platform1'
        matched_element = scripting_data_with_elements.find_matching_scripting(scenario, platform)

        assert matched_element is not None, f"Expected a match for ({scenario}, {platform}) but got None."
        assert matched_element.scenarios == ['test_scenario1'], "Matched element scenarios don't match expected."
        assert platform in matched_element.platforms, f"Platform '{platform}' not found in matched element."
        assert matched_element.comment == 'Match 1', f"Expected comment 'Match 1', but got '{matched_element.comment}'."


    def test_find_matching_scripting_no_match(self, scripting_data_with_elements):
        # Test finding a matching scripting element
        # for a given scenario and platform that should not match
        matched_element = scripting_data_with_elements.find_matching_scripting(
            'nonexistent_test', 'platform1'
        )
        assert matched_element is None

    def test_find_matching_scripting_wildcard_scenario(self, scripting_data_with_elements):
        # Test finding a matching scripting element with a wildcard scenario
        matched_element = scripting_data_with_elements.find_matching_scripting(
            'any_scenario', 'platform3'
        )
        assert matched_element is not None
        assert matched_element.comment == 'Wildcard scenario'

    def test_find_matching_scripting_wildcard_platform(self, scripting_data_with_elements):
        # Test finding a matching scripting element with a wildcard platform
        matched_element = scripting_data_with_elements.find_matching_scripting(
            'test_scenario3', 'any_platform'
        )
        assert matched_element is not None
        assert matched_element.comment == 'Wildcard platform'


# Test function for the _matches_element helper function
@pytest.mark.parametrize(
    "element,patterns,expected",
    [
        ("test_scenario1", ["test_scenario1"], True),  # Exact match
        ("test_scenario1", ["test_scenario2"], False),  # No match
        ("test_scenario1", ["scenario1"], False),  # No partial match
        ("test_scenario1", ["test_"], False),  # No partial match
        ("test_scenario1", ["scenario1$"], False),  # No regex support
        ("test_scenario1", ["^scenario"], False),  # No regex support
        ("test_scenario1", ["test_scenario1"], True),  # Exact match
        ("test_scenario1", ["test_scenario", "scenario1"], False),  # No partial match
        ("test_scenario1", [], False),  # No patterns to match
    ],
)
def test_matches_element(element, patterns, expected):
    # Test if the element matches any of the provided regex patterns
    assert _matches_element(element, patterns) == expected


# Fixture to mock the load_from_yaml method
@pytest.fixture
def mock_scripting_data():
    elements = [
        ScriptingElement(
            scenarios=['test_scenario1'],
            platforms=['platform1'],
            pre_script=Script(path='pre_script1.sh'),
            comment='Match 1',
        ),
        ScriptingElement(
            scenarios=['test_scenario2'],
            platforms=['platform2'],
            pre_script=Script(path='pre_script2.sh'),
            comment='Match 2',
        ),
    ]
    return ScriptingData(elements=elements)


# Define the mock_load_from_yaml fixture
@pytest.fixture
def mock_load_from_yaml():
    with patch('twisterlib.scripting.ScriptingData.load_from_yaml') as mock_method:
        # Set the return_value of the mocked load_from_yaml method
        mock_method.return_value = ScriptingData(
            [
                ScriptingElement(
                    scenarios=['scenario1'],
                    platforms=['platform1'],
                    comment='Test comment 1',
                    pre_script='mock_pre_script_1.sh',  # Include a mock pre_script attribute
                ),
                ScriptingElement(
                    scenarios=['scenario2'],
                    platforms=['platform2'],
                    comment='Test comment 2',
                    pre_script='mock_pre_script_2.sh',  # Include a mock pre_script attribute
                ),
            ]
        )
        yield mock_method


def test_scripting_initialization(mock_load_from_yaml):
    # Initialize Scripting with a list of dummy file paths
    scripting = Scripting(scripting_files=['dummy_path1.yaml'], scripting_schema={})
    # Check if the scripting data was loaded correctly
    # The mock_load_from_yaml fixture should have been used to mock the load_from_yaml method
    assert len(scripting.scripting.elements) == 2


# Test function for getting matched scripting elements
def test_get_matched_scripting(mock_scripting_data):
    # Initialize Scripting without any scripting files
    scripting = Scripting(scripting_files=[], scripting_schema={})
    # Manually set the scripting data to the mock_scripting_data
    scripting.scripting = mock_scripting_data

    # Test get_matched_scripting with a test name and platform that should find a match
    matched_element = scripting.get_matched_scripting('test_scenario1', 'platform1')
    assert matched_element is not None
    assert matched_element.comment == 'Match 1'

    # Test get_matched_scripting with a test name and platform that should not find a match
    matched_element = scripting.get_matched_scripting('nonexistent_test', 'platform1')
    assert matched_element is None


@pytest.fixture
def scripting_data_instances():
    scripting_data1 = ScriptingData(
        elements=[
            ScriptingElement(
                scenarios=['scenario1'],
                platforms=['platform1'],
                pre_script=Script(path='pre_script1.sh'),
                comment='Data1 Match 1',
            ),
            ScriptingElement(
                scenarios=['scenario2'],
                platforms=['platform2'],
                pre_script=Script(path='pre_script2.sh'),
                comment='Data1 Match 2',
            ),
        ]
    )
    scripting_data2 = ScriptingData(
        elements=[
            ScriptingElement(
                scenarios=['scenario3'],
                platforms=['platform3'],
                pre_script=Script(path='pre_script3.sh'),
                comment='Data2 Match 1',
            ),
            ScriptingElement(
                scenarios=['scenario4'],
                platforms=['platform4'],
                pre_script=Script(path='pre_script4.sh'),
                comment='Data2 Match 2',
            ),
        ]
    )
    return scripting_data1, scripting_data2


def test_scripting_data_extension(scripting_data_instances):
    scripting_data1, scripting_data2 = scripting_data_instances
    # Extend the first ScriptingData instance with the second one
    scripting_data1.extend(scripting_data2)

    # Check if the elements are combined correctly
    assert len(scripting_data1.elements) == 4
    assert scripting_data1.elements[0].comment == 'Data1 Match 1'
    assert scripting_data1.elements[1].comment == 'Data1 Match 2'
    assert scripting_data1.elements[2].comment == 'Data2 Match 1'
    assert scripting_data1.elements[3].comment == 'Data2 Match 2'

    # Check if the elements are instances of ScriptingElement
    for element in scripting_data1.elements:
        assert isinstance(element, ScriptingElement)
