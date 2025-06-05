# vote_adjuster.py
import csv
import logging
from typing import Dict, Set, Optional, Tuple

# Import configurations
import config

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CalculationResult:
    """Holds the results of the vote calculation and adjustment."""
    def __init__(self, totals: Dict[str, int], processed_rows: int, swapped_count: int, file_path: str):
        self.totals = totals
        self.processed_rows = processed_rows
        self.swapped_count = swapped_count
        self.file_path = file_path # Store the path of the processed file for clarity

    def __str__(self) -> str:
        report = [
            f"--- Vote Adjustment Report for: {self.file_path} ---",
            f"Processed {self.processed_rows} rows.",
            f"Votes were swapped for {self.swapped_count} TERYT codes."
            "--- Adjusted Total Votes ---"
        ]
        for candidate, total_votes in self.totals.items():
            report.append(f"{candidate}: {total_votes}")
        return "\n".join(report)


def load_error_teryts_from_file(filepath: str) -> Set[str]:
    """Loads a set of TERYT codes from a text file (one TERYT per line)."""
    teryts: Set[str] = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                teryts.add(line.strip())
        logging.info(f"Successfully loaded {len(teryts)} error TERYTs from {filepath}")
    except FileNotFoundError:
        logging.warning(f"Error TERYTs file not found: {filepath}. Proceeding with an empty set of error TERYTs.")
    except IOError as e:
        logging.error(f"Could not read error TERYTs file {filepath}: {e}. Proceeding with an empty set.")
    return teryts


def calculate_adjusted_total_votes(
    csv_filepath: str, 
    candidate1_col: str, 
    candidate2_col: str, 
    error_teryts_set: Set[str]
) -> Optional[CalculationResult]:
    """
    Calculates total votes for two candidates from a CSV file,
    swapping votes for specified TERYT codes identified as errors.

    Args:
        csv_filepath: Path to the CSV file to process.
        candidate1_col: Column name for the first candidate.
        candidate2_col: Column name for the second candidate.
        error_teryts_set: A set of TERYT codes for which votes should be swapped.

    Returns:
        A CalculationResult object or None if a critical error occurs.
    """
    totals: Dict[str, int] = {candidate1_col: 0, candidate2_col: 0}
    processed_rows = 0
    swapped_teryts_count = 0

    try:
        with open(csv_filepath, mode='r', encoding=config.CSV_ENCODING) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=config.CSV_DELIMITER)

            if not reader.fieldnames:
                logging.error(f"File {csv_filepath} is empty or does not contain headers.")
                return None

            required_cols_in_file = [config.TERYT_COLUMN_NAME, candidate1_col, candidate2_col]
            missing_cols = [col for col in required_cols_in_file if col not in reader.fieldnames]
            if missing_cols:
                logging.error(f"File {csv_filepath} is missing required columns: {missing_cols}.")
                return None

            for i, row in enumerate(reader):
                teryt = row.get(config.TERYT_COLUMN_NAME)
                if not teryt:
                    logging.warning(f"Missing TERYT in row {i+2} of {csv_filepath}. Skipping.")
                    continue

                try:
                    # Get vote strings, default to "0" if missing or None, then convert to int
                    votes_cand1_str = row.get(candidate1_col, "0") or "0"
                    votes_cand2_str = row.get(candidate2_col, "0") or "0"
                    votes_cand1 = int(votes_cand1_str)
                    votes_cand2 = int(votes_cand2_str)
                except ValueError:
                    logging.warning(f"Non-integer vote count for TERYT {teryt} (row {i+2}) in {csv_filepath}. "
                                    "Treating as 0 for this row's candidates.")
                    votes_cand1, votes_cand2 = 0, 0
                
                original_votes_cand1 = votes_cand1
                original_votes_cand2 = votes_cand2

                if teryt in error_teryts_set:
                    votes_cand1, votes_cand2 = votes_cand2, votes_cand1 # Perform swap
                    swapped_teryts_count += 1
                    logging.info(f"TERYT {teryt} found in error list. Votes swapped: "
                                 f"{candidate1_col}: {original_votes_cand1}->{votes_cand1}, "
                                 f"{candidate2_col}: {original_votes_cand2}->{votes_cand2}")

                totals[candidate1_col] += votes_cand1
                totals[candidate2_col] += votes_cand2
                processed_rows += 1

    except FileNotFoundError:
        logging.error(f"File {csv_filepath} not found.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing {csv_filepath}: {e}")
        return None
    
    logging.info(f"Finished processing {csv_filepath}. Processed {processed_rows} rows. Swapped votes for {swapped_teryts_count} TERYTs.")
    return CalculationResult(totals, processed_rows, swapped_teryts_count, csv_filepath)


if __name__ == "__main__":
    logging.info(f"Starting vote adjustment process.")
    logging.info(f"Processing file: {config.VOTE_ADJUSTER_INPUT_FILE_PATH}")
    logging.info(f"Adjusting votes between: {config.ADJUST_CANDIDATE_1_NAME} and {config.ADJUST_CANDIDATE_2_NAME}")

    # Load the TERYTs suggested for swapping by the error_identifier script
    error_teryts_to_swap = load_error_teryts_from_file(config.TERYTS_FOR_SWAP_FILE) # ZMIANA TUTAJ

    if not error_teryts_to_swap:
        logging.warning("The set of TERYTs for swapping is empty. "
                        f"This could be because no swaps were suggested by the analysis in '{config.ERROR_ANALYSIS_REPORT_FILE}', "
                        f"or the file '{config.TERYTS_FOR_SWAP_FILE}' was not found or empty.")
    else:
        logging.info(f"Using {len(error_teryts_to_swap)} TERYT codes for potential vote swapping listed in {config.TERYTS_FOR_SWAP_FILE}")

    result = calculate_adjusted_total_votes(
        config.VOTE_ADJUSTER_INPUT_FILE_PATH,
        config.ADJUST_CANDIDATE_1_NAME,
        config.ADJUST_CANDIDATE_2_NAME,
        error_teryts_to_swap
    )

    if result:
        logging.info("Vote adjustment calculation successful.")
        print(result) # Print the formatted report from CalculationResult.__str__
    else:
        logging.error("Vote adjustment calculation failed due to errors.")
    
    logging.info("Vote adjustment process finished.")