import csv
import logging
import json
from typing import Dict, List, Optional, Any
from enum import Enum
import math

import config

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RatioShiftAnomalyLevel(Enum):
    NO_ANOMALY = "NO_ANOMALY"
    SMALL_ANOMALY_A_LOST_SHARE_VS_B = "SMALL_ANOMALY_A_LOST_SHARE_VS_B"
    SMALL_ANOMALY_B_LOST_SHARE_VS_A = "SMALL_ANOMALY_B_LOST_SHARE_VS_A"
    LARGE_ANOMALY_A_LOST_SHARE_VS_B = "LARGE_ANOMALY_A_LOST_SHARE_VS_B"
    LARGE_ANOMALY_B_LOST_SHARE_VS_A = "LARGE_ANOMALY_B_LOST_SHARE_VS_A"
    INCONCLUSIVE_LOW_VOTES_R1 = "INCONCLUSIVE_LOW_VOTES_R1"
    INCONCLUSIVE_LOW_VOTES_R2 = "INCONCLUSIVE_LOW_VOTES_R2"
    INCONCLUSIVE_ZERO_DENOMINATOR_R1 = "INCONCLUSIVE_ZERO_DENOMINATOR_R1"
    INCONCLUSIVE_ZERO_DENOMINATOR_R2 = "INCONCLUSIVE_ZERO_DENOMINATOR_R2"
    DATA_ISSUE_INVALID_VOTES = "DATA_ISSUE_INVALID_VOTES"

class TerytRatioAnalysis:
    def __init__(self, teryt: str):
        self.teryt: str = teryt
        self.votes_r1_cand_A: Optional[int] = None
        self.votes_r1_cand_B: Optional[int] = None
        self.votes_r2_cand_A: Optional[int] = None
        self.votes_r2_cand_B: Optional[int] = None
        self.ratio_A_div_B_r1: Optional[float] = None
        self.ratio_A_div_B_r2: Optional[float] = None
        self.ratio_of_ratios_R2_div_R1: Optional[float] = None
        self.estimated_votes_A_if_R1_ratio_kept_in_R2: Optional[float] = None
        self.estimated_vote_shift_for_A: Optional[float] = None
        self.anomaly_level: RatioShiftAnomalyLevel = RatioShiftAnomalyLevel.NO_ANOMALY
        self.description: str = "Analysis pending."

    def to_dict(self) -> Dict[str, Any]:
        def fmt_float(val: Optional[float]) -> Optional[str]:
            if val is None or math.isnan(val) or math.isinf(val):
                return None
            return f"{val:.3f}"
        def fmt_float_signed(val: Optional[float]) -> Optional[str]:
            if val is None or math.isnan(val) or math.isinf(val):
                return None
            return f"{val:+.1f}"
        return {
            "teryt": self.teryt,
            "votes_r1_cand_A": self.votes_r1_cand_A,
            "votes_r1_cand_B": self.votes_r1_cand_B,
            "votes_r2_cand_A": self.votes_r2_cand_A,
            "votes_r2_cand_B": self.votes_r2_cand_B,
            "ratio_A_div_B_r1": fmt_float(self.ratio_A_div_B_r1),
            "ratio_A_div_B_r2": fmt_float(self.ratio_A_div_B_r2),
            "ratio_of_ratios_R2_div_R1": fmt_float(self.ratio_of_ratios_R2_div_R1),
            "estimated_votes_A_if_R1_ratio_kept_in_R2": fmt_float_signed(self.estimated_votes_A_if_R1_ratio_kept_in_R2),
            "estimated_vote_shift_for_A": fmt_float_signed(self.estimated_vote_shift_for_A),
            "anomaly_level": self.anomaly_level.value,
            "description": self.description,
        }

def _load_election_data(filename: str, required_candidate_cols: List[str]) -> Optional[Dict[str, Dict[str, Any]]]:
    data_dict: Dict[str, Dict[str, Any]] = {}
    all_required_cols_in_header = list(set([config.TERYT_COLUMN_NAME] + required_candidate_cols))
    try:
        with open(filename, mode='r', encoding=config.CSV_ENCODING) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=config.CSV_DELIMITER)
            if not reader.fieldnames:
                logging.error(f"File {filename} is empty or does not contain headers.")
                return None
            missing_cols = [col for col in all_required_cols_in_header if col not in reader.fieldnames]
            if missing_cols:
                logging.error(f"Data file {filename} is missing required columns: {missing_cols}. "
                              "Please check column names in the file and in config.py.")
                return None
            for i, row in enumerate(reader):
                teryt = row.get(config.TERYT_COLUMN_NAME)
                if not teryt:
                    logging.warning(f"Missing TERYT identifier in data row {i+2} of {filename}. Skipping this row.")
                    continue
                data_dict[teryt] = row
    except FileNotFoundError:
        logging.error(f"Data file {filename} not found.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while reading data file {filename}: {e}")
        return None
    logging.info(f"Successfully loaded {len(data_dict)} entries from data file {filename}.")
    return data_dict

def _get_int_vote(row_dict: Dict[str, Any], candidate_name: str, teryt: str) -> Optional[int]:
    try:
        vote_str = row_dict.get(candidate_name)
        if vote_str is None or vote_str.strip() == "":
            return 0
        votes = int(vote_str)
        if votes < 0:
            logging.warning(f"Data integrity issue: Negative vote count ({votes}) found for candidate "
                            f"'{candidate_name}' in TERYT {teryt}. Treating as invalid (None).")
            return None
        return votes
    except (ValueError, TypeError):
        logging.warning(f"Data integrity issue: Invalid (non-integer or malformed) vote count "
                        f"for candidate '{candidate_name}' in TERYT {teryt} (value: '{vote_str}'). Treating as invalid (None).")
        return None

def calculate_ratio(numerator: Optional[int], denominator: Optional[int]) -> Optional[float]:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        if numerator == 0:
            return None
        elif numerator > 0:
            return float('inf')
        else:
            return float('-inf')
    return numerator / denominator

def analyze_vote_ratios_between_rounds(
    data_r1: Dict[str, Dict[str, Any]],
    data_r2: Dict[str, Dict[str, Any]]
) -> List[TerytRatioAnalysis]:
    analysis_results: List[TerytRatioAnalysis] = []
    common_teryts = set(data_r1.keys()) & set(data_r2.keys())
    logging.info(f"Found {len(common_teryts)} common TERYTs for ratio shift analysis.")

    for teryt_code in common_teryts:
        result = TerytRatioAnalysis(teryt_code)
        row_r1 = data_r1[teryt_code]
        row_r2 = data_r2[teryt_code]
        v1A = _get_int_vote(row_r1, config.CANDIDATE_A_NAME_R1, teryt_code)
        v1B = _get_int_vote(row_r1, config.CANDIDATE_B_NAME_R1, teryt_code)
        v2A = _get_int_vote(row_r2, config.CANDIDATE_A_NAME_R2, teryt_code)
        v2B = _get_int_vote(row_r2, config.CANDIDATE_B_NAME_R2, teryt_code)
        result.votes_r1_cand_A, result.votes_r1_cand_B = v1A, v1B
        result.votes_r2_cand_A, result.votes_r2_cand_B = v2A, v2B

        if any(v is None for v in [v1A, v1B, v2A, v2B]):
            result.anomaly_level = RatioShiftAnomalyLevel.DATA_ISSUE_INVALID_VOTES
            result.description = "One or more key candidate vote counts were invalid (e.g., non-numeric, negative), preventing ratio analysis."
            analysis_results.append(result)
            continue

        if (v1A + v1B) < config.MIN_TOTAL_VOTES_AB_FOR_RATIO_ANALYSIS_R1:
            result.anomaly_level = RatioShiftAnomalyLevel.INCONCLUSIVE_LOW_VOTES_R1
            result.description = (f"R1 A+B votes ({v1A + v1B}) is below the threshold "
                                  f"({config.MIN_TOTAL_VOTES_AB_FOR_RATIO_ANALYSIS_R1}) for reliable ratio calculation.")
            analysis_results.append(result)
            continue

        if (v2A + v2B) < config.MIN_TOTAL_VOTES_AB_FOR_RATIO_ANALYSIS_R2:
            result.anomaly_level = RatioShiftAnomalyLevel.INCONCLUSIVE_LOW_VOTES_R2
            result.description = (f"R2 A+B votes ({v2A + v2B}) is below the threshold "
                                  f"({config.MIN_TOTAL_VOTES_AB_FOR_RATIO_ANALYSIS_R2}) for reliable shift analysis.")
            analysis_results.append(result)
            continue

        result.ratio_A_div_B_r1 = calculate_ratio(v1A, v1B)
        result.ratio_A_div_B_r2 = calculate_ratio(v2A, v2B)

        if result.ratio_A_div_B_r1 is None or math.isinf(result.ratio_A_div_B_r1):
            result.anomaly_level = RatioShiftAnomalyLevel.INCONCLUSIVE_ZERO_DENOMINATOR_R1
            desc = f"{config.CANDIDATE_B_NAME_R1} (denominator) had 0 votes in R1 (A votes: {v1A}). " \
                   f"Cannot reliably calculate R1 A/B ratio or its shift."
            if v1B == 0 and v1A > 0 and v2A == 0 and v2B > 0:
                result.anomaly_level = RatioShiftAnomalyLevel.LARGE_ANOMALY_A_LOST_SHARE_VS_B
                desc += " Extreme reversal: A had all R1 votes, B gained all R2 votes."
                result.estimated_vote_shift_for_A = float(v2A - v1A)
            result.description = desc
            analysis_results.append(result)
            continue

        if result.ratio_A_div_B_r2 is None or math.isinf(result.ratio_A_div_B_r2):
            result.anomaly_level = RatioShiftAnomalyLevel.INCONCLUSIVE_ZERO_DENOMINATOR_R2
            desc = f"{config.CANDIDATE_B_NAME_R2} (denominator) had 0 votes in R2 (A votes: {v2A}). " \
                   f"Cannot reliably calculate R2 A/B ratio or its shift."
            if v1A == 0 and v1B > 0 and v2B == 0 and v2A > 0:
                result.anomaly_level = RatioShiftAnomalyLevel.LARGE_ANOMALY_B_LOST_SHARE_VS_A
                desc += " Extreme reversal: B had all R1 votes, A gained all R2 votes."
                result.estimated_vote_shift_for_A = float(v2A)
            result.description = desc
            analysis_results.append(result)
            continue

        result.ratio_of_ratios_R2_div_R1 = result.ratio_A_div_B_r2 / result.ratio_A_div_B_r1
        result.estimated_votes_A_if_R1_ratio_kept_in_R2 = v2B * result.ratio_A_div_B_r1
        result.estimated_vote_shift_for_A = v2A - result.estimated_votes_A_if_R1_ratio_kept_in_R2

        desc_parts = [
            f"R1: {config.CANDIDATE_A_NAME_R1}={v1A}, {config.CANDIDATE_B_NAME_R1}={v1B} (A/B Ratio: {result.ratio_A_div_B_r1:.2f}).",
            f"R2: {config.CANDIDATE_A_NAME_R2}={v2A}, {config.CANDIDATE_B_NAME_R2}={v2B} (A/B Ratio: {result.ratio_A_div_B_r2:.2f}).",
            f"Change Factor (R2 Ratio / R1 Ratio): {result.ratio_of_ratios_R2_div_R1:.2f}."
        ]
        if result.estimated_vote_shift_for_A is not None:
            desc_parts.append(f"Estimated vote shift for {config.CANDIDATE_A_NAME_R2}: {result.estimated_vote_shift_for_A:+.1f} votes "
                              f"(Actual R2 A: {v2A}, Expected A if R1 A/B ratio kept: {result.estimated_votes_A_if_R1_ratio_kept_in_R2:.1f}).")

        ror = result.ratio_of_ratios_R2_div_R1
        abs_vote_shift_A = abs(result.estimated_vote_shift_for_A)
        current_anomaly_level = RatioShiftAnomalyLevel.NO_ANOMALY
        anomaly_description_suffix = "No significant ratio shift detected."

        if abs_vote_shift_A >= config.MIN_ABS_VOTE_SHIFT_FOR_SIGNIFICANT_ANOMALY:
            if ror < (1 / config.LARGE_ANOMALY_RATIO_CHANGE_FACTOR):
                current_anomaly_level = RatioShiftAnomalyLevel.LARGE_ANOMALY_A_LOST_SHARE_VS_B
                anomaly_description_suffix = f"LARGE shift: {config.CANDIDATE_A_NAME_R1}'s vote share relative to B significantly DECREASED."
            elif ror > config.LARGE_ANOMALY_RATIO_CHANGE_FACTOR:
                current_anomaly_level = RatioShiftAnomalyLevel.LARGE_ANOMALY_B_LOST_SHARE_VS_A
                anomaly_description_suffix = f"LARGE shift: {config.CANDIDATE_A_NAME_R1}'s vote share relative to B significantly INCREASED (i.e., B lost share to A)."
            elif ror < (1 / config.SMALL_ANOMALY_RATIO_CHANGE_FACTOR):
                current_anomaly_level = RatioShiftAnomalyLevel.SMALL_ANOMALY_A_LOST_SHARE_VS_B
                anomaly_description_suffix = f"Small shift: {config.CANDIDATE_A_NAME_R1}'s vote share relative to B DECREASED."
            elif ror > config.SMALL_ANOMALY_RATIO_CHANGE_FACTOR:
                current_anomaly_level = RatioShiftAnomalyLevel.SMALL_ANOMALY_B_LOST_SHARE_VS_A
                anomaly_description_suffix = f"Small shift: {config.CANDIDATE_A_NAME_R1}'s vote share relative to B INCREASED (i.e., B lost share to A)."
        else:
            if (ror < (1 / config.SMALL_ANOMALY_RATIO_CHANGE_FACTOR) or ror > config.SMALL_ANOMALY_RATIO_CHANGE_FACTOR):
                anomaly_description_suffix = (f"Ratio change detected, but absolute vote shift for A ({result.estimated_vote_shift_for_A:+.1f}) "
                                              f"is below threshold ({config.MIN_ABS_VOTE_SHIFT_FOR_SIGNIFICANT_ANOMALY}).")

        result.anomaly_level = current_anomaly_level
        desc_parts.append(anomaly_description_suffix)
        result.description = " ".join(desc_parts)
        analysis_results.append(result)

    r1_only_teryts = set(data_r1.keys()) - common_teryts
    r2_only_teryts = set(data_r2.keys()) - common_teryts
    if r1_only_teryts:
        logging.info(f"{len(r1_only_teryts)} TERYTs found only in Round 1 data (first 5 shown): {list(r1_only_teryts)[:5]}")
    if r2_only_teryts:
        logging.info(f"{len(r2_only_teryts)} TERYTs found only in Round 2 data (first 5 shown): {list(r2_only_teryts)[:5]}")

    return analysis_results

def save_analysis_report_to_json(report_data: List[TerytRatioAnalysis], filename: str) -> None:
    dict_report = [res.to_dict() for res in report_data]
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(dict_report, f, indent=2, ensure_ascii=False)
        logging.info(f"Successfully saved detailed ratio analysis report to {filename}")
    except IOError as e:
        logging.error(f"Failed to write ratio analysis report to {filename}: {e}")

def generate_significant_shifts_teryts_file(report_data: List[TerytRatioAnalysis], filename: str) -> None:
    teryts_for_investigation: List[str] = []
    for res in report_data:
        if res.anomaly_level in [
            RatioShiftAnomalyLevel.LARGE_ANOMALY_A_LOST_SHARE_VS_B,
            RatioShiftAnomalyLevel.LARGE_ANOMALY_B_LOST_SHARE_VS_A,
        ]:
            teryts_for_investigation.append(res.teryt)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for teryt_code in sorted(teryts_for_investigation):
                f.write(f"{teryt_code}\n")
        logging.info(f"Saved {len(teryts_for_investigation)} TERYTs identified with large ratio shifts to {filename}")
    except IOError as e:
        logging.error(f"Failed to write TERYTs with large ratio shifts file to {filename}: {e}")

def generate_summary_report(report_data: List[TerytRatioAnalysis], filename: str) -> None:
    summary_lines = [
        "--- Election Vote Ratio Shift Analysis Summary ---",
        f"Analysis based on configured candidates: A='{config.CANDIDATE_A_NAME_R1}' (R1) / '{config.CANDIDATE_A_NAME_R2}' (R2) "
        f"and B='{config.CANDIDATE_B_NAME_R1}' (R1) / '{config.CANDIDATE_B_NAME_R2}' (R2)."
    ]
    anomaly_counts: Dict[RatioShiftAnomalyLevel, int] = {}
    total_estimated_shift_A_overall: float = 0.0
    teryts_counted_for_shift_A: int = 0
    sum_shift_when_A_lost_share: float = 0.0
    count_teryts_A_lost_share: int = 0
    sum_shift_when_B_lost_share: float = 0.0
    count_teryts_B_lost_share: int = 0

    for res in report_data:
        anomaly_counts[res.anomaly_level] = anomaly_counts.get(res.anomaly_level, 0) + 1
        if res.estimated_vote_shift_for_A is not None and \
           res.anomaly_level not in [RatioShiftAnomalyLevel.INCONCLUSIVE_LOW_VOTES_R1,
                                      RatioShiftAnomalyLevel.INCONCLUSIVE_LOW_VOTES_R2,
                                      RatioShiftAnomalyLevel.INCONCLUSIVE_ZERO_DENOMINATOR_R1,
                                      RatioShiftAnomalyLevel.INCONCLUSIVE_ZERO_DENOMINATOR_R2,
                                      RatioShiftAnomalyLevel.DATA_ISSUE_INVALID_VOTES,
                                      RatioShiftAnomalyLevel.NO_ANOMALY]:
            total_estimated_shift_A_overall += res.estimated_vote_shift_for_A
            teryts_counted_for_shift_A += 1
            if res.anomaly_level in [RatioShiftAnomalyLevel.SMALL_ANOMALY_A_LOST_SHARE_VS_B, RatioShiftAnomalyLevel.LARGE_ANOMALY_A_LOST_SHARE_VS_B]:
                sum_shift_when_A_lost_share += res.estimated_vote_shift_for_A
                count_teryts_A_lost_share += 1
            elif res.anomaly_level in [RatioShiftAnomalyLevel.SMALL_ANOMALY_B_LOST_SHARE_VS_A, RatioShiftAnomalyLevel.LARGE_ANOMALY_B_LOST_SHARE_VS_A]:
                sum_shift_when_B_lost_share += res.estimated_vote_shift_for_A
                count_teryts_B_lost_share += 1

    summary_lines.append("\n--- Anomaly Level Distribution ---")
    for level, count in sorted(anomaly_counts.items(), key=lambda item: item[0].value):
        summary_lines.append(f"- {level.value}: {count} TERYTs")

    summary_lines.append(f"\n--- Estimated Vote Shift Summary for Candidate A ('{config.CANDIDATE_A_NAME_R2}') ---")
    summary_lines.append(f"(Based on {teryts_counted_for_shift_A} TERYTs with conclusive anomaly and estimable shift)")

    if count_teryts_A_lost_share > 0:
        summary_lines.append(
            f"- Total estimated 'loss' for {config.CANDIDATE_A_NAME_R2} where A's share anomalously decreased: "
            f"{sum_shift_when_A_lost_share:+.1f} votes (across {count_teryts_A_lost_share} TERYTs)."
        )
    if count_teryts_B_lost_share > 0:
        summary_lines.append(
            f"- Total estimated 'gain' for {config.CANDIDATE_A_NAME_R2} where B's share anomalously decreased (favoring A): "
            f"{sum_shift_when_B_lost_share:+.1f} votes (across {count_teryts_B_lost_share} TERYTs)."
        )
    summary_lines.append(
        f"- Overall net estimated shift for {config.CANDIDATE_A_NAME_R2} across all flagged anomalous TERYTs: "
        f"{total_estimated_shift_A_overall:+.1f} votes."
    )
    summary_lines.append("\nInterpretation Note:")
    summary_lines.append("  'Estimated vote shift' is a heuristic. It quantifies how many more (positive) or fewer (negative) "
                         "votes Candidate A received in R2 compared to what would be expected if the A/B vote ratio from R1 "
                         "had been perfectly preserved in R2 (given Candidate B's actual R2 votes).")
    summary_lines.append("  This does NOT definitively prove errors or fraud but highlights areas for closer inspection.")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for line in summary_lines:
                f.write(line + "\n")
        logging.info(f"Successfully saved summary report of ratio shift analysis to {filename}")
    except IOError as e:
        logging.error(f"Failed to write summary report to {filename}: {e}")

if __name__ == "__main__":
    logging.info(f"Starting election vote ratio shift analysis between Round 1 and Round 2.")
    r1_essential_candidate_cols = [config.CANDIDATE_A_NAME_R1, config.CANDIDATE_B_NAME_R1]
    r2_essential_candidate_cols = [config.CANDIDATE_A_NAME_R2, config.CANDIDATE_B_NAME_R2]
    data_r1 = _load_election_data(config.ROUND1_RESULTS_FILE_PATH, r1_essential_candidate_cols)
    data_r2 = _load_election_data(config.ROUND2_RESULTS_FILE_PATH, r2_essential_candidate_cols)
    if data_r1 and data_r2:
        analysis_results = analyze_vote_ratios_between_rounds(data_r1, data_r2)
        save_analysis_report_to_json(analysis_results, config.RATIO_ANALYSIS_REPORT_FILE)
        generate_significant_shifts_teryts_file(analysis_results, config.SIGNIFICANT_RATIO_SHIFTS_TERYTS_FILE)
        generate_summary_report(analysis_results, config.SUMMARY_REPORT_FILE)
        logging.info("--- Ratio Shift Analysis Conclusion Summary (from main execution) ---")
        conclusion_counts: Dict[RatioShiftAnomalyLevel, int] = {}
        for res in analysis_results:
            conclusion_counts[res.anomaly_level] = conclusion_counts.get(res.anomaly_level, 0) + 1
        for conclusion_type, count in sorted(conclusion_counts.items(), key=lambda item: item[0].value):
            logging.info(f"{conclusion_type.value}: {count} TERYTs")
    else:
        logging.error("Ratio shift analysis aborted due to critical issues in loading data files. "
                      "Please check previous error messages and file paths in config.py.")
    logging.info("Election vote ratio shift analysis process finished.")