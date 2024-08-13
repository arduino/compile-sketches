import atexit
import time
import contextlib
import enum
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib
import urllib.request

import git
import gitdb.exc
import github
import semver
import yaml
import yaml.parser


def main():
    if "INPUT_SIZE-REPORT-SKETCH" in os.environ:
        print("::warning::The size-report-sketch input is no longer used")

    if "INPUT_SIZE-DELTAS-REPORT-FOLDER-NAME" in os.environ:
        print(
            "::warning::The size-deltas-report-folder-name input is deprecated. Use the equivalent input: "
            "sketches-report-path instead."
        )
        os.environ["INPUT_SKETCHES-REPORT-PATH"] = os.environ["INPUT_SIZE-DELTAS-REPORT-FOLDER-NAME"]

    if "INPUT_ENABLE-SIZE-DELTAS-REPORT" in os.environ:
        print(
            "::warning::The enable-size-deltas-report input is deprecated. Use the equivalent input: "
            "enable-deltas-report instead."
        )
        os.environ["INPUT_ENABLE-DELTAS-REPORT"] = os.environ["INPUT_ENABLE-SIZE-DELTAS-REPORT"]

    if "INPUT_ENABLE-SIZE-TRENDS-REPORT" in os.environ:
        print(
            "::warning::The size trends report feature has been moved to a dedicated action. See the documentation "
            "at https://github.com/arduino/actions/tree/report-size-trends-action/libraries/report-size-trends"
        )

    compile_sketches = CompileSketches(
        cli_version=os.environ["INPUT_CLI-VERSION"],
        fqbn_arg=os.environ["INPUT_FQBN"],
        platforms=os.environ["INPUT_PLATFORMS"],
        libraries=os.environ["INPUT_LIBRARIES"],
        sketch_paths=os.environ["INPUT_SKETCH-PATHS"],
        cli_compile_flags=os.environ["INPUT_CLI-COMPILE-FLAGS"],
        verbose=os.environ["INPUT_VERBOSE"],
        github_token=os.environ["INPUT_GITHUB-TOKEN"],
        enable_deltas_report=os.environ["INPUT_ENABLE-DELTAS-REPORT"],
        enable_warnings_report=os.environ["INPUT_ENABLE-WARNINGS-REPORT"],
        sketches_report_path=os.environ["INPUT_SKETCHES-REPORT-PATH"],
    )

    compile_sketches.compile_sketches()


class CompileSketches:
    """Methods for compilation testing of Arduino sketches.

    Keyword arguments:
    cli_version -- version of the Arduino CLI to use
    fqbn_arg -- fully qualified board name of the board to compile for. Space separated list with Boards Manager URL if
                needed
    platforms -- YAML-format list of platforms to install
    libraries -- YAML-format or space-separated list of libraries to install
    sketch_paths -- space-separated list of paths containing sketches to compile. These paths will be searched
                    recursively for sketches.
    cli_compile_flags -- Arbitrary Arduino CLI flags to add to the compile command.
    verbose -- set to "true" for verbose output ("true", "false")
    github_token -- GitHub access token
    enable_deltas_report -- set to "true" to cause the action to determine the change in memory usage
                                 ("true", "false")
    enable_warnings_report -- set to "true" to cause the action to add compiler warning count to the sketches report
                                 ("true", "false")
    sketches_report_path -- folder to save the sketches report to
    """

    class RunCommandOutput(enum.Enum):
        NONE = enum.auto()
        ON_FAILURE = enum.auto()
        ALWAYS = enum.auto()

    not_applicable_indicator = "N/A"
    relative_size_report_decimal_places = 2

    temporary_directory = tempfile.TemporaryDirectory(prefix="compilesketches-")
    arduino_cli_installation_path = pathlib.Path.home().joinpath("bin")
    arduino_cli_user_directory_path = pathlib.Path.home().joinpath("Arduino")
    arduino_cli_data_directory_path = pathlib.Path.home().joinpath(".arduino15")
    libraries_path = arduino_cli_user_directory_path.joinpath("libraries")
    user_platforms_path = arduino_cli_user_directory_path.joinpath("hardware")
    board_manager_platforms_path = arduino_cli_data_directory_path.joinpath("packages")

    class ReportKeys:
        boards = "boards"
        board = "board"
        commit_hash = "commit_hash"
        commit_url = "commit_url"
        compilation_success = "compilation_success"
        sizes = "sizes"
        warnings = "warnings"
        name = "name"
        absolute = "absolute"
        relative = "relative"
        current = "current"
        previous = "previous"
        delta = "delta"
        minimum = "minimum"
        maximum = "maximum"
        sketches = "sketches"

    dependency_name_key = "name"
    dependency_version_key = "version"
    dependency_source_path_key = "source-path"
    dependency_source_url_key = "source-url"
    dependency_destination_name_key = "destination-name"

    latest_release_indicator = "latest"

    def __init__(
        self,
        cli_version,
        fqbn_arg,
        platforms,
        libraries,
        sketch_paths,
        cli_compile_flags,
        verbose,
        github_token,
        enable_deltas_report,
        enable_warnings_report,
        sketches_report_path,
    ):
        """Process, store, and validate the action's inputs."""
        self.cli_version = cli_version

        parsed_fqbn_arg = parse_fqbn_arg_input(fqbn_arg=fqbn_arg)
        self.fqbn = parsed_fqbn_arg["fqbn"]
        self.additional_url = parsed_fqbn_arg["additional_url"]
        self.platforms = platforms
        self.libraries = libraries

        # Save the space-separated list of paths as a Python list
        sketch_paths = get_list_from_multiformat_input(input_value=sketch_paths)
        absolute_sketch_paths = [absolute_path(path=sketch_path) for sketch_path in sketch_paths.value]
        self.sketch_paths = absolute_sketch_paths

        self.cli_compile_flags = yaml.load(stream=cli_compile_flags, Loader=yaml.SafeLoader)
        self.verbose = parse_boolean_input(boolean_input=verbose)

        if github_token == "":
            # Access token is not needed for public repositories
            self.github_api = github.Github()
        else:
            self.github_api = github.Github(login_or_token=github_token)

        self.enable_deltas_report = parse_boolean_input(boolean_input=enable_deltas_report)
        # The enable-deltas-report input has a default value so it should always be either True or False
        if self.enable_deltas_report is None:
            print("::error::Invalid value for enable-deltas-report input")
            sys.exit(1)

        self.enable_warnings_report = parse_boolean_input(boolean_input=enable_warnings_report)
        # The enable-deltas-report input has a default value so it should always be either True or False
        if self.enable_warnings_report is None:
            print("::error::Invalid value for enable-warnings-report input")
            sys.exit(1)

        if self.enable_deltas_report:
            self.deltas_base_ref = self.get_deltas_base_ref()
        else:
            # If deltas reports are not enabled, there is no use for the base ref and it could result in an GitHub API
            # request which requires a GitHub token when used in a private repository
            self.deltas_base_ref = None

        self.sketches_report_path = pathlib.PurePath(sketches_report_path)

    def get_deltas_base_ref(self):
        """Return the Git ref to make deltas comparisons against."""
        if os.environ["GITHUB_EVENT_NAME"] == "pull_request":
            # For pull requests, the comparison is done against the PR's base branch
            return self.get_pull_request_base_ref()
        else:
            # For pushes, the base ref is the immediate parent
            return get_parent_commit_ref()

    def get_pull_request_base_ref(self):
        """Return the name of the pull request's base branch."""
        # Determine the pull request number, to use for the GitHub API request
        with open(file=os.environ["GITHUB_EVENT_PATH"]) as github_event_file:
            pull_request_number = json.load(github_event_file)["pull_request"]["number"]

        # Get the PR's base ref from the GitHub API
        try:
            repository_api = self.github_api.get_repo(full_name_or_id=os.environ["GITHUB_REPOSITORY"])
        except github.UnknownObjectException:
            print(
                "::error::Unable to access repository data. Please specify the github-token input in your "
                "workflow configuration."
            )
            sys.exit(1)

        return repository_api.get_pull(number=pull_request_number).base.ref

    def compile_sketches(self):
        """Do compilation tests and record data."""
        self.install_arduino_cli()

        # Install the platform dependency
        self.install_platforms()

        # Install the library dependencies
        self.install_libraries()

        # Compile all sketches under the paths specified by the sketch-paths input
        all_compilations_successful = True
        sketch_report_list = []

        sketch_list = self.find_sketches()
        for sketch in sketch_list:
            # It's necessary to clear the cache between each compilation to get a true compiler warning count, otherwise
            # only the first sketch compilation's warning count would reflect warnings from cached code
            compilation_result = self.compile_sketch(sketch_path=sketch, clean_build_cache=self.enable_warnings_report)
            if not compilation_result.success:
                all_compilations_successful = False

            # Store the size data for this sketch
            sketch_report_list.append(self.get_sketch_report(compilation_result=compilation_result))

        sketches_report = self.get_sketches_report(sketch_report_list=sketch_report_list)

        self.create_sketches_report_file(sketches_report=sketches_report)

        if not all_compilations_successful:
            print("::error::One or more compilations failed")
            sys.exit(1)

    def install_arduino_cli(self):
        """Install Arduino CLI."""
        self.verbose_print("Installing Arduino CLI version", self.cli_version)
        arduino_cli_archive_download_url_prefix = "https://downloads.arduino.cc/arduino-cli/"
        arduino_cli_archive_file_name = "arduino-cli_" + self.cli_version + "_Linux_64bit.tar.gz"

        self.install_from_download(
            url=arduino_cli_archive_download_url_prefix + arduino_cli_archive_file_name,
            # The Arduino CLI has no root folder, so just install the arduino-cli executable from the archive root
            source_path="arduino-cli",
            destination_parent_path=self.arduino_cli_installation_path,
            force=False,
        )

        # Configure the location of the Arduino CLI user directory
        os.environ["ARDUINO_DIRECTORIES_USER"] = str(self.arduino_cli_user_directory_path)
        # Configure the location of the Arduino CLI data directory
        os.environ["ARDUINO_DIRECTORIES_DATA"] = str(self.arduino_cli_data_directory_path)

    def verbose_print(self, *print_arguments):
        """Print log output when in verbose mode"""
        if self.verbose:
            print(*print_arguments)

    def install_from_download(self, url, source_path, destination_parent_path, destination_name=None, force=False):
        """Download an archive, extract, and install.

        Keyword arguments:
        url -- URL to download the archive from
        source_path -- path relative to the root folder of the archive to install.
        destination_parent_path -- path under which to install
        destination_name -- folder name to use for the installation. Set to None to take the name from source_path.
                            (default None)
        force -- replace existing destination folder if present. (default False)
        """
        destination_parent_path = pathlib.Path(destination_parent_path)

        # Create temporary folder with function duration for the download
        with tempfile.TemporaryDirectory("-compilesketches-download_folder") as download_folder:
            download_file_path = pathlib.PurePath(download_folder, url.rsplit(sep="/", maxsplit=1)[1])

            # https://stackoverflow.com/a/38358646
            with open(file=str(download_file_path), mode="wb") as out_file:
                with contextlib.closing(thing=urllib.request.urlopen(url=url)) as file_pointer:
                    block_size = 1024 * 8
                    while True:
                        block = file_pointer.read(block_size)
                        if not block:
                            break
                        out_file.write(block)

            # Create temporary folder with script run duration for the extraction
            extract_folder = tempfile.mkdtemp(dir=self.temporary_directory.name, prefix="install_from_download-")

            # Extract archive
            shutil.unpack_archive(filename=str(download_file_path), extract_dir=extract_folder)

            archive_root_path = get_archive_root_path(extract_folder)

            absolute_source_path = pathlib.Path(archive_root_path, source_path).resolve()

            if not absolute_source_path.exists():
                print("::error::Archive source path:", source_path, "not found")
                sys.exit(1)

            self.install_from_path(
                source_path=absolute_source_path,
                destination_parent_path=destination_parent_path,
                destination_name=destination_name,
                force=force,
            )

    def install_platforms(self):
        """Install Arduino boards platforms."""
        platform_list = self.Dependencies()
        if self.platforms == "":
            # When no platforms input is provided, automatically determine the board's platform dependency from the FQBN
            platform_list.manager.append(self.get_fqbn_platform_dependency())
        else:
            platform_list = self.sort_dependency_list(yaml.load(stream=self.platforms, Loader=yaml.SafeLoader))

        if len(platform_list.manager) > 0:
            # This should always be called before the functions to install platforms from other sources so that the
            # override system will work
            self.install_platforms_from_board_manager(platform_list=platform_list.manager)

        if len(platform_list.path) > 0:
            self.install_platforms_from_path(platform_list=platform_list.path)

        if len(platform_list.repository) > 0:
            self.install_platforms_from_repository(platform_list=platform_list.repository)

        if len(platform_list.download) > 0:
            self.install_platforms_from_download(platform_list=platform_list.download)

    def get_fqbn_platform_dependency(self):
        """Return the platform dependency definition automatically generated from the FQBN."""
        # Extract the platform name from the FQBN (e.g., arduino:avr:uno => arduino:avr)
        fqbn_component_list = self.fqbn.split(sep=":")
        fqbn_platform_dependency = {self.dependency_name_key: fqbn_component_list[0] + ":" + fqbn_component_list[1]}
        if self.additional_url is not None:
            fqbn_platform_dependency[self.dependency_source_url_key] = self.additional_url

        return fqbn_platform_dependency

    def sort_dependency_list(self, dependency_list):
        """Sort a list of sketch dependencies by source type

        Keyword arguments:
        dependency_list -- a list of dictionaries defining dependencies
        """
        sorted_dependencies = self.Dependencies()
        for dependency in dependency_list:
            if dependency is not None:
                if self.dependency_source_url_key in dependency:
                    # Repositories are identified by the URL starting with git:// or ending in .git
                    if dependency[self.dependency_source_url_key].rstrip("/").endswith(".git") or dependency[
                        self.dependency_source_url_key
                    ].startswith("git://"):
                        sorted_dependencies.repository.append(dependency)
                    elif (
                        re.match(pattern=".*/package_.*index.json", string=dependency[self.dependency_source_url_key])
                        is not None
                    ):
                        # URLs that match the filename requirements of the package_index.json specification are assumed
                        # to be additional Board Manager URLs (platform index)
                        sorted_dependencies.manager.append(dependency)
                    else:
                        # All other URLs are assumed to be downloads
                        sorted_dependencies.download.append(dependency)
                elif self.dependency_source_path_key in dependency:
                    # Dependencies with source-path and no source-url are assumed to be paths
                    sorted_dependencies.path.append(dependency)
                else:
                    # All others are Library/Board Manager names
                    sorted_dependencies.manager.append(dependency)

        return sorted_dependencies

    class Dependencies:
        """Container for sorted sketch dependencies"""

        def __init__(self):
            self.manager = []
            self.path = []
            self.repository = []
            self.download = []

    def install_platforms_from_board_manager(self, platform_list):
        """Install platform dependencies from the Arduino Board Manager

        Keyword arguments:
        platform_list -- list of dictionaries defining the Board Manager platform dependencies
        """
        # Although Arduino CLI supports doing this all in one command, it may assist troubleshooting to install one
        # platform at a time, and most users will only do a single Board Manager platform installation anyway
        for platform in platform_list:
            core_update_index_command = ["core", "update-index"]
            core_install_command = ["core", "install"]

            # Append additional Boards Manager URLs to the commands, if required
            if self.dependency_source_url_key in platform:
                additional_urls_option = ["--additional-urls", platform[self.dependency_source_url_key]]
                core_update_index_command.extend(additional_urls_option)
                core_install_command.extend(additional_urls_option)

            core_install_command.append(self.get_manager_dependency_name(platform))

            # Download the platform index for the platform
            self.run_arduino_cli_command(
                command=core_update_index_command, enable_output=self.get_run_command_output_level()
            )

            # Install the platform
            self.run_arduino_cli_command(
                command=core_install_command, enable_output=self.get_run_command_output_level()
            )

    def get_manager_dependency_name(self, dependency):
        """Return the appropriate name value for a manager dependency. This allows the NAME@VERSION syntax to be used
        with the special "latest" ref for the sake of consistency (though the documented approach is to use the version
        key to specify version.

        Keyword arguments:
        dependency -- dictionary defining the Library/Board Manager dependency
        """
        name = dependency[self.dependency_name_key]
        if self.dependency_version_key in dependency:
            # If "latest" special version name is used, just don't add a version to cause LM to use the latest release
            if dependency[self.dependency_version_key] != self.latest_release_indicator:
                name = name + "@" + dependency[self.dependency_version_key]

        return name

    def get_run_command_output_level(self):
        """Determine and return the appropriate output setting for the run_command function."""
        if self.verbose:
            enable_stdout = self.RunCommandOutput.ALWAYS
        else:
            enable_stdout = self.RunCommandOutput.ON_FAILURE

        return enable_stdout

    def run_arduino_cli_command(self, command, enable_output=RunCommandOutput.ON_FAILURE, exit_on_failure=True):
        """Run the specified Arduino CLI command and return the object returned by subprocess.run().

        Keyword arguments:
        command -- Arduino CLI command to run
        enable_output -- whether to display the stdout from the command (stderr will always be displayed)
                         (default RunCommandOutput.ON_FAILURE)
        exit_on_failure -- whether to immediately exit if the Arduino CLI returns a non-zero status
                           (default True)
        """
        debug_output_log_level = "warn"
        full_command = [self.arduino_cli_installation_path.joinpath("arduino-cli")]
        full_command.extend(command)
        if self.verbose:
            full_command.extend(["--log-level", debug_output_log_level, "--verbose"])
        arduino_cli_output = self.run_command(
            command=full_command, enable_output=enable_output, exit_on_failure=exit_on_failure
        )

        return arduino_cli_output

    def run_command(self, command, enable_output=RunCommandOutput.ON_FAILURE, exit_on_failure=True):
        """Run a command and return the subprocess.CompletedProcess instance (stdout attribute contains combined stdout
        and stderr).

        Keyword arguments:
        command -- the command to run
        enable_output -- whether to print the output (stdout and stderr combined) from the command on success. Output is
                         always printed on failure. (default RunCommandOutput.ON_FAILURE)
                         (RunCommandOutput.NONE, RunCommandOutput.ON_FAILURE, RunCommandOutput.ALWAYS)
        exit_on_failure -- whether to exit the script if the command returns a non-zero exit status (default True)
        """
        command_data = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Print output if appropriate
        if enable_output == self.RunCommandOutput.ALWAYS or (
            command_data.returncode != 0
            and (enable_output == self.RunCommandOutput.ON_FAILURE or enable_output == self.RunCommandOutput.ALWAYS)
        ):
            # Cast args to string and join them to form a string
            print(
                "::group::Running command:",
                list_to_string(command_data.args),
                "\n",
                command_data.stdout,
                "\n",
                "::endgroup::",
            )

            if command_data.returncode != 0:
                print("::error::Command failed")

        if command_data.returncode != 0 and exit_on_failure:
            sys.exit(command_data.returncode)

        return command_data

    def install_platforms_from_path(self, platform_list):
        """Install libraries from local paths

        Keyword arguments:
        platform_list -- Dependencies object containing lists of dictionaries defining platform dependencies of each
                         source type
        """
        for platform in platform_list:
            source_path = absolute_path(platform[self.dependency_source_path_key])
            self.verbose_print("Installing platform from path:", path_relative_to_workspace(path=source_path))

            if not source_path.exists():
                print("::error::Platform source path:", path_relative_to_workspace(path=source_path), "doesn't exist")
                sys.exit(1)

            platform_installation_path = self.get_platform_installation_path(platform=platform)

            # Install the platform
            self.install_from_path(
                source_path=source_path,
                destination_parent_path=platform_installation_path.path.parent,
                destination_name=platform_installation_path.path.name,
                force=platform_installation_path.is_overwrite,
            )

    def get_platform_installation_path(self, platform):
        """Determines the correct installation path for the given platform and returns an object with the attributes:
        path -- correct installation path for the platform (pathlib.Path() object)
        is_overwrite -- whether there is an existing installation of the platform (True, False)

        Keyword arguments:
        platform -- dictionary defining the platform dependency
        """

        class PlatformInstallationPath:
            def __init__(self):
                self.path = pathlib.Path()
                self.is_overwrite = False

        platform_installation_path = PlatformInstallationPath()

        # Default to installing to the sketchbook
        platform_vendor = platform[self.dependency_name_key].split(sep=":")[0]
        platform_architecture = platform[self.dependency_name_key].rsplit(sep=":", maxsplit=1)[1]

        # Default to installing to the sketchbook
        platform_installation_path.path = self.user_platforms_path.joinpath(platform_vendor, platform_architecture)

        # I have no clue why this is needed, but arduino-cli core list fails if this isn't done first. The 3rd party
        # platforms are still shown in the list even if their index URLs are not specified to the command via the
        # --additional-urls option
        self.run_arduino_cli_command(command=["core", "update-index"])
        # Use Arduino CLI to get the list of installed platforms
        command_data = self.run_arduino_cli_command(command=["core", "list", "--format", "json"])
        installed_platform_list = self.cli_core_list_platform_list(json.loads(command_data.stdout))
        for installed_platform in installed_platform_list:
            if installed_platform[self.cli_json_key("core list", "id")] == platform[self.dependency_name_key]:
                # The platform has been installed via Board Manager, so do an overwrite
                platform_installation_path.path = self.board_manager_platforms_path.joinpath(
                    platform_vendor,
                    "hardware",
                    platform_architecture,
                    installed_platform[self.cli_json_key("core list", "installed_version")],
                )
                platform_installation_path.is_overwrite = True

                break

        return platform_installation_path

    def install_from_path(self, source_path, destination_parent_path, destination_name=None, force=False):
        """Create a symlink to the source path in the destination path.

        Keyword arguments:
        source_path -- path to install
        destination_parent_path -- path under which to install
        destination_name -- folder or filename name to use for the installation. Set to None to take the name from
                            source_path. (default None)
        force -- replace existing destination if present. (default False)
        """
        if destination_name is None:
            destination_name = source_path.name

        destination_path = destination_parent_path.joinpath(destination_name)

        if destination_path.exists() or destination_path.is_symlink():
            if force:
                # Clear existing item
                self.verbose_print("Overwriting installation at:", destination_path)
                if destination_path.is_symlink() or destination_path.is_file():
                    destination_path.unlink()
                else:
                    shutil.rmtree(path=destination_path)
            else:
                print("::error::Installation already exists:", destination_path)
                sys.exit(1)

        # Create the parent path if it doesn't already exist
        destination_parent_path.mkdir(parents=True, exist_ok=True)

        destination_path.symlink_to(target=source_path, target_is_directory=source_path.is_dir())

        # Remove the symlink on script exit. The source path files added by the script are stored in a temporary folder
        # which is deleted on exit, so the symlink will serve no purpose.
        atexit.register(destination_path.unlink)

    def install_platforms_from_repository(self, platform_list):
        """Install libraries by cloning Git repositories

        Keyword arguments:
        platform_list -- list of dictionaries defining the dependencies
        """
        for platform in platform_list:
            self.verbose_print("Installing platform from repository:", platform[self.dependency_source_url_key])

            git_ref = self.get_repository_dependency_ref(dependency=platform)

            if self.dependency_source_path_key in platform:
                source_path = platform[self.dependency_source_path_key]
            else:
                source_path = "."

            destination_path = self.get_platform_installation_path(platform=platform)

            self.install_from_repository(
                url=platform[self.dependency_source_url_key],
                git_ref=git_ref,
                source_path=source_path,
                destination_parent_path=destination_path.path.parent,
                destination_name=destination_path.path.name,
                force=destination_path.is_overwrite,
            )

    def get_repository_dependency_ref(self, dependency):
        """Return the appropriate git ref value for a repository dependency

        Keyword arguments:
        dependency -- dictionary defining the repository dependency
        """
        if self.dependency_version_key in dependency:
            git_ref = dependency[self.dependency_version_key]
        else:
            git_ref = None

        return git_ref

    def install_from_repository(
        self, url, git_ref, source_path, destination_parent_path, destination_name=None, force=False
    ):
        """Install by cloning a repository

        Keyword arguments:
        url -- URL to download the archive from
        git_ref -- the Git ref (e.g., branch, tag, commit) to checkout after cloning
        source_path -- path relative to the root of the repository to install from
        destination_parent_path -- path under which to install
        destination_name -- folder name to use for the installation. Set to None to use the repository name.
                            (default None)
        force -- replace existing destination folder if present. (default False)
        """
        if destination_name is None and source_path.rstrip("/") == ".":
            # Use the repository name
            destination_name = url.rstrip("/").rsplit(sep="/", maxsplit=1)[1].rsplit(sep=".", maxsplit=1)[0]

        # Clone to a temporary folder with script run duration to allow installing from subfolders of repos
        clone_folder = tempfile.mkdtemp(dir=self.temporary_directory.name, prefix="install_from_repository-")
        self.clone_repository(url=url, git_ref=git_ref, destination_path=clone_folder)
        # Install to the final location
        self.install_from_path(
            source_path=pathlib.Path(clone_folder, source_path),
            destination_parent_path=destination_parent_path,
            destination_name=destination_name,
            force=force,
        )

    def clone_repository(self, url, git_ref, destination_path):
        """Clone a Git repository to a specified location and check out the specified ref

        Keyword arguments:
        git_ref -- Git ref to check out. Set to None to leave repository checked out at the tip of the default branch.
        destination_path -- destination for the cloned repository. This is the full path of the repository, not the
                            parent path.
        """
        if git_ref is None:
            # Shallow clone is only possible if using the tip of the branch
            # Use `None` as value for `git clone` options with no argument
            clone_arguments = {"depth": 1, "shallow-submodules": None, "recurse-submodules": True}
        else:
            clone_arguments = {}
        cloned_repository = git.Repo.clone_from(url=url, to_path=destination_path, **clone_arguments)
        if git_ref is not None:
            if git_ref == self.latest_release_indicator:
                # "latest" may be used in place of a ref to cause a checkout of the latest tag
                try:
                    # Check if there is a real ref named "latest", in which case it will be used
                    cloned_repository.rev_parse(git_ref)
                except gitdb.exc.BadName:
                    # There is no real ref named "latest", so checkout latest (associated with most recent commit) tag
                    git_ref = sorted(cloned_repository.tags, key=lambda tag: tag.commit.committed_date)[-1]

            # checkout ref
            cloned_repository.git.checkout(git_ref)
            cloned_repository.git.submodule("update", "--init", "--recursive", "--recommend-shallow")

    def install_platforms_from_download(self, platform_list):
        """Install libraries by downloading them

        Keyword arguments:
        platform_list -- list of dictionaries defining the dependencies
        """
        for platform in platform_list:
            self.verbose_print("Installing platform from download URL:", platform[self.dependency_source_url_key])
            if self.dependency_source_path_key in platform:
                source_path = platform[self.dependency_source_path_key]
            else:
                source_path = "."

            destination_path = self.get_platform_installation_path(platform=platform)

            self.install_from_download(
                url=platform[self.dependency_source_url_key],
                source_path=source_path,
                destination_parent_path=destination_path.path.parent,
                destination_name=destination_path.path.name,
                force=destination_path.is_overwrite,
            )

    def install_libraries(self):
        """Install Arduino libraries."""
        libraries = get_list_from_multiformat_input(input_value=self.libraries)

        library_list = self.Dependencies()
        if libraries.was_yaml_list:
            # libraries input is YAML
            library_list = self.sort_dependency_list(libraries.value)
        else:
            # libraries input uses the old space-separated list syntax
            library_list.manager = [{self.dependency_name_key: library_name} for library_name in libraries.value]

            # The original behavior of the action was to assume the root of the repo is a library to be installed, so
            # that behavior is retained when using the old input syntax
            library_list.path = [{self.dependency_source_path_key: os.environ["GITHUB_WORKSPACE"]}]

        # Dependencies of Library Manager sourced libraries (as defined by the library's metadata file) are
        # automatically installed. For this reason, LM-sources must be installed first so the library dependencies from
        # other sources which were explicitly defined won't be replaced.
        if len(library_list.manager) > 0:
            self.install_libraries_from_library_manager(library_list=library_list.manager)

        if len(library_list.path) > 0:
            self.install_libraries_from_path(library_list=library_list.path)

        if len(library_list.repository) > 0:
            self.install_libraries_from_repository(library_list=library_list.repository)

        if len(library_list.download) > 0:
            self.install_libraries_from_download(library_list=library_list.download)

    def install_libraries_from_library_manager(self, library_list):
        """Install libraries using the Arduino Library Manager

        Keyword arguments:
        library_list -- list of dictionaries defining the dependencies
        """
        lib_install_base_command = ["lib", "install"]
        # `arduino-cli lib install` fails if one of the libraries in the list has a dependency on another, but an
        # earlier version of the dependency is specified in the list. The solution is to install one library at a time
        # (even though `arduino-cli lib install` supports installing multiple libraries at once). This also allows the
        # user to control which version is installed in the end by the order of the list passed via the libraries input.
        for library in library_list:
            lib_install_command = lib_install_base_command.copy()
            lib_install_command.append(self.get_manager_dependency_name(library))
            self.run_arduino_cli_command(command=lib_install_command, enable_output=self.get_run_command_output_level())

    def install_libraries_from_path(self, library_list):
        """Install libraries from local paths

        Keyword arguments:
        library_list -- list of dictionaries defining the dependencies
        """
        for library in library_list:
            source_path = absolute_path(library[self.dependency_source_path_key])
            self.verbose_print("Installing library from path:", path_relative_to_workspace(source_path))

            if not source_path.exists():
                print("::error::Library source path:", path_relative_to_workspace(source_path), "doesn't exist")
                sys.exit(1)

            # Determine library folder name (important because it is a factor in dependency resolution)
            if self.dependency_destination_name_key in library:
                # If a name was specified, use it
                destination_name = library[self.dependency_destination_name_key]
            elif source_path == absolute_path(os.environ["GITHUB_WORKSPACE"]):
                # If source_path is the root of the workspace (i.e., repository root), name the folder according to the
                # repository name, otherwise it will unexpectedly be "workspace"
                destination_name = os.environ["GITHUB_REPOSITORY"].split(sep="/")[1]
            else:
                # Use the existing folder name
                destination_name = None

            self.install_from_path(
                source_path=source_path,
                destination_parent_path=self.libraries_path,
                destination_name=destination_name,
                force=True,
            )

    def install_libraries_from_repository(self, library_list):
        """Install libraries by cloning Git repositories

        Keyword arguments:
        library_list -- list of dictionaries defining the dependencies
        """
        for library in library_list:
            self.verbose_print("Installing library from repository:", library[self.dependency_source_url_key])

            # Determine library folder name (important because it is a factor in dependency resolution)
            if self.dependency_destination_name_key in library:
                # If a folder name was specified, use it
                destination_name = library[self.dependency_destination_name_key]
            else:
                # None will cause the repository name to be used by install_from_repository()
                destination_name = None

            git_ref = self.get_repository_dependency_ref(dependency=library)

            if self.dependency_source_path_key in library:
                source_path = library[self.dependency_source_path_key]
            else:
                source_path = "."

            self.install_from_repository(
                url=library[self.dependency_source_url_key],
                git_ref=git_ref,
                source_path=source_path,
                destination_parent_path=self.libraries_path,
                destination_name=destination_name,
                force=True,
            )

    def install_libraries_from_download(self, library_list):
        """Install libraries by downloading them

        Keyword arguments:
        library_list -- list of dictionaries defining the dependencies
        """
        for library in library_list:
            self.verbose_print("Installing library from download URL:", library[self.dependency_source_url_key])
            if self.dependency_source_path_key in library:
                source_path = library[self.dependency_source_path_key]
            else:
                source_path = "."

            if self.dependency_destination_name_key in library:
                destination_name = library[self.dependency_destination_name_key]
            else:
                destination_name = None

            self.install_from_download(
                url=library[self.dependency_source_url_key],
                source_path=source_path,
                destination_parent_path=self.libraries_path,
                destination_name=destination_name,
                force=True,
            )

    def find_sketches(self):
        """Return a list of all sketches under the paths specified in the sketch paths list recursively."""
        sketch_list = []
        self.verbose_print("Finding sketches under paths:", list_to_string(self.sketch_paths))
        for sketch_path in self.sketch_paths:
            sketch_path_sketch_list = []
            if not sketch_path.exists():
                print("::error::Sketch path:", path_relative_to_workspace(path=sketch_path), "doesn't exist")
                sys.exit(1)

            # Check if the specified path is a sketch (as opposed to containing sketches in subfolders)
            if sketch_path.is_file():
                if path_is_sketch(path=sketch_path):
                    # The path directly to a sketch file was provided, so don't search recursively
                    sketch_list.append(sketch_path.parent)
                    continue
                else:
                    print("::error::Sketch path:", path_relative_to_workspace(path=sketch_path), "is not a sketch")
                    sys.exit(1)
            else:
                # Path is a directory
                if path_is_sketch(path=sketch_path):
                    # Add sketch to list, but also search the path recursively for more sketches
                    sketch_path_sketch_list.append(sketch_path)

            # Search the sketch path recursively for sketches
            for sketch in sorted(sketch_path.rglob("*")):
                if sketch.is_dir() and path_is_sketch(path=sketch):
                    sketch_path_sketch_list.append(sketch)

            if len(sketch_path_sketch_list) == 0:
                # If a path provided via the sketch-paths input doesn't contain sketches, that indicates user error
                print("::error::No sketches were found in", path_relative_to_workspace(path=sketch_path))
                sys.exit(1)

            sketch_list.extend(sketch_path_sketch_list)

        return sketch_list

    def compile_sketch(self, sketch_path, clean_build_cache):
        """Compile the specified sketch and returns an object containing the result:
        sketch -- the sketch path relative to the workspace
        success -- the success of the compilation (True, False)
        output -- stdout from Arduino CLI

        Keyword arguments:
        sketch_path -- path of the sketch to compile
        clean_build_cache -- whether to delete cached compiled from previous compilations before compiling
        """
        compilation_command = ["compile", "--warnings", "all", "--fqbn", self.fqbn]
        if self.cli_compile_flags is not None:
            compilation_command.extend(self.cli_compile_flags)
        compilation_command.append(sketch_path)

        if clean_build_cache:
            for cache_path in pathlib.Path("/tmp").glob(pattern="arduino*"):
                shutil.rmtree(path=cache_path)
        start_time = time.monotonic()
        compilation_data = self.run_arduino_cli_command(
            command=compilation_command, enable_output=self.RunCommandOutput.NONE, exit_on_failure=False
        )
        diff_time = time.monotonic() - start_time

        # Group compilation output to make the log easy to read
        # https://github.com/actions/toolkit/blob/master/docs/commands.md#group-and-ungroup-log-lines
        print("::group::Compiling sketch:", path_relative_to_workspace(path=sketch_path))
        print(compilation_data.stdout)
        print("::endgroup::")

        class CompilationResult:
            sketch = sketch_path
            success = compilation_data.returncode == 0
            output = compilation_data.stdout

        if not CompilationResult.success:
            print("::error::Compilation failed")
        else:
            time_summary = ""
            if diff_time > 60:
                if diff_time > 360:
                    time_summary += f"{int(diff_time / 360)}h "
                time_summary += f"{int(diff_time / 60) % 60}m "
            time_summary += f"{int(diff_time) % 60}s"
            print("Compilation time elapsed:", time_summary)

        return CompilationResult()

    def get_sketch_report(self, compilation_result):
        """Return a dictionary containing data on the sketch.

        Keyword arguments:
        compilation_result -- object returned by compile_sketch()
        """
        current_sizes = self.get_sizes_from_output(compilation_result=compilation_result)
        if self.enable_warnings_report:
            current_warning_count = self.get_warning_count_from_output(compilation_result=compilation_result)
        else:
            current_warning_count = None
        previous_sizes = None
        previous_warning_count = None
        if self.do_deltas_report(
            compilation_result=compilation_result, current_sizes=current_sizes, current_warnings=current_warning_count
        ):
            # Get data for the sketch at the base ref
            # Get the head ref
            repository = git.Repo(path=os.environ["GITHUB_WORKSPACE"])
            original_git_ref = repository.head.object.hexsha

            # git checkout the base ref
            self.checkout_deltas_base_ref()

            # Compile the sketch again
            print("Compiling previous version of sketch to determine memory usage change")
            previous_compilation_result = self.compile_sketch(
                sketch_path=compilation_result.sketch, clean_build_cache=self.enable_warnings_report
            )

            # git checkout the head ref to return the repository to its previous state
            repository.git.checkout(original_git_ref, recurse_submodules=True)

            previous_sizes = self.get_sizes_from_output(compilation_result=previous_compilation_result)
            if self.enable_warnings_report:
                previous_warning_count = self.get_warning_count_from_output(
                    compilation_result=previous_compilation_result
                )

        # Add global data for sketch to report
        sketch_report = {
            self.ReportKeys.name: str(path_relative_to_workspace(path=compilation_result.sketch)),
            self.ReportKeys.compilation_success: compilation_result.success,
            self.ReportKeys.sizes: self.get_sizes_report(current_sizes=current_sizes, previous_sizes=previous_sizes),
        }
        if self.enable_warnings_report:
            sketch_report[self.ReportKeys.warnings] = self.get_warnings_report(
                current_warnings=current_warning_count, previous_warnings=previous_warning_count
            )

        return sketch_report

    def get_sizes_from_output(self, compilation_result):
        """Parse the stdout from the compilation process and return a list containing memory usage data.

        Keyword arguments:
        compilation_result -- object returned by compile_sketch()
        """
        memory_types = [
            {
                "name": "flash",
                # Use capturing parentheses to identify the location of the data in the regular expression
                "regex": {
                    # The regular expression for the absolute memory usage
                    self.ReportKeys.absolute: r"Sketch uses ([0-9]+) bytes .*of program storage space\.",
                    # The regular expression for the total memory
                    self.ReportKeys.maximum: (
                        r"Sketch uses [0-9]+ bytes .*of program storage space\. Maximum is ([0-9]+) bytes."
                    ),
                },
            },
            {
                "name": "RAM for global variables",
                "regex": {
                    self.ReportKeys.absolute: r"Global variables use ([0-9]+) bytes .*of dynamic memory",
                    self.ReportKeys.maximum: (
                        r"Global variables use [0-9]+ bytes .*of dynamic memory.*\. Maximum is ([0-9]+) bytes."
                    ),
                },
            },
        ]

        sizes = []
        for memory_type in memory_types:
            size = {
                self.ReportKeys.name: memory_type["name"],
                # Set default memory usage value, to be used if memory usage can't be determined
                self.ReportKeys.absolute: self.not_applicable_indicator,
                self.ReportKeys.maximum: self.not_applicable_indicator,
                self.ReportKeys.relative: self.not_applicable_indicator,
            }

            if compilation_result.success is True:
                # Determine memory usage of the sketch by parsing Arduino CLI's output
                size_data = self.get_size_data_from_output(
                    compilation_output=compilation_result.output,
                    memory_type=memory_type,
                    size_data_type=self.ReportKeys.absolute,
                )
                if size_data:
                    size[self.ReportKeys.absolute] = size_data

                    size_data = self.get_size_data_from_output(
                        compilation_output=compilation_result.output,
                        memory_type=memory_type,
                        size_data_type=self.ReportKeys.maximum,
                    )
                    if size_data:
                        size[self.ReportKeys.maximum] = size_data

                        size[self.ReportKeys.relative] = round(
                            (100 * size[self.ReportKeys.absolute] / size[self.ReportKeys.maximum]),
                            self.relative_size_report_decimal_places,
                        )

            sizes.append(size)

        return sizes

    def get_size_data_from_output(self, compilation_output, memory_type, size_data_type):
        """Parse the stdout from the compilation process for a specific datum and return it, or None if not found.

        Keyword arguments:
        compilation_output -- stdout from the compilation process
        memory_type -- dictionary defining a memory type
        size_data_type -- the type of size data to get
        """
        size_data = None
        regex_match = re.search(pattern=memory_type["regex"][size_data_type], string=compilation_output)
        if regex_match:
            size_data = int(regex_match.group(1))
        else:
            # If any of the following:
            # - recipe.size.regex is not defined in platform.txt
            # - upload.maximum_size is not defined in boards.txt
            # flash usage will not be reported in the Arduino CLI output
            # If any of the following:
            # - recipe.size.regex.data is not defined in platform.txt (e.g., Arduino SAM Boards)
            # - recipe.size.regex is not defined in platform.txt
            # - upload.maximum_size is not defined in boards.txt
            # RAM usage will not be reported in the Arduino CLI output
            self.verbose_print(
                '::warning::Unable to determine the: "'
                + size_data_type
                + '" value for memory type: "'
                + memory_type["name"]
                + "\". The board's platform may not have been configured to provide this information."
            )

        return size_data

    def get_warning_count_from_output(self, compilation_result):
        """Parse the stdout from the compilation process and return the number of compiler warnings. Since the
        information is likely not relevant in that case, "N/A" is returned if compilation failed.

        Keyword arguments:
        compilation_result -- object returned by compile_sketch()
        """
        if compilation_result.success is True:
            compiler_warning_regex = ":[0-9]+:[0-9]+: warning:"
            warning_count = len(re.findall(pattern=compiler_warning_regex, string=compilation_result.output))
        else:
            warning_count = self.not_applicable_indicator

        return warning_count

    def do_deltas_report(self, compilation_result, current_sizes, current_warnings):
        """Return whether size deltas reporting is enabled.

        Keyword arguments:
        compilation_result -- object returned by compile_sketch()
        current_sizes -- memory usage data from the compilation
        current_warnings -- compiler warning count
        """
        return (
            self.enable_deltas_report
            and compilation_result.success
            and (
                any(size.get(self.ReportKeys.absolute) != self.not_applicable_indicator for size in current_sizes)
                or (current_warnings is not None and current_warnings != self.not_applicable_indicator)
            )
        )

    def checkout_deltas_base_ref(self):
        """git checkout the base ref of the deltas comparison"""
        repository = git.Repo(path=os.environ["GITHUB_WORKSPACE"])

        # git fetch the deltas base ref
        origin_remote = repository.remotes["origin"]
        origin_remote.fetch(
            refspec=self.deltas_base_ref,
            verbose=self.verbose,
            no_tags=True,
            prune=True,
            depth=1,
            recurse_submodules=True,
        )

        # git checkout the deltas base ref
        repository.git.checkout(self.deltas_base_ref, recurse_submodules=True)

    def get_sizes_report(self, current_sizes, previous_sizes):
        """Return a list containing all memory usage data assembled.

        Keyword arguments:
        current_sizes -- memory usage data at the head ref
        previous_sizes -- memory usage data at the base ref, or None if the size deltas feature is not enabled
        """

        if previous_sizes is None:
            # Generate a dummy previous_sizes list full of None
            previous_sizes = [None for _ in current_sizes]

        sizes_report = []
        for current_size, previous_size in zip(current_sizes, previous_sizes):
            sizes_report.append(self.get_size_report(current_size=current_size, previous_size=previous_size))

        return sizes_report

    def get_size_report(self, current_size, previous_size):
        """Return a list of the combined current and previous size data, with deltas.

        Keyword arguments:
        current_size -- data from the compilation of the sketch at the pull request's head ref
        previous_size -- data from the compilation of the sketch at the pull request's base ref, or None if the size
                         deltas feature is not enabled
        """
        size_report = {
            self.ReportKeys.name: current_size[self.ReportKeys.name],
            self.ReportKeys.maximum: current_size[self.ReportKeys.maximum],
            self.ReportKeys.current: {
                self.ReportKeys.absolute: current_size[self.ReportKeys.absolute],
                self.ReportKeys.relative: current_size[self.ReportKeys.relative],
            },
        }

        if previous_size is not None:
            # Calculate the memory usage change
            if (
                current_size[self.ReportKeys.absolute] == self.not_applicable_indicator
                or previous_size[self.ReportKeys.absolute] == self.not_applicable_indicator
            ):
                absolute_delta = self.not_applicable_indicator
            else:
                absolute_delta = current_size[self.ReportKeys.absolute] - previous_size[self.ReportKeys.absolute]

            if (
                absolute_delta == self.not_applicable_indicator
                or size_report[self.ReportKeys.maximum] == self.not_applicable_indicator
            ):
                relative_delta = self.not_applicable_indicator
            else:
                # Calculate from absolute values to avoid rounding errors
                relative_delta = round(
                    (100 * absolute_delta / size_report[self.ReportKeys.maximum]),
                    self.relative_size_report_decimal_places,
                )

            # Size deltas reports are enabled
            # Print the memory usage change data to the log
            delta_message = "Change in " + str(current_size[self.ReportKeys.name]) + ": " + str(absolute_delta)
            if relative_delta != self.not_applicable_indicator:
                delta_message += " (" + str(relative_delta) + "%)"
            print(delta_message)

            size_report[self.ReportKeys.previous] = {
                self.ReportKeys.absolute: previous_size[self.ReportKeys.absolute],
                self.ReportKeys.relative: previous_size[self.ReportKeys.relative],
            }
            size_report[self.ReportKeys.delta] = {
                self.ReportKeys.absolute: absolute_delta,
                self.ReportKeys.relative: relative_delta,
            }

        return size_report

    def get_warnings_report(self, current_warnings, previous_warnings):
        """Return a dictionary containing the compiler warning counts.

        Keyword arguments:
        current_warnings -- compiler warning count at the head ref
        previous_warnings -- compiler warning count at the base ref, or None if the size deltas feature is not enabled
        """
        warnings_report = {
            self.ReportKeys.current: {
                self.ReportKeys.absolute: current_warnings,
            }
        }

        if previous_warnings is not None:
            # Deltas reports are enabled
            # Calculate the change in the warnings count
            if current_warnings == self.not_applicable_indicator or previous_warnings == self.not_applicable_indicator:
                warnings_delta = self.not_applicable_indicator
            else:
                warnings_delta = current_warnings - previous_warnings

            # Print the warning count change to the log
            print("Change in compiler warning count:", warnings_delta)

            warnings_report[self.ReportKeys.previous] = {self.ReportKeys.absolute: previous_warnings}
            warnings_report[self.ReportKeys.delta] = {self.ReportKeys.absolute: warnings_delta}

        return warnings_report

    def get_sketches_report(self, sketch_report_list):
        """Return the dictionary containing data on all sketch compilations for each board

        Keyword arguments:
        sketch_report_list -- list of reports from each sketch compilation
        """
        current_git_ref = get_head_commit_hash()

        sketches_report = {
            self.ReportKeys.commit_hash: current_git_ref,
            self.ReportKeys.commit_url: (
                "https://github.com/" + os.environ["GITHUB_REPOSITORY"] + "/commit/" + current_git_ref
            ),
            # The action is currently designed to only compile for one board per run, so the boards list will only have
            # a single element, but this provides a report format that can accommodate the possible addition of multiple
            # boards support
            self.ReportKeys.boards: [{self.ReportKeys.board: self.fqbn, self.ReportKeys.sketches: sketch_report_list}],
        }

        sizes_summary_report = self.get_sizes_summary_report(sketch_report_list=sketch_report_list)
        if sizes_summary_report:
            sketches_report[self.ReportKeys.boards][0][self.ReportKeys.sizes] = sizes_summary_report

        warnings_summary_report = self.get_warnings_summary_report(sketch_report_list=sketch_report_list)
        if warnings_summary_report:
            sketches_report[self.ReportKeys.boards][0][self.ReportKeys.warnings] = warnings_summary_report

        return sketches_report

    def get_sizes_summary_report(self, sketch_report_list):
        """Return the list containing a summary of size data for all sketch compilations for each memory type.

        Keyword arguments:
        sketch_report_list -- list of reports from each sketch compilation
        """
        sizes_summary_report = []
        for sketch_report in sketch_report_list:
            for size_report in sketch_report[self.ReportKeys.sizes]:
                # Determine the sizes_summary_report index for this memory type
                size_summary_report_index_list = [
                    index
                    for index, size_summary in enumerate(sizes_summary_report)
                    if size_summary.get(self.ReportKeys.name) == size_report[self.ReportKeys.name]
                ]
                if not size_summary_report_index_list:
                    # There is no existing entry in the summary list for this memory type, so create one
                    sizes_summary_report.append({self.ReportKeys.name: size_report[self.ReportKeys.name]})
                    size_summary_report_index = len(sizes_summary_report) - 1
                else:
                    size_summary_report_index = size_summary_report_index_list[0]

                if (
                    self.ReportKeys.maximum not in sizes_summary_report[size_summary_report_index]
                    or sizes_summary_report[size_summary_report_index][self.ReportKeys.maximum]
                    == self.not_applicable_indicator
                ):
                    sizes_summary_report[size_summary_report_index][self.ReportKeys.maximum] = size_report[
                        self.ReportKeys.maximum
                    ]

                if self.ReportKeys.delta in size_report:
                    if (
                        self.ReportKeys.delta not in sizes_summary_report[size_summary_report_index]
                        or sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                            self.ReportKeys.absolute
                        ][self.ReportKeys.minimum]
                        == self.not_applicable_indicator
                    ):
                        sizes_summary_report[size_summary_report_index][self.ReportKeys.delta] = {
                            self.ReportKeys.absolute: {
                                self.ReportKeys.minimum: size_report[self.ReportKeys.delta][self.ReportKeys.absolute],
                                self.ReportKeys.maximum: size_report[self.ReportKeys.delta][self.ReportKeys.absolute],
                            },
                            self.ReportKeys.relative: {
                                self.ReportKeys.minimum: size_report[self.ReportKeys.delta][self.ReportKeys.relative],
                                self.ReportKeys.maximum: size_report[self.ReportKeys.delta][self.ReportKeys.relative],
                            },
                        }
                    elif size_report[self.ReportKeys.delta][self.ReportKeys.absolute] != self.not_applicable_indicator:
                        if (
                            size_report[self.ReportKeys.delta][self.ReportKeys.absolute]
                            < sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                                self.ReportKeys.absolute
                            ][self.ReportKeys.minimum]
                        ):
                            sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                                self.ReportKeys.absolute
                            ][self.ReportKeys.minimum] = size_report[self.ReportKeys.delta][self.ReportKeys.absolute]

                            sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                                self.ReportKeys.relative
                            ][self.ReportKeys.minimum] = size_report[self.ReportKeys.delta][self.ReportKeys.relative]

                        if (
                            size_report[self.ReportKeys.delta][self.ReportKeys.absolute]
                            > sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                                self.ReportKeys.absolute
                            ][self.ReportKeys.maximum]
                        ):
                            sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                                self.ReportKeys.absolute
                            ][self.ReportKeys.maximum] = size_report[self.ReportKeys.delta][self.ReportKeys.absolute]

                            sizes_summary_report[size_summary_report_index][self.ReportKeys.delta][
                                self.ReportKeys.relative
                            ][self.ReportKeys.maximum] = size_report[self.ReportKeys.delta][self.ReportKeys.relative]

        return sizes_summary_report

    def get_warnings_summary_report(self, sketch_report_list):
        """Return a dictionary containing a summary of the compilation warnings count for all sketch compilations.

        Keyword arguments:
        sketch_report_list -- list of reports from each sketch compilation
        """
        summary_report_minimum = None
        summary_report_maximum = None
        for sketch_report in sketch_report_list:
            if (
                self.ReportKeys.warnings in sketch_report
                and self.ReportKeys.delta in sketch_report[self.ReportKeys.warnings]
            ):
                sketch_report_delta = sketch_report[self.ReportKeys.warnings][self.ReportKeys.delta][
                    self.ReportKeys.absolute
                ]

                if summary_report_minimum is None or summary_report_minimum == self.not_applicable_indicator:
                    summary_report_minimum = sketch_report_delta
                elif (
                    sketch_report_delta != self.not_applicable_indicator
                    and summary_report_minimum > sketch_report_delta
                ):
                    summary_report_minimum = sketch_report_delta

                if summary_report_maximum is None or summary_report_maximum == self.not_applicable_indicator:
                    summary_report_maximum = sketch_report_delta
                elif (
                    sketch_report_delta != self.not_applicable_indicator
                    and summary_report_maximum < sketch_report_delta
                ):
                    summary_report_maximum = sketch_report_delta

        if summary_report_minimum is not None:
            warnings_summary_report = {
                self.ReportKeys.delta: {
                    self.ReportKeys.absolute: {
                        self.ReportKeys.minimum: summary_report_minimum,
                        self.ReportKeys.maximum: summary_report_maximum,
                    }
                }
            }
        else:
            warnings_summary_report = {}

        return warnings_summary_report

    def create_sketches_report_file(self, sketches_report):
        """Write the report for the report sketch to a file.

        Keyword arguments:
        sketches_report -- dictionary containing data on the compiled sketches
        """
        self.verbose_print("Creating sketch report file")

        sketches_report_path = absolute_path(path=self.sketches_report_path)

        # Create the report folder
        sketches_report_path.mkdir(parents=True, exist_ok=True)

        # Write the memory usage data to a file named according to the FQBN
        with open(
            file=sketches_report_path.joinpath(self.fqbn.replace(":", "-") + ".json"), mode="w", encoding="utf-8"
        ) as report_file:
            json.dump(obj=sketches_report, fp=report_file, indent=2)

    def cli_core_list_platform_list(self, data):
        """Extract the list of platform data from the `arduino-cli core list` command output according to the Arduino
        CLI version in use.

        Keyword arguments:
        data -- Arduino CLI command output data
        """
        # Interface was changed at this Arduino CLI release:
        # https://arduino.github.io/arduino-cli/dev/UPGRADING/#cli-changed-json-output-for-some-lib-core-config-board-and-sketch-commands
        first_new_interface_version = "1.0.0"

        if (
            not semver.VersionInfo.is_valid(version=self.cli_version)
            or semver.Version.parse(version=self.cli_version).compare(other=first_new_interface_version) >= 0
        ):
            # cli_version is either "latest" (which will now always be >=1.0.0) or an explicit version >=1.0.0

            # Workaround for https://github.com/arduino/arduino-cli/issues/2690
            if data["platforms"] is None:
                return []

            return data["platforms"]

        return data

    def cli_json_key(self, command, key_name):
        """Return the appropriate JSON output key name for the Arduino CLI version in use.

        Keyword arguments:
        command -- Arduino CLI command (e.g., "core list")
        key_name -- key name used by the current Arduino CLI JSON interface
        """
        key_translations = {
            "core list": {
                "id": [
                    {"constraints": [">=0.0.0", "<=0.17.0"], "name": "ID"},
                    # https://arduino.github.io/arduino-cli/dev/UPGRADING/#arduino-cli-json-output-breaking-changes
                    {"constraints": [">0.17.0"], "name": "id"},
                ],
                "installed_version": [
                    {"constraints": [">=0.0.0", "<=0.17.0"], "name": "Installed"},
                    # https://arduino.github.io/arduino-cli/dev/UPGRADING/#arduino-cli-json-output-breaking-changes
                    {"constraints": [">0.17.0", "<1.0.0"], "name": "installed"},
                    # https://arduino.github.io/arduino-cli/dev/UPGRADING/#cli-core-list-and-core-search-changed-json-output
                    {"constraints": [">=1.0.0"], "name": "installed_version"},
                ],
            }
        }

        if not semver.VersionInfo.is_valid(version=self.cli_version):
            # cli_version is "latest", so use the current key name
            return key_name

        for translation in key_translations[command][key_name]:
            match = True
            for constraint in translation["constraints"]:
                if not semver.Version.parse(version=self.cli_version).match(match_expr=constraint):
                    # The Arduino CLI version does not match the translation's version constraints
                    match = False
                    break

            if match:
                # The Arduino CLI version matches the translation's version constraints
                return translation["name"]

        raise RuntimeError(
            f"Translation not implemented for `{key_name}` key of `arduino-cli {command}` for version {self.cli_version}"
        )  # pragma: no cover


def parse_list_input(list_input):
    """Parse a space separated list and return the equivalent Python list

    Keyword arguments:
    list_input -- a string containing a space separated list (in the style of a bash array)
    """
    if list_input.find("'") != -1 and list_input.find('"') != -1:
        list_input = list_input.strip("' ")
    list_input = shlex.split(list_input, posix=False)
    list_input = [item.strip("\"'") for item in list_input]

    return list_input


def parse_fqbn_arg_input(fqbn_arg):
    """Parse the space separated fqbn input and return the equivalent list

    Keyword arguments:
    fqbn_arg -- a string containing the FQBN and, optionally, the Boards Manager URL as a space separated list (in the
                style of a bash array)
    """
    fqbn_arg_list = parse_list_input(list_input=fqbn_arg)
    fqbn = fqbn_arg_list[0]
    if len(fqbn_arg_list) == 1:
        # Only the FQBN was specified
        additional_url = None
    else:
        additional_url = fqbn_arg_list[1]

    return {"fqbn": fqbn, "additional_url": additional_url}


def parse_boolean_input(boolean_input):
    """Return the Boolean value of a string representation.

    Keyword arguments:
    boolean_input -- a string representing a boolean value, case insensitive
    """
    if boolean_input.lower() == "true":
        parsed_boolean_input = True
    elif boolean_input.lower() == "false":
        parsed_boolean_input = False
    else:
        parsed_boolean_input = None

    return parsed_boolean_input


def get_parent_commit_ref():
    """Return the Git ref of the immediate parent commit."""
    repository_object = git.Repo(path=os.environ["GITHUB_WORKSPACE"])
    return repository_object.head.object.parents[0].hexsha


def path_relative_to_workspace(path):
    """Returns the path relative to the workspace of the action's Docker container. This is the path used in all
    human-targeted output.

    Keyword arguments:
    path -- the path to make relative
    """
    path = absolute_path(path=path)
    try:
        relative_path = path.relative_to(absolute_path(path=os.environ["GITHUB_WORKSPACE"]))
    except ValueError:
        # Path is outside workspace, so just use the given path
        relative_path = path

    return relative_path


def absolute_path(path):
    """Returns the absolute path equivalent. Relative paths are assumed to be relative to the workspace of the action's
    Docker container (the root of the repository).

    Keyword arguments:
    path -- the path to make absolute
    """
    # Make path into a pathlib.Path object, with ~ expanded
    path = pathlib.Path(path).expanduser()
    if not path.is_absolute():
        # path is relative
        path = pathlib.Path(os.environ["GITHUB_WORKSPACE"], path)

    # Resolve .. and symlinks to get a true absolute path
    path = path.resolve()

    return path


def get_list_from_multiformat_input(input_value):
    """For backwards compatibility with the legacy API, some inputs support a space-separated list format in addition to
    the modern YAML format. This function converts either input format into a list and returns an object with the
    attributes:
    value -- the list that was parsed from the input
    was_yaml_list -- whether the input was in YAML format (True, False)

    Keyword arguments:
    input_value -- the raw input
    """

    class InputList:
        def __init__(self):
            self.value = []
            self.was_yaml_list = False

    input_list = InputList()

    try:
        processed_input_value = yaml.load(stream=input_value, Loader=yaml.SafeLoader)
    except yaml.parser.ParserError:
        # The input value was not valid YAML
        # This exception occurs when the space separated list items are individually quoted (e.g., '"Foo" "Bar"')
        # Note: some old format list values are also valid YAML by chance (e.g., a normal string), so old format input
        # won't always cause this exception
        processed_input_value = input_value
        pass

    if type(processed_input_value) is list:
        # The input value was valid YAML and in list format
        input_list.value = processed_input_value
        input_list.was_yaml_list = True
    else:
        # The input value was either valid YAML, but not a list, or invalid YAML
        input_list.value = parse_list_input(list_input=input_value)
        input_list.was_yaml_list = False

    return input_list


def path_is_sketch(path):
    """Return whether the specified path is an Arduino sketch.

    Keyword arguments:
    path -- path of to check for a sketch
    """
    sketch_extensions = [".ino", ".pde"]

    path = pathlib.Path(path)

    is_sketch = False
    if path.is_file():
        for sketch_extension in sketch_extensions:
            if path.suffix == sketch_extension:
                is_sketch = True
    else:
        for sketch_extension in sketch_extensions:
            files = path.glob(pattern="*" + sketch_extension)
            for _ in files:
                is_sketch = True

    return is_sketch


def list_to_string(list_input):
    """Cast the list items to string and join them, then return the resulting string"""
    return " ".join([str(item) for item in list_input])


def get_archive_root_path(archive_extract_path):
    """Return the path of the archive's root folder.

    Keyword arguments:
    archive_extract_path -- path the archive was extracted to
    """
    archive_root_folder_name = archive_extract_path
    for extract_folder_content in pathlib.Path(archive_extract_path).glob("*"):
        if extract_folder_content.is_dir():
            # Path is a folder
            # Ignore the __MACOSX folder
            if extract_folder_content.name != "__MACOSX":
                if archive_root_folder_name == archive_extract_path:
                    # This is the first folder found
                    archive_root_folder_name = extract_folder_content
                else:
                    # Multiple folders found
                    archive_root_folder_name = archive_extract_path
                    break
        else:
            # Path is a file
            archive_root_folder_name = archive_extract_path
            break

    return archive_root_folder_name


def get_head_commit_hash():
    """Return the head commit's hash."""
    if os.environ["GITHUB_EVENT_NAME"] == "pull_request":
        # When the workflow is triggered by a pull_request event, actions/checkout checks out the hypothetical merge
        # commit GitHub automatically generates for PRs. The user will expect the report to show the hash of the head
        # commit of the PR, not of this hidden merge commit. So it's necessary it get it from GITHUB_EVENT_PATH instead
        # of git rev-parse HEAD.
        with open(file=os.environ["GITHUB_EVENT_PATH"]) as github_event_file:
            commit_hash = json.load(github_event_file)["pull_request"]["head"]["sha"]
    else:
        repository = git.Repo(path=os.environ["GITHUB_WORKSPACE"])
        commit_hash = repository.git.rev_parse("HEAD")

    return commit_hash


# Only execute the following code if the script is run directly, not imported
if __name__ == "__main__":
    main()  # pragma: no cover
