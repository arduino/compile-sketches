#!/bin/bash -x

CLI_VERSION=$1
FQBN=$2
LIBRARIES=$3

# Determine cli archive
CLI_ARCHIVE=arduino-cli_${CLI_VERSION}_Linux_64bit.tar.gz

# Extract the core name from the FQBN
# for example arduino:avr:uno => arduino:avr
CORE=`echo "$FQBN" | cut -d':' -f1,2`

# Download the arduino-cli
wget -P $HOME https://downloads.arduino.cc/arduino-cli/$CLI_ARCHIVE

# Extract the arduino-cli to $HOME/bin
mkdir $HOME/bin
tar xf $HOME/$CLI_ARCHIVE -C $HOME/bin

# Add arduino-cli to the PATH
export PATH=$PATH:$HOME/bin

# Update the code index and install the required CORE
arduino-cli core update-index
arduino-cli core install $CORE

# Install libraries if needed
if [ -z "$LIBRARIES" ]
then
  echo "No libraries to install"
else
  arduino-cli lib install $LIBRARIES
fi

# Symlink the library that needs to be built in the sketchbook
mkdir -p $HOME/Arduino/libraries
ln -s $PWD $HOME/Arduino/libraries/.

# Find all the examples and loop build each
EXAMPLES=`find examples/ -name '*.ino' | xargs dirname | uniq`
for EXAMPLE in $EXAMPLES; do
  echo Building example $EXAMPLE
  arduino-cli compile --verbose --warnings all --fqbn $FQBN $EXAMPLE
done || exit 1