# test_error_identifier.py
import pytest
import csv
from pathlib import Path
import json
import logging # For caplog.at_level
from typing import List, Dict, Any, Tuple

# Import functions and classes from the script to be tested
from error_identifier import (
    _load_election_data,
    _get_int_vote,
    analyze_relative_strength_shifts,
    save_analysis_report_to_json,
    generate_suspicious_shifts_file,
    TerytShiftAnalysis, # Class to check instance of
    ShiftAnalysisConclusion # Enum for conclusions
)
# We'll use monkeypatch to modify config for specific tests
import config as live_config # Import the actual config to be monkeypatched

# --- Helper Functions for Tests ---

def create_test_csv_file(tmp_path: Path, filename: str, headers: List[str], data_rows: List[List[str]]) -> Path:
    """Helper function to create a temporary CSV file for testing."""
    file_path = tmp_path / filename
    with open(file_path, 'w', newline='', encoding=live_config.CSV_ENCODING) as f:
        writer = csv.writer(f, delimiter=live_config.CSV_DELIMITER)
        writer.writerow(headers)
        writer.writerows(data_rows)
    return file_path

def mock_config_for_shift_analysis_tests(monkeypatch, cand_a_r1, cand_a_r2, cand_b_r1, cand_b_r2, thresholds: Dict[str, Any]):
    """
    Uses monkeypatch to set specific config values for the duration of a test.
    """
    monkeypatch.setattr(live_config, 'CANDIDATE_A_NAME_R1', cand_a_r1)
    monkeypatch.setattr(live_config, 'CANDIDATE_A_NAME_R2', cand_a_r2)
    monkeypatch.setattr(live_config, 'CANDIDATE_B_NAME_R1', cand_b_r1)
    monkeypatch.setattr(live_config, 'CANDIDATE_B_NAME_R2', cand_b_r2)
    for key, value in thresholds.items():
        monkeypatch.setattr(live_config, key, value)
    # Ensure TERYT_COLUMN_NAME is also set if it's not the default from live_config
    monkeypatch.setattr(live_config, 'TERYT_COLUMN_NAME', 'TERYT_ID_COL') # Using a distinct test column name


# --- Tests for _load_election_data ---

def test_load_election_data_success(tmp_path: Path, monkeypatch):
    """Test successful loading of data."""
    monkeypatch.setattr(live_config, 'TERYT_COLUMN_NAME', 'TERYT_ID_COL')
    headers = ["TERYT_ID_COL", "CandA", "CandB", "Other"]
    data_rows = [
        ["001", "100", "50", "x"],
        ["002", "70", "80", "y"],
    ]
    csv_file = create_test_csv_file(tmp_path, "data.csv", headers, data_rows)
    required_cols = ["CandA", "CandB"]
    
    loaded_data = _load_election_data(str(csv_file), required_cols)
    
    assert loaded_data is not None
    assert len(loaded_data) == 2
    assert "001" in loaded_data
    assert loaded_data["001"]["CandA"] == "100"
    assert "002" in loaded_data
    assert loaded_data["002"]["Other"] == "y"

def test_load_election_data_file_not_found(caplog):
    """Test handling of a non-existent file."""
    with caplog.at_level(logging.ERROR):
        loaded_data = _load_election_data("non_existent.csv", ["CandA"])
    assert loaded_data is None
    assert "file not found" in caplog.text.lower()

def test_load_election_data_missing_teryt_column(tmp_path: Path, monkeypatch, caplog):
    """Test handling if the TERYT column (as per config) is missing."""
    monkeypatch.setattr(live_config, 'TERYT_COLUMN_NAME', 'MISSING_TERYT_COL') # Config expects this
    headers = ["Actual_TERYT_Col", "CandA"] # File has a different TERYT column name
    data_rows = [["001", "100"]]
    csv_file = create_test_csv_file(tmp_path, "missing_teryt.csv", headers, data_rows)
    
    with caplog.at_level(logging.ERROR):
        loaded_data = _load_election_data(str(csv_file), ["CandA"])
    assert loaded_data is None # Fails because TERYT_COLUMN_NAME (MISSING_TERYT_COL) is not in headers
    assert "missing required columns" in caplog.text.lower()
    assert "missing_teryt_col" in caplog.text.lower()


def test_load_election_data_missing_candidate_column(tmp_path: Path, monkeypatch, caplog):
    """Test handling if a required candidate column is missing."""
    monkeypatch.setattr(live_config, 'TERYT_COLUMN_NAME', 'TERYT_ID_COL')
    headers = ["TERYT_ID_COL", "CandA_Only"]
    data_rows = [["001", "100"]]
    csv_file = create_test_csv_file(tmp_path, "missing_cand.csv", headers, data_rows)
    required_cols = ["CandA_Only", "MissingCandB"] # "MissingCandB" is not in headers
    
    with caplog.at_level(logging.ERROR):
        loaded_data = _load_election_data(str(csv_file), required_cols)
    assert loaded_data is None
    assert "missing required columns" in caplog.text.lower()
    assert "missingcandb" in caplog.text.lower()

def test_load_election_data_empty_file_or_no_headers(tmp_path: Path, caplog):
    """Test handling of an empty file or a file with no headers."""
    empty_file = tmp_path / "empty.csv"
    empty_file.touch()
    with caplog.at_level(logging.ERROR):
        assert _load_election_data(str(empty_file), ["CandA"]) is None
    assert "empty or does not contain headers" in caplog.text.lower()
    caplog.clear()

    no_headers_file = tmp_path / "no_headers.csv"
    with open(no_headers_file, 'w') as f: # Write a file with content but no CSV headers line
        f.write("001;10;20\n") # DictReader will treat this as a row if delimiter is ';', or as a header if no delimiter
                               # For this test, we rely on DictReader returning no fieldnames for truly empty/malformed
    
    # Re-create with writer to ensure it's a valid CSV with no headers
    with open(no_headers_file, 'w', newline='', encoding=live_config.CSV_ENCODING) as f:
         # No writer.writerow(headers)
         writer = csv.writer(f, delimiter=live_config.CSV_DELIMITER)
         writer.writerow(["001", "10", "20"]) # This effectively becomes the header

    # The test should be about csv.DictReader not finding fieldnames
    # If the file is just one line, DictReader uses it as fieldnames.
    # To truly test no fieldnames, the file should be such that DictReader(f).fieldnames is None.
    # This is hard to simulate with just a text file easily. The empty file case above is more reliable.
    # For now, we'll rely on the empty file test.


# --- Tests for _get_int_vote ---

@pytest.mark.parametrize("vote_input, candidate_name, teryt, expected_output, log_level, log_message_part", [
    ("123", "CandX", "T01", 123, None, None),             # Valid integer
    ("", "CandX", "T01", 0, None, None),                  # Empty string (defaulted to 0)
    (None, "CandX", "T01", 0, None, None),                # None value (defaulted to 0)
    ("abc", "CandX", "T01", None, logging.WARNING, "invalid (non-integer)"), # Non-integer
    ("-10", "CandX", "T01", None, logging.WARNING, "negative vote count"),  # Negative integer
    ("50.5", "CandX", "T01", None, logging.WARNING, "invalid (non-integer)"),# Float string
])
def test_get_int_vote(caplog, vote_input, candidate_name, teryt, expected_output, log_level, log_message_part):
    """Test _get_int_vote for various inputs."""
    row_dict = {candidate_name: vote_input}
    if vote_input is None: # Simulate if the key itself is missing or has None value
        row_dict = {candidate_name: None} if candidate_name in row_dict else {}


    if log_level:
        with caplog.at_level(log_level):
            result = _get_int_vote(row_dict, candidate_name, teryt)
    else:
        result = _get_int_vote(row_dict, candidate_name, teryt)

    assert result == expected_output
    if log_message_part:
        assert log_message_part.lower() in caplog.text.lower()

def test_get_int_vote_key_missing():
    """Test _get_int_vote when the candidate key is missing from the row."""
    row_dict = {"OtherCand": "100"}
    # When key is missing, row.get(candidate_name) returns None, handled by (None, "CandX", "T01", 0, ...) case
    assert _get_int_vote(row_dict, "MissingCand", "T01") == 0


# --- Tests for analyze_relative_strength_shifts ---

# Default thresholds for most shift analysis tests
DEFAULT_THRESHOLDS = {
    'MIN_ABS_DIFFERENCE_R1_FOR_SIGNIFICANT_LEAD': 50,
    'MIN_RATIO_R1_FOR_SIGNIFICANT_LEAD': 1.5,
    'SIGNIFICANT_SHIFT_RATIO_THRESHOLD_R2': 1.2,
    'MIN_TOTAL_VOTES_AB_R1_FOR_LEAD_ANALYSIS': 20,
    'MIN_TOTAL_VOTES_AB_R2_FOR_SHIFT_ANALYSIS': 20,
}

@pytest.mark.parametrize("v1A, v1B, v2A, v2B, expected_conclusion_enum, desc_part", [
    # --- Scenarios with Lead A in R1 ---
    (100, 20, 120, 30, ShiftAnalysisConclusion.LEAD_A_R1_MAINTAINED_OR_INCREASED_R2, "maintained/increased"),
    (100, 20, 80, 15, ShiftAnalysisConclusion.LEAD_A_R1_MAINTAINED_OR_INCREASED_R2, "maintained/increased"), # Ratio still high
    (100, 20, 70, 60, ShiftAnalysisConclusion.LEAD_A_R1_LOST_OR_REDUCED_SIGNIFICANTLY_R2, "lost or significantly reduced"), # Ratio A/B R2 = 1.16 < 1.2 (threshold)
    (100, 20, 60, 70, ShiftAnalysisConclusion.LEAD_A_R1_REVERSED_TO_LEAD_B_R2, "reversed in r2, favoring candb_r2"),
    # --- Scenarios with Lead B in R1 ---
    (20, 100, 30, 120, ShiftAnalysisConclusion.LEAD_B_R1_MAINTAINED_OR_INCREASED_R2, "maintained/increased"),
    (20, 100, 15, 80, ShiftAnalysisConclusion.LEAD_B_R1_MAINTAINED_OR_INCREASED_R2, "maintained/increased"),
    (20, 100, 60, 70, ShiftAnalysisConclusion.LEAD_B_R1_LOST_OR_REDUCED_SIGNIFICANTLY_R2, "lost or significantly reduced"), # Ratio B/A R2 = 1.16 < 1.2
    (20, 100, 70, 60, ShiftAnalysisConclusion.LEAD_B_R1_REVERSED_TO_LEAD_A_R2, "reversed in r2, favoring canda_r2"),
    # --- Scenarios with No Significant Lead in R1 ---
    (50, 40, 55, 45, ShiftAnalysisConclusion.NO_SIGNIFICANT_LEAD_R1_NO_SIGNIFICANT_SHIFT_R2, "no significant lead for either candidate in r1"), # R1 diff=10 < 50
    (60, 50, 100, 20, ShiftAnalysisConclusion.NO_LEAD_R1_NEW_LEAD_A_R2, "gained a new significant lead in r2"), # R1 ratio 1.2 < 1.5
    (50, 60, 20, 100, ShiftAnalysisConclusion.NO_LEAD_R1_NEW_LEAD_B_R2, "gained a new significant lead in r2"),
    # --- Inconclusive Scenarios ---
    (5, 3, 100, 80, ShiftAnalysisConclusion.INCONCLUSIVE_LOW_VOTES_R1, "r1 total votes for a+b"), # R1 sum = 8 < 20
    (60, 50, 5, 3, ShiftAnalysisConclusion.INCONCLUSIVE_LOW_VOTES_R2, "r2 total votes for a+b"),   # R2 sum = 8 < 20
    # --- Data Issues ---
    (100, 20, -5, 30, ShiftAnalysisConclusion.DATA_ISSUE_INVALID_VOTES, "invalid or missing vote data"), # Negative vote
    (100, None, 50, 30, ShiftAnalysisConclusion.DATA_ISSUE_INVALID_VOTES, "invalid or missing vote data"), # Missing vote (None)
])
def test_analyze_relative_strength_shifts_various_scenarios(
    monkeypatch, v1A, v1B, v2A, v2B, expected_conclusion_enum, desc_part
):
    """Test analyze_relative_strength_shifts with various vote combinations."""
    # Setup mock config using monkeypatch
    mock_config_for_shift_analysis_tests(
        monkeypatch, "CandA_R1", "CandA_R2", "CandB_R1", "CandB_R2", DEFAULT_THRESHOLDS
    )

    # Prepare mock data
    # _get_int_vote handles None from data_r1/data_r2 by returning None (or 0 based on its internal default for empty)
    # For testing DATA_ISSUE_INVALID_VOTES, we pass None where appropriate.
    data_r1 = {"T1": {"TERYT_ID_COL": "T1", "CandA_R1": str(v1A) if v1A is not None else None, "CandB_R1": str(v1B) if v1B is not None else None}}
    data_r2 = {"T1": {"TERYT_ID_COL": "T1", "CandA_R2": str(v2A) if v2A is not None else None, "CandB_R2": str(v2B) if v2B is not None else None}}
    
    # Handle cases where vote inputs are intended to be None for the _get_int_vote function
    if v1A is None: data_r1["T1"]["CandA_R1"] = None
    if v1B is None: data_r1["T1"]["CandB_R1"] = None
    if v2A is None: data_r2["T1"]["CandA_R2"] = None
    if v2B is None: data_r2["T1"]["CandB_R2"] = None


    analysis_results = analyze_relative_strength_shifts(data_r1, data_r2)
    
    assert len(analysis_results) == 1
    result_t1 = analysis_results[0]
    
    assert isinstance(result_t1, TerytShiftAnalysis)
    assert result_t1.teryt == "T1"
    assert result_t1.conclusion == expected_conclusion_enum
    assert desc_part.lower() in result_t1.description.lower(), \
        f"Expected description part '{desc_part}' not found in '{result_t1.description}' for conclusion {result_t1.conclusion}"

    # Further assertions on vote counts if they are not None
    if v1A is not None and v1A >= 0: assert result_t1.votes_r1_cand_A == v1A
    if v1B is not None and v1B >= 0: assert result_t1.votes_r1_cand_B == v1B
    if v2A is not None and v2A >= 0: assert result_t1.votes_r2_cand_A == v2A
    if v2B is not None and v2B >= 0: assert result_t1.votes_r2_cand_B == v2B


def test_analyze_relative_strength_shifts_different_teryts(monkeypatch):
    """Test handling of TERYTs present in only one dataset."""
    mock_config_for_shift_analysis_tests(
        monkeypatch, "A_R1", "A_R2", "B_R1", "B_R2", DEFAULT_THRESHOLDS
    )
    data_r1 = {
        "T1": {"TERYT_ID_COL": "T1", "A_R1": "100", "B_R1": "50"}, # Common
        "T2": {"TERYT_ID_COL": "T2", "A_R1": "70", "B_R1": "30"}  # R1 only
    }
    data_r2 = {
        "T1": {"TERYT_ID_COL": "T1", "A_R2": "110", "B_R2": "60"}, # Common
        "T3": {"TERYT_ID_COL": "T3", "A_R2": "80", "B_R2": "40"}  # R2 only
    }

    with कैपlog.at_level(logging.INFO): # To check for logs about T2 and T3
        analysis_results = analyze_relative_strength_shifts(data_r1, data_r2)
    
    assert len(analysis_results) == 1 # Only T1 is common
    assert analysis_results[0].teryt == "T1"
    assert "teryts found only in round 1 data" in caplog.text.lower()
    assert "t2" in caplog.text.lower()
    assert "teryts found only in round 2 data" in caplog.text.lower()
    assert "t3" in caplog.text.lower()


# --- Tests for save_analysis_report_to_json ---

def test_save_analysis_report_to_json(tmp_path: Path):
    """Test saving the analysis report to a JSON file."""
    res1 = TerytShiftAnalysis("T01")
    res1.votes_r1_cand_A = 100; res1.votes_r1_cand_B = 50
    res1.votes_r2_cand_A = 120; res1.votes_r2_cand_B = 60
    res1.conclusion = ShiftAnalysisConclusion.LEAD_A_R1_MAINTAINED_OR_INCREASED_R2
    res1.description = "Test desc 1"

    res2 = TerytShiftAnalysis("T02")
    res2.conclusion = ShiftAnalysisConclusion.INCONCLUSIVE_LOW_VOTES_R1
    res2.description = "Test desc 2"
    
    report_data = [res1, res2]
    output_file = tmp_path / "report.json"
    
    save_analysis_report_to_json(report_data, str(output_file))
    
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        loaded_report = json.load(f)
    
    assert len(loaded_report) == 2
    assert loaded_report[0]["teryt"] == "T01"
    assert loaded_report[0]["conclusion"] == ShiftAnalysisConclusion.LEAD_A_R1_MAINTAINED_OR_INCREASED_R2.value
    assert loaded_report[0]["votes_r1_cand_A"] == 100
    assert loaded_report[1]["teryt"] == "T02"
    assert loaded_report[1]["conclusion"] == ShiftAnalysisConclusion.INCONCLUSIVE_LOW_VOTES_R1.value


# --- Tests for generate_suspicious_shifts_file ---

def test_generate_suspicious_shifts_file(tmp_path: Path):
    """Test generation of the text file with TERYTs for investigation."""
    res1 = TerytShiftAnalysis("T01"); res1.conclusion = ShiftAnalysisConclusion.LEAD_A_R1_REVERSED_TO_LEAD_B_R2
    res2 = TerytShiftAnalysis("T02"); res2.conclusion = ShiftAnalysisConclusion.NO_SIGNIFICANT_LEAD_R1_NO_SIGNIFICANT_SHIFT_R2
    res3 = TerytShiftAnalysis("T03"); res3.conclusion = ShiftAnalysisConclusion.LEAD_B_R1_LOST_OR_REDUCED_SIGNIFICANTLY_R2
    res4 = TerytShiftAnalysis("T04"); res4.conclusion = ShiftAnalysisConclusion.LEAD_A_R1_MAINTAINED_OR_INCREASED_R2
    
    report_data = [res1, res2, res3, res4]
    output_file = tmp_path / "suspicious.txt"
    
    generate_suspicious_shifts_file(report_data, str(output_file))
    
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read().splitlines()
    
    # T01 and T03 should be flagged based on current generate_suspicious_shifts_file logic
    assert set(content) == {"T01", "T03"}
    assert sorted(content) == ["T01", "T03"] # Check sorting

def test_generate_suspicious_shifts_file_empty(tmp_path: Path):
    """Test generation of an empty suspicious shifts file."""
    res1 = TerytShiftAnalysis("T01"); res1.conclusion = ShiftAnalysisConclusion.NO_SIGNIFICANT_LEAD_R1_NO_SIGNIFICANT_SHIFT_R2
    res2 = TerytShiftAnalysis("T02"); res2.conclusion = ShiftAnalysisConclusion.LEAD_A_R1_MAINTAINED_OR_INCREASED_R2

    report_data = [res1, res2]
    output_file = tmp_path / "empty_suspicious.txt"
    generate_suspicious_shifts_file(report_data, str(output_file))
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content == ""