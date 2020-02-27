#!/bin/bash

CLI_VERSION=$1
FQBN_ARG=$2
LIBRARIES=$3

# Determine cli archive
CLI_ARCHIVE=arduino-cli_${CLI_VERSION}_Linux_64bit.tar.gz

declare -a -r FQBN_ARRAY="(${FQBN_ARG})"
FQBN="${FQBN_ARRAY[0]}"
# Extract the core name from the FQBN
# for example arduino:avr:uno => arduino:avr
CORE=`echo "$FQBN" | cut -d':' -f1,2`

# Additional Boards Manager URL
ADDITIONAL_URL="${FQBN_ARRAY[1]}"

# Download the arduino-cli
wget --no-verbose -P $HOME https://downloads.arduino.cc/arduino-cli/$CLI_ARCHIVE

# Extract the arduino-cli to $HOME/bin
mkdir $HOME/bin
tar xf $HOME/$CLI_ARCHIVE -C $HOME/bin

# Add arduino-cli to the PATH
export PATH=$PATH:$HOME/bin

# Update the code index and install the required CORE
if [ -z "$ADDITIONAL_URL" ]; then
  arduino-cli core update-index
  arduino-cli core install $CORE
else
  arduino-cli core update-index --additional-urls $ADDITIONAL_URL
  arduino-cli core install $CORE --additional-urls $ADDITIONAL_URL
fi

# Install libraries if needed
if [ -z "$LIBRARIES" ]
then
  echo "No libraries to install"
else
  # Support library names which contain whitespace
  declare -a -r LIBRARIES_ARRAY="(${LIBRARIES})"

  arduino-cli lib install "${LIBRARIES_ARRAY[@]}"
fi

# Symlink the library that needs to be built in the sketchbook
mkdir -p $HOME/Arduino/libraries
ln -s $PWD $HOME/Arduino/libraries/.

# Find all the examples and loop build each
EXAMPLES=`find examples/ -name '*.ino' | xargs dirname | uniq`
# Set default exit status
SCRIPT_EXIT_STATUS=0
for EXAMPLE in $EXAMPLES; do
  echo Building example $EXAMPLE
  arduino-cli compile --verbose --warnings all --fqbn $FQBN $EXAMPLE
  ARDUINO_CLI_EXIT_STATUS=$?
  if [[ $ARDUINO_CLI_EXIT_STATUS -ne 0 ]]; then
    SCRIPT_EXIT_STATUS=$ARDUINO_CLI_EXIT_STATUS
  fi
done

exit $SCRIPT_EXIT_STATUS
