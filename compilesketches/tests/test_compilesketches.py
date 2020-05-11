import filecmp
import json
import os
import pathlib
import subprocess
import tarfile
import unittest.mock
import urllib
import urllib.request

import git
import github
import pytest

import compilesketches
import reportsizetrends

test_data_path = pathlib.PurePath(os.path.dirname(os.path.realpath(__file__)), "testdata")


def get_compilesketches_object(
    cli_version=unittest.mock.sentinel.cli_version,
    fqbn_arg="foo fqbn_arg",
    libraries="foo libraries",
    sketch_paths="foo sketch_paths",
    verbose="false",
    github_token="",
    report_sketch=unittest.mock.sentinel.report_sketch,
    enable_size_deltas_report="false",
    sketches_report_path="foo report_folder_name",
    enable_size_trends_report="false",
    google_key_file=unittest.mock.sentinel.google_key_file,
    size_trends_report_spreadsheet_id=unittest.mock.sentinel.size_trends_report_spreadsheet_id,
    size_trends_report_sheet_name=unittest.mock.sentinel.size_trends_report_sheet_name
):
    return compilesketches.CompileSketches(cli_version=cli_version,
                                           fqbn_arg=fqbn_arg,
                                           libraries=libraries,
                                           sketch_paths=sketch_paths,
                                           verbose=verbose,
                                           github_token=github_token,
                                           report_sketch=report_sketch,
                                           enable_size_deltas_report=enable_size_deltas_report,
                                           sketches_report_path=sketches_report_path,
                                           enable_size_trends_report=enable_size_trends_report,
                                           google_key_file=google_key_file,
                                           size_trends_report_spreadsheet_id=size_trends_report_spreadsheet_id,
                                           size_trends_report_sheet_name=size_trends_report_sheet_name
                                           )


def test_main(monkeypatch, mocker):
    cli_version = "1.0.0"
    fqbn_arg = "foo:bar:baz"
    libraries = "foo libraries"
    sketch_paths = "foo/Sketch bar/OtherSketch"
    verbose = "true"
    github_token = "FooGitHubToken"
    report_sketch = "FooReportSketch"
    enable_size_deltas_report = "true"
    sketches_report_path = "FooSizeDeltasReportFolderName"
    enable_size_trends_report = "true"
    google_key_file = "FooKeyfile"
    size_trends_report_spreadsheet_id = "FooSpreadsheetID"
    size_trends_report_sheet_name = "FooSheetName"

    class CompileSketches:
        def compile_sketches(self):
            pass

    monkeypatch.setenv("INPUT_CLI-VERSION", cli_version)
    monkeypatch.setenv("INPUT_FQBN", fqbn_arg)
    monkeypatch.setenv("INPUT_LIBRARIES", libraries)
    monkeypatch.setenv("INPUT_SKETCH-PATHS", sketch_paths)
    monkeypatch.setenv("INPUT_GITHUB-TOKEN", github_token)
    monkeypatch.setenv("INPUT_VERBOSE", verbose)
    monkeypatch.setenv("INPUT_SIZE-REPORT-SKETCH", report_sketch)
    monkeypatch.setenv("INPUT_ENABLE-SIZE-DELTAS-REPORT", enable_size_deltas_report)
    monkeypatch.setenv("INPUT_SIZE-DELTAS-REPORT-FOLDER-NAME", sketches_report_path)
    monkeypatch.setenv("INPUT_ENABLE-SIZE-TRENDS-REPORT", enable_size_trends_report)
    monkeypatch.setenv("INPUT_KEYFILE", google_key_file)
    monkeypatch.setenv("INPUT_SIZE-TRENDS-REPORT-SPREADSHEET-ID", size_trends_report_spreadsheet_id)
    monkeypatch.setenv("INPUT_SIZE-TRENDS-REPORT-SHEET-NAME", size_trends_report_sheet_name)

    mocker.patch("compilesketches.CompileSketches", autospec=True, return_value=CompileSketches())
    mocker.patch.object(CompileSketches, "compile_sketches")

    compilesketches.main()

    compilesketches.CompileSketches.assert_called_once_with(
        cli_version=cli_version,
        fqbn_arg=fqbn_arg,
        libraries=libraries,
        sketch_paths=sketch_paths,
        verbose=verbose,
        github_token=github_token,
        report_sketch=report_sketch,
        enable_size_deltas_report=enable_size_deltas_report,
        sketches_report_path=sketches_report_path,
        enable_size_trends_report=enable_size_trends_report,
        google_key_file=google_key_file,
        size_trends_report_spreadsheet_id=size_trends_report_spreadsheet_id,
        size_trends_report_sheet_name=size_trends_report_sheet_name
    )
    CompileSketches.compile_sketches.assert_called_once()


def test_compilesketches():
    expected_fqbn = "foo:bar:baz"
    expected_additional_url = "https://example.com/package_foo_index.json"
    cli_version = unittest.mock.sentinel.cli_version
    libraries = unittest.mock.sentinel.libraries
    sketch_paths = "examples/FooSketchPath examples/BarSketchPath"
    expected_sketch_paths_list = [pathlib.PurePath("examples/FooSketchPath"),
                                  pathlib.PurePath("examples/BarSketchPath")]
    verbose = "false"
    github_token = "fooGitHubToken"
    report_sketch = unittest.mock.sentinel.report_sketch
    enable_size_deltas_report = "true"
    sketches_report_path = "FooSketchesReportFolder"
    enable_size_trends_report = "false"
    google_key_file = unittest.mock.sentinel.google_key_file
    size_trends_report_spreadsheet_id = unittest.mock.sentinel.size_trends_report_spreadsheet_id
    size_trends_report_sheet_name = unittest.mock.sentinel.size_trends_report_sheet_name

    compile_sketches = compilesketches.CompileSketches(
        cli_version=cli_version,
        fqbn_arg="\'\"" + expected_fqbn + "\" \"" + expected_additional_url + "\"\'",
        libraries=libraries,
        sketch_paths=sketch_paths,
        verbose=verbose,
        github_token=github_token,
        report_sketch=report_sketch,
        enable_size_deltas_report=enable_size_deltas_report,
        sketches_report_path=sketches_report_path,
        enable_size_trends_report=enable_size_trends_report,
        google_key_file=google_key_file,
        size_trends_report_spreadsheet_id=size_trends_report_spreadsheet_id,
        size_trends_report_sheet_name=size_trends_report_sheet_name
    )

    assert compile_sketches.cli_version == cli_version
    assert compile_sketches.fqbn == expected_fqbn
    assert compile_sketches.additional_url == expected_additional_url
    assert compile_sketches.libraries == libraries
    assert compile_sketches.sketch_paths == expected_sketch_paths_list
    assert compile_sketches.verbose is False
    assert compile_sketches.report_sketch == report_sketch
    assert compile_sketches.enable_size_deltas_report is True
    assert compile_sketches.sketches_report_path == pathlib.PurePath(sketches_report_path)
    assert compile_sketches.enable_size_trends_report is False
    assert compile_sketches.google_key_file == google_key_file
    assert compile_sketches.size_trends_report_spreadsheet_id == size_trends_report_spreadsheet_id
    assert compile_sketches.size_trends_report_sheet_name == size_trends_report_sheet_name

    # Test invalid enable_size_deltas_report value
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_size_deltas_report="fooInvalidEnableSizeDeltasBoolean")

    # Test invalid enable_size_trends_report value
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_size_trends_report="fooInvalidEnableSizeTrendsBoolean")

    # Test undefined google_key_file
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_size_trends_report="true", google_key_file="")

    # Test undefined size_trends_report_spreadsheet_id
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_size_trends_report="true", size_trends_report_spreadsheet_id="")

    # Test undefined report_sketch
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_size_deltas_report="true", report_sketch="")

    # Test undefined report_sketch
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_size_trends_report="true", report_sketch="")


@pytest.mark.parametrize("compilation_success_list, expected_success",
                         [([True, True, True], True),
                          ([False, True, True], False),
                          ([True, False, True], False),
                          ([True, True, False], False)])
@pytest.mark.parametrize("do_size_trends_report", [True, False])
@pytest.mark.parametrize("report_sketch", [unittest.mock.sentinel.report_sketch, ""])
def test_compile_sketches(mocker, compilation_success_list, expected_success, do_size_trends_report,
                          report_sketch):
    sketch_list = [unittest.mock.sentinel.sketch1, unittest.mock.sentinel.sketch2, unittest.mock.sentinel.sketch3]

    compilation_result_list = []
    for success in compilation_success_list:
        compilation_result_list.append(type("CompilationResult", (), {"success": success}))
    sketch_report = unittest.mock.sentinel.sketch_report
    sketch_report_from_sketches_report = unittest.mock.sentinel.sketch_report_from_sketches_report

    compile_sketches = get_compilesketches_object(report_sketch=report_sketch)

    mocker.patch("compilesketches.CompileSketches.install_arduino_cli", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_platforms", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries", autospec=True)
    mocker.patch("compilesketches.CompileSketches.find_sketches", autospec=True, return_value=sketch_list)
    mocker.patch("compilesketches.CompileSketches.compile_sketch", autospec=True, side_effect=compilation_result_list)
    mocker.patch("compilesketches.CompileSketches.get_sketch_report", autospec=True, return_value=sketch_report)
    mocker.patch("compilesketches.CompileSketches.get_sketch_report_from_sketches_report", autospec=True,
                 return_value=sketch_report_from_sketches_report)
    mocker.patch("compilesketches.CompileSketches.do_size_trends_report", autospec=True,
                 return_value=do_size_trends_report)
    mocker.patch("compilesketches.CompileSketches.make_size_trends_report", autospec=True)
    mocker.patch("compilesketches.CompileSketches.create_sketches_report_file", autospec=True)

    if expected_success:
        compile_sketches.compile_sketches()
    else:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            compile_sketches.compile_sketches()

    compile_sketches.install_arduino_cli.assert_called_once()
    compile_sketches.install_platforms.assert_called_once()
    compile_sketches.install_libraries.assert_called_once()
    compile_sketches.find_sketches.assert_called_once()

    compile_sketch_calls = []
    get_sketch_report_calls = []
    sketch_sizes = []
    for sketch, compilation_result in zip(sketch_list, compilation_result_list):
        compile_sketch_calls.append(unittest.mock.call(compile_sketches, sketch_path=sketch))
        get_sketch_report_calls.append(unittest.mock.call(compile_sketches, compilation_result=compilation_result))
        sketch_sizes.append(sketch_report)
    compile_sketches.compile_sketch.assert_has_calls(calls=compile_sketch_calls)
    compile_sketches.get_sketch_report.assert_has_calls(calls=get_sketch_report_calls)

    if report_sketch == "":
        compile_sketches.get_sketch_report_from_sketches_report.assert_not_called()
        compile_sketches.do_size_trends_report.assert_not_called()
        compile_sketches.make_size_trends_report.assert_not_called()
        compile_sketches.create_sketches_report_file.assert_not_called()
    else:
        compile_sketches.get_sketch_report_from_sketches_report.assert_called_once_with(compile_sketches,
                                                                                        sketches_report=sketch_sizes)
        compile_sketches.do_size_trends_report.assert_called_once()

        if do_size_trends_report:
            compile_sketches.make_size_trends_report.assert_called_once_with(
                compile_sketches,
                sketch_report=sketch_report_from_sketches_report
            )
        else:
            compile_sketches.make_size_trends_report.assert_not_called()

        compile_sketches.create_sketches_report_file.assert_called_once_with(
            compile_sketches,
            sketches_report=sketch_report_from_sketches_report
        )


def test_install_arduino_cli(tmpdir, mocker):
    cli_version = "1.2.3"
    arduino_cli_user_directory_path = pathlib.PurePath("/foo/arduino_cli_user_directory_path")
    source_file_path = test_data_path.joinpath("githubevent.json")
    # Create temporary folder
    arduino_cli_installation_path = pathlib.PurePath(tmpdir.mkdir("test_install_arduino_cli"))
    output_archive_path = arduino_cli_installation_path.joinpath("foo_archive.tar.gz")

    # Create an archive file
    with tarfile.open(name=output_archive_path, mode="w:gz") as tar:
        tar.add(name=source_file_path, arcname=source_file_path.name)

    compile_sketches = get_compilesketches_object(cli_version=cli_version)
    compile_sketches.arduino_cli_installation_path = arduino_cli_installation_path
    compile_sketches.arduino_cli_user_directory_path = arduino_cli_user_directory_path

    # Patch urllib.request.urlopen so that the generated archive file is opened instead of the Arduino CLI download
    mocker.patch("urllib.request.urlopen",
                 return_value=urllib.request.urlopen(url="file:///" + str(output_archive_path)))

    compile_sketches.install_arduino_cli()

    urllib.request.urlopen.assert_called_once_with(url="https://downloads.arduino.cc/arduino-cli/arduino-cli_"
                                                       + cli_version + "_Linux_64bit.tar.gz")

    # Verify that the installation matches the source file
    assert filecmp.cmp(f1=source_file_path, f2=arduino_cli_installation_path.joinpath(source_file_path.name)) is True

    assert os.environ["ARDUINO_DIRECTORIES_USER"] == str(arduino_cli_user_directory_path)


@pytest.mark.parametrize(
    "fqbn_arg, expected_platform, expected_additional_url_list",
    [("arduino:avr:uno", "arduino:avr", []),
     ('\'"foo bar:baz:asdf" "https://example.com/platform_foo_index.json"\'', "foo bar:baz",
      ["https://example.com/platform_foo_index.json"])]
)
def test_install_platforms(mocker, fqbn_arg, expected_platform, expected_additional_url_list):
    compile_sketches = get_compilesketches_object(fqbn_arg=fqbn_arg)

    mocker.patch("compilesketches.CompileSketches.install_platforms_from_board_manager", autospec=True)

    compile_sketches.install_platforms()

    compile_sketches.install_platforms_from_board_manager.assert_called_once_with(
        compile_sketches,
        platform_list=[expected_platform],
        additional_url_list=expected_additional_url_list
    )


@pytest.mark.parametrize(
    "dependency_list, expected_dependency_type_list",
    [([None], []),
     ([{compilesketches.CompileSketches.dependency_source_path_key: "foo/bar"}], ["path"]),
     ([{compilesketches.CompileSketches.dependency_name_key: "FooBar"}], ["manager"])]
)
def test_sort_dependency_list(monkeypatch, dependency_list, expected_dependency_type_list):
    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/GitHubWorkspace")

    compile_sketches = get_compilesketches_object()

    for dependency, expected_dependency_type in zip(dependency_list, expected_dependency_type_list):
        assert dependency in getattr(compile_sketches.sort_dependency_list(dependency_list=[dependency]),
                                     expected_dependency_type)


@pytest.mark.parametrize("additional_url_list",
                         [["https://example.com/package_foo_index.json", "https://example.com/package_bar_index.json"],
                          []])
def test_install_platforms_from_board_manager(mocker, additional_url_list):
    run_command_output_level = unittest.mock.sentinel.run_command_output_level
    platform_list = [unittest.mock.sentinel.platform1, unittest.mock.sentinel.platform2]

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_run_command_output_level", autospec=True,
                 return_value=run_command_output_level)
    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True)

    compile_sketches.install_platforms_from_board_manager(platform_list=platform_list,
                                                          additional_url_list=additional_url_list)

    core_update_command = ["core", "update-index"]
    core_install_command = ["core", "install"]
    core_install_command.extend(platform_list)
    if len(additional_url_list) > 0:
        additional_urls_option = ["--additional-urls", ",".join(additional_url_list)]
        core_update_command.extend(additional_urls_option)
        core_install_command.extend(additional_urls_option)
    run_arduino_cli_command_calls = [
        unittest.mock.call(compile_sketches, command=core_update_command, enable_output=run_command_output_level),
        unittest.mock.call(compile_sketches, command=core_install_command, enable_output=run_command_output_level)]
    compile_sketches.run_arduino_cli_command.assert_has_calls(calls=run_arduino_cli_command_calls)


@pytest.mark.parametrize("verbose, expected_output_level",
                         [("true", compilesketches.CompileSketches.RunCommandOutput.ALWAYS),
                          ("false", compilesketches.CompileSketches.RunCommandOutput.ON_FAILURE)])
def test_get_run_command_output_level(verbose, expected_output_level):
    compile_sketches = get_compilesketches_object(verbose=verbose)

    assert compile_sketches.get_run_command_output_level() == expected_output_level


@pytest.mark.parametrize("verbose", [True, False])
def test_run_arduino_cli_command(mocker, verbose):
    run_command_return = unittest.mock.sentinel.run_command_return
    command = ["foo", "command"]
    enable_output = unittest.mock.sentinel.enable_output
    exit_on_failure = unittest.mock.sentinel.exit_on_failure
    arduino_cli_installation_path = pathlib.PurePath("fooCLIinstallationPath")

    compile_sketches = get_compilesketches_object()
    compile_sketches.verbose = verbose

    compile_sketches.arduino_cli_installation_path = arduino_cli_installation_path

    mocker.patch("compilesketches.CompileSketches.run_command", autospec=True, return_value=run_command_return)

    assert compile_sketches.run_arduino_cli_command(command=command,
                                                    enable_output=enable_output,
                                                    exit_on_failure=exit_on_failure) == run_command_return

    expected_run_command_command = [arduino_cli_installation_path.joinpath("arduino-cli")]
    expected_run_command_command.extend(command)
    if verbose:
        expected_run_command_command.extend(["--log-level", "warn", "--verbose"])
    compile_sketches.run_command.assert_called_once_with(
        compile_sketches,
        command=expected_run_command_command,
        enable_output=enable_output,
        exit_on_failure=exit_on_failure
    )


@pytest.mark.parametrize("enable_output", [compilesketches.CompileSketches.RunCommandOutput.NONE,
                                           compilesketches.CompileSketches.RunCommandOutput.ON_FAILURE,
                                           compilesketches.CompileSketches.RunCommandOutput.ALWAYS])
@pytest.mark.parametrize("exit_on_failure, returncode, expected_success",
                         [(False, 0, True),
                          (False, 1, True),
                          (True, 0, True),
                          (True, 1, False)])
def test_run_command(capsys, mocker, enable_output, exit_on_failure, returncode, expected_success):
    command = unittest.mock.sentinel.command

    # Stub
    class CommandData:
        stdout = "foo stdout"
        args = ["foo", "args"]

    CommandData.returncode = returncode

    command_data = CommandData()

    compile_sketches = get_compilesketches_object()

    mocker.patch("subprocess.run", autospec=True, return_value=command_data)

    if expected_success:
        run_command_output = compile_sketches.run_command(command=command,
                                                          enable_output=enable_output,
                                                          exit_on_failure=exit_on_failure)
        assert run_command_output == command_data

    else:
        with pytest.raises(expected_exception=SystemExit, match=str(returncode)):
            compile_sketches.run_command(command=command,
                                         enable_output=enable_output,
                                         exit_on_failure=exit_on_failure)

    expected_output = ("::group::Running command: " + " ".join(command_data.args) + " \n "
                       + str(CommandData.stdout) + " \n "
                       + "::endgroup::")

    if returncode != 0 and (enable_output == compilesketches.CompileSketches.RunCommandOutput.ON_FAILURE
                            or enable_output == compilesketches.CompileSketches.RunCommandOutput.ALWAYS):
        expected_output = expected_output + "\n::error::Command failed"
    elif enable_output == compilesketches.CompileSketches.RunCommandOutput.ALWAYS:
        expected_output = expected_output
    else:
        expected_output = ""
    assert capsys.readouterr().out.strip() == expected_output

    # noinspection PyUnresolvedReferences
    subprocess.run.assert_called_once_with(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


@pytest.mark.parametrize(
    "dependency, expected_name",
    [({compilesketches.CompileSketches.dependency_name_key: "Foo",
       compilesketches.CompileSketches.dependency_version_key: "1.2.3"}, "Foo@1.2.3"),
     ({compilesketches.CompileSketches.dependency_name_key: "Foo",
       compilesketches.CompileSketches.dependency_version_key: "latest"}, "Foo"),
     ({compilesketches.CompileSketches.dependency_name_key: "Foo@1.2.3"}, "Foo@1.2.3"),
     ({compilesketches.CompileSketches.dependency_name_key: "Foo"}, "Foo")])
def test_get_manager_dependency_name(dependency, expected_name):
    compile_sketches = get_compilesketches_object()
    assert compile_sketches.get_manager_dependency_name(dependency=dependency) == expected_name


@pytest.mark.parametrize(
    "libraries, expected_manager, expected_path",
    [("", [], [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.PurePath("/foo/GitHubWorkspace")}]),
     ("foo bar", [{compilesketches.CompileSketches.dependency_name_key: "foo"},
                  {compilesketches.CompileSketches.dependency_name_key: "bar"}],
      [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.PurePath("/foo/GitHubWorkspace")}]),
     ("\"foo\" \"bar\"", [{compilesketches.CompileSketches.dependency_name_key: "foo"},
                          {compilesketches.CompileSketches.dependency_name_key: "bar"}],
      [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.PurePath("/foo/GitHubWorkspace")}]),
     ("-", [], []),
     ("- " + compilesketches.CompileSketches.dependency_name_key + ": foo",
      [{compilesketches.CompileSketches.dependency_name_key: "foo"}], []),
     ("- " + compilesketches.CompileSketches.dependency_source_path_key + ": /foo/bar", [],
      [{compilesketches.CompileSketches.dependency_source_path_key: "/foo/bar"}])]
)
def test_install_libraries(monkeypatch, mocker, libraries, expected_manager, expected_path):
    libraries_path = pathlib.Path("/foo/LibrariesPath")

    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/GitHubWorkspace")

    compile_sketches = get_compilesketches_object(libraries=libraries)
    compile_sketches.libraries_path = libraries_path

    mocker.patch.object(pathlib.Path, "mkdir", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries_from_library_manager", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries_from_path", autospec=True)

    compile_sketches.install_libraries()

    # noinspection PyUnresolvedReferences
    pathlib.Path.mkdir.assert_called_with(libraries_path, parents=True, exist_ok=True)

    if len(expected_manager) > 0:
        compile_sketches.install_libraries_from_library_manager.assert_called_once_with(
            compile_sketches,
            library_list=expected_manager)
    else:
        compile_sketches.install_libraries_from_library_manager.assert_not_called()

    if len(expected_path) > 0:
        compile_sketches.install_libraries_from_path.assert_called_once_with(
            compile_sketches,
            library_list=expected_path)
    else:
        compile_sketches.install_libraries_from_path.assert_not_called()


def test_install_libraries_from_library_manager(mocker):
    run_command_output_level = unittest.mock.sentinel.run_command_output_level
    compile_sketches = get_compilesketches_object()

    library_list = [{compile_sketches.dependency_name_key: "foo"}, {compile_sketches.dependency_name_key: "bar"}]

    mocker.patch("compilesketches.CompileSketches.get_run_command_output_level", autospec=True,
                 return_value=run_command_output_level)
    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True)

    compile_sketches.install_libraries_from_library_manager(library_list=library_list)

    lib_install_command = ["lib", "install"] + [library["name"] for library in library_list]
    compile_sketches.run_arduino_cli_command.assert_called_once_with(compile_sketches,
                                                                     command=lib_install_command,
                                                                     enable_output=run_command_output_level)


@pytest.mark.parametrize("path_exists, library_list, expected_destination_name_list",
                         [(False, [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.Path(
                             "/foo/GitHubWorkspace/Nonexistent")}], []),
                          (True, [{compilesketches.CompileSketches.dependency_destination_name_key: "FooName",
                                   compilesketches.CompileSketches.dependency_source_path_key: pathlib.Path(
                                       "/foo/GitHubWorkspace/FooLibrary")}], ["FooName"]),
                          (True, [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.Path(
                              "/foo/GitHubWorkspace")}], ["FooRepoName"]),
                          (True,
                           [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.Path(
                               "/foo/GitHubWorkspace/Bar")}], ["Bar"])])
def test_install_libraries_from_path(capsys, monkeypatch, mocker, path_exists, library_list,
                                     expected_destination_name_list):
    libraries_path = pathlib.Path("/foo/LibrariesPath")
    symlink_source_path = pathlib.Path("/foo/SymlinkSourcePath")

    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/GitHubWorkspace")
    monkeypatch.setenv("GITHUB_REPOSITORY", "foo/FooRepoName")

    compile_sketches = get_compilesketches_object()
    compile_sketches.libraries_path = libraries_path

    mocker.patch.object(pathlib.Path, "exists", autospec=True, return_value=path_exists)
    mocker.patch.object(pathlib.Path, "joinpath", autospec=True, return_value=symlink_source_path)
    mocker.patch.object(pathlib.Path, "symlink_to", autospec=True)

    if not path_exists:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            compile_sketches.install_libraries_from_path(library_list=library_list)
        assert capsys.readouterr().out.strip() == (
            "::error::Library source path: "
            + str(compilesketches.path_relative_to_workspace(library_list[0]["source-path"]))
            + " doesn't exist"
        )

    else:
        compile_sketches.install_libraries_from_path(library_list=library_list)

        joinpath_calls = []
        symlink_to_calls = []
        for library, expected_destination_name in zip(library_list, expected_destination_name_list):
            joinpath_calls.append(unittest.mock.call(libraries_path, expected_destination_name))
            symlink_to_calls.append(
                unittest.mock.call(symlink_source_path,
                                   target=library[compilesketches.CompileSketches.dependency_source_path_key],
                                   target_is_directory=True))

        # noinspection PyUnresolvedReferences
        pathlib.Path.joinpath.assert_has_calls(calls=joinpath_calls)
        pathlib.Path.symlink_to.assert_has_calls(calls=symlink_to_calls)


def test_find_sketches(capsys, monkeypatch):
    nonexistent_sketch_path = "/foo/NonexistentSketch"

    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/bar")

    # Test sketch path doesn't exist
    compile_sketches = get_compilesketches_object(
        sketch_paths="\'\"" + nonexistent_sketch_path + "\"\'"
    )
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.find_sketches()
    assert capsys.readouterr().out.strip() == ("::error::Sketch path: " + str(pathlib.PurePath(nonexistent_sketch_path))
                                               + " doesn't exist")

    # Test sketch path is a sketch file
    compile_sketches = get_compilesketches_object(
        sketch_paths="\"" + str(test_data_path.joinpath("HasSketches", "Sketch1", "Sketch1.ino")) + "\""
    )
    assert compile_sketches.find_sketches() == [
        test_data_path.joinpath("HasSketches", "Sketch1")
    ]

    # Test sketch path is a non-sketch file
    non_sketch_path = str(test_data_path.joinpath("NoSketches", "NotSketch", "NotSketch.foo"))
    compile_sketches = get_compilesketches_object(sketch_paths="\"" + non_sketch_path + "\"")
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.find_sketches()
    assert capsys.readouterr().out.strip() == ("::error::Sketch path: " + non_sketch_path + " is not a sketch")

    # Test sketch path is a sketch folder
    compile_sketches = get_compilesketches_object(
        sketch_paths="\"" + str(test_data_path.joinpath("HasSketches", "Sketch1")) + "\""
    )
    assert compile_sketches.find_sketches() == [
        test_data_path.joinpath("HasSketches", "Sketch1")
    ]

    # Test sketch path does contain sketches
    compile_sketches = get_compilesketches_object(
        sketch_paths="\"" + str(test_data_path.joinpath("HasSketches")) + "\"")
    assert compile_sketches.find_sketches() == [
        test_data_path.joinpath("HasSketches", "Sketch1"),
        test_data_path.joinpath("HasSketches", "Sketch2")
    ]

    # Test sketch path doesn't contain any sketches
    no_sketches_path = str(test_data_path.joinpath("NoSketches"))
    compile_sketches = get_compilesketches_object(
        sketch_paths="\"" + no_sketches_path + "\"")
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.find_sketches()
    assert capsys.readouterr().out.strip() == ("::error::No sketches were found in "
                                               + no_sketches_path)


def test_path_is_sketch():
    # Sketch file
    assert compilesketches.path_is_sketch(path=test_data_path.joinpath("HasSketches", "Sketch1", "Sketch1.ino")) is True

    # Not a sketch file
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("NoSketches", "NotSketch", "NotSketch.foo")) is False

    # Sketch folder
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("HasSketches", "Sketch1")) is True

    # No files in path
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("HasSketches")) is False

    # Not a sketch folder
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("NoSketches", "NotSketch")) is False


@pytest.mark.parametrize("returncode, expected_success", [(1, False),
                                                          (0, True)])
def test_compile_sketch(capsys, monkeypatch, mocker, returncode, expected_success):
    stdout = unittest.mock.sentinel.stdout
    relative_sketch_path = pathlib.PurePath("FooSketch", "FooSketch.ino")

    # Stub
    class CompilationData:
        _ = 42

    CompilationData.returncode = returncode
    CompilationData.stdout = stdout

    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/bar")

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True,
                 return_value=CompilationData())

    compilation_result = compile_sketches.compile_sketch(
        sketch_path=pathlib.PurePath(os.environ["GITHUB_WORKSPACE"]).joinpath(relative_sketch_path)
    )

    expected_stdout = (
        "::group::Compiling sketch: " + str(relative_sketch_path) + "\n"
        + str(stdout) + "\n"
        + "::endgroup::"
    )
    if not expected_success:
        expected_stdout += "\n::error::Compilation failed"
    assert capsys.readouterr().out.strip() == expected_stdout

    assert compilation_result.sketch == relative_sketch_path
    assert compilation_result.success == expected_success
    assert compilation_result.output == stdout


@pytest.mark.parametrize("do_size_deltas_report", [True, False])
def test_get_sketch_report(monkeypatch, mocker, do_size_deltas_report):
    original_git_ref = unittest.mock.sentinel.original_git_ref
    sketch_report_list = [unittest.mock.sentinel.sketch_report_list1, unittest.mock.sentinel.sketch_report_list2]
    sketch = unittest.mock.sentinel.sketch

    class CompilationResult:
        def __init__(self, sketch_input):
            self.sketch = sketch_input

    compilation_result = CompilationResult(sketch_input=sketch)

    sketch_absolute_path = unittest.mock.sentinel.sketch_absolute_path
    previous_compilation_result = unittest.mock.sentinel.previous_compilation_result
    sketch_size = unittest.mock.sentinel.sketch_size

    # Stub
    class Repo:
        hexsha = original_git_ref

        def __init__(self):
            self.head = self
            self.object = self
            self.git = self

        def checkout(self):
            pass

    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/bar")

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_sketch_report_from_output", autospec=True,
                 side_effect=sketch_report_list)
    mocker.patch("compilesketches.CompileSketches.do_size_deltas_report", autospec=True,
                 return_value=do_size_deltas_report)
    mocker.patch("git.Repo", autospec=True, return_value=Repo())
    mocker.patch("compilesketches.CompileSketches.checkout_pull_request_base_ref", autospec=True)
    mocker.patch("compilesketches.absolute_path", autospec=True, return_value=sketch_absolute_path)
    mocker.patch("compilesketches.CompileSketches.compile_sketch", autospec=True,
                 return_value=previous_compilation_result)
    mocker.patch.object(Repo, "checkout")
    mocker.patch("compilesketches.CompileSketches.get_size_deltas", autospec=True, return_value=sketch_size)

    sketch_size_output = compile_sketches.get_sketch_report(compilation_result=compilation_result)

    get_sketch_size_from_output_calls = [unittest.mock.call(compile_sketches, compilation_result=compilation_result)]
    compilesketches.CompileSketches.do_size_deltas_report.assert_called_once_with(compile_sketches,
                                                                                  sketch_report=sketch_report_list[0])
    if do_size_deltas_report:
        git.Repo.assert_called_once_with(path=os.environ["GITHUB_WORKSPACE"])
        compile_sketches.checkout_pull_request_base_ref.assert_called_once()
        compilesketches.absolute_path.assert_called_once_with(path=compilation_result.sketch)
        compile_sketches.compile_sketch.assert_called_once_with(compile_sketches, sketch_path=sketch_absolute_path)
        Repo.checkout.assert_called_once_with(original_git_ref)
        get_sketch_size_from_output_calls.append(
            unittest.mock.call(compile_sketches, compilation_result=previous_compilation_result))
        compile_sketches.get_size_deltas.assert_called_once_with(compile_sketches,
                                                                 current_sketch_report=sketch_report_list[0],
                                                                 previous_sketch_report=sketch_report_list[1])

        assert sketch_size_output == sketch_size

    else:
        assert sketch_size_output == sketch_report_list[0]

    compilesketches.CompileSketches.get_sketch_report_from_output.assert_has_calls(
        calls=get_sketch_size_from_output_calls)


@pytest.mark.parametrize(
    "compilation_success, compilation_output, flash, ram",
    [(False, "foo output", get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator),
     (True,
      "/home/per/.arduino15/packages/arduino/hardware/megaavr/1.8.5/cores/arduino/NANO_compat.cpp:23:2: warning: #warni"
      "ng \"ATMEGA328 registers emulation is enabled. You may encounter some speed issue. Please consider to disable it"
      " in the Tools menu\" [-Wcpp]\n"
      " #warning \"ATMEGA328 registers emulation is enabled. You may encounter some speed issue. Please consider to dis"
      "able it in the Tools menu\"\n"
      "  ^~~~~~~\n"
      "Sketch uses {flash} bytes (1%) of program storage space. Maximum is 49152 bytes.\n"
      "Global variables use {ram} bytes (0%) of dynamic memory, leaving 6122 bytes for local variables. Maximum is 6144"
      " bytes.\n",
      802, 22),
     (True,
      "In file included from /home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/samd21/in"
      "clude/samd21.h:69:0,\n"
      "                 from /home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/samd.h:10"
      "5,\n"
      "                 from /home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/sam.h:540"
      ",\n"
      "                 from /home/per/.arduino15/packages/arduino/hardware/samd/1.8.6/cores/arduino/Arduino.h:48,\n"
      "                 from /home/per/Arduino/libraries/Arduino_MKRGPS/src/GPS.h:23,\n"
      "                 from /home/per/Arduino/libraries/Arduino_MKRGPS/src/GPS.cpp:28:\n"
      "/home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/samd21/include/samd21g18a.h:226"
      ":0: warning: \"LITTLE_ENDIAN\" redefined\n"
      " #define LITTLE_ENDIAN          1\n"
      " \n"
      "In file included from /home/per/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/arm-none-eabi/inclu"
      "de/sys/types.h:67:0,\n"
      "                 from /home/per/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/arm-none-eabi/inclu"
      "de/stdio.h:61,\n"
      "                 from /home/per/Arduino/libraries/Arduino_MKRGPS/src/minmea/minmea.h:16,\n"
      "                 from /home/per/Arduino/libraries/Arduino_MKRGPS/src/GPS.cpp:23:\n"
      "/home/per/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/arm-none-eabi/include/machine/endian.h:17"
      ":0: note: this is the location of the previous definition\n"
      " #define LITTLE_ENDIAN _LITTLE_ENDIAN\n"
      " \n"
      "Sketch uses {flash} bytes (12%) of program storage space. Maximum is 262144 bytes.\n"
      "Global variables use {ram} bytes of dynamic memory.\n",
      32740, 3648),
     (True,
      "/home/per/Arduino/libraries/Servo/src/samd/Servo.cpp: In function 'void _initISR(Tc*, uint8_t, uint32_t, IRQn_Ty"
      "pe, uint8_t, uint8_t)':\n"
      "/home/per/Arduino/libraries/Servo/src/samd/Servo.cpp:120:56: warning: unused parameter 'id' [-Wunused-parameter]"
      "\n"
      " static void _initISR(Tc *tc, uint8_t channel, uint32_t id, IRQn_Type irqn, uint8_t gcmForTimer, uint8_t intEnab"
      " leBit)\n"
      "                                                        ^~\n"
      "/home/per/Arduino/libraries/Servo/src/samd/Servo.cpp: In function 'void finISR(timer16_Sequence_t)':\n"
      "/home/per/Arduino/libraries/Servo/src/samd/Servo.cpp:174:39: warning: unused parameter 'timer' [-Wunused-paramet"
      "er]\n"
      " static void finISR(timer16_Sequence_t timer)\n"
      "                                       ^~~~~\n"
      "Sketch uses {flash} bytes (4%) of program storage space. Maximum is 262144 bytes.\n",
      12636, get_compilesketches_object().not_applicable_indicator),
     (True,
      "In file included from /home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/samd21/in"
      "clude/samd21.h:69:0,\n"
      "                 from /home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/samd.h:10"
      "5,\n"
      "                 from /home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/sam.h:540"
      ",\n"
      "                 from /home/per/.arduino15/packages/arduino/hardware/samd/1.8.6/cores/arduino/Arduino.h:48,\n"
      "                 from /home/per/Arduino/libraries/RTCZero/src/RTCZero.h:23,\n"
      "                 from /home/per/Arduino/libraries/RTCZero/src/RTCZero.cpp:22:\n"
      "/home/per/.arduino15/packages/arduino/tools/CMSIS-Atmel/1.2.0/CMSIS/Device/ATMEL/samd21/include/samd21g18a.h:226"
      ":0: warning: \"LITTLE_ENDIAN\" redefined\n"
      " #define LITTLE_ENDIAN          1\n"
      " \n"
      "In file included from /home/per/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/arm-none-eabi/inclu"
      "de/sys/types.h:67:0,\n"
      "                 from /home/per/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/arm-none-eabi/inclu"
      "de/time.h:28,\n"
      "                 from /home/per/Arduino/libraries/RTCZero/src/RTCZero.cpp:20:\n"
      "/home/per/.arduino15/packages/arduino/tools/arm-none-eabi-gcc/7-2017q4/arm-none-eabi/include/machine/endian.h:17"
      ":0: note: this is the location of the previous definition\n"
      " #define LITTLE_ENDIAN _LITTLE_ENDIAN\n"
      " \n"
      "/home/per/Arduino/libraries/RTCZero/src/RTCZero.cpp: In member function 'void RTCZero::begin(bool)':\n"
      "/home/per/Arduino/libraries/RTCZero/src/RTCZero.cpp:96:26: warning: 'oldTime.RTC_MODE2_CLOCK_Type::reg' may be u"
      "sed uninitialized in this function [-Wmaybe-uninitialized]\n"
      "     RTC->MODE2.CLOCK.reg = oldTime.reg;\n"
      "Couldn't determine program size",
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator)]
)
def test_get_sketch_report_from_output(compilation_success, compilation_output, flash, ram):
    sketch_path = unittest.mock.sentinel.sketch
    compilation_output = compilation_output.format(flash=str(flash), ram=str(ram))
    compile_sketches = get_compilesketches_object()
    compilation_result = type("CompilationResult", (),
                              {compile_sketches.report_sketch_key: sketch_path,
                               "success": compilation_success,
                               "output": compilation_output})

    sketch_report = compile_sketches.get_sketch_report_from_output(compilation_result=compilation_result)

    assert sketch_report == {compile_sketches.report_sketch_key: str(sketch_path),
                             compile_sketches.report_compilation_success_key: compilation_success,
                             compile_sketches.report_flash_key: flash,
                             compile_sketches.report_ram_key: ram}


@pytest.mark.parametrize(
    "enable_size_deltas_report, github_event_name, sketch_path, sketch_report_compilation_success,"
    "sketch_report_flash, sketch_report_ram, do_size_deltas_report_expected",
    [("true", "pull_request", "foo/ReportSketch", True, 123, 42, True),
     ("false", "pull_request", "foo/ReportSketch", True, 123, 42, False),
     ("true", "push", "foo/ReportSketch", True, 123, 42, False),
     ("true", "pull_request", "foo/NotReportSketch", True, 123, 42, False),
     ("true", "pull_request", "foo/ReportSketch", False, 123, 42, False),
     (
         "true", "pull_request", "foo/ReportSketch", True, get_compilesketches_object().not_applicable_indicator,
         42,
         True),
     ("true", "pull_request", "foo/ReportSketch", True, 123, get_compilesketches_object().not_applicable_indicator,
      True),
     ("true", "pull_request", "foo/ReportSketch", True, get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator, False)]
)
def test_do_size_deltas_report(monkeypatch, enable_size_deltas_report, github_event_name, sketch_path,
                               sketch_report_compilation_success, sketch_report_flash, sketch_report_ram,
                               do_size_deltas_report_expected):
    monkeypatch.setenv("GITHUB_EVENT_NAME", github_event_name)

    compile_sketches = get_compilesketches_object(enable_size_deltas_report=enable_size_deltas_report,
                                                  report_sketch="ReportSketch")

    sketch_report = {compile_sketches.report_sketch_key: sketch_path,
                     compile_sketches.report_compilation_success_key: sketch_report_compilation_success,
                     compile_sketches.report_flash_key: sketch_report_flash,
                     compile_sketches.report_ram_key: sketch_report_ram}
    assert compile_sketches.do_size_deltas_report(sketch_report=sketch_report) == do_size_deltas_report_expected


@pytest.mark.parametrize("report_sketch, sketch_path, expected_result",
                         [("ReportSketch", "/foo/ReportSketch", True),
                          ("ReportSketch", "/foo/NotReportSketch", False)])
def test_is_report_sketch(report_sketch, sketch_path, expected_result):
    compile_sketches = get_compilesketches_object(report_sketch=report_sketch)

    assert compile_sketches.is_report_sketch(sketch_path=sketch_path) == expected_result


def test_checkout_pull_request_base_ref(monkeypatch, mocker):
    # Stubs
    class Repo:
        def __init__(self):
            self.remotes = {"origin": self}
            self.git = self

        def fetch(self):
            pass

        def checkout(self):
            pass

    class Github:
        ref = unittest.mock.sentinel.pull_request_base_ref

        def __init__(self):
            self.base = self

        def get_repo(self):
            pass

        def get_pull(self):
            pass

    monkeypatch.setenv("GITHUB_REPOSITORY", "fooRepository/fooOwner")
    monkeypatch.setenv("GITHUB_WORKSPACE", "/fooWorkspace")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(test_data_path.joinpath("githubevent.json")))

    compile_sketches = get_compilesketches_object()

    mocker.patch("git.Repo", autospec=True, return_value=Repo())
    mocker.patch.object(Repo, "fetch")
    mocker.patch.object(Repo, "checkout")

    compile_sketches.github_api = Github()
    mocker.patch.object(Github, "get_repo", return_value=Github())
    mocker.patch.object(Github, "get_pull", return_value=Github())

    compile_sketches.checkout_pull_request_base_ref()

    git.Repo.assert_called_once_with(path=os.environ["GITHUB_WORKSPACE"])
    Github.get_repo.assert_called_once_with(full_name_or_id=os.environ["GITHUB_REPOSITORY"])
    Github.get_pull.assert_called_once_with(number=42)  # PR number is hardcoded into test file

    Repo.fetch.assert_called_once_with(refspec=Github.ref,
                                       verbose=compile_sketches.verbose,
                                       no_tags=True, prune=True,
                                       depth=1)
    Repo.checkout.assert_called_once_with(Github.ref)

    mocker.patch.object(Github, "get_repo", side_effect=github.UnknownObjectException(status=42, data="foo"))
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.checkout_pull_request_base_ref()


@pytest.mark.parametrize("flash, ram, previous_flash, previous_ram, expected_flash_delta,expected_ram_delta",
                         [(get_compilesketches_object().not_applicable_indicator, 42, 42,
                           get_compilesketches_object().not_applicable_indicator,
                           get_compilesketches_object().not_applicable_indicator,
                           get_compilesketches_object().not_applicable_indicator),
                          (52, 42, 42, 52, 10, -10)])
def test_get_size_deltas(capsys, flash, ram, previous_flash, previous_ram, expected_flash_delta,
                         expected_ram_delta):
    compile_sketches = get_compilesketches_object()

    current_sketch_size = {compile_sketches.report_flash_key: flash, compile_sketches.report_ram_key: ram}
    previous_sketch_size = {compile_sketches.report_flash_key: previous_flash,
                            compile_sketches.report_ram_key: previous_ram}

    sketch_size = compile_sketches.get_size_deltas(current_sketch_size,
                                                   previous_sketch_size)

    assert capsys.readouterr().out.strip() == ("Change in flash memory usage: " + str(expected_flash_delta) + "\n"
                                               + "Change in RAM used by globals: " + str(expected_ram_delta))

    assert sketch_size[compile_sketches.report_flash_key] == flash
    assert sketch_size[compile_sketches.report_ram_key] == ram
    assert sketch_size[compile_sketches.report_previous_flash_key] == previous_flash
    assert sketch_size[compile_sketches.report_previous_ram_key] == previous_ram
    assert sketch_size[compile_sketches.report_flash_delta_key] == expected_flash_delta
    assert sketch_size[compile_sketches.report_ram_delta_key] == expected_ram_delta


@pytest.mark.parametrize("enable_size_trends_report, github_event_name, is_default_branch, expected",
                         [("true", "push", True, True),
                          ("false", "push", True, False),
                          ("true", "pull_request", True, False),
                          ("true", "push", False, False)])
def test_do_size_trends_report(monkeypatch, mocker, enable_size_trends_report, github_event_name, is_default_branch,
                               expected):
    monkeypatch.setenv("GITHUB_EVENT_NAME", github_event_name)

    compile_sketches = get_compilesketches_object(enable_size_trends_report=enable_size_trends_report)

    mocker.patch("compilesketches.CompileSketches.is_default_branch", autospec=True, return_value=is_default_branch)

    assert compile_sketches.do_size_trends_report() == expected


@pytest.mark.parametrize("current_branch, default_branch, is_default",
                         [("foo-default-branch", "foo-default-branch", True),
                          ("foo-not-default-branch", "foo-default-branch", False)])
def test_is_default_branch(monkeypatch, mocker, current_branch, default_branch, is_default):
    # Stub
    class Github:
        def get_repo(self):
            pass

    Github.default_branch = default_branch

    monkeypatch.setenv("GITHUB_REPOSITORY", "fooRepository/fooOwner")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/" + current_branch)

    compile_sketches = get_compilesketches_object()

    compile_sketches.github_api = Github()
    mocker.patch.object(Github, "get_repo", return_value=Github())

    assert compile_sketches.is_default_branch() == is_default

    mocker.patch.object(Github, "get_repo", side_effect=github.UnknownObjectException(status=42, data="foo"))
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.is_default_branch()


@pytest.mark.parametrize("report_sketch, expected_success", [("FooSketch", True), ("NonexistentSketch", False)])
def test_get_sketch_report_from_sketches_report(report_sketch, expected_success):
    report_sketch_report = {compilesketches.CompileSketches.report_sketch_key: "FooSketch"}
    sketch_sizes = [report_sketch_report, {compilesketches.CompileSketches.report_sketch_key: "BarSketch"}]

    compile_sketches = get_compilesketches_object(report_sketch=report_sketch)

    if expected_success:
        assert compile_sketches.get_sketch_report_from_sketches_report(sketch_sizes) == report_sketch_report
    else:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            compile_sketches.get_sketch_report_from_sketches_report(sketch_sizes)


def test_make_size_trends_report(monkeypatch, mocker):
    current_git_ref = "fooref"
    sketch_report = {compilesketches.CompileSketches.report_sketch_key: unittest.mock.sentinel.sketch_report_sketch,
                     compilesketches.CompileSketches.report_flash_key: unittest.mock.sentinel.sketch_report_flash,
                     compilesketches.CompileSketches.report_ram_key: unittest.mock.sentinel.sketch_report_ram}

    # Stub
    class Repo:
        def __init__(self):
            self.git = self

        def rev_parse(self):
            pass

    class ReportSizeTrends:
        def report_size_trends(self):
            pass

    monkeypatch.setenv("GITHUB_REPOSITORY", "fooRepository/fooOwner")
    monkeypatch.setenv("GITHUB_WORKSPACE", "/fooWorkspace")

    compile_sketches = get_compilesketches_object()

    mocker.patch("git.Repo", autospec=True, return_value=Repo())
    mocker.patch.object(Repo, "rev_parse", return_value=current_git_ref)
    mocker.patch("reportsizetrends.ReportSizeTrends", autospec=True, return_value=ReportSizeTrends())
    mocker.patch.object(ReportSizeTrends, "report_size_trends")

    compile_sketches.make_size_trends_report(sketch_report)

    git.Repo.assert_called_once_with(path=os.environ["GITHUB_WORKSPACE"])
    Repo.rev_parse.assert_called_once_with("HEAD", short=True)
    reportsizetrends.ReportSizeTrends.assert_called_once_with(
        google_key_file=compile_sketches.google_key_file,
        spreadsheet_id=compile_sketches.size_trends_report_spreadsheet_id,
        sheet_name=compile_sketches.size_trends_report_sheet_name,
        sketch_name=sketch_report[compilesketches.CompileSketches.report_sketch_key],
        commit_hash=current_git_ref,
        commit_url=("https://github.com/"
                    + os.environ["GITHUB_REPOSITORY"]
                    + "/commit/"
                    + current_git_ref),
        fqbn=compile_sketches.fqbn,
        flash=str(sketch_report[compilesketches.CompileSketches.report_flash_key]),
        ram=str(sketch_report[compilesketches.CompileSketches.report_ram_key])
    )
    ReportSizeTrends.report_size_trends.assert_called_once()


def test_create_sketches_report_file(tmp_path):
    sketches_report_path = tmp_path
    fqbn_arg = "arduino:avr:uno"
    sketches_report = {
        "sketch": "examples/Foo",
        "compilation_success": True,
        "flash": 444,
        "ram": 9,
        "previous_flash": 1438,
        "previous_ram": 184,
        "flash_delta": -994,
        "ram_delta": -175,
        "fqbn": "arduino:avr:uno"
    }

    compile_sketches = get_compilesketches_object(sketches_report_path=str(sketches_report_path),
                                                  fqbn_arg=fqbn_arg)

    compile_sketches.create_sketches_report_file(sketches_report=sketches_report)

    with open(file=str(sketches_report_path.joinpath("arduino-avr-uno.json"))) as sketch_report_file:
        assert json.load(sketch_report_file) == sketches_report


@pytest.mark.parametrize("verbose", ["true", "false"])
def test_verbose_print(capsys, verbose):
    string_print_argument = "foo string argument"
    int_print_argument = 42
    path_print_argument = pathlib.PurePath("foo/bar")

    compile_sketches = get_compilesketches_object(verbose=verbose)

    compile_sketches.verbose_print(string_print_argument, int_print_argument, path_print_argument)

    if verbose == "true":
        assert capsys.readouterr().out.strip() == (string_print_argument + " "
                                                   + str(int_print_argument) + " "
                                                   + str(path_print_argument))
    else:
        assert capsys.readouterr().out.strip() == ""


@pytest.mark.parametrize("list_argument, expected_list",
                         [("", []),
                          ("foobar", ["foobar"]),
                          ("foo bar", ["foo", "bar"]),
                          ("\"foo bar\"", ["foo bar"]),
                          ("\'foo bar\'", ["foo bar"]),
                          ("\'\"foo bar\" \"baz\"\'", ["foo bar", "baz"]),
                          ("\'\"foo bar\" baz\'", ["foo bar", "baz"])])
def test_parse_list_input(list_argument, expected_list):
    assert compilesketches.parse_list_input(list_argument) == expected_list


@pytest.mark.parametrize("fqbn_arg, expected_fqbn, expected_additional_url",
                         [("foo:bar:baz", "foo:bar:baz", None),
                          ("\"foo:bar:baz\"", "foo:bar:baz", None),
                          ("\"foo asdf:bar:baz\"", "foo asdf:bar:baz", None),
                          ("\'foo:bar:baz\'", "foo:bar:baz", None),
                          ("\'\"foo asdf:bar:baz\" https://example.com/package_foo_index.json\'",
                           "foo asdf:bar:baz",
                           "https://example.com/package_foo_index.json"),
                          ("\'\"foo asdf:bar:baz\" \"https://example.com/package_foo_index.json\"\'",
                           "foo asdf:bar:baz",
                           "https://example.com/package_foo_index.json")])
def test_parse_fqbn_arg_input(fqbn_arg, expected_fqbn, expected_additional_url):
    parsed_fqbn_arg = compilesketches.parse_fqbn_arg_input(fqbn_arg=fqbn_arg)

    assert parsed_fqbn_arg["fqbn"] == expected_fqbn
    assert parsed_fqbn_arg["additional_url"] == expected_additional_url


@pytest.mark.parametrize("boolean_input, expected_output",
                         [("true", True), ("True", True), ("false", False), ("False", False), ("foo", None)])
def test_parse_boolean_input(boolean_input, expected_output):
    assert compilesketches.parse_boolean_input(boolean_input=boolean_input) == expected_output


def test_path_relative_to_workspace(monkeypatch):
    monkeypatch.setenv("GITHUB_WORKSPACE", "/fooWorkspace")

    assert compilesketches.path_relative_to_workspace(path=pathlib.PurePath("/fooWorkspace", "baz")
                                                      ) == pathlib.PurePath("baz")
    assert compilesketches.path_relative_to_workspace(path="/fooWorkspace/baz") == pathlib.PurePath("baz")


@pytest.mark.parametrize("path, expected_absolute_path", [("/asdf", "/asdf"), ("asdf", "/fooWorkspace/asdf")])
def test_absolute_path(monkeypatch, path, expected_absolute_path):
    monkeypatch.setenv("GITHUB_WORKSPACE", "/fooWorkspace")

    assert compilesketches.absolute_path(path=path) == pathlib.PurePath(expected_absolute_path)
    assert compilesketches.absolute_path(path=pathlib.PurePath(path)) == pathlib.PurePath(expected_absolute_path)


def test_list_to_string():
    path = pathlib.PurePath("/foo/bar")
    assert compilesketches.list_to_string([42, path]) == "42 " + str(path)
