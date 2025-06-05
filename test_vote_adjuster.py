# test_vote_adjuster.py
import pytest
import csv
from pathlib import Path
from typing import Set, List, Dict # Added Dict for type hint consistency

# Import functions and classes from the script to be tested
from vote_adjuster import (
    calculate_adjusted_total_votes, 
    CalculationResult,
    load_teryts_from_file # Renamed from load_error_teryts_from_file
)
# Import config for consistent candidate names and file paths
import config as test_config


# Use candidate names from the config file for testing adjustments
# These are the candidates whose votes will be swapped in the R2 file
C1_ADJUST_NAME = test_config.ADJUST_CANDIDATE_1_NAME_IN_R2_FILE
C2_ADJUST_NAME = test_config.ADJUST_CANDIDATE_2_NAME_IN_R2_FILE
TEST_TERYT_COL_NAME = test_config.TERYT_COLUMN_NAME


def create_csv_file_for_adjuster(tmp_path: Path, filename: str, headers: List[str], data_rows: List[List[str]]) -> Path:
    """Creates a temporary CSV file for adjuster tests."""
    file_path = tmp_path / filename
    with open(file_path, 'w', newline='', encoding=test_config.CSV_ENCODING) as f:
        writer = csv.writer(f, delimiter=test_config.CSV_DELIMITER)
        writer.writerow(headers)
        writer.writerows(data_rows)
    return file_path

@pytest.fixture
def default_adjuster_csv_headers() -> List[str]:
    """Provides default headers for adjuster test CSV files."""
    return [TEST_TERYT_COL_NAME, "SomeOtherCol", C1_ADJUST_NAME, C2_ADJUST_NAME, "AnotherCol"]

# --- Tests for load_teryts_from_file ---
def test_load_teryts_from_file_success(tmp_path: Path):
    """Test successful loading of TERYTs from a file."""
    teryts_content = "000001\n000002\n000003\n"
    teryt_list_file = tmp_path / "teryts_for_action.txt"
    teryt_list_file.write_text(teryts_content, encoding='utf-8')
    
    loaded_teryts = load_teryts_from_file(str(teryt_list_file))
    assert loaded_teryts == {"000001", "000002", "000003"}

def test_load_teryts_from_file_not_found(tmp_path: Path, caplog):
    """Test handling when the TERYT list file is not found."""
    non_existent_file = tmp_path / "no_teryts_here.txt"
    with caplog.at_level(logging.WARNING):
        loaded_teryts = load_teryts_from_file(str(non_existent_file))
    assert loaded_teryts == set()
    assert f"teryt list file not found: {str(non_existent_file)}" in caplog.text.lower()

def test_load_teryts_from_file_empty(tmp_path: Path):
    """Test loading from an empty TERYT list file."""
    empty_teryt_file = tmp_path / "empty_teryts.txt"
    empty_teryt_file.write_text("", encoding='utf-8')
    loaded_teryts = load_teryts_from_file(str(empty_teryt_file))
    assert loaded_teryts == set()


# --- Tests for calculate_adjusted_total_votes (largely similar to previous versions) ---
def test_calculate_adjusted_total_votes_no_swaps(tmp_path: Path, default_adjuster_csv_headers: List[str]):
    """Test basic case with no TERYTs specified for swapping."""
    data_rows = [
        ["0101011", "code1", "100", "50", "abc"],
        ["0101022", "code2", "70", "80", "def"],
    ]
    csv_file = create_csv_file_for_adjuster(tmp_path, "adjust_test1.csv", default_adjuster_csv_headers, data_rows)
    
    teryts_for_action: Set[str] = set() # No TERYTs to swap
    result = calculate_adjusted_total_votes(str(csv_file), C1_ADJUST_NAME, C2_ADJUST_NAME, teryts_for_action)

    assert result is not None
    assert result.totals[C1_ADJUST_NAME] == 170
    assert result.totals[C2_ADJUST_NAME] == 130
    assert result.processed_rows == 2
    assert result.swapped_count == 0
    assert result.file_path == str(csv_file)

def test_calculate_adjusted_total_votes_with_swaps(tmp_path: Path, default_adjuster_csv_headers: List[str]):
    """Test case where votes are swapped for specified TERYTs."""
    data_rows = [
        ["0101011", "code1", "100", "50", "abc"], # This will be swapped
        ["0101022", "code2", "70", "80", "def"], # This not
        ["0101033", "code3", "20", "30", "ghi"], # This will be swapped
    ]
    csv_file = create_csv_file_for_adjuster(tmp_path, "adjust_test2.csv", default_adjuster_csv_headers, data_rows)
    
    teryts_for_action: Set[str] = {"0101011", "0101033"}
    result = calculate_adjusted_total_votes(str(csv_file), C1_ADJUST_NAME, C2_ADJUST_NAME, teryts_for_action)

    assert result is not None
    # Expected votes after swap:
    # C1: 50 (from 0101011) + 70 (from 0101022) + 30 (from 0101033) = 150
    # C2: 100 (from 0101011) + 80 (from 0101022) + 20 (from 0101033) = 200
    assert result.totals[C1_ADJUST_NAME] == 150
    assert result.totals[C2_ADJUST_NAME] == 200
    assert result.processed_rows == 3
    assert result.swapped_count == 2

def test_calculate_adjusted_total_votes_data_file_not_found(caplog):
    """Test handling if the main data CSV file is not found."""
    with caplog.at_level(logging.ERROR):
        result = calculate_adjusted_total_votes("non_existent_data.csv", C1_ADJUST_NAME, C2_ADJUST_NAME, set())
    assert result is None
    assert "file non_existent_data.csv not found" in caplog.text.lower()

def test_calculate_adjusted_total_votes_missing_adj_candidate_columns(tmp_path: Path, caplog):
    """Test handling if columns for candidates to be adjusted are missing."""
    headers = [TEST_TERYT_COL_NAME, "SomeOtherCol", "WrongCand1_NotInConfig", "WrongCand2_NotInConfig"]
    data_rows = [["0101011", "code1", "100", "50"]]
    csv_file = create_csv_file_for_adjuster(tmp_path, "adjust_test3.csv", headers, data_rows)

    with caplog.at_level(logging.ERROR):
        # C1_ADJUST_NAME and C2_ADJUST_NAME (from config) are expected but not in `headers`
        result = calculate_adjusted_total_votes(str(csv_file), C1_ADJUST_NAME, C2_ADJUST_NAME, set())
    assert result is None
    assert f"file {str(csv_file)} is missing required columns for adjustment" in caplog.text.lower()
    assert C1_ADJUST_NAME.lower() in caplog.text.lower() 
    assert C2_ADJUST_NAME.lower() in caplog.text.lower()

def test_calculate_adjusted_total_votes_missing_main_teryt_column(tmp_path: Path, caplog):
    """Test handling if the main TERYT column (from config) is missing in the data file."""
    headers = ["WrongTERYTColName", C1_ADJUST_NAME, C2_ADJUST_NAME]
    data_rows = [["0101011", "100", "50"]]
    csv_file = create_csv_file_for_adjuster(tmp_path, "adjust_test4.csv", headers, data_rows)

    with caplog.at_level(logging.ERROR):
        result = calculate_adjusted_total_votes(str(csv_file), C1_ADJUST_NAME, C2_ADJUST_NAME, set())
    assert result is None
    assert f"file {str(csv_file)} is missing required columns for adjustment" in caplog.text.lower()
    assert TEST_TERYT_COL_NAME.lower() in caplog.text.lower() # Checks if the expected TERYT column name is mentioned

def test_calculate_adjusted_total_votes_non_integer_votes_in_data(tmp_path: Path, default_adjuster_csv_headers: List[str], caplog):
    """Test handling of non-integer or negative vote counts in the data file."""
    data_rows = [
        ["0101011", "c1", "100", "abc", "text1"], # "abc" is non-integer -> row's votes for C1,C2 become 0,0
        ["0101022", "c2", "70", "80", "text2"],  # Valid
        ["0101033", "c3", "", "30", "text3"],    # Empty string for C1 -> C1 becomes 0
        ["0101044", "c4", "-5", "40", "text4"],  # Negative vote for C1 -> row's votes for C1,C2 become 0,0
    ]
    csv_file = create_csv_file_for_adjuster(tmp_path, "adjust_test5.csv", default_adjuster_csv_headers, data_rows)
    
    with caplog.at_level(logging.WARNING):
        result = calculate_adjusted_total_votes(str(csv_file), C1_ADJUST_NAME, C2_ADJUST_NAME, set())
    
    assert result is not None
    # Expected sums after handling invalid data:
    # C1: 0 (from 0101011 due to C2's "abc") + 70 (from 0101022) + 0 (from 0101033) + 0 (from 0101044 due to C1's -5) = 70
    # C2: 0 (from 0101011) + 80 (from 0101022) + 30 (from 0101033) + 0 (from 0101044) = 110
    assert result.totals[C1_ADJUST_NAME] == 70
    assert result.totals[C2_ADJUST_NAME] == 110
    assert result.processed_rows == 4
    assert result.swapped_count == 0
    assert "non-integer vote count for teryt 0101011" in caplog.text.lower()
    assert "negative vote count detected for teryt 0101044" in caplog.text.lower()

def test_calculation_result_str_representation(tmp_path: Path):
    """Test the __str__ method of CalculationResult for correct report format."""
    totals = {C1_ADJUST_NAME: 100, C2_ADJUST_NAME: 200}
    dummy_file_path = str(tmp_path / "dummy_data.csv")
    calc_res_with_swaps = CalculationResult(totals, 10, 2, dummy_file_path)
    calc_res_no_swaps = CalculationResult(totals, 5, 0, dummy_file_path)
    
    report_str_swaps = str(calc_res_with_swaps)
    assert dummy_file_path in report_str_swaps
    assert "Processed 10 rows" in report_str_swaps
    assert "Votes were swapped for 2 TERYT codes" in report_str_swaps
    assert f"{C1_ADJUST_NAME}: 100" in report_str_swaps
    assert f"{C2_ADJUST_NAME}: 200" in report_str_swaps

    report_str_no_swaps = str(calc_res_no_swaps)
    assert "No votes were swapped" in report_str_no_swaps