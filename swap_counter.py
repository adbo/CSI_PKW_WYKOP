import csv

# Define candidate groups and individual candidates for clarity
# For File 1
candidates_group1_f1 = ["ZANDBERG Adrian Tadeusz", "TRZASKOWSKI Rafał Kazimierz", "BIEJAT Magdalena Agnieszka"]
candidates_group2_f1 = ["BRAUN Grzegorz Michał", "MENTZEN Sławomir Jerzy", "NAWROCKI Karol Tadeusz"]

# For File 2
candidate1_f2 = "TRZASKOWSKI Rafał Kazimierz" # This will be dict2_value[0]
candidate2_f2 = "NAWROCKI Karol Tadeusz"    # This will be dict2_value[1]

def create_dict_from_file1(filename):
    """
    Creates a dictionary from the first CSV file.
    Key: "TERYT Gminy"
    Value: (sum_of_votes_for_group1, sum_of_votes_for_group2)
    """
    data_dict1 = {}
    try:
        with open(filename, mode='r', encoding='utf-8-sig') as csvfile: # utf-8-sig handles BOM
            reader = csv.DictReader(csvfile, delimiter=';')
            expected_cols = ["TERYT Gminy"] + candidates_group1_f1 + candidates_group2_f1
            # Basic check for essential columns in the header
            if not all(col in reader.fieldnames for col in expected_cols):
                missing = [col for col in expected_cols if col not in reader.fieldnames]
                print(f"Error: File {filename} is missing critical columns: {missing}")
                return None

            for i, row in enumerate(reader):
                teryt = row.get("TERYT Gminy")
                if not teryt:
                    print(f"Warning: Missing TERYT Gminy in row {i+2} of {filename}. Skipping.")
                    continue
                try:
                    sum_g1 = sum(int(row.get(cand, 0) or 0) for cand in candidates_group1_f1)
                    sum_g2 = sum(int(row.get(cand, 0) or 0) for cand in candidates_group2_f1)
                    data_dict1[teryt] = (sum_g1, sum_g2)
                except ValueError as e:
                    print(f"Warning: ValueError for TERYT {teryt} (row {i+2}) in {filename}: {e}. Check data for non-integer vote counts. Treating as 0 for affected candidate(s).")
                    # Attempt partial sum if possible, or skip if critical
                    sum_g1_robust = 0
                    for cand in candidates_group1_f1:
                        try: sum_g1_robust += int(row.get(cand, 0) or 0)
                        except: pass # ignore error for this specific candidate's vote
                    sum_g2_robust = 0
                    for cand in candidates_group2_f1:
                        try: sum_g2_robust += int(row.get(cand, 0) or 0)
                        except: pass
                    data_dict1[teryt] = (sum_g1_robust, sum_g2_robust)

    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {filename}: {e}")
        return None
    return data_dict1

def create_dict_from_file2(filename):
    """
    Creates a dictionary from the second CSV file.
    Key: "TERYT Gminy"
    Value: (votes_for_candidate1, votes_for_candidate2)
    """
    data_dict2 = {}
    try:
        with open(filename, mode='r', encoding='utf-8-sig') as csvfile: # utf-8-sig handles BOM
            reader = csv.DictReader(csvfile, delimiter=';')
            expected_cols = ["TERYT Gminy", candidate1_f2, candidate2_f2]
            if not all(col in reader.fieldnames for col in expected_cols):
                missing = [col for col in expected_cols if col not in reader.fieldnames]
                print(f"Error: File {filename} is missing critical columns: {missing}")
                return None

            for i, row in enumerate(reader):
                teryt = row.get("TERYT Gminy")
                if not teryt:
                    print(f"Warning: Missing TERYT Gminy in row {i+2} of {filename}. Skipping.")
                    continue
                try:
                    val1 = int(row.get(candidate1_f2, 0) or 0)
                    val2 = int(row.get(candidate2_f2, 0) or 0)
                    data_dict2[teryt] = (val1, val2)
                except ValueError as e:
                    print(f"Warning: ValueError for TERYT {teryt} (row {i+2}) in {filename}: {e}. Check data for non-integer vote counts. Treating as 0.")
                    val1_robust = 0
                    try: val1_robust = int(row.get(candidate1_f2, 0) or 0)
                    except: pass
                    val2_robust = 0
                    try: val2_robust = int(row.get(candidate2_f2, 0) or 0)
                    except: pass
                    data_dict2[teryt] = (val1_robust, val2_robust)

    except FileNotFoundError:
        print(f"Error: File {filename} not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {filename}: {e}")
        return None
    return data_dict2

def compare_dictionaries(dict1, dict2):
    """
    Compares the two dictionaries based on the specified proportionality rule.
    An error is counted if value[0] from dict1 is not "closer" to value[0] from dict2.
    """
    if dict1 is None or dict2 is None:
        print("Cannot compare dictionaries due to earlier file reading errors.")
        return 0
        
    error_count = 0
    common_keys_count = 0

    for teryt, val_dict1 in dict1.items():
        if teryt in dict2:
            common_keys_count += 1
            val_dict2 = dict2[teryt]
            
            d1_v0, d1_v1 = val_dict1 # d1_v0 = sum(Zandberg, Trzaskowski_f1, Biejat)
            d2_v0, d2_v1 = val_dict2 # d2_v0 = Trzaskowski_f2

            is_error_for_teryt = False
            error_reason = ""

            # --- Start of error condition as per prompt ---
            # Rule: "value[0] from dict1 should be closer to value[0] from dict2"
            # This means d1_v0 should be "closer" to d2_v0.

            # Step 1: Basic data integrity for the first component.
            # d1_v0 (sum of 3, incl. Trzaskowski) cannot be less than d2_v0 (Trzaskowski alone).
            if d1_v0 < d2_v0:
                error_reason = (f"Data Inconsistency: Dict1_val0 ({d1_v0}) < Dict2_val0 ({d2_v0}). "
                                f"Sum of group cannot be less than one of its components.")
                is_error_for_teryt = True
            else:
                # Step 2: Check "closeness" for the first component based on our interpretation.
                # "Not closer" if:
                #   a) Main candidate (d2_v0) has 0 votes, but group sum (d1_v0) has >0 votes.
                #   b) Main candidate (d2_v0) has >0 votes, but others in group (d1_v0 - d2_v0) 
                #      got AS MANY OR MORE votes than the main one (d2_v0).
                #      Condition: (d1_v0 - d2_v0) >= d2_v0  which simplifies to  d1_v0 >= 2 * d2_v0
                
                condition_a = (d2_v0 == 0 and d1_v0 > 0)
                condition_b = (d2_v0 > 0 and d1_v0 >= 2 * d2_v0) # Trzaskowski got <= 50% of his group's vote

                if condition_a:
                    error_reason = (f"Not 'closer': Main candidate in dict2 (Trzaskowski, d2_v0={d2_v0}) has 0 votes, "
                                    f"but group sum in dict1 (d1_v0={d1_v0}) is positive.")
                    is_error_for_teryt = True
                elif condition_b:
                    others_in_d1_v0 = d1_v0 - d2_v0
                    error_reason = (f"Not 'closer': Other candidates in dict1 group1 ({others_in_d1_v0} votes) "
                                    f"are >= main candidate in dict2 (Trzaskowski, d2_v0={d2_v0} votes). "
                                    f"Dict1_group_sum={d1_v0}.")
                    is_error_for_teryt = True
            # --- End of error condition as per prompt ---
            
            if is_error_for_teryt:
                print(f"ERROR: TERYT {teryt} - {error_reason}")
                error_count += 1
            
            # Informational: A general consistency check for the second components.
            # This is not part of the error count as per the strict interpretation of the prompt.
            if d1_v1 < d2_v1: # sum(Braun, Mentzen, Nawrocki_f1) < Nawrocki_f2
                 print(f"INFO (Not an error by prompt): TERYT {teryt} - Data Inconsistency for second components: "
                       f"Dict1_val1 ({d1_v1}) < Dict2_val1 ({d2_v1}).")
        else:
            print(f"Warning: TERYT {teryt} from file1 not found in file2.")
            
    print(f"\nComparison finished. Processed {common_keys_count} common TERYT codes.")
    if common_keys_count == 0 and (dict1 and len(dict1) > 0) and (dict2 and len(dict2) > 0) :
        print("Warning: No common TERYT codes found between the two files. "
              "Please check 'TERYT Gminy' columns and file contents.")
    return error_count

# --- Main script execution ---
if __name__ == "__main__":
    # IMPORTANT: Replace with your actual filenames
    # Ensure these files are in the same directory as the script, or provide full paths.
    file1_path = "wyniki_gl_na_kandydatow_po_gminach_utf8.csv" 
    file2_path = "wyniki_gl_na_kandydatow_po_gminach_w_drugiej_turze_utf8.csv" 

    print(f"Processing {file1_path}...")
    dictionary1 = create_dict_from_file1(file1_path)
    
    print(f"\nProcessing {file2_path}...")
    dictionary2 = create_dict_from_file2(file2_path)

    if dictionary1 and dictionary2:
        print(f"\nComparing dictionaries (Dict1: {len(dictionary1)} entries, Dict2: {len(dictionary2)} entries)...")
        total_errors = compare_dictionaries(dictionary1, dictionary2)
        print(f"\nTotal errors based on the 'proportionality' (closeness of first tuple elements) rule: {total_errors}")
    else:
        print("\nComparison aborted due to errors in reading one or both files.")