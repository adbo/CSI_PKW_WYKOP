# error_identifier.py
import csv
import logging
import json # For structured report
from typing import Dict, Tuple, Set, List, Optional, Callable, Any
from enum import Enum

import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AnomalyType(Enum):
    NO_ANOMALY = "NO_ANOMALY"
    # Anomalie dla Kandydata A
    A_R1_SUM_LESS_THAN_R2_VOTES = "A_R1_SUM_LESS_THAN_R2_VOTES" # d1_A < d2_A
    A_R2_ZERO_R1_GROUP_POSITIVE = "A_R2_ZERO_R1_GROUP_POSITIVE" # d2_A = 0, d1_A > threshold
    A_LOW_R2_PROPORTION_TO_R1_GROUP = "A_LOW_R2_PROPORTION_TO_R1_GROUP" # d1_A >= factor * d2_A
    # Anomalie dla Kandydata B
    B_R1_SUM_LESS_THAN_R2_VOTES = "B_R1_SUM_LESS_THAN_R2_VOTES" # d1_B < d2_B
    B_R2_ZERO_R1_GROUP_POSITIVE = "B_R2_ZERO_R1_GROUP_POSITIVE" # d2_B = 0, d1_B > threshold
    B_LOW_R2_PROPORTION_TO_R1_GROUP = "B_LOW_R2_PROPORTION_TO_R1_GROUP" # d1_B >= factor * d2_B
    # Wnioski oparte na kombinacji
    POTENTIAL_SWAP_A_FAVORS_B = "POTENTIAL_SWAP_A_FAVORS_B" # Anomalia A, B wygląda OK lub ma "odwrotną" anomalię
    POTENTIAL_SWAP_B_FAVORS_A = "POTENTIAL_SWAP_B_FAVORS_A" # Anomalia B, A wygląda OK lub ma "odwrotną" anomalię
    BOTH_CANDIDATES_ANOMALOUS_INDEPENDENTLY = "BOTH_CANDIDATES_ANOMALOUS_INDEPENDENTLY"
    DATA_INCONSISTENCY_COMPLEX = "DATA_INCONSISTENCY_COMPLEX" # Np. obaj d1 < d2
    UNKNOWN_ANOMALY = "UNKNOWN_ANOMALY"

class TerytAnalysisResult:
    def __init__(self, teryt: str):
        self.teryt = teryt
        self.votes_r1_group_A: Optional[int] = None
        self.votes_r1_group_B: Optional[int] = None
        self.votes_r2_cand_A: Optional[int] = None
        self.votes_r2_cand_B: Optional[int] = None
        self.anomalies_A: List[AnomalyType] = []
        self.anomalies_B: List[AnomalyType] = []
        self.derived_conclusion: AnomalyType = AnomalyType.NO_ANOMALY
        self.description: str = ""
        self.data_source_r1: Dict[str, Any] = {} # Original row from R1 data if needed
        self.data_source_r2: Dict[str, Any] = {} # Original row from R2 data if needed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "teryt": self.teryt,
            "votes_r1_group_A": self.votes_r1_group_A,
            "votes_r1_group_B": self.votes_r1_group_B,
            "votes_r2_cand_A": self.votes_r2_cand_A,
            "votes_r2_cand_B": self.votes_r2_cand_B,
            "anomalies_A": [a.value for a in self.anomalies_A],
            "anomalies_B": [a.value for a in self.anomalies_B],
            "derived_conclusion": self.derived_conclusion.value,
            "description": self.description,
            # "data_source_r1": self.data_source_r1, # Potentially large, include if necessary
            # "data_source_r2": self.data_source_r2,
        }

# Funkcja _load_data_from_csv pozostaje podobna, ale dostosujemy jej użycie

def load_round1_data_for_analysis(filename: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """Loads R1 data, returning the full row for richer analysis."""
    data_dict: Dict[str, Dict[str, Any]] = {}
    # All candidates mentioned in R1 groups are potentially required
    required_cols = list(set([config.TERYT_COLUMN_NAME] + config.CANDIDATE_A_R1_GROUP + config.CANDIDATE_B_R1_GROUP))
    try:
        with open(filename, mode='r', encoding=config.CSV_ENCODING) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=config.CSV_DELIMITER)
            if not reader.fieldnames:
                logging.error(f"File {filename} is empty or does not contain headers.")
                return None
            missing = [col for col in required_cols if col not in reader.fieldnames]
            if missing:
                logging.error(f"R1 data file {filename} is missing columns: {missing}")
                return None
            for i, row in enumerate(reader):
                teryt = row.get(config.TERYT_COLUMN_NAME)
                if not teryt:
                    logging.warning(f"Missing TERYT in R1 data row {i+2} of {filename}. Skipping.")
                    continue
                data_dict[teryt] = row # Store the whole row
    except FileNotFoundError:
        logging.error(f"File {filename} not found.")
        return None
    except Exception as e:
        logging.error(f"Error reading R1 data {filename}: {e}")
        return None
    logging.info(f"Successfully loaded {len(data_dict)} entries from R1 data file {filename}.")
    return data_dict


def load_round2_data_for_analysis(filename: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """Loads R2 data, returning the full row."""
    data_dict: Dict[str, Dict[str, Any]] = {}
    required_cols = [config.TERYT_COLUMN_NAME, config.CANDIDATE_A_NAME_R2, config.CANDIDATE_B_NAME_R2]
    try:
        with open(filename, mode='r', encoding=config.CSV_ENCODING) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=config.CSV_DELIMITER)
            if not reader.fieldnames:
                logging.error(f"File {filename} is empty or does not contain headers.")
                return None
            missing = [col for col in required_cols if col not in reader.fieldnames]
            if missing:
                logging.error(f"R2 data file {filename} is missing columns: {missing}")
                return None
            for i, row in enumerate(reader):
                teryt = row.get(config.TERYT_COLUMN_NAME)
                if not teryt:
                    logging.warning(f"Missing TERYT in R2 data row {i+2} of {filename}. Skipping.")
                    continue
                data_dict[teryt] = row
    except FileNotFoundError:
        logging.error(f"File {filename} not found.")
        return None
    except Exception as e:
        logging.error(f"Error reading R2 data {filename}: {e}")
        return None
    logging.info(f"Successfully loaded {len(data_dict)} entries from R2 data file {filename}.")
    return data_dict

def _get_int_vote(row_dict: Dict[str, Any], candidate_name: str, default: int = 0) -> int:
    try:
        return int(row_dict.get(candidate_name, default) or default)
    except (ValueError, TypeError):
        return default

def _get_group_sum(row_dict: Dict[str, Any], candidate_group: List[str]) -> int:
    s = 0
    for cand in candidate_group:
        s += _get_int_vote(row_dict, cand)
    return s


def analyze_teryt_anomalies(
    data_r1: Dict[str, Dict[str, Any]],
    data_r2: Dict[str, Dict[str, Any]]
) -> List[TerytAnalysisResult]:
    """
    Performs detailed anomaly analysis for each TERYT common to both datasets.
    """
    analysis_results: List[TerytAnalysisResult] = []
    common_teryts = set(data_r1.keys()) & set(data_r2.keys())
    logging.info(f"Found {len(common_teryts)} common TERYTs for analysis.")

    if config.CANDIDATE_A_NAME_R2 not in config.CANDIDATE_A_R1_GROUP:
        logging.warning(f"Config check: CANDIDATE_A_NAME_R2 ('{config.CANDIDATE_A_NAME_R2}') "
                        f"is not in CANDIDATE_A_R1_GROUP. Analysis for A might be flawed.")
    if config.CANDIDATE_B_NAME_R2 not in config.CANDIDATE_B_R1_GROUP:
        logging.warning(f"Config check: CANDIDATE_B_NAME_R2 ('{config.CANDIDATE_B_NAME_R2}') "
                        f"is not in CANDIDATE_B_R1_GROUP. Analysis for B might be flawed.")

    for teryt in common_teryts:
        res = TerytAnalysisResult(teryt)
        row_r1 = data_r1[teryt]
        row_r2 = data_r2[teryt]

        res.data_source_r1 = row_r1 # For potential deeper inspection
        res.data_source_r2 = row_r2

        # Calculate votes
        res.votes_r1_group_A = _get_group_sum(row_r1, config.CANDIDATE_A_R1_GROUP)
        res.votes_r1_group_B = _get_group_sum(row_r1, config.CANDIDATE_B_R1_GROUP)
        res.votes_r2_cand_A = _get_int_vote(row_r2, config.CANDIDATE_A_NAME_R2)
        res.votes_r2_cand_B = _get_int_vote(row_r2, config.CANDIDATE_B_NAME_R2)

        d1A, d1B = res.votes_r1_group_A, res.votes_r1_group_B
        d2A, d2B = res.votes_r2_cand_A, res.votes_r2_cand_B
        
        # --- Analyze for Candidate A ---
        if d1A < d2A:
            res.anomalies_A.append(AnomalyType.A_R1_SUM_LESS_THAN_R2_VOTES)
        else: # Only if not the above, check proportionality
            if d2A == 0 and d1A >= config.MIN_R1_GROUP_VOTES_FOR_ZERO_R2_ANOMALY:
                res.anomalies_A.append(AnomalyType.A_R2_ZERO_R1_GROUP_POSITIVE)
            elif d2A > 0 and d1A >= config.PROPORTIONALITY_THRESHOLD_FACTOR * d2A:
                res.anomalies_A.append(AnomalyType.A_LOW_R2_PROPORTION_TO_R1_GROUP)

        # --- Analyze for Candidate B ---
        if d1B < d2B:
            res.anomalies_B.append(AnomalyType.B_R1_SUM_LESS_THAN_R2_VOTES)
        else: # Only if not the above, check proportionality
            if d2B == 0 and d1B >= config.MIN_R1_GROUP_VOTES_FOR_ZERO_R2_ANOMALY:
                res.anomalies_B.append(AnomalyType.B_R2_ZERO_R1_GROUP_POSITIVE)
            elif d2B > 0 and d1B >= config.PROPORTIONALITY_THRESHOLD_FACTOR * d2B:
                res.anomalies_B.append(AnomalyType.B_LOW_R2_PROPORTION_TO_R1_GROUP)

        # --- Derive Conclusion ---
        # This logic can be quite complex and domain-specific
        desc_parts = []
        if res.anomalies_A:
            desc_parts.append(f"Anomalies for {config.CANDIDATE_A_NAME_R2}: {', '.join(a.value for a in res.anomalies_A)}")
        if res.anomalies_B:
            desc_parts.append(f"Anomalies for {config.CANDIDATE_B_NAME_R2}: {', '.join(a.value for a in res.anomalies_B)}")

        # Simplified conclusion logic - can be expanded
        is_A_problematic = bool(res.anomalies_A)
        is_B_problematic = bool(res.anomalies_B)

        if AnomalyType.A_R1_SUM_LESS_THAN_R2_VOTES in res.anomalies_A and \
           AnomalyType.B_R1_SUM_LESS_THAN_R2_VOTES in res.anomalies_B:
            res.derived_conclusion = AnomalyType.DATA_INCONSISTENCY_COMPLEX
            desc_parts.append("Severe data inconsistency for both candidates (R1 sum < R2 votes).")
        elif is_A_problematic and not is_B_problematic:
            # If A has issues, and B's R2 votes are significantly higher than A's R2 votes (and A's R2 is low)
            # it might suggest A's votes were swapped to B.
            if d2A < d2B and (AnomalyType.A_R2_ZERO_R1_GROUP_POSITIVE in res.anomalies_A or \
                              AnomalyType.A_LOW_R2_PROPORTION_TO_R1_GROUP in res.anomalies_A):
                res.derived_conclusion = AnomalyType.POTENTIAL_SWAP_A_FAVORS_B
                desc_parts.append(f"Potential swap: {config.CANDIDATE_A_NAME_R2} anomaly, {config.CANDIDATE_B_NAME_R2} has higher R2 votes.")
            else:
                res.derived_conclusion = res.anomalies_A[0] # Take first anomaly as primary
        elif not is_A_problematic and is_B_problematic:
            if d2B < d2A and (AnomalyType.B_R2_ZERO_R1_GROUP_POSITIVE in res.anomalies_B or \
                              AnomalyType.B_LOW_R2_PROPORTION_TO_R1_GROUP in res.anomalies_B):
                res.derived_conclusion = AnomalyType.POTENTIAL_SWAP_B_FAVORS_A
                desc_parts.append(f"Potential swap: {config.CANDIDATE_B_NAME_R2} anomaly, {config.CANDIDATE_A_NAME_R2} has higher R2 votes.")
            else:
                res.derived_conclusion = res.anomalies_B[0]
        elif is_A_problematic and is_B_problematic:
            res.derived_conclusion = AnomalyType.BOTH_CANDIDATES_ANOMALOUS_INDEPENDENTLY
            desc_parts.append("Both candidates show independent anomalies.")
        
        if not res.anomalies_A and not res.anomalies_B:
            res.derived_conclusion = AnomalyType.NO_ANOMALY
            desc_parts.append("No specific anomalies detected based on current rules.")
        
        res.description = "; ".join(desc_parts)
        analysis_results.append(res)

    # Log summary of TERYTs not in common
    r1_only = set(data_r1.keys()) - common_teryts
    r2_only = set(data_r2.keys()) - common_teryts
    if r1_only:
        logging.info(f"{len(r1_only)} TERYTs present only in R1 data: {list(r1_only)[:5]}...") # Show a few
    if r2_only:
        logging.info(f"{len(r2_only)} TERYTs present only in R2 data: {list(r2_only)[:5]}...")

    return analysis_results

def save_analysis_report(report_data: List[TerytAnalysisResult], filename: str):
    """Saves the detailed analysis report to a JSON file."""
    dict_report = [res.to_dict() for res in report_data]
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(dict_report, f, indent=2, ensure_ascii=False)
        logging.info(f"Successfully saved detailed analysis report to {filename}")
    except IOError as e:
        logging.error(f"Failed to write analysis report to {filename}: {e}")

def generate_teryts_for_swap_file(report_data: List[TerytAnalysisResult], filename: str):
    """
    Generates a simple text file with TERYTs suggested for vote swapping.
    This is a simplified action based on the report; manual review is advised.
    """
    teryts_to_swap: Set[str] = set()
    for res in report_data:
        if res.derived_conclusion in [AnomalyType.POTENTIAL_SWAP_A_FAVORS_B, AnomalyType.POTENTIAL_SWAP_B_FAVORS_A]:
            teryts_to_swap.add(res.teryt)
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for teryt in sorted(list(teryts_to_swap)):
                f.write(f"{teryt}\n")
        logging.info(f"Saved {len(teryts_to_swap)} TERYTs suggested for vote swapping to {filename}")
    except IOError as e:
        logging.error(f"Failed to write TERYTs for swap file to {filename}: {e}")


if __name__ == "__main__":
    logging.info(f"Starting detailed error analysis process.")
    
    data_r1 = load_round1_data_for_analysis(config.ERROR_ID_INPUT_FILE1_PATH)
    data_r2 = load_round2_data_for_analysis(config.ERROR_ID_INPUT_FILE2_PATH)

    if data_r1 and data_r2:
        analysis_results = analyze_teryt_anomalies(data_r1, data_r2)
        save_analysis_report(analysis_results, config.ERROR_ANALYSIS_REPORT_FILE)

        # Optionally, generate a list of TERYTs for the vote_adjuster if a swap is suspected
        generate_teryts_for_swap_file(analysis_results, config.TERYTS_FOR_SWAP_FILE)

        # Log summary of conclusions
        conclusion_counts: Dict[AnomalyType, int] = {}
        for res in analysis_results:
            conclusion_counts[res.derived_conclusion] = conclusion_counts.get(res.derived_conclusion, 0) + 1
        
        logging.info("--- Analysis Conclusion Summary ---")
        for anomaly_type, count in conclusion_counts.items():
            logging.info(f"{anomaly_type.value}: {count} TERYTs")
    else:
        logging.error("Detailed error analysis aborted due to issues loading data files.")

    logging.info("Detailed error analysis process finished.")