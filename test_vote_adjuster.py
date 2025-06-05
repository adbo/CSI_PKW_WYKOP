# test_vote_adjuster.py
import pytest
import csv
from pathlib import Path
from typing import Set, Dict, List

# Import functions and classes from the script to be tested
from vote_adjuster import (
    calculate_adjusted_total_votes, 
    CalculationResult,
    load_error_teryts_from_file
)
# Import config for consistent candidate names and file paths
import config as test_config


# Use candidate names from the config file for testing
C1_TEST_NAME = test_config.ADJUST_CANDIDATE_1_NAME
C2_TEST_NAME = test_config.ADJUST_CANDIDATE_2_NAME
TEST_TERYT_COL = test_config.TERYT_COLUMN_NAME


def create_csv_file(tmp_path: Path, filename: str, headers: List[str], data_rows: List[List[str]]) -> Path:
    """Creates a temporary CSV file for tests."""
    file_path = tmp_path / filename
    with open(file_path, 'w', newline='', encoding=test_config.CSV_ENCODING) as f:
        writer = csv.writer(f, delimiter=test_config.CSV_DELIMITER)
        writer.writerow(headers)
        writer.writerows(data_rows)
    return file_path

@pytest.fixture
def default_adjuster_headers() -> List[str]:
    return [TEST_TERYT_COL, "SomeOtherCol", C1_TEST_NAME, C2_TEST_NAME, "AnotherCol"]

# --- Tests for load_error_teryts_from_file ---
def test_load_error_teryts_from_file_success(tmp_path: Path):
    teryts_content = "000001\n000002\n000003\n"
    error_file = tmp_path / "errors.txt"
    error_file.write_text(teryts_content, encoding='utf-8')
    
    loaded_teryts = load_error_teryts_from_file(str(error_file))
    assert loaded_teryts == {"000001", "000002", "000003"}

def test_load_error_teryts_from_file_not_found(tmp_path: Path, caplog):
    non_existent_file = tmp_path / "no_errors_here.txt"
    loaded_teryts = load_error_teryts_from_file(str(non_existent_file))
    assert loaded_teryts == set()
    assert f"Error TERYTs file not found: {str(non_existent_file)}" in caplog.text

def test_load_error_teryts_from_file_empty(tmp_path: Path):
    error_file = tmp_path / "empty_errors.txt"
    error_file.write_text("", encoding='utf-8')
    loaded_teryts = load_error_teryts_from_file(str(error_file))
    assert loaded_teryts == set()


# --- Tests for calculate_adjusted_total_votes (similar to before) ---
def test_calculate_adjusted_total_votes_happy_path_no_swaps(tmp_path: Path, default_adjuster_headers: List[str]):
    data_rows = [
        ["0101011", "code1", "100", "50", "abc"],
        ["0101022", "code2", "70", "80", "def"],
    ]
    csv_file = create_csv_file(tmp_path, "test1.csv", default_adjuster_headers, data_rows)
    
    error_teryts: Set[str] = set()
    result = calculate_adjusted_total_votes(str(csv_file), C1_TEST_NAME, C2_TEST_NAME, error_teryts)

    assert result is not None
    assert result.totals[C1_TEST_NAME] == 170
    assert result.totals[C2_TEST_NAME] == 130
    assert result.processed_rows == 2
    assert result.swapped_count == 0
    assert result.file_path == str(csv_file)

def test_calculate_adjusted_total_votes_with_swaps(tmp_path: Path, default_adjuster_headers: List[str]):
    data_rows = [
        ["0101011", "code1", "100", "50", "abc"], # This will be swapped
        ["0101022", "code2", "70", "80", "def"], # This not
        ["0101033", "code3", "20", "30", "ghi"], # This will be swapped
    ]
    csv_file = create_csv_file(tmp_path, "test2.csv", default_adjuster_headers, data_rows)
    
    error_teryts: Set[str] = {"0101011", "0101033"}
    result = calculate_adjusted_total_votes(str(csv_file), C1_TEST_NAME, C2_TEST_NAME, error_teryts)

    assert result is not None
    assert result.totals[C1_TEST_NAME] == (50 + 70 + 30) # 150
    assert result.totals[C2_TEST_NAME] == (100 + 80 + 20) # 200
    assert result.processed_rows == 3
    assert result.swapped_count == 2

def test_calculate_adjusted_total_votes_file_not_found(caplog):
    result = calculate_adjusted_total_votes("non_existent_file.csv", C1_TEST_NAME, C2_TEST_NAME, set())
    assert result is None
    assert "File non_existent_file.csv not found" in caplog.text

def test_calculate_adjusted_total_votes_missing_candidate_columns(tmp_path: Path, caplog):
    headers = [TEST_TERYT_COL, "SomeOtherCol", "WrongCand1", "WrongCand2"]
    data_rows = [["0101011", "code1", "100", "50"]]
    csv_file = create_csv_file(tmp_path, "test3.csv", headers, data_rows)

    result = calculate_adjusted_total_votes(str(csv_file), C1_TEST_NAME, C2_TEST_NAME, set())
    assert result is None
    assert f"File {str(csv_file)} is missing required columns" in caplog.text
    assert C1_TEST_NAME in caplog.text # Check that the expected (missing) candidate name is mentioned

def test_calculate_adjusted_total_votes_missing_teryt_column(tmp_path: Path, caplog):
    headers = ["WrongTERYTCol", C1_TEST_NAME, C2_TEST_NAME]
    data_rows = [["0101011", "100", "50"]]
    csv_file = create_csv_file(tmp_path, "test4.csv", headers, data_rows)

    result = calculate_adjusted_total_votes(str(csv_file), C1_TEST_NAME, C2_TEST_NAME, set())
    assert result is None
    assert f"File {str(csv_file)} is missing required columns" in caplog.text
    assert TEST_TERYT_COL in caplog.text

def test_calculate_adjusted_total_votes_non_integer_votes(tmp_path: Path, default_adjuster_headers: List[str], caplog):
    data_rows = [
        ["0101011", "c1", "100", "abc", "text1"], # C1="100", C2="abc" -> ValueError -> C1=0, C2=0 for this row
        ["0101022", "c2", "70", "80", "text2"],  # C1=70, C2=80
        ["0101033", "c3", "", "30", "text3"],    # C1="" -> C1=0, C2=30
    ]
    csv_file = create_csv_file(tmp_path, "test5.csv", default_adjuster_headers, data_rows)
    
    result = calculate_adjusted_total_votes(str(csv_file), C1_TEST_NAME, C2_TEST_NAME, set())
    
    assert result is not None
    # Updated expectations:
    # If a ValueError occurs for any candidate in a row, both are treated as 0 for that row.
    # C1_TEST_NAME: 0 (from 0101011 due to C2's "abc") + 70 (from 0101022) + 0 (from 0101033 as C1 was "") = 70
    # C2_TEST_NAME: 0 (from 0101011 due to C2's "abc") + 80 (from 0101022) + 30 (from 0101033) = 110
    assert result.totals[C1_TEST_NAME] == (0 + 70 + 0) # Oczekiwano 70  <--- ZMIANA
    assert result.totals[C2_TEST_NAME] == (0 + 80 + 30) # Oczekiwano 110 (bez zmian, było poprawne)
    assert result.processed_rows == 3
    assert result.swapped_count == 0
    assert "Non-integer vote count for TERYT 0101011" in caplog.text
    assert "treating as 0 for this row's candidates" in caplog.text.lower()

def test_calculation_result_str_method(tmp_path: Path):
    # Create a dummy CalculationResult
    totals = {C1_TEST_NAME: 100, C2_TEST_NAME: 200}
    dummy_path = str(tmp_path / "dummy.csv")
    calc_res = CalculationResult(totals, 10, 2, dummy_path)
    
    report_str = str(calc_res)
    assert dummy_path in report_str
    assert "Processed 10 rows" in report_str
    assert "swapped for 2 TERYT codes" in report_str
    assert f"{C1_TEST_NAME}: 100" in report_str
    assert f"{C2_TEST_NAME}: 200" in report_str