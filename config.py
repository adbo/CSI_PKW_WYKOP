# config.py

# --- File Paths ---
# Input file for Round 1 results (must contain individual results for CANDIDATE_A_NAME_R1 and CANDIDATE_B_NAME_R1)
ROUND1_RESULTS_FILE_PATH = "wyniki_gl_na_kandydatow_po_gminach_utf8.csv"
# Input file for Round 2 results (must contain individual results for CANDIDATE_A_NAME_R2 and CANDIDATE_B_NAME_R2)
ROUND2_RESULTS_FILE_PATH = "wyniki_gl_na_kandydatow_po_gminach_w_drugiej_turze_utf8.csv"

# Output file for the detailed JSON analysis report based on ratio shifts
RATIO_ANALYSIS_REPORT_FILE = "election_ratio_analysis_report.json"
# Output text file listing TERYTs with significant/suspicious ratio shifts
SIGNIFICANT_RATIO_SHIFTS_TERYTS_FILE = "significant_ratio_shifts_teryts.txt"
# Output text file for a human-readable summary of the ratio shift analysis
SUMMARY_REPORT_FILE = "election_ratio_analysis_summary.txt"


# --- Key Candidate Names for Ratio Shift Analysis ---
# These are the two main candidates whose relative performance shift between R1 and R2 is analyzed.

# Candidate A (e.g., the reference candidate or first major candidate)
CANDIDATE_A_NAME_R1 = "TRZASKOWSKI Rafał Kazimierz" # Name of Candidate A in the Round 1 data file
CANDIDATE_A_NAME_R2 = "TRZASKOWSKI Rafał Kazimierz" # Name of Candidate A in the Round 2 data file

# Candidate B (e.g., the main competitor to Candidate A)
CANDIDATE_B_NAME_R1 = "NAWROCKI Karol Tadeusz"    # Name of Candidate B in the Round 1 data file
CANDIDATE_B_NAME_R2 = "NAWROCKI Karol Tadeusz"    # Name of Candidate B in the Round 2 data file


# --- CSV Settings ---
CSV_DELIMITER = ';'  # Delimiter used in the CSV files
CSV_ENCODING = 'utf-8-sig' # Encoding of the CSV files (utf-8-sig handles BOM)
TERYT_COLUMN_NAME = "TERYT Gminy" # Name of the column containing the TERYT (administrative unit ID)


# --- Thresholds for Ratio Shift Analysis ---

# Minimum sum of votes for Candidate A and Candidate B combined in a given round
# for that round's A/B ratio to be considered reliable for analysis.
# This helps to avoid analyzing ratios based on very few votes, which can be volatile.
MIN_TOTAL_VOTES_AB_FOR_RATIO_ANALYSIS_R1 = 20
MIN_TOTAL_VOTES_AB_FOR_RATIO_ANALYSIS_R2 = 20

# Defines how much the A/B vote ratio must change from R1 to R2 to be flagged as a "small anomaly".
# The check is: (Ratio_R2 / Ratio_R1) < (1 / SMALL_ANOMALY_RATIO_CHANGE_FACTOR) OR
#               (Ratio_R2 / Ratio_R1) > SMALL_ANOMALY_RATIO_CHANGE_FACTOR
# Example: If 1.5, a 50% change in the ratio (e.g., from 2.0 to <1.33 or >3.0) is a small anomaly.
SMALL_ANOMALY_RATIO_CHANGE_FACTOR = 1.5

# Defines how much the A/B vote ratio must change from R1 to R2 to be flagged as a "large anomaly".
# Logic is similar to SMALL_ANOMALY_RATIO_CHANGE_FACTOR.
# Example: If 2.5, a 150% change in the ratio is a large anomaly.
LARGE_ANOMALY_RATIO_CHANGE_FACTOR = 2.5

# Minimum absolute change in votes for the candidate who "lost" share due to the ratio shift,
# for an anomaly (even if the ratio change itself is large) to be considered significant.
# This prevents flagging large percentage changes in ratios when the actual number of votes shifted is tiny.
# E.g., a shift from 2 votes to 1 vote for A (while B stays at 1) is a 100% ratio change for A/B,
# but only 1 vote difference. This threshold filters such cases.
MIN_ABS_VOTE_SHIFT_FOR_SIGNIFICANT_ANOMALY = 10


# --- Configuration for vote_adjuster.py (if used with the output of this analysis) ---
# If vote_adjuster.py is used, it would typically operate on ROUND2_RESULTS_FILE_PATH
# and swap votes between these two candidates for TERYTs listed in SIGNIFICANT_RATIO_SHIFTS_TERYTS_FILE.
ADJUST_CANDIDATE_1_NAME_IN_R2_FILE = CANDIDATE_A_NAME_R2 # Candidate whose votes are taken first for swapping
ADJUST_CANDIDATE_2_NAME_IN_R2_FILE = CANDIDATE_B_NAME_R2 # Candidate whose votes are taken second for swapping