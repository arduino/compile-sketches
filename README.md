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

### `platforms`

YAML-format list of platform dependencies to install.

Default `""`. If no `platforms` input is provided, the board's dependency will be automatically determined from the `fqbn` input and the latest version of that platform will be installed via Board Manager.

#### Sources:

##### Board Manager

Keys:
- `name` - platform name in the form of `VENDOR:ARCHITECTURE`.
- `version` - version of the platform to install. Default is the latest version.

### `libraries`

YAML-format list of library dependencies to install.

Default `"- source-path: ./"`. This causes the repository to be installed as a library. If there are no library dependencies and you want to override the default, set the `libraries` input to an empty list (`- libraries: '-'`).

Note: the original space-separated list format is also supported. When this syntax is used, the repository under test will always be installed as a library.

#### Sources:

##### Library Manager

Keys:
- `name` - name of the library.
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

### `github-token`

GitHub access token used to get information from the GitHub API. Only needed if you're using the size report features with private repositories. It will be convenient to use [`${{ secrets.GITHUB_TOKEN }}`](https://help.github.com/en/actions/configuring-and-managing-workflows/authenticating-with-the-github_token). Default `""`.

### `size-report-sketch`

Name of the sketch used to compare memory usage change. Default `""`.

### `enable-size-deltas-report`

Set to `true` to cause the action to determine the change in memory usage for the [`size-reports-sketch`](#size-reports-sketch) between the pull request branch and the tip of the pull request's base branch. This may be used with the [`arduino/actions/libraries/report-size-deltas` action](https://github.com/arduino/actions/tree/master/libraries/report-size-deltas). Default `false`.

### `size-deltas-report-folder-name`

Folder to save the JSON formatted memory usage change reports to. Should be used only to store reports. It will be created under [`GITHUB_WORKSPACE`](https://help.github.com/en/actions/configuring-and-managing-workflows/using-environment-variables). The folder will be created if it doesn't already exist. Default `"size-deltas-reports"`.

### `enable-size-trends-report`

Set to `true` to cause the action to record the memory usage of [`size-reports-sketch`](#size-reports-sketch) to a Google Sheets spreadsheet on every push to the repository's default branch. Default `false`.

### `keyfile`

Contents of the Google key file used to update the size trends report Google Sheets spreadsheet. This should be defined using a [GitHub secret](https://help.github.com/en/actions/configuring-and-managing-workflows/creating-and-storing-encrypted-secrets). Default `""`.
1. Open https://console.developers.google.com/project
1. Click the "Create Project" button.
1. In the "Project name" field, enter the name you want for your project.
1. You don't need to select anything from the "Location" menu.
1. Click the button with the three horizontal lines at the top left corner of the window.
1. Hover the mouse pointer over "APIs & Services".
1. Click "Library".
1. Make sure the name of the project you created is selected from the dropdown menu at the top of the window.
1. Click 'Google Sheets API".
1. Click the "Enable" button.
1. Click the "Create Credentials" button.
1. From the "Which API are you using?" menu, select "Google Sheets API".
1. From the "Where will you be calling the API from?" menu, select "Other non-UI".
1. From the "What data will you be accessing?" options, select "Application data".
1. From the "Are you planning to use this API with App Engine or Compute Engine?" options, select "No, I’m not using them".
1. Click the "What credentials do I need?" button.
1. In the "Service account name" field, enter the name you want to use for the service account.
1. From the "Role" menu, select "Project > Editor".
1. From the "Key type" options, select "JSON".
1. Click the "Continue" button. The .json file containing your private key will be downloaded. Save this somewhere safe.
1. Open the downloaded file.
1. Copy the entire contents of the file to the clipboard.
1. Open the GitHub page of the repository you are configuring the GitHub Actions workflow for.
1. Click the "Settings" tab.
1. From the menu on the left side of the window, click "Secrets".
1. Click the "Add a new secret" link.
1. In the "Name" field, enter the variable name you want to use for your secret. This will be used for the `size-trends-report-key-file` argument of the `compile-examples` action in your workflow configuration file. For example, if you named the secret `GOOGLE_KEY_FILE`, you would reference it in your workflow configuration as `${{ secrets.GOOGLE_KEY_FILE }}`.
1. In the "Value" field, paste the contents of the key file.
1. Click the "Add secret" button.
1. Open the downloaded key file again.
1. Copy the email address shown in the `client_email` field.
1. Open Google Sheets: https://docs.google.com/spreadsheets
1. Under "Start a new spreadsheet", click "Blank".
1. Click the "Share" button at the top right corner of the window.
1. If you haven't already, give your spreadsheet a name.
1. Paste the `client_email` email address into the "Enter names or email addresses..." field.
1. Uncheck the box next to "Notify people".
1. Click the "OK" button.
1. In the "Skip sending invitations?" dialog, click the "OK" button.

### `size-trends-report-spreadsheet-id`

The ID of the Google Sheets spreadsheet to write the memory usage trends data to. The URL of your spreadsheet will look something like `https://docs.google.com/spreadsheets/d/15WOp3vp-6AnTnWlNWaNWNl61Fe_j8UJhIKE0rVdV-7U/edit#gid=0`. In this example, the spreadsheet ID is `15WOp3vp-6AnTnWlNWaNWNl61Fe_j8UJhIKE0rVdV-7U`. Default `""`.

### `size-trends-report-sheet-name`

The sheet name in the Google Sheets spreadsheet used for the memory usage trends report. Default `"Sheet1"`.

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
    size-report-sketch: Foobar
    enable-size-deltas-report: true
- if: github.event_name == 'pull_request'
  uses: actions/upload-artifact@v1
  with:
    name: size-deltas-reports
    path: size-delta-reports
```

Publishing memory usage trends data to a Google Sheets spreadsheet:
```yaml
- uses: arduino/actions/libraries/compile-examples@master
  with:
    size-report-sketch: Foobar
    enable-size-trends-report: true
    keyfile: ${{ secrets.GOOGLE_KEY_FILE }}
    size-trends-report-spreadsheet-id: 15WOp3vp-6AnTnWlNWaNWNl61Fe_j8UJhIKE0rVdV-7U
```
