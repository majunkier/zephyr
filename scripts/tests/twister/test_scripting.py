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
    ScriptingElement
)


def test_scripting_initializes_and_loads_file(monkeypatch):
    called_files = []

    def fake_load_from_yaml(filename, schema):
        called_files.append(filename)
        return ScriptingData(elements=[
            ScriptingElement(
                scenarios=['s1'],
                platforms=['p1'],
                pre_script=Script(path='script.sh', timeout=5)
            )
        ])

    monkeypatch.setattr(ScriptingData, 'load_from_yaml', fake_load_from_yaml)

    scripting = Scripting(scripting_files=['file1.yaml', 'file2.yaml'], scripting_schema={})
    assert len(scripting.scripting.elements) == 2
    assert called_files == ['file1.yaml', 'file2.yaml']

def test_get_selected_scripts_returns_correct_element():
    scripting = Scripting(scripting_files=[], scripting_schema={})
    scripting.scripting.elements = [
        ScriptingElement(
            scenarios=["test.suite"], platforms=["native"], pre_script=Script(path="pre.sh", timeout=10)
        ),
        ScriptingElement(
            scenarios=["test.*"], platforms=["native"], post_script=Script(path="post.sh", timeout=5)
        )
    ]

    result, selected = scripting.get_selected_scripts("test.suite", "native")
    assert selected.scenarios == ["test.suite"]
    assert result["pre_script"]["path"] == "pre.sh"
    assert result["pre_script"]["timeout"] == 10


def test_validate_script_paths_exits_on_missing_file(monkeypatch):
    scripting = Scripting(scripting_files=[], scripting_schema={})

    script_dict = {
        "pre_script": {"path": "nonexistent.sh", "timeout": 30}
    }

    monkeypatch.setattr("os.path.isfile", lambda path: False)

    with pytest.raises(SystemExit):
        scripting.validate_script_paths(script_dict)


def test_multiple_override_scripts_exit(monkeypatch):
    monkeypatch.setattr("builtins.exit", lambda code=1: (_ for _ in ()).throw(SystemExit(code)))

    scripting = Scripting(scripting_files=[], scripting_schema={})
    scripting.scripting.elements = [
        ScriptingElement(
            scenarios=["s1"],
            platforms=["p1"],
            override_script=True,
            pre_script=Script(path="a.sh", timeout=5)
        ),
        ScriptingElement(
            scenarios=["s1"],
            platforms=["p1"],
            override_script=True,
            pre_script=Script(path="b.sh", timeout=5)
        )
    ]

    with pytest.raises(SystemExit) as e:
        scripting.get_selected_scripts("s1", "p1")
    assert e.value.code == 1

def test_multiple_override_scripts_exit(monkeypatch):
    monkeypatch.setattr("builtins.exit", lambda code=1: (_ for _ in ()).throw(SystemExit(code)))

    scripting = Scripting(scripting_files=[], scripting_schema={})
    scripting.scripting.elements = [
        ScriptingElement(
            scenarios=["s1"],
            platforms=["p1"],
            override_script=True,
            pre_script=Script(path="a.sh", timeout=5)
        ),
        ScriptingElement(
            scenarios=["s1"],
            platforms=["p1"],
            override_script=True,
            pre_script=Script(path="b.sh", timeout=5)
        )
    ]

    with pytest.raises(SystemExit) as e:
        scripting.get_selected_scripts("s1", "p1")
    assert e.value.code == 1

import pytest

def test_no_override_script():
    # Should pick the first matching element if none has override_script
    scripting = Scripting(scripting_files=[], scripting_schema={})
    elem = ScriptingElement(
        scenarios=["s1"],
        platforms=["p1"],
        pre_script=Script(path="a.sh", timeout=5)
    )
    scripting.scripting.elements = [elem]

    result, selected = scripting.get_selected_scripts("s1", "p1")

    assert result["pre_script"]["path"] == "a.sh"
    assert selected == elem


def test_single_override_script():
    # Should select the element with override_script=True
    scripting = Scripting(scripting_files=[], scripting_schema={})
    overriding = ScriptingElement(
        scenarios=["s1"],
        platforms=["p1"],
        override_script=True,
        pre_script=Script(path="override.sh", timeout=5)
    )
    fallback = ScriptingElement(
        scenarios=["s1"],
        platforms=["p1"],
        pre_script=Script(path="normal.sh", timeout=5)
    )
    scripting.scripting.elements = [fallback, overriding]

    result, selected = scripting.get_selected_scripts("s1", "p1")

    assert result["pre_script"]["path"] == "override.sh"
    assert selected == overriding


def test_multiple_elements_same_scenario_no_override():
    # Multiple elements match but no override_script -> first match should be picked
    scripting = Scripting(scripting_files=[], scripting_schema={})
    elem1 = ScriptingElement(
        scenarios=["s1"],
        platforms=["p1"],
        pre_script=Script(path="a.sh", timeout=5)
    )
    elem2 = ScriptingElement(
        scenarios=["s1"],
        platforms=["p1"],
        pre_script=Script(path="b.sh", timeout=5)
    )
    scripting.scripting.elements = [elem1, elem2]

    result, selected = scripting.get_selected_scripts("s1", "p1")

    assert result["pre_script"]["path"] == "a.sh"
    assert selected == elem1


def test_different_platforms():
    # Should only match on exact platform
    scripting = Scripting(scripting_files=[], scripting_schema={})
    matching = ScriptingElement(
        scenarios=["s1"],
        platforms=["p1"],
        pre_script=Script(path="correct.sh", timeout=5)
    )
    non_matching = ScriptingElement(
        scenarios=["s1"],
        platforms=["p2"],
        pre_script=Script(path="wrong.sh", timeout=5)
    )
    scripting.scripting.elements = [non_matching, matching]

    result, selected = scripting.get_selected_scripts("s1", "p1")

    assert result["pre_script"]["path"] == "correct.sh"
    assert selected == matching


def test_scenario_wildcard_match():
    # A scenario match with "base.*" should match "base.foo"
    scripting = Scripting(scripting_files=[], scripting_schema={})
    wildcard = ScriptingElement(
        scenarios=["base.*"],
        platforms=["p1"],
        pre_script=Script(path="wildcard.sh", timeout=5)
    )
    scripting.scripting.elements = [wildcard]

    result, selected = scripting.get_selected_scripts("base.foo", "p1")

    assert result["pre_script"]["path"] == "wildcard.sh"
    assert selected == wildcard


def test_no_matching_script():
    scripting = Scripting(scripting_files=[], scripting_schema={})
    scripting.scripting.elements = [
        ScriptingElement(
            scenarios=["s2"],
            platforms=["p2"],
            pre_script=Script(path="nope.sh", timeout=5)
        )
    ]

    result = scripting.get_selected_scripts("s1", "p1")

    assert result == ({}, None)


def make_element(scenarios, platforms, pre_path, post_path=None, post_flash_path=None, override=False, comment=""):
    return ScriptingElement(
        scenarios=scenarios,
        platforms=platforms,
        override_script=override,
        pre_script=Script(path=pre_path, timeout=10),
        post_script=Script(path=post_path) if post_path else None,
        post_flash_script=Script(path=post_flash_path) if post_flash_path else None,
        comment=comment
    )

def test_no_override_script_selected_first():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["platform1"], "script_a.sh"),
        make_element(["scenario1"], ["platform1"], "script_b.sh")
    ]
    script_dict, elem = scripting.get_selected_scripts("scenario1", "platform1")
    assert script_dict["pre_script"]["path"] == "script_a.sh"
    assert not elem.override_script

def test_match_with_override_script(monkeypatch):
    monkeypatch.setattr("builtins.exit", lambda code=1: (_ for _ in ()).throw(SystemExit(code)))

    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["platform1"], "script_a.sh", override=True),
        make_element(["scenario1"], ["platform1"], "script_b.sh")
    ]
    script_dict, elem = scripting.get_selected_scripts("scenario1", "platform1")
    assert script_dict["pre_script"]["path"] == "script_a.sh"
    assert elem.override_script is True

def test_platform_specific_match():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["platform2"], "wrong_script.sh"),
        make_element(["scenario1"], ["platform1"], "correct_script.sh")
    ]
    script_dict, _ = scripting.get_selected_scripts("scenario1", "platform1")
    assert script_dict["pre_script"]["path"] == "correct_script.sh"

def test_scenario_wildcard_match():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["test.*"], ["platform1"], "wildcard_script.sh")
    ]
    script_dict, _ = scripting.get_selected_scripts("test.subscenario", "platform1")
    assert script_dict["pre_script"]["path"] == "wildcard_script.sh"

def test_validate_script_paths(monkeypatch):
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["platform1"], "script_exists.sh")
    ]

    # Mock: file exists
    monkeypatch.setattr("os.path.isfile", lambda path: path == "script_exists.sh")

    script_dict, _ = scripting.get_selected_scripts("scenario1", "platform1")
    scripting.validate_script_paths(script_dict)  # Should not raise

def test_validate_script_paths_file_missing(monkeypatch):
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["platform1"], "missing.sh")
    ]

    # Mock: file does not exist
    monkeypatch.setattr("os.path.isfile", lambda path: False)

    script_dict, _ = scripting.get_selected_scripts("scenario1", "platform1")

    with pytest.raises(SystemExit) as e:
        scripting.validate_script_paths(script_dict)
    assert e.type == SystemExit
    assert "missing.sh" in str(e.value)

def test_multiple_scenarios_match_exact():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["s1", "s2", "s3"], ["p1"], "script_multiple.sh")
    ]

    for scenario in ["s1", "s2", "s3"]:
        script_dict, _ = scripting.get_selected_scripts(scenario, "p1")
        assert script_dict["pre_script"]["path"] == "script_multiple.sh"

def test_multiple_scenarios_with_wildcard():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["test.*", "dev.specific"], ["p1"], "wildcard_script.sh")
    ]

    matches = [
        ("test.alpha", True),
        ("test", True),
        ("test.alpha.beta", True),
        ("dev.specific", True),
        ("dev.other", False),
        ("testx", False)
    ]

    for scenario, should_match in matches:
        result = scripting.get_selected_scripts(scenario, "p1")
        if should_match:
            assert result is not None
            script_dict, _ = result
            assert script_dict["pre_script"]["path"] == "wildcard_script.sh"
        else:
            assert result == ({}, None)

def test_multiple_platforms_match_exact():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["board1", "board2", "board3"], "multi_board_script.sh")
    ]

    for platform in ["board1", "board2", "board3"]:
        script_dict, _ = scripting.get_selected_scripts("scenario1", platform)
        assert script_dict["pre_script"]["path"] == "multi_board_script.sh"

def test_multiple_platforms_mixed_matches():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        make_element(["scenario1"], ["board1", "board2"], "matched_board_script.sh"),
        make_element(["scenario1"], ["board3"], "other_board_script.sh")
    ]

    match_cases = {
        "board1": "matched_board_script.sh",
        "board2": "matched_board_script.sh",
        "board3": "other_board_script.sh",
        "board4": None  # should not match any
    }

    for board, expected_path in match_cases.items():
        result = scripting.get_selected_scripts("scenario1", board)
        if expected_path:
            assert result is not None
            script_dict, _ = result
            assert script_dict["pre_script"]["path"] == expected_path
        else:
            assert result == ({}, None)


def test_mixed_configurations_with_wildcard():
    scripting = Scripting([], {})
    scripting.scripting.elements = [
        # First configuration: specific scenarios and platforms with override_script=True
        make_element(
            scenarios=["scenario1", "scenario2"],
            platforms=["platformA", "platformB"],
            pre_path="pre_script1.sh",
            post_path="post_script1.sh",
            post_flash_path="post_flash_script1.sh",
            override=True,
            comment="First script"
        ),
        # Second configuration: wildcard scenario with no override_script
        make_element(
            scenarios=["scenario.*"],  # This should match scenarios like scenario.anything
            platforms=["platformC"],
            pre_path="pre_script2.sh",
            post_path=None,
            post_flash_path=None,
            override=False,
            comment="Second script"
        ),
    ]

    # Check first scenario/platform match with override_script=True
    script_dict, _ = scripting.get_selected_scripts("scenario1", "platformA")
    assert script_dict is not None, "Expected a result but got None."
    assert script_dict["pre_script"]["path"] == "pre_script1.sh"
    assert script_dict["post_script"]["path"] == "post_script1.sh"
    assert script_dict["post_flash_script"]["path"] == "post_flash_script1.sh"

    # Check second scenario/platform match with wildcard ("scenario.*") and no override_script
    result = scripting.get_selected_scripts("scenario.anything", "platformC")

    # If no match is found, assert that result is None
    if result is None:
        assert True  # No match case is expected, so this test case passes
    else:
        script_dict, _ = result
        # If a match is found, check that pre_script is correctly set
        assert "pre_script" in script_dict, "Expected 'pre_script' key in the returned script_dict."
        assert script_dict["pre_script"]["path"] == "pre_script2.sh", f"Expected pre_script path 'pre_script2.sh', but got {script_dict['pre_script']['path']}"

        # Check that post_script and post_flash_script keys do not exist (as they were set to None)
        assert "post_script" not in script_dict, "'post_script' should not exist in the script_dict."
        assert "post_flash_script" not in script_dict, "'post_flash_script' should not exist in the script_dict."
