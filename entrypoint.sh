#!/bin/bash

readonly CLI_VERSION="$1"
readonly FQBN_ARG="$2"
readonly LIBRARIES="$3"
readonly GH_TOKEN="$4"
readonly SIZE_REPORT_SKETCH="$5"
ENABLE_SIZE_DELTAS_REPORT="$6"
readonly SIZE_DELTAS_REPORT_FOLDER_NAME="$7"

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

# Get value from a key=value properties list file
function get_property_value() {
  local -r filePath="$1"
  local -r key="$2"

  local propertyValue
  propertyValue="$(grep --regex='^[[:blank:]]*'"$key"'[[:blank:]]*=' "$filePath" | cut --delimiter='=' --fields=2)"
  # Strip leading spaces
  propertyValue="${propertyValue#"${propertyValue%%[! ]*}"}"
  # Strip trailing spaces
  propertyValue="${propertyValue%"${propertyValue##*[! ]}"}"

  echo "$propertyValue"
}

function compile_example() {
  local -r examplePath="$1"
  arduino-cli compile --verbose --warnings all --fqbn "$FQBN" --output "${OUTPUT_FOLDER_PATH}/${OUTPUT_NAME}" "$examplePath" || {
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
  local compilationOutput

  FLASH_SIZE=""
  RAM_SIZE=""

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

  # Some hardware cores aren't configured to output RAM usage by global variables, but the flash usage should at least be in the output
  if [[ "$FLASH_SIZE" == "" && "$RAM_SIZE" == "" ]]; then
    echo "::error::Something went wrong while while determining memory usage of the size-report-sketch"
    exit 1
  fi
}

# Parse the compiler size command to determine memory usage
function get_size_from_size_output() {
  local -r sizeOutput="$1"
  local -r sizeRegex="$2"

  local -r sizeOutputLines="$(echo "$sizeOutput" | grep --perl-regexp --regex="$sizeRegex")"

  local totalSize=0
  while read -r -a replyArray; do
    local replyValue="${replyArray[1]}"
    totalSize="$((totalSize + replyValue))"
  done <<<"$sizeOutputLines"

  if [[ "$totalSize" == "" ]]; then
    echo "::error::Something went wrong while while determining memory usage of the size-report-sketch"
    exit 1
  fi

  echo "$totalSize"
}

# Use the compiler size command to determine memory usage
function compile_example_get_size_from_size_cmd() {
  local -r examplePath="$1"

  FLASH_SIZE=""
  RAM_SIZE=""

  compile_example "$EXAMPLE" || {
    return $?
  }

  local -r size_output="$("$COMPILER_SIZE_CMD_PATH" -A "${OUTPUT_FOLDER_PATH}/${OUTPUT_NAME}.elf")"
  FLASH_SIZE="$(get_size_from_size_output "$size_output" "$RECIPE_SIZE_REGEX")"
  RAM_SIZE="$(get_size_from_size_output "$size_output" "$RECIPE_SIZE_REGEX_DATA")"
}

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

if [[ "$GITHUB_EVENT_NAME" != "pull_request" ]]; then
  ENABLE_SIZE_DELTAS_REPORT='false'
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

if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" ]]; then
  # https://stedolan.github.io/jq/
  apt-get install --quiet=2 --assume-yes jq >/dev/null || {
    echo "::error::Failed to install jq"
    exit 1
  }
fi

GET_SIZE_FROM_OUTPUT=true
if [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" && ("$CORE" == "arduino:sam" || "$CORE" == "arduino:samd") ]]; then
  # arduino-cli doesn't report RAM usage for Arduino SAM Boards or Arduino SAMD Boards and doesn't include the data section in the flash usage report, so it's necessary to determine the sizes independently
  GET_SIZE_FROM_OUTPUT=false

  DATA_DIRECTORY_PATH="$(arduino-cli config dump --format json | jq --raw-output '.directories.data')"
  DATA_DIRECTORY_PATH="${DATA_DIRECTORY_PATH//\"/}"

  readonly VENDOR="$(echo "$FQBN" | cut --delimiter=':' --fields=1)"
  readonly ARCHITECTURE="$(echo "$FQBN" | cut --delimiter=':' --fields=2)"
  readonly PLATFORM_TXT_PATH="$(find "${DATA_DIRECTORY_PATH}/packages/${VENDOR}/hardware/${ARCHITECTURE}" -name platform.txt)"
  if [[ "$PLATFORM_TXT_PATH" == "" ]]; then
    echo "::error::Unable to find platform folder"
    exit 1
  fi

  readonly COMPILER_SIZE_CMD="$(get_property_value "$PLATFORM_TXT_PATH" 'compiler\.size\.cmd')"
  readonly COMPILER_SIZE_CMD_PATH="$(find "$DATA_DIRECTORY_PATH/packages/$VENDOR/tools" -name "$COMPILER_SIZE_CMD")"
  if [[ "$COMPILER_SIZE_CMD_PATH" == "" ]]; then
    echo "::error::Unable to find compiler size tool"
    exit 1
  fi

  readonly RECIPE_SIZE_REGEX='(?:\.text|\.data)\s+[0-9]'
  readonly RECIPE_SIZE_REGEX_DATA='(?:\.data|\.bss)\s+[0-9]'
fi

# Create a folder for the compilation output files
readonly OUTPUT_FOLDER_PATH="$(mktemp -d)"
# The name of the output files. arduino-cli adds the file extensions.
readonly OUTPUT_NAME='output'

# Find all the examples and loop build each
readonly EXAMPLES="$(find "examples/" -name '*.ino' -print0 | xargs --null dirname | uniq)"
if [[ "$EXAMPLES" == "" ]]; then
  exit 1
fi
# Set default exit status
SCRIPT_EXIT_STATUS=0
for EXAMPLE in $EXAMPLES; do
  echo "Building example $EXAMPLE"

  if [[ "$ENABLE_SIZE_DELTAS_REPORT" != "true" || "${EXAMPLE##*/}" != "$SIZE_REPORT_SKETCH" ]]; then
    # Don't determine size
    compile_example "$EXAMPLE" || {
      SCRIPT_EXIT_STATUS="$?"
    }
    continue
  elif [[ "$ENABLE_SIZE_DELTAS_REPORT" == "true" && "${EXAMPLE##*/}" == "$SIZE_REPORT_SKETCH" ]]; then
    # Do determine size

    # Determine memory usage of the sketch at the tip of the pull request branch
    if [[ "$GET_SIZE_FROM_OUTPUT" == "true" ]]; then
      compile_example_get_size_from_output "$EXAMPLE" || {
        SCRIPT_EXIT_STATUS="$?"
        continue
      }
    else
      compile_example_get_size_from_size_cmd "$EXAMPLE" || {
        SCRIPT_EXIT_STATUS="$?"
        continue
      }
    fi
    check_sizes

    CURRENT_FLASH_SIZE="$FLASH_SIZE"
    CURRENT_RAM_SIZE="$RAM_SIZE"

    # Determine memory usage of the sketch at the tip of the target repository's default branch
    apt-get install --quiet=2 --assume-yes git >/dev/null || {
      echo "::error::Failed to install git"
      exit 1
    }

    # Save the commit hash for the tip of the pull request branch
    readonly CURRENT_COMMIT="$(git rev-parse HEAD)"

    # checkout the tip of the pull request's base branch
    apt-get install --quiet=2 --assume-yes curl >/dev/null || {
      echo "::error::Failed to install curl"
      exit 1
    }

    # Determine the pull request number, to use for the GitHub API request
    readonly PULL_REQUEST_NUMBER="$(jq --raw-output '.pull_request.number' "$GITHUB_EVENT_PATH")"
    if [[ "$GH_TOKEN" == "" ]]; then
      # Access token is not needed for public repositories
      readonly BASE_BRANCH_NAME="$(curl "https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls/${PULL_REQUEST_NUMBER}" | jq --raw-output .base.ref)"
    else
      readonly BASE_BRANCH_NAME="$(curl --header "Authorization: token ${GH_TOKEN}" "https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls/${PULL_REQUEST_NUMBER}" | jq --raw-output .base.ref)"
    fi
    if [[ "$BASE_BRANCH_NAME" == "null" ]]; then
      echo "::error::Unable to determine base branch name. Please specify the github-token argument in your workflow configuration."
      exit 1
    fi
    git checkout "$BASE_BRANCH_NAME" || {
      echo "::error::Failed to checkout base branch"
      exit 1
    }

    # Compile the example sketch and get the sizes
    if [[ "$GET_SIZE_FROM_OUTPUT" == "true" ]]; then
      compile_example_get_size_from_output "$EXAMPLE"
    else
      compile_example_get_size_from_size_cmd "$EXAMPLE"
    fi
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
done

exit $SCRIPT_EXIT_STATUS
