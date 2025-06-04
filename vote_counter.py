import csv

# --- Configuration ---
FILE1_PATH = "wyniki_gl_na_kandydatow_po_gminach_utf8.csv"
FILE2_PATH = "wyniki_gl_na_kandydatow_po_gminach_w_drugiej_turze_utf8.csv"  # Path to your second CSV file
CANDIDATE_1_NAME = "NAWROCKI Karol Tadeusz"
CANDIDATE_2_NAME = "TRZASKOWSKI Rafał Kazimierz"

# !!! CRITICAL !!!
# You MUST populate this set with the TERYT Gminy codes that were
# identified as having an "error" by your FIRST script.
# Example:
# ERROR_TERYTS = {"0201011", "0202032", "1465011"}
#
# If you ran the first script and it printed errors like:
# ERROR: TERYT 0201011 - Data Inconsistency...
# ERROR: TERYT 0202032 - Not 'closer'...
# Then ERROR_TERYTS would be {"0201011", "0202032"}
#
# For demonstration, I'll leave it empty. You need to fill this.
ERROR_TERYTS = set()

# --- Helper function to get candidate columns from the first script (for error definition) ---
# This is just for context; the actual error TERYTs must be provided by you.
# For File 1 (context for error definition)
candidates_group1_f1 = ["ZANDBERG Adrian Tadeusz", "TRZASKOWSKI Rafał Kazimierz", "BIEJAT Magdalena Agnieszka"]
# For File 2 (context for error definition)
candidate1_f2_error_context = "TRZASKOWSKI Rafał Kazimierz"

def get_error_teryts_from_first_script_logic(file1_path, file2_path_for_context):
    """
    This function simulates running the logic of the *first* script
    to determine the error TERYTs. In a real scenario, you would run
    the first script and copy its output of error TERYTs.
    This is provided for completeness of understanding how ERROR_TERYTS are generated.
    """
    print("\n--- (Simulating First Script Logic to Identify Error TERYTs) ---")
    error_teryts_identified = set()

    # Simplified logic from your first script's create_dict_from_file1
    dict1 = {}
    try:
        with open(file1_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            expected_cols_f1 = ["TERYT Gminy"] + candidates_group1_f1
            if not all(col in reader.fieldnames for col in expected_cols_f1):
                print(f"Error (Sim): File {file1_path} missing critical cols for dict1.")
                return error_teryts_identified # Empty set

            for row in reader:
                teryt = row.get("TERYT Gminy")
                if not teryt: continue
                try:
                    sum_g1 = sum(int(row.get(cand, 0) or 0) for cand in candidates_group1_f1)
                    dict1[teryt] = (sum_g1, 0) # Second val not needed for this error check
                except ValueError:
                    dict1[teryt] = (0,0) # Default on error
    except FileNotFoundError:
        print(f"Error (Sim): File {file1_path} not found.")
        return error_teryts_identified
    except Exception as e:
        print(f"Error (Sim) reading {file1_path}: {e}")
        return error_teryts_identified

    # Simplified logic from your first script's create_dict_from_file2
    dict2 = {}
    try:
        with open(file2_path_for_context, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            expected_cols_f2 = ["TERYT Gminy", candidate1_f2_error_context]
            if not all(col in reader.fieldnames for col in expected_cols_f2):
                print(f"Error (Sim): File {file2_path_for_context} missing critical cols for dict2.")
                return error_teryts_identified

            for row in reader:
                teryt = row.get("TERYT Gminy")
                if not teryt: continue
                try:
                    val1 = int(row.get(candidate1_f2_error_context, 0) or 0)
                    dict2[teryt] = (val1, 0) # Second val not needed
                except ValueError:
                    dict2[teryt] = (0,0)
    except FileNotFoundError:
        print(f"Error (Sim): File {file2_path_for_context} not found.")
        return error_teryts_identified
    except Exception as e:
        print(f"Error (Sim) reading {file2_path_for_context}: {e}")
        return error_teryts_identified

    # Simplified comparison logic from your first script
    for teryt, val_dict1 in dict1.items():
        if teryt in dict2:
            val_dict2 = dict2[teryt]
            d1_v0 = val_dict1[0]
            d2_v0 = val_dict2[0]
            is_error_for_teryt = False

            if d1_v0 < d2_v0:
                is_error_for_teryt = True
            else:
                condition_a = (d2_v0 == 0 and d1_v0 > 0)
                condition_b = (d2_v0 > 0 and d1_v0 >= 2 * d2_v0)
                if condition_a or condition_b:
                    is_error_for_teryt = True
            
            if is_error_for_teryt:
                error_teryts_identified.add(teryt)
    
    print(f"--- (End Simulation: {len(error_teryts_identified)} error TERYTs identified conceptually) ---")
    return error_teryts_identified


def calculate_adjusted_total_votes(csv_filepath, candidate1_col, candidate2_col, error_teryts_set):
    """
    Calculates total votes for two candidates from a CSV file,
    swapping votes for specified TERYT codes.
    """
    totals = {
        candidate1_col: 0,
        candidate2_col: 0
    }
    processed_rows = 0
    swapped_teryts_count = 0

    try:
        with open(csv_filepath, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')

            # Check if candidate columns exist
            if candidate1_col not in reader.fieldnames or \
               candidate2_col not in reader.fieldnames:
                print(f"Error: One or both candidate columns ('{candidate1_col}', '{candidate2_col}') not found in {csv_filepath}.")
                return None

            for i, row in enumerate(reader):
                teryt = row.get("TERYT Gminy")
                if not teryt:
                    print(f"Warning: Missing TERYT Gminy in row {i+2} of {csv_filepath}. Skipping.")
                    continue

                try:
                    votes_cand1 = int(row.get(candidate1_col, 0) or 0)
                    votes_cand2 = int(row.get(candidate2_col, 0) or 0)
                except ValueError:
                    print(f"Warning: Non-integer vote count for TERYT {teryt} (row {i+2}) in {csv_filepath}. Treating as 0 for this row.")
                    votes_cand1 = 0
                    votes_cand2 = 0
                
                original_votes_cand1 = votes_cand1
                original_votes_cand2 = votes_cand2

                if teryt in error_teryts_set:
                    # Flip the results for this TERYT code
                    votes_cand1, votes_cand2 = votes_cand2, votes_cand1
                    swapped_teryts_count += 1
                    print(f"INFO: TERYT {teryt} is in error list. Votes swapped: "
                          f"{candidate1_col}: {original_votes_cand1}->{votes_cand1}, "
                          f"{candidate2_col}: {original_votes_cand2}->{votes_cand2}")


                totals[candidate1_col] += votes_cand1
                totals[candidate2_col] += votes_cand2
                processed_rows += 1

    except FileNotFoundError:
        print(f"Error: File {csv_filepath} not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing {csv_filepath}: {e}")
        return None

    print(f"\nProcessed {processed_rows} rows from {csv_filepath}.")
    if error_teryts_set: # Only print if there was a possibility of swapping
        print(f"Votes were swapped for {swapped_teryts_count} TERYT codes based on the provided error list.")
    
    return totals

if __name__ == "__main__":
    print(f"Calculating adjusted total votes for candidates in {FILE2_PATH}")
    print(f"Candidate 1: {CANDIDATE_1_NAME}")
    print(f"Candidate 2: {CANDIDATE_2_NAME}")

    # --- How to populate ERROR_TERYTS ---
    # Option 1: Manually define it (as shown in the ERROR_TERYTS declaration above)
    #   ERROR_TERYTS = {"TERYT_CODE_1", "TERYT_CODE_2", ...}
    #   Make sure this is done *before* this script runs, based on output from the first script.

    # Option 2: (For demonstration) Simulate getting them from the first script's logic.
    # In a real workflow, you'd run the first script, get the list, and then put it into ERROR_TERYTS.
    # This simulation requires "file1.csv" to exist.
    # Comment this out if you are manually providing ERROR_TERYTS.
    simulated_error_teryts = get_error_teryts_from_first_script_logic(FILE1_PATH, FILE2_PATH)
    if simulated_error_teryts:
         print(f"\nUsing SIMULATED error TERYTs for calculation: {simulated_error_teryts}")
         ERROR_TERYTS = simulated_error_teryts # Use the simulated list
    else:
         print("\nCould not simulate error TERYTs. If you haven't manually set ERROR_TERYTS, results will not be swapped.")


    if not ERROR_TERYTS:
        print("\nWARNING: The 'ERROR_TERYTS' set is empty. No votes will be swapped.")
        print("Please ensure you populate this set with TERYT codes identified as errors by your first script.")
    else:
        print(f"\nUsing the following TERYT codes for swapping votes: {ERROR_TERYTS}")


    adjusted_totals = calculate_adjusted_total_votes(
        FILE2_PATH,
        CANDIDATE_1_NAME,
        CANDIDATE_2_NAME,
        ERROR_TERYTS
    )

    if adjusted_totals:
        print("\n--- Adjusted Total Votes (after potential swaps) ---")
        for candidate, total_votes in adjusted_totals.items():
            print(f"{candidate}: {total_votes}")
    else:
        print("\nCould not calculate adjusted total votes due to errors.")