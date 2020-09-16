# `arduino/compile-sketches` action

[![Tests](https://github.com/arduino/compile-sketches/workflows/Test%20Python%20code/badge.svg)](https://github.com/arduino/compile-sketches/actions?workflow=Test+Python+code)
[![Lint](https://github.com/arduino/compile-sketches/workflows/Lint%20Python%20code/badge.svg)](https://github.com/arduino/compile-sketches/actions?workflow=Lint+Python+code)
[![Spell Check](https://github.com/arduino/compile-sketches/workflows/Spell%20Check/badge.svg)](https://github.com/arduino/compile-sketches/actions?workflow=Spell+Check)
[![codecov](https://codecov.io/gh/arduino/compile-sketches/branch/master/graph/badge.svg)](https://codecov.io/gh/arduino/compile-sketches)

This action checks whether [Arduino](https://www.arduino.cc/) sketches compile and produces a report of data from the compilations.

## Table of contents

<!-- toc -->

- [Inputs](#inputs)
  - [`cli-version`](#cli-version)
  - [`fqbn`](#fqbn)
  - [`platforms`](#platforms)
    - [Supported platform sources:](#supported-platform-sources)
      - [Boards Manager](#boards-manager)
      - [Local path](#local-path)
      - [Repository](#repository)
      - [Archive download](#archive-download)
  - [`libraries`](#libraries)
    - [Supported library sources:](#supported-library-sources)
      - [Library Manager](#library-manager)
      - [Local path](#local-path-1)
      - [Repository](#repository-1)
      - [Archive download](#archive-download-1)
  - [`sketch-paths`](#sketch-paths)
  - [`verbose`](#verbose)
  - [`sketches-report-path`](#sketches-report-path)
  - [`github-token`](#github-token)
  - [`enable-deltas-report`](#enable-deltas-report)
    - [How it works](#how-it-works)
  - [`enable-warnings-report`](#enable-warnings-report)
- [Example usage](#example-usage)

<!-- tocstop -->

## Inputs

### `cli-version`

The version of [Arduino CLI](https://github.com/arduino/arduino-cli) to use.

**Default**: `"latest"`

### `fqbn`

The fully qualified board name to use when compiling.

**Default**: `"arduino:avr:uno"`

If the board is from one of the platforms provided by Arduino's [default package index](https://downloads.arduino.cc/packages/package_index.json), the board's platform dependency will be automatically detected and the latest version installed. For boards of platforms not in the default package index, previous versions, or other platform sources, the platform dependency must be defined via the [`platforms` input](#platforms).

### `platforms`

[YAML](https://en.wikipedia.org/wiki/YAML)-format list of platform dependencies to install.

**Default**: The board's dependency will be automatically determined from the `fqbn` input and the latest version of that platform will be installed via Boards Manager.

If a platform dependency from a non-Boards Manager source of the same name as another Boards Manager source platform dependency is defined, they will both be installed, with the non-Boards Manager dependency overwriting the Boards Manager platform installation. This permits testing against a non-release version of a platform while using Boards Manager to install the platform's tools dependencies.
Example:
```yaml
platforms: |
  # Install the latest release of Arduino SAMD Boards and its toolchain via Boards Manager
  - name: "arduino:samd"
  # Install the platform from the root of the repository, replacing the BM installed platform
  - source-path: "."
    name: "arduino:samd"
```

#### Supported platform sources:

##### Boards Manager

Keys:
- **`name`** - (**required**) platform name in the form of `VENDOR:ARCHITECTURE` (e.g., `arduino:avr`).
- **`version`** - version of the platform to install.
  - **Default**: the latest version.
- **`source-url`** - Boards Manager URL of the platform.
  - **Default**: Arduino's package index, which allows installation of all official platforms.

##### Local path

Keys:
- **`source-path`** - (**required**) path to install as a platform. Relative paths are assumed to be relative to the root of the repository.
- **`name`** - (**required**) platform name in the form of `VENDOR:ARCHITECTURE` (e.g., `arduino:avr`).

##### Repository

Keys:
- **`source-url`** - (**required**) URL to clone the repository from. It must start with `git://` or end with `.git`.
- **`name`** -  (**required**) platform name in the form of `VENDOR:ARCHITECTURE` (e.g., `arduino:avr`).
- **`version`** - [Git ref](https://git-scm.com/book/en/v2/Git-Internals-Git-References) of the repository to checkout. The special version name `latest` will cause the latest tag to be used.
  - **Default**: the repository is checked out to the tip of the default branch.
- **`source-path`** - path to install as a platform. Paths are relative to the root of the repository.
  - **Default**: root of the repository.

##### Archive download

Keys:
- **`source-url`** -  (**required**) download URL for the archive (e.g., `https://github.com/arduino/ArduinoCore-avr/archive/master.zip`).
- **`name`** -  (**required**) platform name in the form of `VENDOR:ARCHITECTURE` (e.g., `arduino:avr`).
- **`source-path`** - path to install as a platform. Paths are relative to the root folder of the archive, or the root of the archive if it has no root folder.
  - **Default**: root folder of the archive.

### `libraries`

[YAML](https://en.wikipedia.org/wiki/YAML)-format list of library dependencies to install.

**Default**: `"- source-path: ./"`
This causes the repository to be installed as a library. If there are no library dependencies and you want to override the default, set the `libraries` input to an empty list (`- libraries: '-'`).

Libraries are installed under the Arduino user folder at `~/Arduino/libraries`.

**Note**: when the deprecated space-separated list format of this input is used, the repository under test will always be installed as a library.

#### Supported library sources:

##### Library Manager

Keys:
- **`name`** - (**required**) name of the library, as defined in the `name` field of its [library.properties](https://arduino.github.io/arduino-cli/latest/library-specification/#libraryproperties-file-format) metadata file.
- **`version`** - version of the library to install.
  - **Default**: the latest version.

**Notes**:
- The library will be installed to a folder matching its name, but with any spaces replaced by `_`.
- If the library's author defined dependencies, those libraries will be installed automatically.

##### Local path

Keys:
- **`source-path`** - (**required**) path to install as a library. Relative paths are assumed to be relative to the root of the repository.
- **`destination-name`** - folder name to install the library to.
  - **Default**: the folder will be named according to the source repository or subfolder name.

##### Repository

Keys:
- **`source-url`** - (**required**) URL to clone the repository from. It must start with `git://` or end with `.git`.
- **`version`** - [Git ref](https://git-scm.com/book/en/v2/Git-Internals-Git-References) of the repository to checkout. The special version name `latest` will cause the latest tag to be used.
  - **Default**: the tip of the default branch.
- **`source-path`** - path to install as a library. Paths are relative to the root of the repository.
  - **Default**: root of the repository.
- **`destination-name`** - folder name to install the library to.
  - **Default**: named according to the source repository or subfolder name.

##### Archive download

Keys:
- **`source-url`** - (**required**) download URL for the archive (e.g., `https://github.com/arduino-libraries/Servo/archive/master.zip`).
- **`source-path`** - path to install as a library. Paths are relative to the root folder of the archive, or the root of the archive if it has no root folder.
  - **Default**: root folder of the archive.
- **`destination-name`** - folder name to install the library to.
  - **Default**: named according to the source archive or subfolder name.

### `sketch-paths`

[YAML](https://en.wikipedia.org/wiki/YAML)-format list of paths containing sketches to compile. These paths will be searched recursively.

**Default**: `"- examples"`

### `verbose`

Set to true to show verbose output in the log.

**Default**: `false`

### `sketches-report-path`

Path in which to save a JSON formatted file containing data from the sketch compilations. Should be used only to store reports. Relative paths are relative to [`GITHUB_WORKSPACE`](https://help.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables). The folder will be created if it doesn't already exist.

This report is used by the [`arduino/report-size-deltas`](https://github.com/arduino/report-size-deltas) and [`arduino/report-size-trends`](https://github.com/arduino/report-size-trends) actions.

**Default**: `"sketches-reports"`

### `github-token`

GitHub access token used to get information from the GitHub API. Only needed for private repositories with [`enable-deltas-report`](#enable-deltas-report) set to `true`. It will be convenient to use [`${{ secrets.GITHUB_TOKEN }}`](https://help.github.com/en/actions/configuring-and-managing-workflows/authenticating-with-the-github_token).

**Default**: `""`

### `enable-deltas-report`

Set to `true` to cause the action to determine the change in memory usage and compiler warnings of the compiled sketches.

If the workflow is triggered by a [`pull_request` event](https://docs.github.com/en/actions/reference/events-that-trigger-workflows#pull_request), the comparison is between the pull request branch and the tip of the pull request's base branch.

If the workflow is triggered by a [`push` event](https://docs.github.com/en/actions/reference/events-that-trigger-workflows#push), the comparison is between the pushed commit and its immediate parent.

The deltas will be displayed in the GitHub Actions build log.

This report may be used with the [`arduino/report-size-deltas` action](https://github.com/arduino/report-size-deltas).

**Default**: `false`

#### How it works

The sketch is first compiled with the repository in [`$GITHUB_WORKSPACE`](https://docs.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables#default-environment-variables) at the state it was at before the action's step. Data from the compilation is recorded in the sketches report. Next, a [`git checkout`] to the [Git ref](https://git-scm.com/book/en/v2/Git-Internals-Git-References) used as the base of the comparison is done and the compilation + data recording process repeated. The delta is the change in the data between the two compilations.

Dependencies defined via the [`libraries`](#libraries) or [`platforms`](#platforms) inputs are installed via [symlinks](https://en.wikipedia.org/wiki/Symbolic_link), meaning dependencies from local paths under `$GITHUB_WORKSPACE` reflect the deltas checkouts even though they are installed outside `$GITHUB_WORKSPACE`.

### `enable-warnings-report`

Set to `true` to cause the action to record the compiler warning count for each sketch compilation in the sketches report.

**Default**: `false`

## Example usage

```yaml
- uses: arduino/compile-sketches@main
  with:
    fqbn: 'arduino:avr:uno'
    libraries: |
      - name: Servo
      - name: Stepper
        version: 1.1.3
```
