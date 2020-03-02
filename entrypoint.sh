#!/bin/bash

readonly CLI_VERSION="$1"
readonly FQBN_ARG="$2"
readonly LIBRARIES="$3"

# Determine cli archive
readonly CLI_ARCHIVE="arduino-cli_${CLI_VERSION}_Linux_64bit.tar.gz"

declare -a -r FQBN_ARRAY="(${FQBN_ARG})"
readonly FQBN="${FQBN_ARRAY[0]}"
# Extract the core name from the FQBN
# for example arduino:avr:uno => arduino:avr
readonly CORE="$(echo "$FQBN" | cut --delimiter=':' --fields=1,2)"

# Additional Boards Manager URL
readonly ADDITIONAL_URL="${FQBN_ARRAY[1]}"

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

# Find all the examples and loop build each
readonly EXAMPLES="$(find "examples/" -name '*.ino' -print0 | xargs --null dirname | uniq)"
if [[ "$EXAMPLES" == "" ]]; then
  exit 1
fi
# Set default exit status
SCRIPT_EXIT_STATUS=0
for EXAMPLE in $EXAMPLES; do
  echo "Building example $EXAMPLE"
  arduino-cli compile --verbose --warnings all --fqbn "$FQBN" "$EXAMPLE" || {
    SCRIPT_EXIT_STATUS="$?"
  }
done

exit $SCRIPT_EXIT_STATUS
