# test_error_identifier.py
import pytest
import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Set

# Import functions and config from the script to be tested
from error_identifier import (
    _load_data_from_csv,
    load_round1_data,
    load_round2_data_for_comparison,
    identify_error_teryts,
    save_error_teryts
)
import config as test_config # Use the main config for consistency in tests

# Override config for testing if necessary, or use test-specific CSVs
# For simplicity, we'll rely on creating test CSVs that match the main config's candidate names

def create_test_csv(tmp_path: Path, filename: str, headers: List[str], data_rows: List[List[str]]) -> Path:
    file_path = tmp_path / filename
    with open(file_path, 'w', newline='', encoding=test_config.CSV_ENCODING) as f:
        writer = csv.writer(f, delimiter=test_config.CSV_DELIMITER)
        writer.writerow(headers)
        writer.writerows(data_rows)
    return file_path

@pytest.fixture
def round1_headers() -> List[str]:
    return [test_config.TERYT_COLUMN_NAME] + test_config.R1_CANDIDATES_GROUP1 + test_config.R1_CANDIDATES_GROUP2

@pytest.fixture
def round2_headers() -> List[str]:
    return [test_config.TERYT_COLUMN_NAME, test_config.R2_COMPARISON_CANDIDATE1_NAME, test_config.R2_COMPARISON_CANDIDATE2_NAME]


# --- Tests for _load_data_from_csv (indirectly via specific loaders) ---
def test_load_round1_data_happy_path(tmp_path: Path, round1_headers: List[str]):
    # R1_CANDIDATES_GROUP1 = ["ZANDBERG", "TRZASKOWSKI_R1", "BIEJAT"] (assuming these are first 3 after TERYT)
    # R1_CANDIDATES_GROUP2 = ["BRAUN", "MENTZEN", "NAWROCKI_R1"] (assuming these are next 3)
    # For test_config:
    # test_config.R1_CANDIDATES_GROUP1[0] = "ZANDBERG Adrian Tadeusz"
    # test_config.R1_CANDIDATES_GROUP1[1] = "TRZASKOWSKI Rafał Kazimierz"
    # test_config.R1_CANDIDATES_GROUP1[2] = "BIEJAT Magdalena Agnieszka"
    # test_config.R1_CANDIDATES_GROUP2[2] = "NAWROCKI Karol Tadeusz"

    data_rows = [
        # TERYT, ZANDBERG, TRZASKOWSKI_R1, BIEJAT, BRAUN, MENTZEN, NAWROCKI_R1
        ["01",   "10",     "100",          "5",    "2",   "3",     "50"], # G1_sum=115, G2_sum=55
        ["02",   "20",     "200",          "10",   "4",   "6",     "100"],# G1_sum=230, G2_sum=110
    ]
    # Pad with zeros for other candidates if R1_CANDIDATES_GROUPx have more than 3 elements
    full_data_rows = []
    for row_base in data_rows:
        row = [row_base[0]] # TERYT
        row.extend(row_base[1:1+len(test_config.R1_CANDIDATES_GROUP1)]) # Group 1 votes
        # Pad if fewer votes provided than candidates in group 1
        row.extend(["0"] * (len(test_config.R1_CANDIDATES_GROUP1) - (len(row_base)-1-len(test_config.R1_CANDIDATES_GROUP2)))) 
        row.extend(row_base[1+len(test_config.R1_CANDIDATES_GROUP1):]) # Group 2 votes
        # Pad if fewer votes provided than candidates in group 2
        row.extend(["0"] * (len(test_config.R1_CANDIDATES_GROUP2) - (len(row_base)-1-len(test_config.R1_CANDIDATES_GROUP1))))
        full_data_rows.append(row)


    csv_file = create_test_csv(tmp_path, "r1_test.csv", round1_headers, data_rows) # Use original data_rows for this test
    
    result = load_round1_data(str(csv_file))
    assert result is not None
    assert len(result) == 2
    assert result["01"] == (10 + 100 + 5, 2 + 3 + 50) # (115, 55)
    assert result["02"] == (20 + 200 + 10, 4 + 6 + 100) # (230, 110)

def test_load_round2_data_happy_path(tmp_path: Path, round2_headers: List[str]):
    # test_config.R2_COMPARISON_CANDIDATE1_NAME = "TRZASKOWSKI Rafał Kazimierz"
    # test_config.R2_COMPARISON_CANDIDATE2_NAME = "NAWROCKI Karol Tadeusz"
    data_rows = [
        # TERYT, TRZASKOWSKI_R2, NAWROCKI_R2
        ["01",   "90",             "60"],
        ["02",   "180",            "120"],
    ]
    csv_file = create_test_csv(tmp_path, "r2_test.csv", round2_headers, data_rows)
    result = load_round2_data_for_comparison(str(csv_file))
    assert result is not None
    assert len(result) == 2
    assert result["01"] == (90, 60)
    assert result["02"] == (180, 120)

def test_load_data_missing_column(tmp_path: Path, caplog):
    bad_headers = [test_config.TERYT_COLUMN_NAME, "SomeOtherCandidate"] # Missing R1_CANDIDATES_GROUP1
    csv_file = create_test_csv(tmp_path, "bad_headers.csv", bad_headers, [["01", "100"]])
    
    result = load_round1_data(str(csv_file))
    assert result is None
    assert "missing required columns" in caplog.text.lower()

def test_load_data_value_error(tmp_path: Path, round1_headers: List[str], caplog):
    data_rows = [["01", "10", "ABC", "5", "2", "3", "50"]] # ABC is not int
    csv_file = create_test_csv(tmp_path, "value_error.csv", round1_headers, data_rows)
    
    result = load_round1_data(str(csv_file))
    assert result is not None
    assert "01" in result
    assert result["01"] == (0,0) # Defaulted to zeros due to parse error
    assert "data parsing error for teryt 01" in caplog.text.lower()
    assert "defaulting votes to zeros" in caplog.text.lower()

# --- Tests for identify_error_teryts ---
# R1_G1 = sum(Z, TR1, B), R2_C1 = TR2
# Error if:
# 1. R1_G1 < R2_C1
# 2. R2_C1 == 0 AND R1_G1 > 0
# 3. R2_C1 > 0 AND R1_G1 >= 2 * R2_C1

@pytest.mark.parametrize("dict1_val, dict2_val, expected_error", [
    # Case 1: R1_G1 < R2_C1 (Error)
    ((100, 50), (110, 40), True),  # 100 < 110
    # Case 2: R2_C1 == 0 AND R1_G1 > 0 (Error)
    ((10, 50), (0, 40), True),    # 0, 10 > 0
    # Case 3: R2_C1 > 0 AND R1_G1 >= 2 * R2_C1 (Error)
    ((100, 50), (50, 40), True),  # 100 >= 2*50 (100)
    ((100, 50), (40, 30), True),  # 100 >= 2*40 (80)
    # No Error cases
    ((100, 50), (90, 60), False), # R1_G1 > R2_C1, R1_G1 < 2*R2_C1 (100 < 180)
    ((100, 50), (60, 40), False), # R1_G1 > R2_C1, R1_G1 < 2*R2_C1 (100 < 120)
    ((0, 50), (0, 40), False),    # Both zero
    ((100, 0), (0, 0), True), # R2_C1 ==0, R1_G1 >0
])
def test_identify_error_teryts_logic(dict1_val: Tuple[int, int], dict2_val: Tuple[int, int], expected_error: bool):
    # Assuming R2_COMPARISON_CANDIDATE1_NAME is in R1_CANDIDATES_GROUP1 for valid logic
    assert test_config.R2_COMPARISON_CANDIDATE1_NAME in test_config.R1_CANDIDATES_GROUP1
    
    dict1 = {"T1": dict1_val}
    dict2 = {"T1": dict2_val}
    
    error_teryts = identify_error_teryts(dict1, dict2)
    if expected_error:
        assert "T1" in error_teryts
    else:
        assert "T1" not in error_teryts

def test_identify_error_teryts_multiple_entries(caplog):
    with caplog.at_level(logging.INFO):
        dict1 = {
            "E1": (90, 10),
            "OK1": (150, 20),
            "E2": (20, 30),
            "E3": (120, 40),
            "OK2": (0, 50),
            "M1": (100,10)    # TERYT only in dict1
        }
        dict2 = {
            "E1": (100, 5),
            "OK1": (100, 15),
            "E2": (0, 25),
            "E3": (60, 35),
            "OK2": (0, 45),
            "M2": (10,100)    # TERYT only in dict2
        }
        expected_errors = {"E1", "E2", "E3"}

        error_teryts = identify_error_teryts(dict1, dict2)
        assert error_teryts == expected_errors
        
        assert "from file1 (r1 data) not found in file2 (r2 data)" in caplog.text.lower()
        assert "teryt m1" in caplog.text.lower()


# --- Test for save_error_teryts ---
def test_save_error_teryts_output(tmp_path: Path):
    error_teryts: Set[str] = {"0101011", "0202032", "1465011"}
    output_file = tmp_path / "test_errors.txt"
    
    save_error_teryts(error_teryts, str(output_file))
    
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read().splitlines()
    
    assert sorted(list(error_teryts)) == sorted(content) # Compare sorted content

def test_save_error_teryts_empty_set(tmp_path: Path):
    error_teryts: Set[str] = set()
    output_file = tmp_path / "empty_errors.txt"
    save_error_teryts(error_teryts, str(output_file))
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content == ""