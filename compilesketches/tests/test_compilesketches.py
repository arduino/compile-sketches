import filecmp
import json
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile
import unittest.mock

import git
import github
import pytest

import compilesketches

os.environ["GITHUB_WORKSPACE"] = "/foo/github-workspace"

test_data_path = pathlib.PurePath(os.path.dirname(os.path.realpath(__file__)), "testdata")


def get_compilesketches_object(
    cli_version="0.12.3",
    fqbn_arg="foo fqbn_arg",
    platforms="- name: FooVendor:BarArchitecture",
    libraries="foo libraries",
    sketch_paths="foo sketch_paths",
    cli_compile_flags="--foo",
    verbose="false",
    github_token="",
    github_api=unittest.mock.sentinel.github_api,
    deltas_base_ref="foodeltasbaseref",
    enable_deltas_report="false",
    enable_warnings_report="false",
    sketches_report_path="foo report_folder_name"
):
    with unittest.mock.patch("compilesketches.CompileSketches.get_deltas_base_ref",
                             autospec=True,
                             return_value=deltas_base_ref):
        compilesketches_object = compilesketches.CompileSketches(cli_version=cli_version,
                                                                 fqbn_arg=fqbn_arg,
                                                                 platforms=platforms,
                                                                 libraries=libraries,
                                                                 sketch_paths=sketch_paths,
                                                                 cli_compile_flags=cli_compile_flags,
                                                                 verbose=verbose,
                                                                 github_token=github_token,
                                                                 enable_deltas_report=enable_deltas_report,
                                                                 enable_warnings_report=enable_warnings_report,
                                                                 sketches_report_path=sketches_report_path)

    compilesketches_object.github_api = github_api

    return compilesketches_object


def directories_are_same(left_directory, right_directory):
    """Check recursively whether two directories contain the same files.
    Based on https://stackoverflow.com/a/24860799
    """
    directory_comparison = filecmp.dircmp(a=left_directory, b=right_directory)
    if (
        directory_comparison.left_only
        or directory_comparison.right_only
        or directory_comparison.diff_files
        or directory_comparison.funny_files
    ):
        return False
    for subdirectory in directory_comparison.common_dirs:
        if not directories_are_same(left_directory.joinpath(subdirectory), right_directory.joinpath(subdirectory)):
            return False
    return True


def test_directories_are_same():
    assert directories_are_same(left_directory=test_data_path, right_directory=test_data_path) is True
    assert directories_are_same(
        left_directory=test_data_path.joinpath("HasSketches"), right_directory=test_data_path.joinpath("NoSketches")
    ) is False
    assert directories_are_same(
        left_directory=test_data_path.joinpath("HasSketches", "NoSketches"),
        right_directory=test_data_path.joinpath("NoSketches")
    ) is False


@pytest.fixture
def setup_action_inputs(monkeypatch):
    class ActionInputs:
        cli_version = "1.0.0"
        fqbn_arg = "foo:bar:baz"
        platforms = "- name: FooVendor:BarArchitecture"
        libraries = "foo libraries"
        sketch_paths = "foo/Sketch bar/OtherSketch"
        cli_compile_flags = "--foo"
        verbose = "true"
        github_token = "FooGitHubToken"
        enable_size_deltas_report = "FooEnableSizeDeltasReport"
        enable_deltas_report = "FooEnableDeltasReport"
        enable_warnings_report = "FooEnableWarningsReport"
        sketches_report_path = "FooSketchesReportPath"
        size_deltas_report_folder_name = "FooSizeDeltasReportFolderName"

    monkeypatch.setenv("INPUT_CLI-VERSION", ActionInputs.cli_version)
    monkeypatch.setenv("INPUT_FQBN", ActionInputs.fqbn_arg)
    monkeypatch.setenv("INPUT_PLATFORMS", ActionInputs.platforms)
    monkeypatch.setenv("INPUT_LIBRARIES", ActionInputs.libraries)
    monkeypatch.setenv("INPUT_SKETCH-PATHS", ActionInputs.sketch_paths)
    monkeypatch.setenv("INPUT_CLI-COMPILE-FLAGS", ActionInputs.cli_compile_flags)
    monkeypatch.setenv("INPUT_VERBOSE", ActionInputs.verbose)
    monkeypatch.setenv("INPUT_GITHUB-TOKEN", ActionInputs.github_token)
    monkeypatch.setenv("INPUT_ENABLE-DELTAS-REPORT", ActionInputs.enable_deltas_report)
    monkeypatch.setenv("INPUT_ENABLE-WARNINGS-REPORT", ActionInputs.enable_warnings_report)
    monkeypatch.setenv("INPUT_SKETCHES-REPORT-PATH", ActionInputs.sketches_report_path)

    return ActionInputs()


@pytest.fixture
def stub_compilesketches_object(mocker):
    class CompileSketches:
        def compile_sketches(self):
            pass  # pragma: no cover

    mocker.patch("compilesketches.CompileSketches", autospec=True, return_value=CompileSketches())
    mocker.patch.object(CompileSketches, "compile_sketches")


@pytest.mark.parametrize("use_size_report_sketch", [True, False])
def test_main_size_report_sketch_deprecation_warning(capsys, monkeypatch, setup_action_inputs,
                                                     stub_compilesketches_object, use_size_report_sketch):
    if use_size_report_sketch:
        monkeypatch.setenv("INPUT_SIZE-REPORT-SKETCH", "foo")

    compilesketches.main()

    expected_output = ""
    if use_size_report_sketch:
        expected_output = "::warning::The size-report-sketch input is no longer used"

    assert capsys.readouterr().out.strip() == expected_output


@pytest.mark.parametrize("use_enable_size_trends_report", [True, False])
def test_main_enable_size_trends_report_deprecation_warning(capsys, monkeypatch, setup_action_inputs,
                                                            stub_compilesketches_object, use_enable_size_trends_report):
    if use_enable_size_trends_report:
        monkeypatch.setenv("INPUT_ENABLE-SIZE-TRENDS-REPORT", "true")

    compilesketches.main()

    expected_output = ""
    if use_enable_size_trends_report:
        expected_output = (
            expected_output
            + "::warning::The size trends report feature has been moved to a dedicated action. See the "
              "documentation at "
              "https://github.com/arduino/actions/tree/report-size-trends-action/libraries/report-size-trends"
        )

    assert capsys.readouterr().out.strip() == expected_output


@pytest.mark.parametrize("use_size_deltas_report_folder_name", [True, False])
def test_main_size_deltas_report_folder_name_deprecation(capsys, monkeypatch, setup_action_inputs,
                                                         stub_compilesketches_object,
                                                         use_size_deltas_report_folder_name):
    size_deltas_report_folder_name = "foo-size-deltas-report-folder-name"
    if use_size_deltas_report_folder_name:
        monkeypatch.setenv("INPUT_SIZE-DELTAS-REPORT-FOLDER-NAME", size_deltas_report_folder_name)

    compilesketches.main()

    expected_output = ""
    if use_size_deltas_report_folder_name:
        expected_output = (
            expected_output
            + "::warning::The size-deltas-report-folder-name input is deprecated. Use the equivalent input: "
              "sketches-report-path instead."
        )

    assert capsys.readouterr().out.strip() == expected_output

    if use_size_deltas_report_folder_name:
        expected_sketches_report_path = size_deltas_report_folder_name
    else:
        expected_sketches_report_path = setup_action_inputs.sketches_report_path

    assert os.environ["INPUT_SKETCHES-REPORT-PATH"] == expected_sketches_report_path


@pytest.mark.parametrize("use_enable_size_deltas_report", [True, False])
def test_main_enable_size_deltas_report_deprecation(capsys, monkeypatch, setup_action_inputs,
                                                    stub_compilesketches_object, use_enable_size_deltas_report):
    enable_size_deltas_report = "foo-enable-size-deltas-report"
    if use_enable_size_deltas_report:
        monkeypatch.setenv("INPUT_ENABLE-SIZE-DELTAS-REPORT", enable_size_deltas_report)

    compilesketches.main()

    expected_output = ""
    if use_enable_size_deltas_report:
        expected_output = (
            expected_output
            + "::warning::The enable-size-deltas-report input is deprecated. Use the equivalent input: "
              "enable-deltas-report instead."
        )

    assert capsys.readouterr().out.strip() == expected_output

    if use_enable_size_deltas_report:
        expected_enable_deltas_report = enable_size_deltas_report
    else:
        expected_enable_deltas_report = setup_action_inputs.enable_deltas_report

    assert os.environ["INPUT_ENABLE-DELTAS-REPORT"] == expected_enable_deltas_report


def test_main(mocker, setup_action_inputs):
    class CompileSketches:
        def compile_sketches(self):
            pass  # pragma: no cover

    mocker.patch("compilesketches.CompileSketches", autospec=True, return_value=CompileSketches())
    mocker.patch.object(CompileSketches, "compile_sketches")

    compilesketches.main()

    compilesketches.CompileSketches.assert_called_once_with(
        cli_version=setup_action_inputs.cli_version,
        fqbn_arg=setup_action_inputs.fqbn_arg,
        platforms=setup_action_inputs.platforms,
        libraries=setup_action_inputs.libraries,
        sketch_paths=setup_action_inputs.sketch_paths,
        cli_compile_flags=setup_action_inputs.cli_compile_flags,
        verbose=setup_action_inputs.verbose,
        github_token=setup_action_inputs.github_token,
        enable_deltas_report=setup_action_inputs.enable_deltas_report,
        enable_warnings_report=setup_action_inputs.enable_warnings_report,
        sketches_report_path=setup_action_inputs.sketches_report_path
    )

    CompileSketches.compile_sketches.assert_called_once()


def test_compilesketches():
    expected_fqbn = "foo:bar:baz"
    expected_additional_url = "https://example.com/package_foo_index.json"
    cli_version = unittest.mock.sentinel.cli_version
    platforms = unittest.mock.sentinel.platforms
    libraries = unittest.mock.sentinel.libraries
    sketch_paths = "examples/FooSketchPath examples/BarSketchPath"
    expected_sketch_paths_list = [compilesketches.absolute_path(path="examples/FooSketchPath"),
                                  compilesketches.absolute_path(path="examples/BarSketchPath")]
    cli_compile_flags = "- --foo\n- --bar"
    expected_cli_compile_flags = ["--foo", "--bar"]
    verbose = "false"
    github_token = "fooGitHubToken"
    expected_deltas_base_ref = unittest.mock.sentinel.deltas_base_ref
    enable_deltas_report = "true"
    enable_warnings_report = "true"
    sketches_report_path = "FooSketchesReportFolder"

    with unittest.mock.patch("compilesketches.CompileSketches.get_deltas_base_ref",
                             autospec=True,
                             return_value=expected_deltas_base_ref):
        compile_sketches = compilesketches.CompileSketches(
            cli_version=cli_version,
            fqbn_arg="\'\"" + expected_fqbn + "\" \"" + expected_additional_url + "\"\'",
            platforms=platforms,
            libraries=libraries,
            sketch_paths=sketch_paths,
            cli_compile_flags=cli_compile_flags,
            verbose=verbose,
            github_token=github_token,
            enable_deltas_report=enable_deltas_report,
            enable_warnings_report=enable_warnings_report,
            sketches_report_path=sketches_report_path
        )

    assert compile_sketches.cli_version == cli_version
    assert compile_sketches.fqbn == expected_fqbn
    assert compile_sketches.additional_url == expected_additional_url
    assert compile_sketches.platforms == platforms
    assert compile_sketches.libraries == libraries
    assert compile_sketches.sketch_paths == expected_sketch_paths_list
    assert compile_sketches.cli_compile_flags == expected_cli_compile_flags
    assert compile_sketches.verbose is False
    assert compile_sketches.deltas_base_ref == expected_deltas_base_ref
    assert compile_sketches.enable_deltas_report is True
    assert compile_sketches.enable_warnings_report is True
    assert compile_sketches.sketches_report_path == pathlib.PurePath(sketches_report_path)

    assert get_compilesketches_object(cli_compile_flags="").cli_compile_flags is None
    assert get_compilesketches_object(cli_compile_flags="- --foo").cli_compile_flags == ["--foo"]
    assert get_compilesketches_object(cli_compile_flags="- --foo\n- \"bar baz\"").cli_compile_flags == ["--foo",
                                                                                                        "bar baz"]

    # Test invalid enable_deltas_report value
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_deltas_report="fooInvalidEnableSizeDeltasBoolean")

    # Test invalid enable_deltas_report value
    with pytest.raises(expected_exception=SystemExit, match="1"):
        get_compilesketches_object(enable_warnings_report="fooInvalidEnableWarningsReportBoolean")

    # Test deltas_base_ref when size deltas report is disabled
    compile_sketches = get_compilesketches_object(enable_deltas_report="false")
    assert compile_sketches.deltas_base_ref is None


@pytest.mark.parametrize("event_name, expected_ref",
                         [("pull_request", unittest.mock.sentinel.pull_request_base_ref),
                          ("push", unittest.mock.sentinel.parent_commit_ref)])
def test_get_deltas_base_ref(monkeypatch, mocker, event_name, expected_ref):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event_name)

    mocker.patch("compilesketches.CompileSketches.get_pull_request_base_ref", autospec=True,
                 return_value=unittest.mock.sentinel.pull_request_base_ref)
    mocker.patch("compilesketches.get_parent_commit_ref", autospec=True,
                 return_value=unittest.mock.sentinel.parent_commit_ref)

    compile_sketches = get_compilesketches_object()

    assert compile_sketches.get_deltas_base_ref() == expected_ref


def test_get_pull_request_base_ref(monkeypatch, mocker):
    class Github:
        """Stub"""
        ref = unittest.mock.sentinel.pull_request_base_ref

        def __init__(self):
            self.base = self

        def get_repo(self):
            pass  # pragma: no cover

        def get_pull(self, number):
            pass  # pragma: no cover

    github_api_object = Github()
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(test_data_path.joinpath("githubevent.json")))
    monkeypatch.setenv("GITHUB_REPOSITORY", "fooRepository/fooOwner")

    mocker.patch.object(Github, "get_repo", return_value=Github())
    mocker.patch.object(Github, "get_pull", return_value=Github())

    compile_sketches = get_compilesketches_object(github_api=github_api_object)

    assert compile_sketches.get_pull_request_base_ref() == unittest.mock.sentinel.pull_request_base_ref

    github_api_object.get_repo.assert_called_once_with(full_name_or_id=os.environ["GITHUB_REPOSITORY"])
    github_api_object.get_pull.assert_called_once_with(number=42)  # PR number is hardcoded into test file

    mocker.patch.object(Github,
                        "get_repo",
                        side_effect=github.UnknownObjectException(status=42, data="foo", headers=None))
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.get_pull_request_base_ref()


def test_get_parent_commit_ref(mocker):
    parent_commit_ref = unittest.mock.sentinel.parent_commit_ref

    class Repo:
        """Stub"""
        hexsha = parent_commit_ref

        def __init__(self):
            self.head = self
            self.object = self
            self.parents = [self]

    mocker.patch("git.Repo", autospec=True, return_value=Repo())

    assert compilesketches.get_parent_commit_ref() == parent_commit_ref
    git.Repo.assert_called_once_with(path=os.environ["GITHUB_WORKSPACE"])


@pytest.mark.parametrize("enable_warnings_report, expected_clean_build_cache",
                         [("true", True),
                          ("false", False)])
@pytest.mark.parametrize("compilation_success_list, expected_success",
                         [([True, True, True], True),
                          ([False, True, True], False),
                          ([True, False, True], False),
                          ([True, True, False], False)])
def test_compile_sketches(mocker, enable_warnings_report, expected_clean_build_cache, compilation_success_list,
                          expected_success):
    sketch_list = [unittest.mock.sentinel.sketch1, unittest.mock.sentinel.sketch2, unittest.mock.sentinel.sketch3]

    compilation_result_list = []
    for success in compilation_success_list:
        compilation_result_list.append(type("CompilationResult", (), {"success": success}))
    sketch_report = unittest.mock.sentinel.sketch_report
    sketches_report = unittest.mock.sentinel.sketch_report_from_sketches_report

    compile_sketches = get_compilesketches_object(enable_warnings_report=enable_warnings_report)

    mocker.patch("compilesketches.CompileSketches.install_arduino_cli", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_platforms", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries", autospec=True)
    mocker.patch("compilesketches.CompileSketches.find_sketches", autospec=True, return_value=sketch_list)
    mocker.patch("compilesketches.CompileSketches.compile_sketch", autospec=True, side_effect=compilation_result_list)
    mocker.patch("compilesketches.CompileSketches.get_sketch_report", autospec=True, return_value=sketch_report)
    mocker.patch("compilesketches.CompileSketches.get_sketches_report", autospec=True,
                 return_value=sketches_report)
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
    sketch_report_list = []
    for sketch, compilation_result in zip(sketch_list, compilation_result_list):
        compile_sketch_calls.append(unittest.mock.call(compile_sketches,
                                                       sketch_path=sketch,
                                                       clean_build_cache=expected_clean_build_cache))
        get_sketch_report_calls.append(unittest.mock.call(compile_sketches,
                                                          compilation_result=compilation_result))
        sketch_report_list.append(sketch_report)
    compile_sketches.compile_sketch.assert_has_calls(calls=compile_sketch_calls)
    compile_sketches.get_sketch_report.assert_has_calls(calls=get_sketch_report_calls)

    compile_sketches.get_sketches_report.assert_called_once_with(compile_sketches,
                                                                 sketch_report_list=sketch_report_list)

    compile_sketches.create_sketches_report_file.assert_called_once_with(
        compile_sketches,
        sketches_report=sketches_report
    )


def test_install_arduino_cli(mocker):
    cli_version = "1.2.3"
    arduino_cli_installation_path = unittest.mock.sentinel.arduino_cli_installation_path
    arduino_cli_data_directory_path = pathlib.PurePath("/foo/arduino_cli_data_directory_path")
    arduino_cli_user_directory_path = pathlib.PurePath("/foo/arduino_cli_user_directory_path")

    compile_sketches = get_compilesketches_object(cli_version=cli_version)
    compile_sketches.arduino_cli_installation_path = arduino_cli_installation_path
    compile_sketches.arduino_cli_user_directory_path = arduino_cli_user_directory_path
    compile_sketches.arduino_cli_data_directory_path = arduino_cli_data_directory_path

    mocker.patch("compilesketches.CompileSketches.install_from_download", autospec=True)

    compile_sketches.install_arduino_cli()

    compile_sketches.install_from_download.assert_called_once_with(
        compile_sketches,
        url="https://downloads.arduino.cc/arduino-cli/arduino-cli_" + cli_version + "_Linux_64bit.tar.gz",
        source_path="arduino-cli",
        destination_parent_path=arduino_cli_installation_path,
        force=False
    )

    assert os.environ["ARDUINO_DIRECTORIES_USER"] == str(arduino_cli_user_directory_path)
    assert os.environ["ARDUINO_DIRECTORIES_DATA"] == str(arduino_cli_data_directory_path)
    del os.environ["ARDUINO_DIRECTORIES_USER"]
    del os.environ["ARDUINO_DIRECTORIES_DATA"]


@pytest.mark.parametrize("platforms", ["", "foo"])
def test_install_platforms(mocker, platforms):
    fqbn_platform_dependency = unittest.mock.sentinel.fqbn_platform_dependency
    dependency_list_manager = [unittest.mock.sentinel.manager]
    dependency_list_path = [unittest.mock.sentinel.path]
    dependency_list_repository = [unittest.mock.sentinel.repository]
    dependency_list_download = [unittest.mock.sentinel.download]

    dependency_list = compilesketches.CompileSketches.Dependencies()
    dependency_list.manager = dependency_list_manager
    dependency_list.path = dependency_list_path
    dependency_list.repository = dependency_list_repository
    dependency_list.download = dependency_list_download

    compile_sketches = get_compilesketches_object(platforms=platforms)

    mocker.patch("compilesketches.CompileSketches.get_fqbn_platform_dependency",
                 autospec=True,
                 return_value=fqbn_platform_dependency)
    mocker.patch("compilesketches.CompileSketches.sort_dependency_list",
                 autospec=True,
                 return_value=dependency_list)
    mocker.patch("compilesketches.CompileSketches.install_platforms_from_board_manager", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_platforms_from_path", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_platforms_from_repository", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_platforms_from_download", autospec=True)

    compile_sketches.install_platforms()

    if platforms == "":
        compile_sketches.install_platforms_from_board_manager.assert_called_once_with(
            compile_sketches,
            platform_list=[fqbn_platform_dependency]
        )
        compile_sketches.install_platforms_from_path.assert_not_called()
        compile_sketches.install_platforms_from_repository.assert_not_called()
        compile_sketches.install_platforms_from_download.assert_not_called()
    else:
        compile_sketches.install_platforms_from_board_manager.assert_called_once_with(
            compile_sketches,
            platform_list=dependency_list_manager
        )
        compile_sketches.install_platforms_from_path.assert_called_once_with(
            compile_sketches,
            platform_list=dependency_list_path
        )
        compile_sketches.install_platforms_from_repository.assert_called_once_with(
            compile_sketches,
            platform_list=dependency_list_repository
        )
        compile_sketches.install_platforms_from_download.assert_called_once_with(
            compile_sketches,
            platform_list=dependency_list_download
        )


@pytest.mark.parametrize(
    "fqbn_arg, expected_platform, expected_additional_url",
    [("arduino:avr:uno", "arduino:avr", None),
     # FQBN with space, additional Board Manager URL
     ('\'"foo bar:baz:asdf" "https://example.com/platform_foo_index.json"\'', "foo bar:baz",
      "https://example.com/platform_foo_index.json"),
     # Custom board option
     ("arduino:avr:nano:cpu=atmega328old", "arduino:avr", None)]
)
def test_get_fqbn_platform_dependency(fqbn_arg, expected_platform, expected_additional_url):
    compile_sketches = get_compilesketches_object(fqbn_arg=fqbn_arg)

    fqbn_platform_dependency = compile_sketches.get_fqbn_platform_dependency()

    assert fqbn_platform_dependency[compilesketches.CompileSketches.dependency_name_key] == expected_platform
    if expected_additional_url is not None:
        assert fqbn_platform_dependency[compilesketches.CompileSketches.dependency_source_url_key] == (
            expected_additional_url
        )


@pytest.mark.parametrize(
    "dependency_list, expected_dependency_type_list",
    [([None], []),
     ([{compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/foo/bar.git"}], ["repository"]),
     (
         [{compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/foo/bar.git/"}],
         ["repository"]),
     ([{compilesketches.CompileSketches.dependency_source_url_key: "git://example.com/foo/bar"}], ["repository"]),
     ([{compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/foo/bar"}], ["download"]),
     ([{compilesketches.CompileSketches.dependency_source_path_key: "foo/bar"}], ["path"]),
     ([{compilesketches.CompileSketches.dependency_name_key: "FooBar"}], ["manager"]),
     ([{compilesketches.CompileSketches.dependency_name_key: "FooBar",
        compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/package_foo_index.json"}],
      ["manager"]),
     ([{compilesketches.CompileSketches.dependency_source_url_key: "git://example.com/foo/bar"},
       {compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/foo/bar"},
       {compilesketches.CompileSketches.dependency_source_path_key: "foo/bar"},
       {compilesketches.CompileSketches.dependency_name_key: "FooBar"}],
      ["repository", "download", "path", "manager"]),
     ([{compilesketches.CompileSketches.dependency_source_url_key: "git://example.com/foo/bar"}], ["repository"]),
     ]
)
def test_sort_dependency_list(dependency_list, expected_dependency_type_list):
    compile_sketches = get_compilesketches_object()

    for dependency, expected_dependency_type in zip(dependency_list, expected_dependency_type_list):
        assert dependency in getattr(compile_sketches.sort_dependency_list(dependency_list=[dependency]),
                                     expected_dependency_type)


@pytest.mark.parametrize(
    "platform_list, expected_core_update_index_command_list, expected_core_install_command_list",
    [(
        [{compilesketches.CompileSketches.dependency_name_key: "Foo"},
         {compilesketches.CompileSketches.dependency_name_key: "Bar"}],
        [["core", "update-index"], ["core", "update-index"]],
        [["core", "install", "Foo"], ["core", "install", "Bar"]]
    ), (
        # Additional Board Manager URL
        [{compilesketches.CompileSketches.dependency_name_key: "Foo",
          compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/package_foo_index.json"},
         {compilesketches.CompileSketches.dependency_name_key: "Bar",
          compilesketches.CompileSketches.dependency_source_url_key: "https://example.com/package_bar_index.json"}],
        [["core", "update-index", "--additional-urls", "https://example.com/package_foo_index.json"],
         ["core", "update-index", "--additional-urls", "https://example.com/package_bar_index.json"]],
        [["core", "install", "--additional-urls", "https://example.com/package_foo_index.json", "Foo"],
         ["core", "install", "--additional-urls", "https://example.com/package_bar_index.json", "Bar"]]
    )])
def test_install_platforms_from_board_manager(mocker,
                                              platform_list,
                                              expected_core_update_index_command_list,
                                              expected_core_install_command_list):
    run_command_output_level = unittest.mock.sentinel.run_command_output_level

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_run_command_output_level", autospec=True,
                 return_value=run_command_output_level)
    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True)

    compile_sketches.install_platforms_from_board_manager(platform_list=platform_list)

    run_arduino_cli_command_calls = []
    for expected_core_update_index_command, expected_core_install_command in zip(
        expected_core_update_index_command_list,
        expected_core_install_command_list
    ):
        run_arduino_cli_command_calls.extend([
            unittest.mock.call(compile_sketches,
                               command=expected_core_update_index_command,
                               enable_output=run_command_output_level),
            unittest.mock.call(compile_sketches,
                               command=expected_core_install_command,
                               enable_output=run_command_output_level)
        ])

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
    "path_exists, platform_list",
    [(False, [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.Path("Foo")}]),
     (True, [{compilesketches.CompileSketches.dependency_source_path_key: pathlib.Path("Foo")}])]
)
def test_install_platforms_from_path(capsys, mocker, path_exists, platform_list):
    class PlatformInstallationPath:
        def __init__(self):
            self.path = pathlib.PurePath()
            self.is_overwrite = False

    platform_installation_path = PlatformInstallationPath()
    platform_installation_path.path = pathlib.Path("/foo/PlatformInstallationPathParent/PlatformInstallationPathName")

    compile_sketches = get_compilesketches_object()

    mocker.patch.object(pathlib.Path, "exists", autospec=True, return_value=path_exists)
    mocker.patch("compilesketches.CompileSketches.get_platform_installation_path",
                 autospec=True,
                 return_value=platform_installation_path)
    mocker.patch("compilesketches.CompileSketches.install_from_path", autospec=True)

    if not path_exists:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            compile_sketches.install_platforms_from_path(platform_list=platform_list)

        assert capsys.readouterr().out.strip() == (
            "::error::Platform source path: "
            + str(platform_list[0][compilesketches.CompileSketches.dependency_source_path_key])
            + " doesn't exist"
        )

    else:
        compile_sketches.install_platforms_from_path(platform_list=platform_list)

        get_platform_installation_path_calls = []
        install_from_path_calls = []
        for platform in platform_list:
            get_platform_installation_path_calls.append(unittest.mock.call(compile_sketches, platform=platform))
            install_from_path_calls.append(
                unittest.mock.call(
                    compile_sketches,
                    source_path=compilesketches.absolute_path(
                        platform[compilesketches.CompileSketches.dependency_source_path_key]
                    ),
                    destination_parent_path=platform_installation_path.path.parent,
                    destination_name=platform_installation_path.path.name,
                    force=platform_installation_path.is_overwrite
                )
            )

        # noinspection PyUnresolvedReferences
        compile_sketches.get_platform_installation_path.assert_has_calls(calls=get_platform_installation_path_calls)
        # noinspection PyUnresolvedReferences
        compile_sketches.install_from_path.assert_has_calls(calls=install_from_path_calls)


@pytest.mark.parametrize(
    "platform,"
    "command_data_stdout,"
    "expected_installation_path",
    # No match to previously installed platforms
    [({compilesketches.CompileSketches.dependency_name_key: "foo:bar"},
      "[{\"ID\": \"asdf:zxcv\"}]",
      pathlib.PurePath("/foo/UserPlatformsPath/foo/bar")),
     # Match with previously installed platform
     ({compilesketches.CompileSketches.dependency_name_key: "foo:bar"},
      "[{\"ID\": \"foo:bar\", \"Installed\": \"1.2.3\"}]",
      pathlib.PurePath("/foo/BoardManagerPlatformsPath/foo/hardware/bar/1.2.3"))]
)
def test_get_platform_installation_path(mocker,
                                        platform,
                                        command_data_stdout,
                                        expected_installation_path):
    class CommandData:
        def __init__(self, stdout):
            self.stdout = stdout

    command_data = CommandData(stdout=command_data_stdout)

    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True, return_value=command_data)

    compile_sketches = get_compilesketches_object()
    compile_sketches.user_platforms_path = pathlib.PurePath("/foo/UserPlatformsPath")
    compile_sketches.board_manager_platforms_path = pathlib.PurePath("/foo/BoardManagerPlatformsPath")

    platform_installation_path = compile_sketches.get_platform_installation_path(platform=platform)
    assert platform_installation_path.path == expected_installation_path

    run_arduino_cli_command_calls = [unittest.mock.call(compile_sketches, command=["core", "update-index"]),
                                     unittest.mock.call(compile_sketches, command=["core", "list", "--format", "json"])]
    compilesketches.CompileSketches.run_arduino_cli_command.assert_has_calls(calls=run_arduino_cli_command_calls)


def test_install_platforms_from_repository(mocker):
    platform_list = [
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url,
         compilesketches.CompileSketches.dependency_source_path_key: unittest.mock.sentinel.source_path,
         compilesketches.CompileSketches.dependency_destination_name_key: unittest.mock.sentinel.destination_name},
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url2}
    ]

    git_ref = unittest.mock.sentinel.git_ref

    class PlatformInstallationPath:
        def __init__(self):
            self.path = pathlib.PurePath()
            self.is_overwrite = False

    platform_installation_path = PlatformInstallationPath()
    platform_installation_path.path = pathlib.Path("/foo/PlatformInstallationPathParent/PlatformInstallationPathName")

    expected_source_path_list = [unittest.mock.sentinel.source_path, "."]
    expected_destination_name_list = [unittest.mock.sentinel.destination_name, None]

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_repository_dependency_ref", autospec=True, return_value=git_ref)
    mocker.patch("compilesketches.CompileSketches.get_platform_installation_path",
                 autospec=True,
                 return_value=platform_installation_path)
    mocker.patch("compilesketches.CompileSketches.install_from_repository", autospec=True, return_value=git_ref)

    compile_sketches.install_platforms_from_repository(platform_list=platform_list)

    get_repository_dependency_ref_calls = []
    get_platform_installation_path_calls = []
    install_from_repository_calls = []
    for platform, expected_source_path, expected_destination_name in zip(platform_list,
                                                                         expected_source_path_list,
                                                                         expected_destination_name_list):
        get_repository_dependency_ref_calls.append(unittest.mock.call(compile_sketches, dependency=platform))
        get_platform_installation_path_calls.append(unittest.mock.call(compile_sketches, platform=platform))
        install_from_repository_calls.append(
            unittest.mock.call(compile_sketches,
                               url=platform[compilesketches.CompileSketches.dependency_source_url_key],
                               git_ref=git_ref,
                               source_path=expected_source_path,
                               destination_parent_path=platform_installation_path.path.parent,
                               destination_name=platform_installation_path.path.name,
                               force=platform_installation_path.is_overwrite)
        )

    compile_sketches.get_repository_dependency_ref.assert_has_calls(calls=get_repository_dependency_ref_calls)
    compile_sketches.install_from_repository.assert_has_calls(calls=install_from_repository_calls)


@pytest.mark.parametrize(
    "dependency, expected_ref",
    [({compilesketches.CompileSketches.dependency_version_key: "1.2.3"}, "1.2.3"),
     ({}, None)]
)
def test_get_repository_dependency_ref(dependency, expected_ref):
    compile_sketches = get_compilesketches_object()
    assert compile_sketches.get_repository_dependency_ref(dependency=dependency) == expected_ref


def test_install_platforms_from_download(mocker):
    platform_list = [
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url1,
         compilesketches.CompileSketches.dependency_source_path_key: unittest.mock.sentinel.source_path,
         compilesketches.CompileSketches.dependency_destination_name_key: unittest.mock.sentinel.destination_name},
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url2}
    ]

    class PlatformInstallationPath:
        def __init__(self):
            self.path = pathlib.PurePath()
            self.is_overwrite = False

    platform_installation_path = PlatformInstallationPath()
    platform_installation_path.path = pathlib.Path("/foo/PlatformInstallationPathParent/PlatformInstallationPathName")

    expected_source_path_list = [unittest.mock.sentinel.source_path, "."]

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_platform_installation_path",
                 autospec=True,
                 return_value=platform_installation_path)
    mocker.patch("compilesketches.CompileSketches.install_from_download", autospec=True)

    compile_sketches.install_platforms_from_download(platform_list=platform_list)

    get_platform_installation_path_calls = []
    install_from_download_calls = []
    for platform, expected_source_path, in zip(platform_list, expected_source_path_list):
        get_platform_installation_path_calls.append(unittest.mock.call(compile_sketches, platform=platform))
        install_from_download_calls.append(
            unittest.mock.call(compile_sketches,
                               url=platform[compilesketches.CompileSketches.dependency_source_url_key],
                               source_path=expected_source_path,
                               destination_parent_path=platform_installation_path.path.parent,
                               destination_name=platform_installation_path.path.name,
                               force=platform_installation_path.is_overwrite)
        )
    compile_sketches.install_from_download.assert_has_calls(calls=install_from_download_calls)


@pytest.mark.parametrize(
    "libraries, expected_manager, expected_path, expected_repository, expected_download",
    [("",
      [],
      [{compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"]}],
      [],
      []),
     ("foo bar",
      [{compilesketches.CompileSketches.dependency_name_key: "foo"},
       {compilesketches.CompileSketches.dependency_name_key: "bar"}],
      [{compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"]}],
      [],
      []),
     ("\"foo\" \"bar\"",
      [{compilesketches.CompileSketches.dependency_name_key: "foo"},
       {compilesketches.CompileSketches.dependency_name_key: "bar"}],
      [{compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"]}],
      [],
      []),
     ("-",
      [],
      [],
      [],
      []),
     ("- " + compilesketches.CompileSketches.dependency_name_key + ": foo",
      [{compilesketches.CompileSketches.dependency_name_key: "foo"}],
      [],
      [],
      []),
     ("- " + compilesketches.CompileSketches.dependency_source_path_key + ": /foo/bar",
      [],
      [{compilesketches.CompileSketches.dependency_source_path_key: "/foo/bar"}],
      [],
      []),
     ("- " + compilesketches.CompileSketches.dependency_source_url_key + ": https://example.com/foo.git",
      [],
      [],
      [{"source-url": "https://example.com/foo.git"}],
      []),
     ("- " + compilesketches.CompileSketches.dependency_source_url_key + ": https://example.com/foo.zip",
      [],
      [],
      [],
      [{"source-url": "https://example.com/foo.zip"}])]
)
def test_install_libraries(mocker, libraries, expected_manager, expected_path, expected_repository,
                           expected_download):
    libraries_path = pathlib.Path("/foo/LibrariesPath")

    compile_sketches = get_compilesketches_object(libraries=libraries)
    compile_sketches.libraries_path = libraries_path

    mocker.patch("compilesketches.CompileSketches.install_libraries_from_library_manager", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries_from_path", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries_from_repository", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_libraries_from_download", autospec=True)

    compile_sketches.install_libraries()

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

    if len(expected_repository) > 0:
        compile_sketches.install_libraries_from_repository.assert_called_once_with(
            compile_sketches,
            library_list=expected_repository)
    else:
        compile_sketches.install_libraries_from_repository.assert_not_called()

    if len(expected_download) > 0:
        compile_sketches.install_libraries_from_download.assert_called_once_with(
            compile_sketches,
            library_list=expected_download)
    else:
        compile_sketches.install_libraries_from_download.assert_not_called()


def test_install_libraries_from_library_manager(mocker):
    run_command_output_level = unittest.mock.sentinel.run_command_output_level
    compile_sketches = get_compilesketches_object()

    library_list = [{compile_sketches.dependency_name_key: "foo"}, {compile_sketches.dependency_name_key: "bar"}]

    mocker.patch("compilesketches.CompileSketches.get_run_command_output_level", autospec=True,
                 return_value=run_command_output_level)
    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True)

    compile_sketches.install_libraries_from_library_manager(library_list=library_list)

    lib_install_base_command = ["lib", "install"]

    run_arduino_cli_command_calls = []
    for library in library_list:
        lib_install_command = lib_install_base_command.copy()
        lib_install_command.append(library["name"])
        run_arduino_cli_command_calls.append(
            unittest.mock.call(
                compile_sketches,
                command=lib_install_command,
                enable_output=run_command_output_level
            )
        )

    # noinspection PyUnresolvedReferences
    compile_sketches.run_arduino_cli_command.assert_has_calls(calls=run_arduino_cli_command_calls)


@pytest.mark.parametrize(
    "path_exists, library_list, expected_destination_name_list",
    [(False,
      [{compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"] + "/Nonexistent"}],
      []),
     (True,
      [{compilesketches.CompileSketches.dependency_destination_name_key: "FooName",
        compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"] + "/FooLibrary"}],
      ["FooName"]),
     (True,
      [{compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"]}],
      ["FooRepoName"]),
     (True,
      [{compilesketches.CompileSketches.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"] + "/Bar"}],
      [None])]
)
def test_install_libraries_from_path(capsys, monkeypatch, mocker, path_exists, library_list,
                                     expected_destination_name_list):
    libraries_path = pathlib.Path("/foo/LibrariesPath")

    monkeypatch.setenv("GITHUB_REPOSITORY", "foo/FooRepoName")

    compile_sketches = get_compilesketches_object()
    compile_sketches.libraries_path = libraries_path

    mocker.patch.object(pathlib.Path, "exists", autospec=True, return_value=path_exists)
    mocker.patch("compilesketches.CompileSketches.install_from_path", autospec=True)

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

        install_from_path_calls = []
        for library, expected_destination_name in zip(library_list, expected_destination_name_list):
            install_from_path_calls.append(
                unittest.mock.call(
                    compile_sketches,
                    source_path=compilesketches.absolute_path(
                        library[compilesketches.CompileSketches.dependency_source_path_key]
                    ),
                    destination_parent_path=libraries_path,
                    destination_name=expected_destination_name,
                    force=True
                )
            )

        # noinspection PyUnresolvedReferences
        compile_sketches.install_from_path.assert_has_calls(calls=install_from_path_calls)


def test_install_libraries_from_repository(mocker):
    git_ref = unittest.mock.sentinel.git_ref
    library_list = [
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url,
         compilesketches.CompileSketches.dependency_source_path_key: unittest.mock.sentinel.source_path,
         compilesketches.CompileSketches.dependency_destination_name_key: unittest.mock.sentinel.destination_name},
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url2}
    ]
    expected_source_path_list = [unittest.mock.sentinel.source_path, "."]
    expected_destination_name_list = [unittest.mock.sentinel.destination_name, None]

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_repository_dependency_ref", autospec=True, return_value=git_ref)
    mocker.patch("compilesketches.CompileSketches.install_from_repository", autospec=True, return_value=git_ref)

    compile_sketches.install_libraries_from_repository(library_list=library_list)

    get_repository_dependency_ref_calls = []
    install_from_repository_calls = []
    for library, expected_source_path, expected_destination_name in zip(library_list,
                                                                        expected_source_path_list,
                                                                        expected_destination_name_list):
        get_repository_dependency_ref_calls.append(unittest.mock.call(compile_sketches, dependency=library))
        install_from_repository_calls.append(
            unittest.mock.call(compile_sketches,
                               url=library[compilesketches.CompileSketches.dependency_source_url_key],
                               git_ref=git_ref,
                               source_path=expected_source_path,
                               destination_parent_path=compile_sketches.libraries_path,
                               destination_name=expected_destination_name,
                               force=True)
        )

    compile_sketches.get_repository_dependency_ref.assert_has_calls(calls=get_repository_dependency_ref_calls)
    compile_sketches.install_from_repository.assert_has_calls(calls=install_from_repository_calls)


def test_install_libraries_from_download(mocker):
    library_list = [
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url1,
         compilesketches.CompileSketches.dependency_source_path_key: unittest.mock.sentinel.source_path,
         compilesketches.CompileSketches.dependency_destination_name_key: unittest.mock.sentinel.destination_name},
        {compilesketches.CompileSketches.dependency_source_url_key: unittest.mock.sentinel.source_url2}
    ]

    expected_source_path_list = [unittest.mock.sentinel.source_path, "."]
    expected_destination_name_list = [unittest.mock.sentinel.destination_name, None]

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.install_from_download", autospec=True)

    compile_sketches.install_libraries_from_download(library_list=library_list)

    install_libraries_from_download_calls = []
    for library, expected_source_path, expected_destination_name in zip(library_list, expected_source_path_list,
                                                                        expected_destination_name_list):
        install_libraries_from_download_calls.append(
            unittest.mock.call(compile_sketches,
                               url=library[compilesketches.CompileSketches.dependency_source_url_key],
                               source_path=expected_source_path,
                               destination_parent_path=compilesketches.CompileSketches.libraries_path,
                               destination_name=expected_destination_name,
                               force=True)
        )
    compile_sketches.install_from_download.assert_has_calls(calls=install_libraries_from_download_calls)


def test_find_sketches(capsys):
    nonexistent_sketch_path = "/foo/NonexistentSketch"

    # Test sketch path doesn't exist
    compile_sketches = get_compilesketches_object(
        sketch_paths="\'\"" + nonexistent_sketch_path + "\"\'"
    )
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.find_sketches()
    assert capsys.readouterr().out.strip() == (
        "::error::Sketch path: "
        + str(compilesketches.path_relative_to_workspace(path=nonexistent_sketch_path))
        + " doesn't exist"
    )

    # Test sketch path is a sketch file
    compile_sketches = get_compilesketches_object(
        sketch_paths="\'" + str(test_data_path.joinpath("HasSketches", "Sketch1", "Sketch1.ino")) + "\'"
    )
    assert compile_sketches.find_sketches() == [
        test_data_path.joinpath("HasSketches", "Sketch1")
    ]

    # Test sketch path is a non-sketch file
    non_sketch_path = str(test_data_path.joinpath("NoSketches", "NotSketch", "NotSketch.foo"))
    compile_sketches = get_compilesketches_object(sketch_paths="\'" + non_sketch_path + "\'")
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.find_sketches()
    assert capsys.readouterr().out.strip() == ("::error::Sketch path: " + non_sketch_path + " is not a sketch")

    # Test sketch path is a sketch folder
    compile_sketches = get_compilesketches_object(
        sketch_paths="\'" + str(test_data_path.joinpath("HasSketches", "Sketch1")) + "\'"
    )
    assert compile_sketches.find_sketches() == [
        test_data_path.joinpath("HasSketches", "Sketch1")
    ]

    # Test sketch path does contain sketches
    compile_sketches = get_compilesketches_object(
        sketch_paths="\'" + str(test_data_path.joinpath("HasSketches")) + "\'")
    assert compile_sketches.find_sketches() == [
        test_data_path.joinpath("HasSketches", "Sketch1"),
        test_data_path.joinpath("HasSketches", "Sketch2")
    ]

    # Test sketch path doesn't contain any sketches
    no_sketches_path = str(test_data_path.joinpath("NoSketches"))
    compile_sketches = get_compilesketches_object(
        sketch_paths="\'" + no_sketches_path + "\'")
    with pytest.raises(expected_exception=SystemExit, match="1"):
        compile_sketches.find_sketches()
    assert capsys.readouterr().out.strip() == ("::error::No sketches were found in "
                                               + no_sketches_path)


@pytest.mark.parametrize(
    "input_value, expected_list, expected_was_yaml_list",
    [("", [], False),
     ("foo", ["foo"], False),
     ("\'\"foo bar\" baz\'", ["foo bar", "baz"], False),
     ("foo: bar", ["foo:", "bar"], False),
     ("-", [None], True),
     ("- foo: asdf\n  bar: qwer\n- baz: zxcv", [{"foo": "asdf", "bar": "qwer"}, {"baz": "zxcv"}], True)])
def test_get_list_from_multiformat_input(input_value, expected_list, expected_was_yaml_list):
    input_list = compilesketches.get_list_from_multiformat_input(input_value=input_value)
    assert input_list.value == expected_list
    assert input_list.was_yaml_list == expected_was_yaml_list


# noinspection PyUnresolvedReferences
@pytest.mark.parametrize(
    "source_sub_path, destination_parent_sub_path, destination_name, expected_destination_sub_path",
    [("foo/source-path",
      "bar/destination-parent-path",
      None,
      "bar/destination-parent-path/source-path"),
     ("foo/source-path",
      "bar/destination-parent-path",
      "destination-name",
      "bar/destination-parent-path/destination-name")])
@pytest.mark.parametrize("exists", ["no", "yes", "symlink", "broken"])
@pytest.mark.parametrize("force", [True, False])
@pytest.mark.parametrize("is_dir", [True, False])
def test_install_from_path(capsys,
                           tmp_path,
                           source_sub_path,
                           destination_parent_sub_path,
                           destination_name,
                           expected_destination_sub_path,
                           exists,
                           force,
                           is_dir):
    source_path = tmp_path.joinpath(source_sub_path)

    # Generate source path
    if is_dir:
        source_path.mkdir(parents=True)
    else:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.touch()

    destination_parent_path = tmp_path.joinpath(destination_parent_sub_path)
    if destination_name is None:
        destination_path = destination_parent_path.joinpath(source_path.name)
    else:
        destination_path = destination_parent_path.joinpath(destination_name)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate pre-existing destination path
    if exists == "yes":
        if is_dir:
            destination_path.mkdir(parents=True)
        else:
            # source_path.parent.mkdir(parents=True)
            destination_path.touch()
    elif exists == "symlink":
        destination_path.symlink_to(target=source_path, target_is_directory=source_path.is_dir())
    elif exists == "broken":
        destination_path.symlink_to(target=tmp_path.joinpath("nonexistent"), target_is_directory=is_dir)

    expected_destination_path = tmp_path.joinpath(expected_destination_sub_path)

    compile_sketches = get_compilesketches_object()

    if exists != "no" and not force:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            compile_sketches.install_from_path(source_path=source_path,
                                               destination_parent_path=destination_parent_path,
                                               destination_name=destination_name,
                                               force=force)
        assert capsys.readouterr().out.strip() == (
            "::error::Installation already exists: "
            + str(expected_destination_path)
        )
    else:
        compile_sketches.install_from_path(source_path=source_path,
                                           destination_parent_path=destination_parent_path,
                                           destination_name=destination_name,
                                           force=force)

        assert expected_destination_path.resolve() == source_path


def test_install_from_path_functional(tmp_path):
    source_path = tmp_path.joinpath("foo-source")
    test_file_path = source_path.joinpath("foo-test-file")
    destination_parent_path = tmp_path.joinpath("foo-destination-parent")

    compile_sketches = get_compilesketches_object()

    def prep_test_folders():
        shutil.rmtree(path=source_path, ignore_errors=True)
        source_path.mkdir(parents=True)
        test_file_path.write_text("foo test file contents")
        shutil.rmtree(path=destination_parent_path, ignore_errors=True)
        # destination_parent_path is created by install_from_path()

    # Test install of folder
    # Test naming according to source
    # Test existing destination_parent_path
    prep_test_folders()
    destination_parent_path.mkdir(parents=True)
    compile_sketches.install_from_path(source_path=source_path, destination_parent_path=destination_parent_path,
                                       destination_name=None)
    assert directories_are_same(left_directory=source_path,
                                right_directory=destination_parent_path.joinpath(source_path.name))

    # Test custom folder name
    prep_test_folders()
    destination_name = "foo-destination-name"
    compile_sketches.install_from_path(source_path=source_path,
                                       destination_parent_path=destination_parent_path,
                                       destination_name=destination_name)
    assert directories_are_same(left_directory=source_path,
                                right_directory=destination_parent_path.joinpath(destination_name))

    # Test install of file
    # Test naming according to source
    prep_test_folders()
    compile_sketches.install_from_path(source_path=test_file_path,
                                       destination_parent_path=destination_parent_path,
                                       destination_name=None)
    assert filecmp.cmp(f1=test_file_path,
                       f2=destination_parent_path.joinpath(test_file_path.name))

    # Test custom folder name
    prep_test_folders()
    destination_name = "foo-destination-name"
    compile_sketches.install_from_path(source_path=test_file_path,
                                       destination_parent_path=destination_parent_path,
                                       destination_name=destination_name)
    assert filecmp.cmp(f1=test_file_path,
                       f2=destination_parent_path.joinpath(destination_name))


def test_path_is_sketch():
    # Sketch file
    assert compilesketches.path_is_sketch(path=test_data_path.joinpath("HasSketches", "Sketch1", "Sketch1.ino")) is True

    # Not a sketch file
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("NoSketches", "NotSketch", "NotSketch.foo")) is False

    # Sketch folder with .ino sketch file
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("HasSketches", "Sketch1")) is True

    # Sketch folder with .pde sketch file
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("HasSketches", "Sketch2")) is True

    # No files in path
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("HasSketches")) is False

    # Not a sketch folder
    assert compilesketches.path_is_sketch(
        path=test_data_path.joinpath("NoSketches", "NotSketch")) is False


@pytest.mark.parametrize("clean_build_cache", [True, False])
@pytest.mark.parametrize("returncode, expected_success", [(1, False),
                                                          (0, True)])
def test_compile_sketch(capsys, mocker, clean_build_cache, returncode, expected_success):
    stdout = unittest.mock.sentinel.stdout
    sketch_path = pathlib.Path("FooSketch", "FooSketch.ino").resolve()

    build_cache_paths = [unittest.mock.sentinel.build_cache_paths1, unittest.mock.sentinel.build_cache_paths2]

    # Stub
    class CompilationData:
        _ = 42

    CompilationData.returncode = returncode
    CompilationData.stdout = stdout

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.run_arduino_cli_command", autospec=True,
                 return_value=CompilationData())
    mocker.patch.object(pathlib.Path, "glob", autospec=True, return_value=build_cache_paths)
    mocker.patch("shutil.rmtree", autospec=True)

    compilation_result = compile_sketches.compile_sketch(
        sketch_path=sketch_path,
        clean_build_cache=clean_build_cache
    )

    if clean_build_cache:
        rmtree_calls = []
        for build_cache_path in build_cache_paths:
            rmtree_calls.append(unittest.mock.call(path=build_cache_path))

        # noinspection PyUnresolvedReferences
        shutil.rmtree.assert_has_calls(calls=rmtree_calls)

    expected_stdout = (
        "::group::Compiling sketch: " + str(compilesketches.path_relative_to_workspace(path=sketch_path)) + "\n"
        + str(stdout) + "\n"
        + "::endgroup::"
    )
    if not expected_success:
        expected_stdout += "\n::error::Compilation failed"
    else:
        expected_stdout += "\nCompilation time elapsed: 0s"
    assert capsys.readouterr().out.strip() == expected_stdout

    assert compilation_result.sketch == sketch_path
    assert compilation_result.success == expected_success
    assert compilation_result.output == stdout


# noinspection PyUnresolvedReferences
@pytest.mark.parametrize("enable_warnings_report", ["true", "false"])
@pytest.mark.parametrize("do_deltas_report", [True, False])
def test_get_sketch_report(mocker, enable_warnings_report, do_deltas_report):
    original_git_ref = unittest.mock.sentinel.original_git_ref
    sizes_list = [unittest.mock.sentinel.sketch_report_list1, unittest.mock.sentinel.sketch_report_list2]
    warning_count_list = [unittest.mock.sentinel.warning_count_list1, unittest.mock.sentinel.warning_count_list2]
    sketch = "/foo/SketchName"
    success = unittest.mock.sentinel.success

    class CompilationResult:
        def __init__(self, sketch_input, success_input):
            self.sketch = sketch_input
            self.success = success_input

    compilation_result = CompilationResult(sketch_input=sketch, success_input=success)

    previous_compilation_result = unittest.mock.sentinel.previous_compilation_result
    sizes_report = unittest.mock.sentinel.sizes_report
    warnings_report = unittest.mock.sentinel.warnings_report

    # Stub
    class Repo:
        hexsha = original_git_ref

        def __init__(self):
            self.head = self
            self.object = self
            self.git = self

        def checkout(self):
            pass  # pragma: no cover

    compile_sketches = get_compilesketches_object(enable_warnings_report=enable_warnings_report)

    mocker.patch("compilesketches.CompileSketches.get_sizes_from_output", autospec=True,
                 side_effect=sizes_list)
    mocker.patch("compilesketches.CompileSketches.get_warning_count_from_output", autospec=True,
                 side_effect=warning_count_list)
    mocker.patch("compilesketches.CompileSketches.do_deltas_report", autospec=True,
                 return_value=do_deltas_report)
    mocker.patch("git.Repo", autospec=True, return_value=Repo())
    mocker.patch("compilesketches.CompileSketches.checkout_deltas_base_ref", autospec=True)
    mocker.patch("compilesketches.CompileSketches.compile_sketch", autospec=True,
                 return_value=previous_compilation_result)
    mocker.patch.object(Repo, "checkout")
    mocker.patch("compilesketches.CompileSketches.get_sizes_report", autospec=True, return_value=sizes_report)
    mocker.patch("compilesketches.CompileSketches.get_warnings_report", autospec=True, return_value=warnings_report)

    sketch_report = compile_sketches.get_sketch_report(compilation_result=compilation_result)

    get_sizes_from_output_calls = [unittest.mock.call(compile_sketches, compilation_result=compilation_result)]
    if enable_warnings_report == "true":
        get_warning_count_from_output_calls = [
            unittest.mock.call(compile_sketches, compilation_result=compilation_result)]
    else:
        get_warning_count_from_output_calls = []

    if enable_warnings_report == "true":
        expected_current_warnings = warning_count_list[0]
    else:
        expected_current_warnings = None
    # noinspection PyUnresolvedReferences
    compilesketches.CompileSketches.do_deltas_report.assert_called_once_with(compile_sketches,
                                                                             compilation_result=compilation_result,
                                                                             current_sizes=sizes_list[0],
                                                                             current_warnings=expected_current_warnings)
    if do_deltas_report:
        git.Repo.assert_called_once_with(path=os.environ["GITHUB_WORKSPACE"])
        compile_sketches.checkout_deltas_base_ref.assert_called_once()
        compile_sketches.compile_sketch.assert_called_once_with(compile_sketches,
                                                                sketch_path=compilation_result.sketch,
                                                                clean_build_cache=(enable_warnings_report == "true"))
        Repo.checkout.assert_called_once_with(original_git_ref, recurse_submodules=True)
        get_sizes_from_output_calls.append(
            unittest.mock.call(compile_sketches, compilation_result=previous_compilation_result))
        if enable_warnings_report == "true":
            get_warning_count_from_output_calls.append(
                unittest.mock.call(compile_sketches, compilation_result=previous_compilation_result))
        expected_previous_sizes = sizes_list[1]
        expected_previous_warnings = warning_count_list[1]

    else:
        expected_previous_sizes = None
        expected_previous_warnings = None

    compilesketches.CompileSketches.get_sizes_from_output.assert_has_calls(
        calls=get_sizes_from_output_calls)
    compilesketches.CompileSketches.get_warning_count_from_output.assert_has_calls(
        calls=get_warning_count_from_output_calls)

    compile_sketches.get_sizes_report.assert_called_once_with(compile_sketches,
                                                              current_sizes=sizes_list[0],
                                                              previous_sizes=expected_previous_sizes)

    if enable_warnings_report == "true":
        # noinspection PyUnresolvedReferences
        compile_sketches.get_warnings_report.assert_called_once_with(compile_sketches,
                                                                     current_warnings=warning_count_list[0],
                                                                     previous_warnings=expected_previous_warnings)

    expected_sketch_report = {
        compile_sketches.ReportKeys.name: (
            str(compilesketches.path_relative_to_workspace(path=compilation_result.sketch))
        ),
        compile_sketches.ReportKeys.compilation_success: compilation_result.success,
        compile_sketches.ReportKeys.sizes: sizes_report,
    }
    if enable_warnings_report == "true":
        expected_sketch_report[compile_sketches.ReportKeys.warnings] = warnings_report
    assert sketch_report == expected_sketch_report


@pytest.mark.parametrize(
    "compilation_success, compilation_output, flash, maximum_flash, relative_flash, ram, maximum_ram, relative_ram",
    [(False,
      "foo output",
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator),
     (True,
      "/home/per/.arduino15/packages/arduino/hardware/megaavr/1.8.5/cores/arduino/NANO_compat.cpp:23:2: warning: #warni"
      "ng \"ATMEGA328 registers emulation is enabled. You may encounter some speed issue. Please consider to disable it"
      " in the Tools menu\" [-Wcpp]\n"
      " #warning \"ATMEGA328 registers emulation is enabled. You may encounter some speed issue. Please consider to dis"
      "able it in the Tools menu\"\n"
      "  ^~~~~~~\n"
      "Sketch uses {flash} bytes (1%) of program storage space. Maximum is {maximum_flash} bytes.\n"
      "Global variables use {ram} bytes (0%) of dynamic memory, leaving 6122 bytes for local variables. Maximum is"
      " {maximum_ram} bytes.\n",
      802, 1604, 50.0, 22, 33, 66.67),
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
      "Sketch uses {flash} bytes (12%) of program storage space. Maximum is {maximum_flash} bytes.\n"
      "Global variables use {ram} bytes of dynamic memory.\n",
      32740,
      32740,
      100.0,
      3648,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator),
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
      "Sketch uses {flash} bytes (4%) of program storage space. Maximum is {maximum_flash} bytes.\n",
      12636,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator),
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
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator,
      get_compilesketches_object().not_applicable_indicator)]
)
def test_get_sizes_from_output(compilation_success,
                               compilation_output,
                               flash,
                               maximum_flash,
                               relative_flash,
                               ram,
                               maximum_ram,
                               relative_ram):
    sketch_path = pathlib.PurePath("foo/bar")
    compilation_output = compilation_output.format(flash=str(flash),
                                                   maximum_flash=str(maximum_flash),
                                                   ram=str(ram),
                                                   maximum_ram=str(maximum_ram))
    compile_sketches = get_compilesketches_object()
    compilation_result = type("CompilationResult", (),
                              {"sketch": sketch_path,
                               "success": compilation_success,
                               "output": compilation_output})

    sizes = compile_sketches.get_sizes_from_output(compilation_result=compilation_result)

    assert sizes == [
        {
            compile_sketches.ReportKeys.name: "flash",
            compile_sketches.ReportKeys.absolute: flash,
            compile_sketches.ReportKeys.maximum: maximum_flash,
            compile_sketches.ReportKeys.relative: relative_flash
        },
        {
            compile_sketches.ReportKeys.name: "RAM for global variables",
            compile_sketches.ReportKeys.absolute: ram,
            compile_sketches.ReportKeys.maximum: maximum_ram,
            compile_sketches.ReportKeys.relative: relative_ram
        }
    ]


@pytest.mark.parametrize(
    "compilation_output, memory_type, size_data_type, expected_output",
    [("foo output",
      {
          "name": "RAM for global variables",
          "regex": {
              get_compilesketches_object().ReportKeys.maximum: (
                  r"Global variables use [0-9]+ bytes .*of dynamic memory.*\. Maximum is ([0-9]+) bytes."
              )
          }
      },
      get_compilesketches_object().ReportKeys.maximum,
      None),
     ("Global variables use 11 bytes (0%) of dynamic memory, leaving 22 bytes for local variables. Maximum is"
      + " {expected_output} bytes.",
      {
          "name": "RAM for global variables",
          "regex": {
              get_compilesketches_object().ReportKeys.maximum: (
                  r"Global variables use [0-9]+ bytes .*of dynamic memory.*\. Maximum is ([0-9]+) bytes."
              )
          }
      },
      get_compilesketches_object().ReportKeys.maximum,
      42)]
)
def test_get_size_data_from_output(capsys, compilation_output, memory_type, size_data_type, expected_output):
    compilation_output = compilation_output.format(expected_output=str(expected_output))
    # print(compilation_output)
    # size_data_type=get_compilesketches_object().ReportKeys.maximum
    compile_sketches = get_compilesketches_object(verbose="true")

    size_data = compile_sketches.get_size_data_from_output(compilation_output, memory_type, size_data_type)
    assert size_data == expected_output
    if expected_output is None:
        expected_stdout = (
            "::warning::Unable to determine the: \"" + str(size_data_type) + "\" value for memory type: \""
            + memory_type["name"]
            + "\". The board's platform may not have been configured to provide this information."
        )
        assert capsys.readouterr().out.strip() == expected_stdout


@pytest.mark.parametrize(
    "compilation_success, test_compilation_output_filename, expected_warning_count",
    [(True,
      pathlib.Path("test_get_warning_count_from_output", "has-warnings.txt"),
      45),
     (True,
      pathlib.Path("test_get_warning_count_from_output", "no-warnings.txt"),
      0),
     (False,
      pathlib.Path("test_get_warning_count_from_output", "has-warnings.txt"),
      get_compilesketches_object().not_applicable_indicator)])
def test_get_warning_count_from_output(compilation_success, test_compilation_output_filename, expected_warning_count):
    compile_sketches = get_compilesketches_object()

    with open(file=test_data_path.joinpath(test_compilation_output_filename),
              mode='r',
              encoding="utf-8") as test_compilation_output_file:
        class CompilationResult:
            success = compilation_success
            output = test_compilation_output_file.read()

    assert compile_sketches.get_warning_count_from_output(CompilationResult()) == expected_warning_count


@pytest.mark.parametrize(
    "enable_deltas_report,"
    "compilation_success,"
    "current_sizes,"
    "current_warnings,"
    "do_deltas_report_expected",
    [("true",
      True,
      [{compilesketches.CompileSketches.ReportKeys.name: "foo",
        compilesketches.CompileSketches.ReportKeys.absolute: 24},
       {compilesketches.CompileSketches.ReportKeys.name: "bar",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator}],
      compilesketches.CompileSketches.not_applicable_indicator,
      True),
     ("true",
      True,
      [{compilesketches.CompileSketches.ReportKeys.name: "foo",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator},
       {compilesketches.CompileSketches.ReportKeys.name: "bar",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator}],
      42,
      True),
     ("false",
      True,
      [{compilesketches.CompileSketches.ReportKeys.name: "foo",
        compilesketches.CompileSketches.ReportKeys.absolute: 24}],
      True,
      False),
     ("true",
      False,
      [{compilesketches.CompileSketches.ReportKeys.name: "foo",
        compilesketches.CompileSketches.ReportKeys.absolute: 24}],
      42,
      False),
     ("true",
      True,
      [{compilesketches.CompileSketches.ReportKeys.name: "foo",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator},
       {compilesketches.CompileSketches.ReportKeys.name: "bar",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator}],
      compilesketches.CompileSketches.not_applicable_indicator,
      False),
     ("true",
      True,
      [{compilesketches.CompileSketches.ReportKeys.name: "foo",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator},
       {compilesketches.CompileSketches.ReportKeys.name: "bar",
        compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator}],
      None,
      False)
     ]
)
def test_do_deltas_report(monkeypatch,
                          enable_deltas_report,
                          compilation_success,
                          current_sizes,
                          current_warnings,
                          do_deltas_report_expected):
    compile_sketches = get_compilesketches_object(enable_deltas_report=enable_deltas_report)

    compilation_result = type("CompilationResult", (),
                              {"sketch": "/foo/SketchName",
                               "success": compilation_success,
                               "output": "foo compilation output"})
    assert compile_sketches.do_deltas_report(compilation_result=compilation_result,
                                             current_sizes=current_sizes,
                                             current_warnings=current_warnings) == do_deltas_report_expected


def test_checkout_deltas_base_ref(monkeypatch, mocker):
    deltas_base_ref = unittest.mock.sentinel.deltas_base_ref

    # Stubs
    class Repo:
        def __init__(self):
            self.remotes = {"origin": self}
            self.git = self

        def fetch(self):
            pass  # pragma: no cover

        def checkout(self):
            pass  # pragma: no cover

    compile_sketches = get_compilesketches_object(enable_deltas_report="true", deltas_base_ref=deltas_base_ref)

    mocker.patch("git.Repo", autospec=True, return_value=Repo())
    mocker.patch.object(Repo, "fetch")
    mocker.patch.object(Repo, "checkout")

    compile_sketches.checkout_deltas_base_ref()

    git.Repo.assert_called_once_with(path=os.environ["GITHUB_WORKSPACE"])
    Repo.fetch.assert_called_once_with(refspec=deltas_base_ref,
                                       verbose=compile_sketches.verbose,
                                       no_tags=True,
                                       prune=True,
                                       depth=1,
                                       recurse_submodules=True)
    Repo.checkout.assert_called_once_with(deltas_base_ref, recurse_submodules=True)


def test_get_sizes_report(mocker):
    sizes_report = [unittest.mock.sentinel.size_report1, unittest.mock.sentinel.size_report1]
    current_sizes = [unittest.mock.sentinel.current_sizes1, unittest.mock.sentinel.current_sizes2]
    previous_sizes = [unittest.mock.sentinel.previous_sizes1, unittest.mock.sentinel.previous_sizes2]

    compile_sketches = get_compilesketches_object()

    mocker.patch("compilesketches.CompileSketches.get_size_report", autospec=True, side_effect=sizes_report)

    assert compile_sketches.get_sizes_report(current_sizes=current_sizes, previous_sizes=previous_sizes) == sizes_report

    get_size_report_calls = []
    for current_size, previous_size in zip(current_sizes, previous_sizes):
        get_size_report_calls.append(unittest.mock.call(compile_sketches,
                                                        current_size=current_size,
                                                        previous_size=previous_size))

    compile_sketches.get_size_report.assert_has_calls(get_size_report_calls)

    # Test size deltas not enabled
    previous_sizes = None
    mocker.resetall()
    compilesketches.CompileSketches.get_size_report.side_effect = sizes_report
    assert compile_sketches.get_sizes_report(current_sizes=current_sizes, previous_sizes=previous_sizes) == sizes_report

    get_size_report_calls = []
    for current_size in current_sizes:
        get_size_report_calls.append(unittest.mock.call(compile_sketches,
                                                        current_size=current_size,
                                                        previous_size=None))

    compile_sketches.get_size_report.assert_has_calls(get_size_report_calls)


@pytest.mark.parametrize(
    "size_maximum, current_absolute, previous_size, expected_absolute_delta, expected_relative_delta",
    [(compilesketches.CompileSketches.not_applicable_indicator,
      compilesketches.CompileSketches.not_applicable_indicator,
      {compilesketches.CompileSketches.ReportKeys.absolute: 11,
       compilesketches.CompileSketches.ReportKeys.relative: 9.91},
      compilesketches.CompileSketches.not_applicable_indicator,
      compilesketches.CompileSketches.not_applicable_indicator),
     (111,
      42,
      {compilesketches.CompileSketches.ReportKeys.absolute: compilesketches.CompileSketches.not_applicable_indicator,
       compilesketches.CompileSketches.ReportKeys.relative: compilesketches.CompileSketches.not_applicable_indicator},
      compilesketches.CompileSketches.not_applicable_indicator,
      compilesketches.CompileSketches.not_applicable_indicator),
     (111,
      42,
      {compilesketches.CompileSketches.ReportKeys.absolute: 11,
       compilesketches.CompileSketches.ReportKeys.relative: 9.91},
      31,
      27.93),
     (111,
      42,
      None,
      None,
      None)]
)
def test_get_size_report(capsys,
                         size_maximum,
                         current_absolute,
                         previous_size,
                         expected_absolute_delta,
                         expected_relative_delta):
    size_name = "Foo size name"
    current_relative = 42
    current_size = {
        compilesketches.CompileSketches.ReportKeys.name: size_name,
        compilesketches.CompileSketches.ReportKeys.maximum: size_maximum,
        compilesketches.CompileSketches.ReportKeys.absolute: current_absolute,
        compilesketches.CompileSketches.ReportKeys.relative: current_relative
    }
    expected_size_report = {
        compilesketches.CompileSketches.ReportKeys.name: size_name,
        compilesketches.CompileSketches.ReportKeys.maximum: size_maximum,
        compilesketches.CompileSketches.ReportKeys.current: {
            compilesketches.CompileSketches.ReportKeys.absolute: current_absolute,
            compilesketches.CompileSketches.ReportKeys.relative: current_relative
        }
    }

    compile_sketches = get_compilesketches_object()

    size_report = compile_sketches.get_size_report(current_size=current_size, previous_size=previous_size)

    if previous_size is None:
        assert capsys.readouterr().out.strip() == ""
    else:
        expected_size_report[compilesketches.CompileSketches.ReportKeys.previous] = {
            compilesketches.CompileSketches.ReportKeys.absolute: previous_size[
                compilesketches.CompileSketches.ReportKeys.absolute],
            compilesketches.CompileSketches.ReportKeys.relative: previous_size[
                compilesketches.CompileSketches.ReportKeys.relative]
        }
        expected_size_report[compilesketches.CompileSketches.ReportKeys.delta] = {
            compilesketches.CompileSketches.ReportKeys.absolute: expected_absolute_delta,
            compilesketches.CompileSketches.ReportKeys.relative: expected_relative_delta
        }
        if expected_relative_delta == compilesketches.CompileSketches.not_applicable_indicator:
            assert capsys.readouterr().out.strip() == ("Change in " + size_name + ": " + str(expected_absolute_delta))
        else:
            assert capsys.readouterr().out.strip() == (
                "Change in " + size_name + ": " + str(expected_absolute_delta) + " (" + str(expected_relative_delta)
                + "%)"
            )

    assert size_report == expected_size_report


@pytest.mark.parametrize(
    "current_warnings, previous_warnings, expected_report",
    [(42,
      None,
      {
          compilesketches.CompileSketches.ReportKeys.current: {
              compilesketches.CompileSketches.ReportKeys.absolute: 42
          }
      }),
     (42,
      compilesketches.CompileSketches.not_applicable_indicator,
      {
          compilesketches.CompileSketches.ReportKeys.current: {
              compilesketches.CompileSketches.ReportKeys.absolute: 42
          },
          compilesketches.CompileSketches.ReportKeys.previous: {
              compilesketches.CompileSketches.ReportKeys.absolute: (
                  compilesketches.CompileSketches.not_applicable_indicator
              )
          },
          compilesketches.CompileSketches.ReportKeys.delta: {
              compilesketches.CompileSketches.ReportKeys.absolute: (
                  compilesketches.CompileSketches.not_applicable_indicator
              )
          }
      }),
     (42,
      43,
      {
          compilesketches.CompileSketches.ReportKeys.current: {
              compilesketches.CompileSketches.ReportKeys.absolute: 42
          },
          compilesketches.CompileSketches.ReportKeys.previous: {
              compilesketches.CompileSketches.ReportKeys.absolute: 43
          },
          compilesketches.CompileSketches.ReportKeys.delta: {
              compilesketches.CompileSketches.ReportKeys.absolute: -1
          }
      })])
def test_get_warnings_report(current_warnings, previous_warnings, expected_report):
    compile_sketches = get_compilesketches_object()
    assert compile_sketches.get_warnings_report(
        current_warnings=current_warnings,
        previous_warnings=previous_warnings
    ) == expected_report


def test_get_sketches_report(monkeypatch, mocker):
    github_repository = "fooRepository/fooOwner"
    fqbn_arg = "arduino:avr:uno"
    current_git_ref = "fooref"

    monkeypatch.setenv("GITHUB_REPOSITORY", github_repository)

    mocker.patch("compilesketches.get_head_commit_hash", autospec=True, return_value=current_git_ref)

    sizes_summary_report = unittest.mock.sentinel.sizes_summary_report
    warnings_summary_report = unittest.mock.sentinel.warnings_summary_report
    sketch_report_list = unittest.mock.sentinel.sketch_report_list

    mocker.patch("compilesketches.CompileSketches.get_sizes_summary_report",
                 autospec=True,
                 return_value=sizes_summary_report)

    mocker.patch("compilesketches.CompileSketches.get_warnings_summary_report",
                 autospec=True,
                 return_value=warnings_summary_report)

    compile_sketches = get_compilesketches_object(fqbn_arg=fqbn_arg)

    assert compile_sketches.get_sketches_report(sketch_report_list=sketch_report_list) == {
        compilesketches.CompileSketches.ReportKeys.commit_hash: current_git_ref,
        compilesketches.CompileSketches.ReportKeys.commit_url: ("https://github.com/"
                                                                + github_repository
                                                                + "/commit/"
                                                                + current_git_ref),
        compilesketches.CompileSketches.ReportKeys.boards: [
            {
                compilesketches.CompileSketches.ReportKeys.board: compile_sketches.fqbn,
                compilesketches.CompileSketches.ReportKeys.sizes: sizes_summary_report,
                compilesketches.CompileSketches.ReportKeys.warnings: warnings_summary_report,
                compilesketches.CompileSketches.ReportKeys.sketches: sketch_report_list
            }
        ]
    }

    compile_sketches.get_sizes_summary_report.assert_called_once_with(compile_sketches,
                                                                      sketch_report_list=sketch_report_list)

    # noinspection PyUnresolvedReferences
    compile_sketches.get_warnings_summary_report.assert_called_once_with(compile_sketches,
                                                                         sketch_report_list=sketch_report_list)

    # Test no summary report data (size deltas not enabled)
    compilesketches.CompileSketches.get_sizes_summary_report.return_value = []
    compilesketches.CompileSketches.get_warnings_summary_report.return_value = {}

    assert compile_sketches.get_sketches_report(sketch_report_list=sketch_report_list) == {
        compilesketches.CompileSketches.ReportKeys.commit_hash: current_git_ref,
        compilesketches.CompileSketches.ReportKeys.commit_url: ("https://github.com/"
                                                                + github_repository
                                                                + "/commit/"
                                                                + current_git_ref),
        compilesketches.CompileSketches.ReportKeys.boards: [
            {
                compilesketches.CompileSketches.ReportKeys.board: compile_sketches.fqbn,
                compilesketches.CompileSketches.ReportKeys.sketches: sketch_report_list
            }
        ]
    }


def test_get_sizes_summary_report():
    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 111,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 42,
                        compilesketches.CompileSketches.ReportKeys.relative: 5.142
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 11,
                        compilesketches.CompileSketches.ReportKeys.relative: 2.242
                    }
                }
            ]
        },
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 111,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 8,
                        compilesketches.CompileSketches.ReportKeys.relative: 1.542
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 33,
                        compilesketches.CompileSketches.ReportKeys.relative: 10.042
                    }
                }
            ]
        }
    ]

    expected_sizes_summary_report = [
        {
            compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
            compilesketches.CompileSketches.ReportKeys.maximum: 111,
            compilesketches.CompileSketches.ReportKeys.delta: {
                compilesketches.CompileSketches.ReportKeys.absolute: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 8,
                    compilesketches.CompileSketches.ReportKeys.maximum: 42
                },
                compilesketches.CompileSketches.ReportKeys.relative: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 1.542,
                    compilesketches.CompileSketches.ReportKeys.maximum: 5.142
                }
            }
        },
        {
            compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
            compilesketches.CompileSketches.ReportKeys.maximum: 222,
            compilesketches.CompileSketches.ReportKeys.delta: {
                compilesketches.CompileSketches.ReportKeys.absolute: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 11,
                    compilesketches.CompileSketches.ReportKeys.maximum: 33
                },
                compilesketches.CompileSketches.ReportKeys.relative: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 2.242,
                    compilesketches.CompileSketches.ReportKeys.maximum: 10.042
                }
            }
        }
    ]

    compile_sketches = get_compilesketches_object()

    assert compile_sketches.get_sizes_summary_report(sketch_report_list=sketch_report_list) == (
        expected_sizes_summary_report
    )

    # N/A in one sketch report
    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: "N/A",
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: "N/A",
                        compilesketches.CompileSketches.ReportKeys.relative: "N/A"
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 11,
                        compilesketches.CompileSketches.ReportKeys.relative: 2.742
                    }
                }
            ]
        },
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 111,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 8,
                        compilesketches.CompileSketches.ReportKeys.relative: 2.442
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 33,
                        compilesketches.CompileSketches.ReportKeys.relative: 4.942
                    }
                }
            ]
        }
    ]

    expected_sizes_summary_report = [
        {
            compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
            compilesketches.CompileSketches.ReportKeys.maximum: 111,
            compilesketches.CompileSketches.ReportKeys.delta: {
                compilesketches.CompileSketches.ReportKeys.absolute: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 8,
                    compilesketches.CompileSketches.ReportKeys.maximum: 8
                },
                compilesketches.CompileSketches.ReportKeys.relative: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 2.442,
                    compilesketches.CompileSketches.ReportKeys.maximum: 2.442
                }
            }
        },
        {
            compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
            compilesketches.CompileSketches.ReportKeys.maximum: 222,
            compilesketches.CompileSketches.ReportKeys.delta: {
                compilesketches.CompileSketches.ReportKeys.absolute: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 11,
                    compilesketches.CompileSketches.ReportKeys.maximum: 33
                },
                compilesketches.CompileSketches.ReportKeys.relative: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 2.742,
                    compilesketches.CompileSketches.ReportKeys.maximum: 4.942
                }
            }
        }
    ]

    assert compile_sketches.get_sizes_summary_report(sketch_report_list=sketch_report_list) == (
        expected_sizes_summary_report
    )

    # N/A in all sketch reports
    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: "N/A",
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: "N/A",
                        compilesketches.CompileSketches.ReportKeys.relative: "N/A"
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 11,
                        compilesketches.CompileSketches.ReportKeys.relative: 0.842
                    }
                }
            ]
        },
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: "N/A",
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: "N/A",
                        compilesketches.CompileSketches.ReportKeys.relative: "N/A"
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.delta: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 33,
                        compilesketches.CompileSketches.ReportKeys.relative: 7.742
                    }
                }
            ]
        }
    ]

    expected_sizes_summary_report = [
        {
            compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
            compilesketches.CompileSketches.ReportKeys.maximum: "N/A",
            compilesketches.CompileSketches.ReportKeys.delta: {
                compilesketches.CompileSketches.ReportKeys.absolute: {
                    compilesketches.CompileSketches.ReportKeys.minimum: "N/A",
                    compilesketches.CompileSketches.ReportKeys.maximum: "N/A"
                },
                compilesketches.CompileSketches.ReportKeys.relative: {
                    compilesketches.CompileSketches.ReportKeys.minimum: "N/A",
                    compilesketches.CompileSketches.ReportKeys.maximum: "N/A"
                }
            }
        },
        {
            compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
            compilesketches.CompileSketches.ReportKeys.maximum: 222,
            compilesketches.CompileSketches.ReportKeys.delta: {
                compilesketches.CompileSketches.ReportKeys.absolute: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 11,
                    compilesketches.CompileSketches.ReportKeys.maximum: 33
                },
                compilesketches.CompileSketches.ReportKeys.relative: {
                    compilesketches.CompileSketches.ReportKeys.minimum: 0.842,
                    compilesketches.CompileSketches.ReportKeys.maximum: 7.742
                }
            }
        }
    ]

    assert compile_sketches.get_sizes_summary_report(sketch_report_list=sketch_report_list) == (
        expected_sizes_summary_report
    )

    # No deltas data
    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 111,
                    compilesketches.CompileSketches.ReportKeys.current: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 42,
                        compilesketches.CompileSketches.ReportKeys.relative: 2.342
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 222,
                    compilesketches.CompileSketches.ReportKeys.current: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 11,
                        compilesketches.CompileSketches.ReportKeys.relative: 1.142
                    }
                }
            ]
        },
        {
            compilesketches.CompileSketches.ReportKeys.sizes: [
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Foo memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 111,
                    compilesketches.CompileSketches.ReportKeys.current: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 5,
                        compilesketches.CompileSketches.ReportKeys.relative: 0.542
                    }
                },
                {
                    compilesketches.CompileSketches.ReportKeys.name: "Bar memory type",
                    compilesketches.CompileSketches.ReportKeys.maximum: 111,
                    compilesketches.CompileSketches.ReportKeys.current: {
                        compilesketches.CompileSketches.ReportKeys.absolute: 33,
                        compilesketches.CompileSketches.ReportKeys.relative: 3.342
                    }
                }
            ]
        }
    ]

    expected_sizes_summary_report = []

    assert compile_sketches.get_sizes_summary_report(sketch_report_list=sketch_report_list) == (
        expected_sizes_summary_report
    )


def test_get_warnings_summary_report():
    compile_sketches = get_compilesketches_object()

    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 42
                }
            },
        },
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 3
                }
            }
        }
    ]

    expected_warnings_summary_report = {
        compilesketches.CompileSketches.ReportKeys.delta: {
            compilesketches.CompileSketches.ReportKeys.absolute: {
                compilesketches.CompileSketches.ReportKeys.minimum: 3,
                compilesketches.CompileSketches.ReportKeys.maximum: 42
            }
        }
    }

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )

    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 3
                }
            },
        },
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 42
                }
            }
        }
    ]

    expected_warnings_summary_report = {
        compilesketches.CompileSketches.ReportKeys.delta: {
            compilesketches.CompileSketches.ReportKeys.absolute: {
                compilesketches.CompileSketches.ReportKeys.minimum: 3,
                compilesketches.CompileSketches.ReportKeys.maximum: 42
            }
        }
    }

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )

    # N/As
    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: compile_sketches.not_applicable_indicator
                }
            },
        },
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 3
                }
            }
        }
    ]

    expected_warnings_summary_report = {
        compilesketches.CompileSketches.ReportKeys.delta: {
            compilesketches.CompileSketches.ReportKeys.absolute: {
                compilesketches.CompileSketches.ReportKeys.minimum: 3,
                compilesketches.CompileSketches.ReportKeys.maximum: 3
            }
        }
    }

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )

    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 42
                }
            },
        },
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: compile_sketches.not_applicable_indicator
                }
            }
        }
    ]

    expected_warnings_summary_report = {
        compilesketches.CompileSketches.ReportKeys.delta: {
            compilesketches.CompileSketches.ReportKeys.absolute: {
                compilesketches.CompileSketches.ReportKeys.minimum: 42,
                compilesketches.CompileSketches.ReportKeys.maximum: 42
            }
        }
    }

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )

    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: compile_sketches.not_applicable_indicator
                }
            },
        },
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.delta: {
                    compilesketches.CompileSketches.ReportKeys.absolute: compile_sketches.not_applicable_indicator
                }
            }
        }
    ]

    expected_warnings_summary_report = {
        compilesketches.CompileSketches.ReportKeys.delta: {
            compilesketches.CompileSketches.ReportKeys.absolute: {
                compilesketches.CompileSketches.ReportKeys.minimum: compile_sketches.not_applicable_indicator,
                compilesketches.CompileSketches.ReportKeys.maximum: compile_sketches.not_applicable_indicator
            }
        }
    }

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )

    # Test with deltas disabled
    sketch_report_list = [
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.current: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 42
                }
            },
        },
        {
            compilesketches.CompileSketches.ReportKeys.warnings: {
                compilesketches.CompileSketches.ReportKeys.current: {
                    compilesketches.CompileSketches.ReportKeys.absolute: 3
                }
            }
        }
    ]

    expected_warnings_summary_report = {}

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )

    # Test with warnings report disabled
    sketch_report_list = [{}, {}]

    expected_warnings_summary_report = {}

    assert compile_sketches.get_warnings_summary_report(sketch_report_list=sketch_report_list) == (
        expected_warnings_summary_report
    )


def test_create_sketches_report_file(monkeypatch, tmp_path):
    sketches_report_path = tmp_path
    sketches_report = [{
        "sketch": "examples/Foo",
        "compilation_success": True,
        "flash": 444,
        "ram": 9,
        "previous_flash": 1438,
        "previous_ram": 184,
        "flash_delta": -994,
        "ram_delta": -175,
        "fqbn": "arduino:avr:uno"
    }]

    compile_sketches = get_compilesketches_object(sketches_report_path=str(sketches_report_path),
                                                  fqbn_arg="arduino:avr:uno")

    compile_sketches.create_sketches_report_file(sketches_report=sketches_report)

    with open(file=str(sketches_report_path.joinpath("arduino-avr-uno.json"))) as sketch_report_file:
        assert json.load(sketch_report_file) == sketches_report


@pytest.mark.parametrize("cli_version, command, original_key, expected_key",
                         [("latest", "core list", "ID", "id"),  # Non-semver
                          ("1.0.0", "core list", "ID", "id"),  # >
                          ("0.17.0", "core list", "ID", "ID"),  # ==
                          ("0.14.0-rc2", "core list", "ID", "ID"),  # <
                          ("1.0.0", "foo", "ID", "ID"),  # Command has no translation
                          ("1.0.0", "core list", "foo", "foo")])  # Key has no translation
def test_cli_json_key(cli_version, command, original_key, expected_key):
    compile_sketches = get_compilesketches_object(cli_version=cli_version)

    assert compile_sketches.cli_json_key(command, original_key) == expected_key


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


@pytest.mark.parametrize("path, expected_relative_path",
                         # Path under workspace
                         [(os.environ["GITHUB_WORKSPACE"] + "/baz", pathlib.PurePath("baz")),
                          # Path outside workspace
                          ("/bar/foo", pathlib.Path("/").resolve().joinpath("bar", "foo"))])
def test_path_relative_to_workspace(path, expected_relative_path):
    assert compilesketches.path_relative_to_workspace(path=path) == expected_relative_path
    assert compilesketches.path_relative_to_workspace(path=pathlib.PurePath(path)) == expected_relative_path


@pytest.mark.parametrize("path, expected_absolute_path",
                         # Absolute path
                         [("/asdf", pathlib.Path("/").resolve().joinpath("asdf")),
                          # Relative path
                          ("asdf", pathlib.Path(os.environ["GITHUB_WORKSPACE"]).resolve().joinpath("asdf")),
                          # Use of ~
                          ("~/foo", pathlib.Path.home().joinpath("foo")),
                          # Use of ..
                          ("/foo/bar/../baz", pathlib.Path("/").resolve().joinpath("foo", "baz"))
                          ])
def test_absolute_path(path, expected_absolute_path):
    assert compilesketches.absolute_path(path=path) == expected_absolute_path
    assert compilesketches.absolute_path(path=pathlib.PurePath(path)) == expected_absolute_path


@pytest.mark.parametrize(
    "path, expected_path",
    [("foo/bar-relative-path", pathlib.PurePath("foo/bar-relative-path")),
     ("/foo/bar-absolute-path", pathlib.Path("/").resolve().joinpath("foo", "bar-absolute-path"))]
)
def test_absolute_relative_path_conversion(path, expected_path):
    assert compilesketches.path_relative_to_workspace(
        path=compilesketches.absolute_path(
            path=path
        )
    ) == expected_path


def test_list_to_string():
    path = pathlib.PurePath("/foo/bar")
    assert compilesketches.list_to_string([42, path]) == "42 " + str(path)


@pytest.mark.parametrize("arcname, source_path, destination_name, expected_destination_name, expected_success",
                         [("FooArcname", ".", None, "FooArcname", True),
                          ("FooArcname", "./Sketch1", "FooDestinationName", "FooDestinationName", True),
                          ("FooArcname", "Sketch1", None, "Sketch1", True),
                          (".", "Sketch1", None, "Sketch1", True),
                          ("FooArcname", "Nonexistent", None, "", False), ])
def test_install_from_download(capsys,
                               tmp_path,
                               arcname,
                               source_path,
                               destination_name,
                               expected_destination_name,
                               expected_success):
    url_source_path = test_data_path.joinpath("HasSketches")

    compile_sketches = get_compilesketches_object()

    # Create temporary folder
    url_path = tmp_path.joinpath("url_path")
    url_path.mkdir()
    url_archive_path = url_path.joinpath("foo_archive.tar.gz")
    url = url_archive_path.as_uri()

    # Create an archive file
    with tarfile.open(name=url_archive_path, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        tar.add(name=url_source_path, arcname=arcname)

    destination_parent_path = tmp_path.joinpath("destination_parent_path")

    if expected_success:
        compile_sketches.install_from_download(url=url,
                                               source_path=source_path,
                                               destination_parent_path=destination_parent_path,
                                               destination_name=destination_name)

        # Verify that the installation matches the source
        assert directories_are_same(left_directory=url_source_path.joinpath(source_path),
                                    right_directory=destination_parent_path.joinpath(expected_destination_name))
    else:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            compile_sketches.install_from_download(url=url,
                                                   source_path=source_path,
                                                   destination_parent_path=destination_parent_path,
                                                   destination_name=destination_name)
        assert capsys.readouterr().out.strip() == ("::error::Archive source path: " + source_path + " not found")


@pytest.mark.parametrize("archive_extract_path, expected_archive_root_path",
                         [(test_data_path.joinpath("test_get_archive_root_folder_name", "has-root"),
                           test_data_path.joinpath("test_get_archive_root_folder_name", "has-root", "root")),
                          (test_data_path.joinpath("test_get_archive_root_folder_name", "has-file"),
                           test_data_path.joinpath("test_get_archive_root_folder_name", "has-file")),
                          (test_data_path.joinpath("test_get_archive_root_folder_name", "has-folders"),
                           test_data_path.joinpath("test_get_archive_root_folder_name", "has-folders"))])
def test_get_archive_root_path(archive_extract_path, expected_archive_root_path):
    assert compilesketches.get_archive_root_path(archive_extract_path) == expected_archive_root_path


@pytest.mark.parametrize("url, source_path, destination_name, expected_destination_name",
                         [("https://example.com/foo/FooRepositoryName.git", ".", None, "FooRepositoryName"),
                          ("https://example.com/foo/FooRepositoryName.git/", "./examples", "FooDestinationName",
                           "FooDestinationName"),
                          ("git://example.com/foo/FooRepositoryName", "examples", None, None)])
def test_install_from_repository(mocker, url, source_path, destination_name, expected_destination_name):
    git_ref = unittest.mock.sentinel.git_ref
    destination_parent_path = unittest.mock.sentinel.destination_parent_path
    force = unittest.mock.sentinel.force
    clone_path = pathlib.PurePath("/foo/ClonePath")

    mocker.patch("tempfile.mkdtemp", autospec=True, return_value=clone_path)
    mocker.patch("compilesketches.CompileSketches.clone_repository", autospec=True)
    mocker.patch("compilesketches.CompileSketches.install_from_path", autospec=True)

    compile_sketches = get_compilesketches_object()

    compile_sketches.install_from_repository(url=url,
                                             git_ref=git_ref,
                                             source_path=source_path,
                                             destination_parent_path=destination_parent_path,
                                             destination_name=destination_name,
                                             force=force)

    # noinspection PyUnresolvedReferences
    tempfile.mkdtemp.assert_called_once_with(dir=compile_sketches.temporary_directory.name,
                                             prefix="install_from_repository-")
    compile_sketches.clone_repository.assert_called_once_with(compile_sketches,
                                                              url=url,
                                                              git_ref=git_ref,
                                                              destination_path=clone_path)
    # noinspection PyUnresolvedReferences
    compile_sketches.install_from_path.assert_called_once_with(
        compile_sketches,
        source_path=clone_path.joinpath(source_path),
        destination_parent_path=destination_parent_path,
        destination_name=expected_destination_name,
        force=force
    )


@pytest.mark.parametrize("git_ref", ["v1.0.2", "latest", None])
def test_clone_repository(tmp_path, git_ref):
    url = "https://github.com/arduino-libraries/LuckyShield"
    destination_path = tmp_path.joinpath("destination_path")

    compile_sketches = get_compilesketches_object()

    compile_sketches.clone_repository(url=url, git_ref=git_ref, destination_path=destination_path)

    # Make another clone of the repository to compare
    test_clone_path = tmp_path.joinpath("test_clone_path")
    test_clone_path.mkdir()
    if git_ref is None:
        git.Repo.clone_from(url=url, to_path=test_clone_path, depth=1)
    else:
        cloned_repository = git.Repo.clone_from(url=url, to_path=test_clone_path)

        if git_ref == "latest":
            # The repo is archived, so the latest tag will always be the same
            git_ref = "v1.0.3"

        cloned_repository.git.checkout(git_ref)

    # Verify that the installation matches the test clone
    assert directories_are_same(left_directory=destination_path,
                                right_directory=test_clone_path)


@pytest.mark.parametrize("github_event, expected_hash",
                         [("pull_request", "pull_request-head-sha"), ("push", "push-head-sha")])
def test_get_head_commit_hash(monkeypatch, mocker, github_event, expected_hash):
    # Stub
    class Repo:
        def __init__(self):
            self.git = self

        def rev_parse(self):
            pass  # pragma: no cover

    monkeypatch.setenv("GITHUB_EVENT_NAME", github_event)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(test_data_path.joinpath("githubevent.json")))

    mocker.patch("git.Repo", autospec=True, return_value=Repo())
    mocker.patch.object(Repo, "rev_parse", return_value="push-head-sha")

    assert compilesketches.get_head_commit_hash() == expected_hash
