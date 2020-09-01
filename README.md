# libraries/compile-examples action

This action checks whether Arduino sketches compile and produces a report of data from the compilations.

## Inputs

### `cli-version`

The version of [Arduino CLI](https://github.com/arduino/arduino-cli) to use. Default `"latest"`.

### `fqbn`

The fully qualified board name to use when compiling. Default `"arduino:avr:uno"`.

If the board is from one of the platforms provided by Arduino's [default package index](https://downloads.arduino.cc/packages/package_index.json), the board's platform dependency will be automatically detected and the latest version installed. For boards of platforms not in the default package index, previous versions, or other platform sources, the platform dependency must be defined via the [`platforms` input](#platforms).

### `platforms`

YAML-format list of platform dependencies to install.

Default `""`. If no `platforms` input is provided, the board's dependency will be automatically determined from the `fqbn` input and the latest version of that platform will be installed via Boards Manager.

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

#### Sources:

##### Boards Manager

Keys:
- `name` - platform name in the form of `VENDOR:ARCHITECTURE`.
- `version` - version of the platform to install. Default is the latest version.
- `source-url` - Boards Manager URL of the platform. Default is Arduino's package index, which allows installation of all official platforms.

##### Local path

Keys:
- `source-path` - path to install as a platform. Relative paths are assumed to be relative to the root of the repository.
- `name` - platform name in the form of `VENDOR:ARCHITECTURE`.

##### Repository

Keys:
- `source-url` - URL to clone the repository from. It must start with `git://` or end with `.git`.
- `version` - [Git ref](https://git-scm.com/book/en/v2/Git-Internals-Git-References) of the repository to checkout. The special version name `latest` will cause the latest tag to be used. By default, the repository will be checked out to the tip of the default branch.
- `source-path` - path to install as a platform. Paths are relative to the root of the repository. The default is to install from the root of the repository.
- `name` - platform name in the form of `VENDOR:ARCHITECTURE`.

##### Archive download

Keys:
- `source-url` - download URL for the archive (e.g., `https://github.com/arduino/ArduinoCore-avr/archive/master.zip`).
- `source-path` - path to install as a platform. Paths are relative to the root folder of the archive, or the root of the archive if it has no root folder. The default is to install from the root folder of the archive.
- `name` - platform name in the form of `VENDOR:ARCHITECTURE`.

### `libraries`

YAML-format list of library dependencies to install.

Default `"- source-path: ./"`. This causes the repository to be installed as a library. If there are no library dependencies and you want to override the default, set the `libraries` input to an empty list (`- libraries: '-'`).

Libraries are installed under the Arduino user folder at `~/Arduino/libraries`.

Note: when the deprecated space-separated list format of this input is used, the repository under test will always be installed as a library.

#### Sources:

##### Library Manager

Keys:
- `name` - name of the library, as defined in the `name` field of its [library.properties](https://arduino.github.io/arduino-cli/latest/library-specification/#libraryproperties-file-format) metadata file. The library will be installed to a folder matching the name, but with any spaces replaced by `_`.
- `version` - version of the library to install. Default is the latest version.

##### Local path

Keys:
- `source-path` - path to install as a library. Relative paths are assumed to be relative to the root of the repository.
- `destination-name` - folder name to install the library to. By default, the folder will be named according to the source repository or subfolder name.

##### Repository

Keys:
- `source-url` - URL to clone the repository from. It must start with `git://` or end with `.git`.
- `version` - [Git ref](https://git-scm.com/book/en/v2/Git-Internals-Git-References) of the repository to checkout. The special version name `latest` will cause the latest tag to be used. By default, the repository will be checked out to the tip of the default branch.
- `source-path` - path to install as a library. Paths are relative to the root of the repository. The default is to install from the root of the repository.
- `destination-name` - folder name to install the library to. By default, the folder will be named according to the source repository or subfolder name.

##### Archive download

Keys:
- `source-url` - download URL for the archive (e.g., `https://github.com/arduino-libraries/Servo/archive/master.zip`).
- `source-path` - path to install as a library. Paths are relative to the root folder of the archive, or the root of the archive if it has no root folder. The default is to install from the root folder of the archive.
- `destination-name` - folder name to install the library to. By default, the folder will be named according to the source archive or subfolder name.

### `sketch-paths`

List of paths containing sketches to compile. These paths will be searched recursively. Default `"examples"`.

### `verbose`

Set to true to show verbose output in the log. Default `false`

### `sketches-report-path`

Path in which to save a JSON formatted file containing data from the sketch compilations. Should be used only to store reports. Relative paths are relative to [`GITHUB_WORKSPACE`](https://help.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables). The folder will be created if it doesn't already exist. This report is used by the `arduino/actions/libraries/report-size-deltas` and `arduino/actions/libraries/report-size-trends` actions. Default `"size-deltas-reports"`.

### `github-token`

GitHub access token used to get information from the GitHub API. Only needed for private repositories with `enable-size-deltas-report` set to `true`. It will be convenient to use [`${{ secrets.GITHUB_TOKEN }}`](https://help.github.com/en/actions/configuring-and-managing-workflows/authenticating-with-the-github_token). Default `""`.

### `enable-size-deltas-report`

Set to `true` to cause the action to determine the change in memory usage of the compiled sketches. If the workflow is triggered by a `pull_request` event, the comparison is between the pull request branch and the tip of the pull request's base branch. If the workflow is triggered by a `push` event, the comparison is between the pushed commit and its immediate parent. This may be used with the [`arduino/actions/libraries/report-size-deltas` action](https://github.com/arduino/actions/tree/master/libraries/report-size-deltas). Default `false`.

## Example usage

Only compiling examples:
```yaml
- uses: arduino/actions/libraries/compile-examples@master
  with:
    fqbn: 'arduino:avr:uno'
    libraries: |
      - name: Servo
      - name: Stepper
        version: 1.1.3
```

Storing the memory usage change report as a [workflow artifact](https://help.github.com/en/actions/configuring-and-managing-workflows/persisting-workflow-data-using-artifacts):
```yaml
- uses: arduino/actions/libraries/compile-examples@master
  with:
    enable-size-deltas-report: true
- if: github.event_name == 'pull_request'
  uses: actions/upload-artifact@v1
  with:
    name: size-deltas-reports
    path: size-delta-reports
```
