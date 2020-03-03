# libraries/compile-examples action

This action compiles all of the examples contained in the library.

## Inputs

### `cli-version`

The version of `arduino-cli` to use. Default `"latest"`.

### `fqbn`

The fully qualified board name to use when compiling. Default `"arduino:avr:uno"`.
For 3rd party boards, also specify the Boards Manager URL:
```yaml
  fqbn: '"sandeepmistry:nRF5:Generic_nRF52832" "https://sandeepmistry.github.io/arduino-nRF5/package_nRF5_boards_index.json"'
```

### `libraries`

List of library dependencies to install (space separated). Default `""`.

### `github-token`

GitHub access token used to get information from the GitHub API. Only needed if you're using the size report features with private repositories. It will be convenient to use [`${{ secrets.GITHUB_TOKEN }}`](https://help.github.com/en/actions/configuring-and-managing-workflows/authenticating-with-the-github_token). Default `""`.

### `size-report-sketch`

Name of the sketch used to compare memory usage change. Default `""`.

### `enable-size-deltas-report`

Set to `true` to cause the action to determine the change in memory usage for the [`size-reports-sketch`](#size-reports-sketch) between the pull request branch and the tip of the pull request's base branch. This may be used with the [`arduino/actions/libraries/report-size-deltas` action](https://github.com/arduino/actions/tree/master/libraries/report-size-deltas). Default `false`.

### `size-deltas-report-folder-name`

Folder to save the JSON formatted memory usage change reports to. Should be used only to store reports. It will be created under [`GITHUB_WORKSPACE`](https://help.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables). The folder will be created if it doesn't already exist. Default `"size-deltas-reports"`.

## Example usage

Only compiling examples:
```yaml
- uses: arduino/actions/libraries/compile-examples@master
  with:
    fqbn: 'arduino:avr:uno'
```

Storing the memory usage change report as a [workflow artifact](https://help.github.com/en/actions/configuring-and-managing-workflows/persisting-workflow-data-using-artifacts):
```yaml
- uses: arduino/actions/libraries/compile-examples@master
  with:
    size-report-sketch: Foobar
    enable-size-deltas-report: true
- if: github.event_name == 'pull_request'
  uses: actions/upload-artifact@v1
  with:
    name: size-deltas-reports
    path: size-delta-reports
```
