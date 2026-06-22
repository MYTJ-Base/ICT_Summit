import pytest
import src.kb.engine as kb_engine

def test_enforce_mastery_gates():
    # Level 0, 1: no gates
    assert kb_engine.enforce_mastery_gates(definition_c=None, target_status=1, connection_count=0) == 1
    assert kb_engine.enforce_mastery_gates(definition_c="", target_status=1, connection_count=0) == 1
    
    # Level 2: requires definition_c
    assert kb_engine.enforce_mastery_gates(definition_c="", target_status=2, connection_count=0) == 1
    assert kb_engine.enforce_mastery_gates(definition_c="My understanding", target_status=2, connection_count=0) == 2
    
    # Level 3: requires definition_c and >= 2 connections
    assert kb_engine.enforce_mastery_gates(definition_c="My understanding", target_status=3, connection_count=0) == 2
    assert kb_engine.enforce_mastery_gates(definition_c="My understanding", target_status=3, connection_count=1) == 2
    assert kb_engine.enforce_mastery_gates(definition_c="My understanding", target_status=3, connection_count=2) == 3
    
    # Level 4, 5: also bound by Level 3 constraints
    assert kb_engine.enforce_mastery_gates(definition_c="", target_status=5, connection_count=2) == 1
    assert kb_engine.enforce_mastery_gates(definition_c="My understanding", target_status=5, connection_count=1) == 2
    assert kb_engine.enforce_mastery_gates(definition_c="My understanding", target_status=5, connection_count=3) == 5
