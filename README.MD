# Election Data Analysis and Anomaly Detection Scripts

This project provides Python scripts for in-depth analysis of election data, designed to identify potential anomalies and inconsistencies between different rounds of voting (or different datasets). It attempts to categorize these anomalies and generates a detailed report, as well as a list of administrative units (TERYTs) where significant ratio shifts between candidates are detected. An additional script can then use this list to perform optional vote adjustments.

## Project Structure

- `config.py`: Central configuration hub for file paths, key candidate names for analysis, CSV settings, and thresholds for anomaly detection.
- `error_identifier.py`:
    - Loads election data from two primary CSV files (e.g., Round 1 and Round 2 results).
    - Performs a detailed, ratio-based analysis for two key candidates, checking for various anomaly types (e.g., zero votes in R2 despite R1 support, disproportionate R2 results compared to R1, extreme reversals).
    - Assigns an anomaly level for each TERYT (e.g., `LARGE_ANOMALY_A_LOST_SHARE_VS_B`, `NO_ANOMALY`, `DATA_ISSUE_INVALID_VOTES`).
    - Generates a comprehensive `election_ratio_analysis_report.json` file detailing the findings for each TERYT.
    - Generates a `significant_ratio_shifts_teryts.txt` file containing TERYTs where a significant or suspicious ratio shift is detected, intended for use by `vote_adjuster.py`.
    - Produces a human-readable summary in `election_ratio_analysis_summary.txt`.
- `vote_adjuster.py`:
    - Reads a specified CSV file (typically Round 2 results).
    - Reads the `significant_ratio_shifts_teryts.txt` file.
    - For TERYTs listed in the file, it swaps the vote counts between two pre-configured candidates.
    - Outputs the recalculated total votes and a summary report.
- `test_error_identifier.py`: Pytest unit tests for `error_identifier.py`.
- `test_vote_adjuster.py`: Pytest unit tests for `vote_adjuster.py`.
- `pyproject.toml`: Project metadata and dependency specification for PDM (Python Development Master).
- `pdm.lock`: Lock file ensuring reproducible builds with PDM, detailing exact versions of all dependencies.
- `.gitignore`: Specifies intentionally untracked files that Git should ignore (e.g., virtual environments, cache files, output reports).
- `README.md`: This file, providing an overview and instructions.

Input data CSV files (e.g., `wyniki_gl_na_kandydatow_po_gminach_utf8.csv`) are expected to be in the project's root directory, or their paths must be correctly configured in `config.py`.

## Setup Instructions (using PDM)

### 1. Prerequisites

- Python 3.7+ (Python 3.8+ recommended for optimal PDM integration).
- PDM (Python Development Master). If PDM is not installed on your system, please refer to the [official PDM installation guide](https://pdm-project.org/latest/usage/installation/).
  A common method for installing PDM on Linux/macOS is:
  ```bash
  curl -sSL https://pdm-project.org/install-pdm.py | python3 -
  ```
  After installation, ensure PDM's binary directory is included in your system's PATH. This might require restarting your terminal session or re-sourcing your shell's configuration file (e.g., `source ~/.bashrc` or `source ~/.zshrc`).
  Verify the installation by running: `pdm --version`.

### 2. Clone the Repository (if applicable)

If you are obtaining this project from a Git repository:
```bash
git clone <repository_url>
cd <repository_directory_name>
```

### 3. Initialize Project and Install Dependencies

PDM utilizes `pyproject.toml` for managing project metadata and dependencies. If you've cloned the repository, `pyproject.toml` and `pdm.lock` should already be present.

**Install all project dependencies (including development tools like pytest):**
```bash
pdm install
```
This command will:
- Parse `pyproject.toml` and `pdm.lock`.
- Automatically create and manage a virtual environment (typically located at `.venv/` within the project directory, as per PDM's default behavior or your `pdm init` configuration).
- Install all required packages into this isolated environment, ensuring a consistent and reproducible setup.

If you are initiating this project from scratch and `pyproject.toml` is not yet created, you would typically start with `pdm init` to generate it, followed by `pdm add --dev pytest` (and commands for any other necessary dependencies), which also handles their installation.

### 4. Prepare Data Files

Ensure your input CSV files are located in the project's root directory, or alternatively, update their paths within the `config.py` file. The default configuration expects:
- `wyniki_gl_na_kandydatow_po_gminach_utf8.csv`
- `wyniki_gl_na_kandydatow_po_gminach_w_drugiej_turze_utf8.csv`

## Workflow and Running the Scripts (using PDM)

Execute all scripts within the PDM-managed environment by prefixing commands with `pdm run`.

### 1. Perform Ratio-Based Anomaly Analysis

This script is the core of the anomaly detection process. It analyzes data from the configured Round 1 and Round 2 CSV files using ratio-based logic.
```bash
pdm run python error_identifier.py
```
**Outputs:**
- `election_ratio_analysis_report.json`: A detailed JSON file containing the analysis results for each common TERYT, including raw vote counts, anomaly levels, and a description of the detected anomaly.
- `significant_ratio_shifts_teryts.txt`: A simple text file listing TERYT codes where the analysis suggests a significant or suspicious ratio shift between the two main configured candidates. This file serves as input for the `vote_adjuster.py` script.
- `election_ratio_analysis_summary.txt`: A human-readable summary of the anomaly analysis.

**It is highly recommended to review `election_ratio_analysis_report.json` and the summary before proceeding with vote adjustments.**

### 2. Adjust Vote Counts (Optional, based on analysis)

This script uses the `significant_ratio_shifts_teryts.txt` generated in the previous step to perform vote adjustments.
```bash
pdm run python vote_adjuster.py
```
The script will read the specified Round 2 results file, swap votes for the configured candidates in the listed TERYTs, and then print a summary report of the adjusted total votes to the console.

## Running Unit Tests (using PDM)

The project includes a suite of unit tests developed with `pytest` to verify the functionality of the core logic. To execute these tests:
```bash
pdm run pytest
```

## Working with PDM - Common Commands

- **Add a new runtime dependency to the project:**
  ```bash
  pdm add <package_name>
  ```
- **Add a new development dependency (e.g., a linter or a new testing tool):**
  ```bash
  pdm add --dev <package_name>
  ```
  Alternatively, to add to a specific development group (e.g., the `test` group, which might already exist for `pytest`):
  ```bash
  pdm add -dG test <package_name>
  ```
- **Update all project dependencies to their latest permissible versions (respecting constraints in `pdm.lock` and `pyproject.toml`):**
  ```bash
  pdm update
  ```
- **Activate the PDM-managed shell:**
  For interactive work within the project's virtual environment without needing to prefix every command with `pdm run`:
  ```bash
  pdm shell
  ```
  Within this activated shell, you can directly execute commands like `python error_identifier.py` or `pytest`.
  To exit the PDM shell, type `exit`.
- **List installed packages within the PDM environment:**
  ```bash
  pdm list
  ```

## Configuration

Critical operational parameters are centralized in `config.py`. This includes:
- Paths to input and output data files.
- Names of key candidates for analysis and vote adjustment.
- CSV processing settings (delimiter, encoding).
- Thresholds used in the anomaly detection logic (e.g., `SMALL_ANOMALY_RATIO_CHANGE_FACTOR`, `LARGE_ANOMALY_RATIO_CHANGE_FACTOR`, `MIN_ABS_VOTE_SHIFT_FOR_SIGNIFICANT_ANOMALY`).

Review and modify `config.py` to match your specific dataset, analytical requirements, and candidate focus.