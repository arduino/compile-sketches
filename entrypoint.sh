#!/bin/bash

readonly CLI_VERSION="${1}"
readonly FQBN_ARG="${2}"
readonly LIBRARIES="${3}"
readonly GH_TOKEN="${4}"
readonly SIZE_REPORT_SKETCH="${5}"
ENABLE_SIZE_DELTAS_REPORT="${6}"
readonly SIZE_DELTAS_REPORT_FOLDER_NAME="${7}"
ENABLE_SIZE_TRENDS_REPORT="${8}"
readonly SIZE_TRENDS_REPORT_SPREADSHEET_ID="${9}"
readonly SIZE_TRENDS_REPORT_SHEET_NAME="${10}"

readonly SIZE_NOT_APPLICABLE_INDICATOR='"N/A"'

# Determine cli archive
readonly CLI_ARCHIVE="arduino-cli_${CLI_VERSION}_Linux_64bit.tar.gz"

declare -a -r FQBN_ARRAY="(${FQBN_ARG})"
readonly FQBN="${FQBN_ARRAY[0]}"
# Extract the core name from the FQBN
# for example arduino:avr:uno => arduino:avr
readonly CORE="$(echo "$FQBN" | cut --delimiter=':' --fields=1,2)"

# Additional Boards Manager URL
readonly ADDITIONAL_URL="${FQBN_ARRAY[1]}"

function compile_example() {
  local -r examplePath="$1"
  arduino-cli compile --verbose --warnings all --fqbn "$FQBN" "$examplePath" || {
    return $?
  }
}

# Provide a more meaningful indicator in the report when a size could not be determined
function check_sizes() {
  if [[ "$FLASH_SIZE" == "" ]]; then
    FLASH_SIZE="$SIZE_NOT_APPLICABLE_INDICATOR"
  fi
  if [[ "$RAM_SIZE" == "" ]]; then
    RAM_SIZE="$SIZE_NOT_APPLICABLE_INDICATOR"
  fi
}

# Get the memory usage from the compilation output
function compile_example_get_size_from_output() {
  local -r examplePath="$1"

  FLASH_SIZE=""
  RAM_SIZE=""

  local compilationOutput
  compilationOutput=$(compile_example "$EXAMPLE" 2>&1)
  local -r compileExampleExitStatus=$?
  # Display the compilation output
  echo "$compilationOutput"
  if [[ $compileExampleExitStatus -ne 0 ]]; then
    return $compileExampleExitStatus
  fi

  while read -r outputLine; do
    # Determine program storage memory usage
    programStorageRegex="Sketch uses ([0-9,]+) *"
    if [[ "$outputLine" =~ $programStorageRegex ]]; then
      FLASH_SIZE="${BASH_REMATCH[1]}"
      # Remove commas
      FLASH_SIZE="${FLASH_SIZE//,/}"
    fi

    # Determine dynamic memory usage
    dynamicMemoryRegex="Global variables use ([0-9,]+) *"
    if [[ "$outputLine" =~ $dynamicMemoryRegex ]]; then
      RAM_SIZE="${BASH_REMATCH[1]}"
      # Remove commas
      RAM_SIZE="${RAM_SIZE//,/}"
    fi
  done <<<"$compilationOutput"

  # Some platforms aren't configured to output RAM usage by global variables (e.g., Arduino SAM Boards), but the flash usage should at least be in the output
  if [[ "$FLASH_SIZE" == "" && "$RAM_SIZE" == "" ]]; then
    echo "::error::Something went wrong while while determining memory usage of the size-report-sketch"
    exit 1
  fi
}

if [[ "$GITHUB_EVENT_NAME" != "pull_request" ]]; then
  ENABLE_SIZE_DELTAS_REPORT='false'
fi

if [[ "$GITHUB_EVENT_NAME" != "push" ]]; then
  ENABLE_SIZE_TRENDS_REPORT='false'
fi

# If the enable-size-deltas-report argument is set to true, the size-report-sketch argument must also be defined
if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" && "$SIZE_REPORT_SKETCH" == "" ]]; then
  echo "::error::size-report-sketch argument was not defined"
  exit 1
fi

# If the enable-size-deltas-report argument is set to true, the size-deltas-report-folder-path argument must also be defined
if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" && "$SIZE_DELTAS_REPORT_FOLDER_NAME" == "" ]]; then
  echo "::error::size-deltas-report-folder-path argument was not defined"
  exit 1
fi

# If the enable-size-trends-report argument is set to true, the size-trends-report-key-file argument must also be defined
if [[ "$ENABLE_SIZE_TRENDS_REPORT" == "true" && "$INPUT_KEYFILE" == "" ]]; then
  echo "::error::size-trends-report-key-file argument was not defined"
  exit 1
fi

# If the enable-size-trends-report argument is set to true, the size-trends-report-spreadsheet-id argument must also be defined
if [[ "$ENABLE_SIZE_TRENDS_REPORT" == "true" && "$SIZE_TRENDS_REPORT_SPREADSHEET_ID" == "" ]]; then
  echo "::error::size-trends-report-spreadsheet-id argument was not defined"
  exit 1
fi

if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" || "$ENABLE_SIZE_TRENDS_REPORT" == "true" ]]; then
  apt-get install --quiet=2 --assume-yes curl >/dev/null || {
    echo "::error::Failed to install curl"
    exit 1
  }

  # https://stedolan.github.io/jq/
  apt-get install --quiet=2 --assume-yes jq >/dev/null || {
    echo "::error::Failed to install jq"
    exit 1
  }
fi

# Only publish size trends report on push to the default branch
if [[ "$ENABLE_SIZE_TRENDS_REPORT" == "true" ]]; then
  # Determine the current branch
  CURRENT_BRANCH_NAME="${GITHUB_REF##*/}"

  if [[ "$GH_TOKEN" == "" ]]; then
    # Access token is not needed for public repositories
    readonly DEFAULT_BRANCH_NAME="$(curl "https://api.github.com/repos/${GITHUB_REPOSITORY}" | jq --raw-output .default_branch)"
  else
    readonly DEFAULT_BRANCH_NAME="$(curl --header "Authorization: token ${GH_TOKEN}" "https://api.github.com/repos/${GITHUB_REPOSITORY}" | jq --raw-output .default_branch)"
  fi
  if [[ "$DEFAULT_BRANCH_NAME" == "null" ]]; then
    echo "::error::Unable to determine default branch name. Please specify the github-token argument in your workflow configuration."
    exit 1
  fi

  if [[ "$CURRENT_BRANCH_NAME" != "$DEFAULT_BRANCH_NAME" ]]; then
    ENABLE_SIZE_TRENDS_REPORT='false'
  fi
fi

# Download the arduino-cli
wget --no-verbose --directory-prefix="$HOME" "https://downloads.arduino.cc/arduino-cli/$CLI_ARCHIVE" || {
  exit 1
}

# Extract the arduino-cli to $HOME/bin
mkdir "$HOME/bin"
tar --extract --file="$HOME/$CLI_ARCHIVE" --directory="$HOME/bin" || {
  exit 1
}

# Add arduino-cli to the PATH
export PATH="$PATH:$HOME/bin"

# Update the code index and install the required CORE
if [ -z "$ADDITIONAL_URL" ]; then
  arduino-cli core update-index
  arduino-cli core install "$CORE" || {
    exit 1
  }
else
  arduino-cli core update-index --additional-urls "$ADDITIONAL_URL"
  arduino-cli core install "$CORE" --additional-urls "$ADDITIONAL_URL" || {
    exit 1
  }
fi

# Install libraries if needed
if [ -z "$LIBRARIES" ]; then
  echo "No libraries to install"
else
  # Support library names which contain whitespace
  declare -a -r LIBRARIES_ARRAY="(${LIBRARIES})"

  arduino-cli lib install "${LIBRARIES_ARRAY[@]}" || {
    exit 1
  }
fi

# Symlink the library that needs to be built in the sketchbook
mkdir --parents "$HOME/Arduino/libraries"
ln --symbolic "$PWD" "$HOME/Arduino/libraries/."

if [[ "$ENABLE_SIZE_TRENDS_REPORT" == "true" ]]; then
  apt-get install --quiet=2 --assume-yes python3 >/dev/null || {
    echo "::error::Failed to install Python"
    exit 1
  }
  apt-get install --quiet=2 --assume-yes python3-pip >/dev/null || {
    echo "::error::Failed to install pip"
    exit 1
  }
  # Install dependencies of reportsizetrends.py
  pip3 install --quiet --requirement /reportsizetrends/requirements.txt || {
    echo "::error::Failed to install Python modules"
    exit 1
  }
fi

# Find all the examples and loop build each
readonly EXAMPLES="$(find "examples/" -name '*.ino' -print0 | xargs --null dirname | uniq)"
if [[ "$EXAMPLES" == "" ]]; then
  exit 1
fi
# Set default exit status
SCRIPT_EXIT_STATUS=0
for EXAMPLE in $EXAMPLES; do
  echo "Building example $EXAMPLE"

  if [[ ("$ENABLE_SIZE_DELTAS_REPORT" != "true" && "$ENABLE_SIZE_TRENDS_REPORT" != "true") || "${EXAMPLE##*/}" != "$SIZE_REPORT_SKETCH" ]]; then
    # Don't determine size
    compile_example "$EXAMPLE" || {
      SCRIPT_EXIT_STATUS="$?"
    }
    continue
  elif [[ ("$ENABLE_SIZE_DELTAS_REPORT" == "true" || "$ENABLE_SIZE_TRENDS_REPORT" == "true") && "${EXAMPLE##*/}" == "$SIZE_REPORT_SKETCH" ]]; then
    # Do determine size

    # Determine memory usage of the sketch at the tip of the pull request branch
    compile_example_get_size_from_output "$EXAMPLE" || {
      SCRIPT_EXIT_STATUS="$?"
      continue
    }
    check_sizes

    # Install Git
    if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" || "$ENABLE_SIZE_TRENDS_REPORT" == "true" ]]; then
      apt-get install --quiet=2 --assume-yes git >/dev/null || {
        echo "::error::Failed to install git"
        exit 1
      }
    fi

    readonly CURRENT_FLASH_SIZE="$FLASH_SIZE"
    readonly CURRENT_RAM_SIZE="$RAM_SIZE"

    if [[ "$ENABLE_SIZE_TRENDS_REPORT" == "true" ]]; then
      readonly SHORT_COMMIT_HASH="$(git rev-parse --short HEAD)"
      python3 /reportsizetrends/reportsizetrends.py --spreadsheet-id "$SIZE_TRENDS_REPORT_SPREADSHEET_ID" --sheet-name "$SIZE_TRENDS_REPORT_SHEET_NAME" --google-key-file "$INPUT_KEYFILE" --sketch-name="$EXAMPLE" --commit-hash="$SHORT_COMMIT_HASH" --commit-url="https://github.com/${GITHUB_REPOSITORY}/commit/${SHORT_COMMIT_HASH}" --fqbn="$FQBN" --flash="$CURRENT_FLASH_SIZE" --ram="$CURRENT_RAM_SIZE" || {
        echo "::error::Could not update size trends report spreadsheet"
        exit 1
      }
    fi

    if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" ]]; then
      # Determine memory usage of the sketch at the tip of the target repository's default branch

      # Save the commit hash for the tip of the pull request branch
      readonly CURRENT_COMMIT="$(git rev-parse HEAD)"

      # checkout the tip of the pull request's base branch

      # Determine the pull request number, to use for the GitHub API request
      readonly PULL_REQUEST_NUMBER="$(jq --raw-output '.pull_request.number' "$GITHUB_EVENT_PATH")"
      if [[ "$GH_TOKEN" == "" ]]; then
        # Access token is not needed for public repositories
        readonly BASE_BRANCH_NAME="$(curl "https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls/${PULL_REQUEST_NUMBER}" | jq --raw-output .base.ref)"
      else
        readonly BASE_BRANCH_NAME="$(curl --header "Authorization: token ${GH_TOKEN}" "https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls/${PULL_REQUEST_NUMBER}" | jq --raw-output .base.ref)"
      fi
      if [[ "$BASE_BRANCH_NAME" == "null" ]]; then
        echo "::error::Unable to determine base branch name. Please specify the size-report-github-token argument in your workflow configuration."
        exit 1
      fi
      git checkout "$BASE_BRANCH_NAME" || {
        echo "::error::Failed to checkout base branch"
        exit 1
      }

      # Compile the example sketch and get the sizes
      compile_example_get_size_from_output "$EXAMPLE"
      check_sizes

      if [[ "$CURRENT_FLASH_SIZE" == "$SIZE_NOT_APPLICABLE_INDICATOR" || "$FLASH_SIZE" == "$SIZE_NOT_APPLICABLE_INDICATOR" ]]; then
        FLASH_DELTA="$SIZE_NOT_APPLICABLE_INDICATOR"
      else
        FLASH_DELTA="$((CURRENT_FLASH_SIZE - FLASH_SIZE))"
      fi
      echo "Change in flash memory usage: $FLASH_DELTA"
      if [[ "$CURRENT_RAM_SIZE" == "$SIZE_NOT_APPLICABLE_INDICATOR" || "$RAM_SIZE" == "$SIZE_NOT_APPLICABLE_INDICATOR" ]]; then
        RAM_DELTA="$SIZE_NOT_APPLICABLE_INDICATOR"
      else
        RAM_DELTA="$((CURRENT_RAM_SIZE - RAM_SIZE))"
      fi
      echo "Change in RAM used by globals: $RAM_DELTA"

      # Create the report folder
      readonly SIZE_REPORT_FOLDER_PATH="${GITHUB_WORKSPACE}/${SIZE_DELTAS_REPORT_FOLDER_NAME}"
      if ! [[ -d "$SIZE_REPORT_FOLDER_PATH" ]]; then
        mkdir --parents "$SIZE_REPORT_FOLDER_PATH"
      fi
      # Create the report file
      readonly SIZE_REPORT_FILE_PATH="${SIZE_REPORT_FOLDER_PATH}/${FQBN//:/-}.json"
      echo "{\"fqbn\": \"${FQBN}\", \"sketch\": \"${EXAMPLE}\", \"previous_flash\": ${FLASH_SIZE}, \"flash\": ${CURRENT_FLASH_SIZE}, \"flash_delta\": ${FLASH_DELTA}, \"previous_ram\": ${RAM_SIZE}, \"ram\": ${CURRENT_RAM_SIZE}, \"ram_delta\": ${RAM_DELTA}}" | jq . >"$SIZE_REPORT_FILE_PATH"

      # Switch back to the previous commit in the repository
      git checkout "$CURRENT_COMMIT" || {
        echo "::error::Could not checkout the PR's head branch"
        exit 1
      }
    fi
  fi
done

exit $SCRIPT_EXIT_STATUS
