"""Unit tests for parsing assistant replies into add/remove (and related) action lists."""

from __future__ import annotations

import pytest

from blender_gpt.apply_actions import extract_actions_json


def test_add_parses_create_primitive():
    text = """Here is the plan.
{"actions":[{"op":"create_primitive","primitive":"CUBE","name":"MyCube","location":[1,2,3]}]}"""
    actions = extract_actions_json(text)
    assert len(actions) == 1
    assert actions[0]["op"] == "create_primitive"
    assert actions[0]["primitive"] == "CUBE"
    assert actions[0]["name"] == "MyCube"
    assert actions[0]["location"] == [1, 2, 3]


def test_remove_parses_delete_objects():
    text = """Removed as requested.
{"actions":[{"op":"delete_objects","names":["Cube","Light"]}]}"""
    actions = extract_actions_json(text)
    assert len(actions) == 1
    assert actions[0]["op"] == "delete_objects"
    assert actions[0]["names"] == ["Cube", "Light"]


def test_add_and_remove_in_one_reply():
    text = """
Analysis first.
{"actions":[
  {"op":"create_primitive","primitive":"SPHERE","name":"S","location":[0,0,0]},
  {"op":"delete_objects","names":["Cube"]}
]}"""
    actions = extract_actions_json(text)
    assert [a["op"] for a in actions] == ["create_primitive", "delete_objects"]


def test_describe_style_no_actions_empty_list():
    """Plain explanation with explicit empty actions (describe-only style)."""
    text = """The default cube is a mesh at the origin.
{"actions":[]}"""
    actions = extract_actions_json(text)
    assert actions == []


def test_describe_style_no_json_returns_empty():
    text = "The scene has a camera and a light. No edits needed."
    assert extract_actions_json(text) == []


def test_uses_last_actions_block():
    text = """Old
{"actions":[{"op":"delete_objects","names":["A"]}]}
New
{"actions":[{"op":"create_primitive","primitive":"PLANE","name":"P"}]}"""
    actions = extract_actions_json(text)
    assert len(actions) == 1
    assert actions[0]["op"] == "create_primitive"


def test_invalid_json_returns_empty():
    assert extract_actions_json('{"actions":[broken') == []


def test_skips_non_dict_entries():
    text = '{"actions":[{"op":"create_primitive","primitive":"CUBE"},"bad",{"op":"delete_objects","names":["X"]}]}'
    actions = extract_actions_json(text)
    assert len(actions) == 2
    assert actions[0]["op"] == "create_primitive"
    assert actions[1]["op"] == "delete_objects"


def test_boolean_and_groove_and_armature_parse():
    text = """Done.
{"actions":[
  {"op":"boolean_difference","target":"Body","cutter":"HoleTool","apply":true,"delete_cutter":true},
  {"op":"groove_box_cut","target":"Plate","center":[0,0,0],"groove_axis":"X","length":2,"width":0.02,"depth":0.05},
  {"op":"create_armature","name":"Rig","location":[0,0,1],"axis":"Z","bone_count":4,"segment_length":0.2}
]}"""
    actions = extract_actions_json(text)
    assert [a["op"] for a in actions] == [
        "boolean_difference",
        "groove_box_cut",
        "create_armature",
    ]
    assert actions[0]["cutter"] == "HoleTool"
    assert actions[1]["groove_axis"] == "X"
    assert actions[2]["bone_count"] == 4


def test_create_primitive_torus_monkey():
    text = '{"actions":[{"op":"create_primitive","primitive":"TORUS","name":"T"},{"op":"create_primitive","primitive":"MONKEY"}]}'
    actions = extract_actions_json(text)
    assert actions[0]["primitive"] == "TORUS"
    assert actions[1]["primitive"] == "MONKEY"


def test_3d_print_workflow_ops_parse():
    text = r"""Ready to slice.
{"actions":[
  {"op":"set_print_units"},
  {"op":"merge_by_distance","name":"Bracket","threshold":0.0002},
  {"op":"normals_make_consistent","name":"Bracket"},
  {"op":"origin_to_geometry","name":"Bracket"},
  {"op":"place_on_build_plate","name":"Bracket"},
  {"op":"apply_scale","names":["Bracket"]},
  {"op":"export_stl","name":"Bracket","filepath":"/tmp/bracket.stl"}
]}"""
    actions = extract_actions_json(text)
    assert [a["op"] for a in actions] == [
        "set_print_units",
        "merge_by_distance",
        "normals_make_consistent",
        "origin_to_geometry",
        "place_on_build_plate",
        "apply_scale",
        "export_stl",
    ]
    assert actions[-1]["filepath"] == "/tmp/bracket.stl"
