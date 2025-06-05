# config.py

# --- File Paths ---
ERROR_ID_INPUT_FILE1_PATH = "wyniki_gl_na_kandydatow_po_gminach_utf8.csv"
ERROR_ID_INPUT_FILE2_PATH = "wyniki_gl_na_kandydatow_po_gminach_w_drugiej_turze_utf8.csv"
ERROR_ANALYSIS_REPORT_FILE = "error_analysis_report.json"

VOTE_ADJUSTER_INPUT_FILE_PATH = "wyniki_gl_na_kandydatow_po_gminach_w_drugiej_turze_utf8.csv"
TERYTS_FOR_SWAP_FILE = "teryts_to_swap_votes.txt"


# --- Candidate Names for Error Identification (Script 1) ---

CANDIDATE_A_NAME_R2 = "TRZASKOWSKI Rafał Kazimierz"
CANDIDATE_A_R1_GROUP = ["ZANDBERG Adrian Tadeusz", "TRZASKOWSKI Rafał Kazimierz", "BIEJAT Magdalena Agnieszka"]

CANDIDATE_B_NAME_R2 = "NAWROCKI Karol Tadeusz"
CANDIDATE_B_R1_GROUP = ["BRAUN Grzegorz Michał", "MENTZEN Sławomir Jerzy", "NAWROCKI Karol Tadeusz"]

ADJUST_CANDIDATE_1_NAME = CANDIDATE_A_NAME_R2
ADJUST_CANDIDATE_2_NAME = CANDIDATE_B_NAME_R2


# --- CSV Settings ---
CSV_DELIMITER = ';'
CSV_ENCODING = 'utf-8-sig'
TERYT_COLUMN_NAME = "TERYT Gminy"

PROPORTIONALITY_THRESHOLD_FACTOR = 2.0
MIN_R1_GROUP_VOTES_FOR_ZERO_R2_ANOMALY = 10