# vote_adjuster.py
import csv
import logging
from typing import Dict, Set, Optional # Tuple no longer needed from here

import config # Import from our configuration file

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CalculationResult:
    """Holds the results of the vote calculation and adjustment."""
    def __init__(self, totals: Dict[str, int], processed_rows: int, swapped_count: int, file_path: str):
        self.totals = totals
        self.processed_rows = processed_rows
        self.swapped_count = swapped_count
        self.file_path = file_path

    def __str__(self) -> str:
        report_lines = [
            f"--- Vote Adjustment Report for: {self.file_path} ---",
            f"Processed {self.processed_rows} rows.",
        ]
        if self.swapped_count > 0:
             report_lines.append(f"Votes were swapped for {self.swapped_count} TERYT codes based on the input list.")
        else:
             report_lines.append("No votes were swapped based on the input list.")
        report_lines.append("--- Adjusted Total Votes ---")
        for candidate, total_votes in self.totals.items():
            report_lines.append(f"{candidate}: {total_votes}")
        return "\n".join(report_lines)


def load_teryts_from_file(filepath: str) -> Set[str]: # Renamed from load_error_teryts_from_file
    """Loads a set of TERYT codes from a text file (one TERYT per line)."""
    teryts: Set[str] = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                teryts.add(line.strip())
        logging.info(f"Successfully loaded {len(teryts)} TERYTs from {filepath}")
    except FileNotFoundError:
        logging.warning(f"TERYT list file not found: {filepath}. Proceeding with an empty set of TERYTs.")
    except IOError as e:
        logging.error(f"Could not read TERYT list file {filepath}: {e}. Proceeding with an empty set.")
    return teryts


def calculate_adjusted_total_votes(
    csv_filepath: str,
    candidate1_col_to_adjust: str,
    candidate2_col_to_adjust: str,
    teryts_for_action: Set[str] # Renamed from error_teryts_set
) -> Optional[CalculationResult]:
    """
    Calculates total votes for two candidates from a CSV file,
    swapping votes for specified TERYT codes.

    Args:
        csv_filepath: Path to the CSV file to process (e.g., Round 2 results).
        candidate1_col_to_adjust: Column name for the first candidate whose votes might be swapped.
        candidate2_col_to_adjust: Column name for the second candidate.
        teryts_for_action: A set of TERYT codes for which votes should be swapped.

    Returns:
        A CalculationResult object or None if a critical error occurs.
    """
    totals: Dict[str, int] = {candidate1_col_to_adjust: 0, candidate2_col_to_adjust: 0}
    processed_rows = 0
    swapped_teryts_count = 0

    try:
        with open(csv_filepath, mode='r', encoding=config.CSV_ENCODING) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=config.CSV_DELIMITER)

            if not reader.fieldnames:
                logging.error(f"File {csv_filepath} is empty or does not contain headers.")
                return None

            required_cols_in_file = [config.TERYT_COLUMN_NAME, candidate1_col_to_adjust, candidate2_col_to_adjust]
            missing_cols = [col for col in required_cols_in_file if col not in reader.fieldnames]
            if missing_cols:
                logging.error(f"File {csv_filepath} is missing required columns for adjustment: {missing_cols}.")
                return None

            for i, row in enumerate(reader):
                teryt = row.get(config.TERYT_COLUMN_NAME)
                if not teryt:
                    logging.warning(f"Missing TERYT in row {i+2} of {csv_filepath}. Skipping.")
                    continue

                try:
                    votes_cand1_str = row.get(candidate1_col_to_adjust, "0") or "0"
                    votes_cand2_str = row.get(candidate2_col_to_adjust, "0") or "0"
                    votes_cand1 = int(votes_cand1_str)
                    votes_cand2 = int(votes_cand2_str)
                    if votes_cand1 < 0 or votes_cand2 < 0:
                        logging.warning(f"Negative vote count detected for TERYT {teryt} (row {i+2}). "
                                        "Treating as 0 for this row's candidates for adjustment purposes.")
                        votes_cand1, votes_cand2 = 0,0 # Or max(0, val) if preferred
                except ValueError:
                    logging.warning(f"Non-integer vote count for TERYT {teryt} (row {i+2}) in {csv_filepath}. "
                                    "Treating as 0 for this row's candidates for adjustment.")
                    votes_cand1, votes_cand2 = 0, 0
                
                original_votes_cand1 = votes_cand1
                original_votes_cand2 = votes_cand2

                if teryt in teryts_for_action:
                    votes_cand1, votes_cand2 = votes_cand2, votes_cand1 # Perform swap
                    swapped_teryts_count += 1
                    logging.info(f"TERYT {teryt} found in action list. Votes swapped: "
                                 f"{candidate1_col_to_adjust}: {original_votes_cand1}->{votes_cand1}, "
                                 f"{candidate2_col_to_adjust}: {original_votes_cand2}->{votes_cand2}")

                totals[candidate1_col_to_adjust] += votes_cand1
                totals[candidate2_col_to_adjust] += votes_cand2
                processed_rows += 1

    except FileNotFoundError:
        logging.error(f"File {csv_filepath} not found.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing {csv_filepath} for adjustment: {e}")
        return None
    
    logging.info(f"Finished processing {csv_filepath} for vote adjustment. "
                 f"Processed {processed_rows} rows. Swapped votes for {swapped_teryts_count} TERYTs.")
    return CalculationResult(totals, processed_rows, swapped_teryts_count, csv_filepath)


if __name__ == "__main__":
    logging.info(f"Starting vote adjustment process (optional, based on prior analysis).")
    logging.info(f"Processing file for potential adjustments: {config.ROUND2_RESULTS_FILE_PATH}") # Assuming R2 file
    logging.info(f"Candidates configured for potential vote swap: "
                 f"{config.ADJUST_CANDIDATE_1_NAME_IN_R2_FILE} and {config.ADJUST_CANDIDATE_2_NAME_IN_R2_FILE}")

    # Load the TERYTs identified by the analysis script as having suspicious shifts
    teryts_for_potential_swap = load_teryts_from_file(config.SIGNIFICANT_RATIO_SHIFTS_TERYTS_FILE)

    if not teryts_for_potential_swap:
        logging.warning("The list of TERYTs for potential vote swapping is empty. "
                        f"This could mean no suspicious shifts were flagged by the analysis, "
                        f"or the file '{config.SIGNIFICANT_RATIO_SHIFTS_TERYTS_FILE}' was not found/empty. No adjustments will be made.")
    else:
        logging.info(f"Found {len(teryts_for_potential_swap)} TERYTs in '{config.SIGNIFICANT_RATIO_SHIFTS_TERYTS_FILE}' "
                     "for which votes will be swapped if present in the data file.")
        logging.warning("IMPORTANT: Proceeding with vote swaps. Ensure this action is justified by prior analysis of the JSON report.")


    # Note: Using ROUND2_RESULTS_FILE_PATH as the file to adjust.
    # Adjust candidate names are also taken from config, assumed to be present in ROUND2_RESULTS_FILE_PATH
    result = calculate_adjusted_total_votes(
        config.ROUND2_RESULTS_FILE_PATH, 
        config.ADJUST_CANDIDATE_1_NAME_IN_R2_FILE,
        config.ADJUST_CANDIDATE_2_NAME_IN_R2_FILE,
        teryts_for_potential_swap
    )

    if result:
        logging.info("Vote adjustment calculation (if any TERYTs were targeted) successful.")
        print(result) # Print the formatted report from CalculationResult.__str__
    else:
        logging.error("Vote adjustment calculation failed or was not applicable.")
    
    logging.info("Vote adjustment process finished.")