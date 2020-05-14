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
import yaml
import yaml.parser

import reportsizetrends


def main():
    compile_sketches = CompileSketches(
        cli_version=os.environ["INPUT_CLI-VERSION"],
        fqbn_arg=os.environ["INPUT_FQBN"],
        platforms=os.environ["INPUT_PLATFORMS"],
        libraries=os.environ["INPUT_LIBRARIES"],
        sketch_paths=os.environ["INPUT_SKETCH-PATHS"],
        verbose=os.environ["INPUT_VERBOSE"],
        github_token=os.environ["INPUT_GITHUB-TOKEN"],
        report_sketch=os.environ["INPUT_SIZE-REPORT-SKETCH"],
        enable_size_deltas_report=os.environ["INPUT_ENABLE-SIZE-DELTAS-REPORT"],
        sketches_report_path=os.environ["INPUT_SIZE-DELTAS-REPORT-FOLDER-NAME"],
        enable_size_trends_report=os.environ["INPUT_ENABLE-SIZE-TRENDS-REPORT"],
        google_key_file=os.environ["INPUT_KEYFILE"],
        size_trends_report_spreadsheet_id=os.environ["INPUT_SIZE-TRENDS-REPORT-SPREADSHEET-ID"],
        size_trends_report_sheet_name=os.environ["INPUT_SIZE-TRENDS-REPORT-SHEET-NAME"]
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
    verbose -- set to "true" for verbose output ("true", "false")
    github_token -- GitHub access token
    report_sketch -- name of the sketch to make the report for
    enable_size_deltas_report -- set to "true" to cause the action to determine the change in memory usage for the
                                 report_sketch ("true", "false")
    sketches_report_path -- folder to save the sketches report to
    enable_size_trends_report -- whether to record the memory usage of report_sketch
                                 ("true", "false")
    google_key_file -- Google key file used to update the size trends report Google Sheets spreadsheet
    size_trends_report_spreadsheet_id -- the ID of the Google Sheets spreadsheet to write the memory usage trends data
                                         to
    size_trends_report_sheet_name -- the sheet name in the Google Sheets spreadsheet used for the memory usage trends
                                     report
    """

    class RunCommandOutput(enum.Enum):
        NONE = enum.auto()
        ON_FAILURE = enum.auto()
        ALWAYS = enum.auto()

    not_applicable_indicator = "N/A"

    arduino_cli_installation_path = pathlib.Path.home().joinpath("bin")
    arduino_cli_user_directory_path = pathlib.Path.home().joinpath("Arduino")
    arduino_cli_data_directory_path = pathlib.Path.home().joinpath(".arduino15")
    libraries_path = arduino_cli_user_directory_path.joinpath("libraries")
    user_platforms_path = arduino_cli_user_directory_path.joinpath("hardware")
    board_manager_platforms_path = arduino_cli_data_directory_path.joinpath("packages")

    report_fqbn_key = "fqbn"
    report_sketch_key = "sketch"
    report_compilation_success_key = "compilation_success"
    report_flash_key = "flash"
    report_previous_flash_key = "previous_flash"
    report_flash_delta_key = "flash_delta"
    report_ram_key = "ram"
    report_previous_ram_key = "previous_ram"
    report_ram_delta_key = "ram_delta"

    dependency_name_key = "name"
    dependency_version_key = "version"
    dependency_source_path_key = "source-path"
    dependency_source_url_key = "source-url"
    dependency_destination_name_key = "destination-name"

    latest_release_indicator = "latest"

    def __init__(self, cli_version, fqbn_arg, platforms, libraries, sketch_paths, verbose, github_token, report_sketch,
                 enable_size_deltas_report, sketches_report_path, enable_size_trends_report, google_key_file,
                 size_trends_report_spreadsheet_id, size_trends_report_sheet_name):
        """Process, store, and validate the action's inputs."""
        self.cli_version = cli_version

        parsed_fqbn_arg = parse_fqbn_arg_input(fqbn_arg=fqbn_arg)
        self.fqbn = parsed_fqbn_arg["fqbn"]
        self.additional_url = parsed_fqbn_arg["additional_url"]
        self.platforms = platforms
        self.libraries = libraries

        # Save the space-separated list of paths as a Python list
        sketch_paths = parse_list_input(sketch_paths)
        sketch_paths = [pathlib.Path(sketch_path) for sketch_path in sketch_paths]
        self.sketch_paths = sketch_paths

        self.verbose = parse_boolean_input(boolean_input=verbose)

        if github_token == "":
            # Access token is not needed for public repositories
            self.github_api = github.Github()
        else:
            self.github_api = github.Github(login_or_token=github_token)

        self.report_sketch = report_sketch

        self.enable_size_deltas_report = parse_boolean_input(boolean_input=enable_size_deltas_report)
        # The enable-size-deltas-report input has a default value so it should always be either True or False
        if self.enable_size_deltas_report is None:
            print("::error::Invalid value for enable-size-deltas-report input")
            sys.exit(1)

        self.sketches_report_path = pathlib.PurePath(sketches_report_path)

        self.enable_size_trends_report = parse_boolean_input(boolean_input=enable_size_trends_report)
        # The enable-size-trends-report input has a default value so it should always be either True or False
        if self.enable_size_trends_report is None:
            print("::error::Invalid value for enable-size-trends-report input")
            sys.exit(1)

        self.google_key_file = google_key_file
        if self.enable_size_trends_report and self.google_key_file == "":
            print("::error::keyfile input was not defined")
            sys.exit(1)

        self.size_trends_report_spreadsheet_id = size_trends_report_spreadsheet_id
        if self.enable_size_trends_report and self.size_trends_report_spreadsheet_id == "":
            print("::error::size-trends-report-spreadsheet-id input was not defined")
            sys.exit(1)

        self.size_trends_report_sheet_name = size_trends_report_sheet_name

        if (self.enable_size_deltas_report or self.enable_size_trends_report) and self.report_sketch == "":
            print("::error::size-report-sketch input was not defined")
            sys.exit(1)

    def compile_sketches(self):
        """Do compilation tests and record data."""
        self.install_arduino_cli()

        # Install the platform dependency
        self.install_platforms()

        # Install the library dependencies
        self.install_libraries()

        # Compile all sketches under the paths specified by the sketch-paths input
        all_compilations_successful = True
        sketches_report = []

        sketch_list = self.find_sketches()
        for sketch in sketch_list:
            compilation_result = self.compile_sketch(sketch_path=sketch)
            if not compilation_result.success:
                all_compilations_successful = False

            # Store the size data for this sketch
            sketches_report.append(self.get_sketch_report(compilation_result=compilation_result))

        if self.report_sketch != "":
            # Make sketch reports
            sketch_report = self.get_sketch_report_from_sketches_report(sketches_report=sketches_report)
            # Make the memory usage trends report
            if self.do_size_trends_report():
                self.make_size_trends_report(sketch_report=sketch_report)
            # TODO: The current behavior is to only write the report for the report sketch, but the plan is to change to
            #       reporting data for all sketches, thus the passing of sketch_report to the function
            self.create_sketches_report_file(sketches_report=sketch_report)

        if not all_compilations_successful:
            print("::error::One or more compilations failed")
            sys.exit(1)

    def install_arduino_cli(self):
        """Install Arduino CLI."""
        self.verbose_print("Installing Arduino CLI version", self.cli_version)
        arduino_cli_archive_download_url_prefix = "https://downloads.arduino.cc/arduino-cli/"
        arduino_cli_archive_file_name = "arduino-cli_" + self.cli_version + "_Linux_64bit.tar.gz"

        install_from_download(
            url=arduino_cli_archive_download_url_prefix + arduino_cli_archive_file_name,
            # The Arduino CLI has no root folder, so just install the arduino-cli executable from the archive root
            source_path="arduino-cli",
            destination_parent_path=self.arduino_cli_installation_path
        )

        # Configure the location of the Arduino CLI user directory
        os.environ["ARDUINO_DIRECTORIES_USER"] = str(self.arduino_cli_user_directory_path)
        # Configure the location of the Arduino CLI data directory
        os.environ["ARDUINO_DIRECTORIES_DATA"] = str(self.arduino_cli_data_directory_path)

    def verbose_print(self, *print_arguments):
        """Print log output when in verbose mode"""
        if self.verbose:
            print(*print_arguments)

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

    def get_fqbn_platform_dependency(self):
        """Return the platform dependency definition automatically generated from the FQBN."""
        # Extract the platform name from the FQBN (e.g., arduino:avr:uno => arduino:avr)
        fqbn_platform_dependency = {self.dependency_name_key: self.fqbn.rsplit(sep=":", maxsplit=1)[0]}
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
                    if (
                        dependency[self.dependency_source_url_key].rstrip("/").endswith(".git")
                        or dependency[self.dependency_source_url_key].startswith("git://")
                    ):
                        sorted_dependencies.repository.append(dependency)
                    elif re.match(
                        pattern=".*/package_.*index.json", string=dependency[self.dependency_source_url_key]
                    ) is not None:
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
            self.run_arduino_cli_command(command=core_update_index_command,
                                         enable_output=self.get_run_command_output_level())

            # Install the platform
            self.run_arduino_cli_command(command=core_install_command,
                                         enable_output=self.get_run_command_output_level())

    def get_manager_dependency_name(self, dependency):
        """Return the appropriate name value for a manager dependency. This allows the NAME@VERSION syntax to be used
        with the special "latest" ref for the sake of consistency (though the documented approach is to use the version
        key to specify version.

        Keyword arguments:
        dependency -- dictionary defining the Library/Board Manger dependency
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
        arduino_cli_output = self.run_command(command=full_command,
                                              enable_output=enable_output,
                                              exit_on_failure=exit_on_failure)

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
        if (enable_output == self.RunCommandOutput.ALWAYS
            or (command_data.returncode != 0
                and (enable_output == self.RunCommandOutput.ON_FAILURE
                     or enable_output == self.RunCommandOutput.ALWAYS))):

            # Cast args to string and join them to form a string
            print("::group::Running command:", list_to_string(command_data.args), "\n",
                  command_data.stdout, "\n",
                  "::endgroup::")

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
            self.verbose_print("Installing platform from path:", platform[self.dependency_source_path_key])

            if not source_path.exists():
                print("::error::Platform source path:", platform[self.dependency_source_path_key], "doesn't exist")
                sys.exit(1)

            platform_installation_path = self.get_platform_installation_path(platform=platform)

            # Create the parent path if it doesn't exist already. This must be the immediate parent, whereas
            # get_platform_installation_path().platform will be multiple nested folders under the base path
            platform_installation_path_parent = (
                pathlib.Path(platform_installation_path.base, platform_installation_path.platform).parent
            )
            platform_installation_path_parent.mkdir(parents=True, exist_ok=True)

            # Install the platform by creating a symlink
            destination_path = platform_installation_path.base.joinpath(platform_installation_path.platform)
            destination_path.symlink_to(target=source_path, target_is_directory=True)

    def get_platform_installation_path(self, platform):
        """Return the correct installation path for the given platform

        Keyword arguments:
        platform -- dictionary defining the platform dependency
        """

        class PlatformInstallationPath:
            def __init__(self):
                self.base = pathlib.PurePath()
                self.platform = pathlib.PurePath()

        platform_installation_path = PlatformInstallationPath()

        platform_vendor = platform[self.dependency_name_key].split(sep=":")[0]
        platform_architecture = platform[self.dependency_name_key].rsplit(sep=":", maxsplit=1)[1]

        # Default to installing to the sketchbook
        platform_installation_path.base = self.user_platforms_path
        platform_installation_path.platform = pathlib.PurePath(platform_vendor, platform_architecture)

        # I have no clue why this is needed, but arduino-cli core list fails if this isn't done first. The 3rd party
        # platforms are still shown in the list even if their index URLs are not specified to the command via the
        # --additional-urls option
        self.run_arduino_cli_command(command=["core", "update-index"])
        # Use Arduino CLI to get the list of installed platforms
        command_data = self.run_arduino_cli_command(command=["core", "list", "--format", "json"])
        installed_platform_list = json.loads(command_data.stdout)
        for installed_platform in installed_platform_list:
            if installed_platform["ID"] == platform[self.dependency_name_key]:
                # The platform has been installed via Board Manager, so do an overwrite
                platform_installation_path.base = self.board_manager_platforms_path
                platform_installation_path.platform = (
                    pathlib.PurePath(platform_vendor,
                                     "hardware",
                                     platform_architecture,
                                     installed_platform["Installed"])
                )

                # Remove the existing installation so it can be replaced by the installation function
                shutil.rmtree(path=platform_installation_path.base.joinpath(platform_installation_path.platform))

                break

        return platform_installation_path

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

    def install_from_repository(self, url, git_ref, source_path, destination_parent_path, destination_name=None):
        """Install by cloning a repository

        Keyword arguments:
        url -- URL to download the archive from
        git_ref -- the Git ref (e.g., branch, tag, commit) to checkout after cloning
        source_path -- path relative to the root of the repository to install from
        destination_parent_path -- path under which to install
        destination_name -- folder name to use for the installation. Set to None to use the repository name.
                            (default None)
        """
        if destination_name is None:
            if source_path.rstrip("/") == ".":
                # Use the repository name
                destination_name = url.rstrip("/").rsplit(sep="/", maxsplit=1)[1].rsplit(sep=".", maxsplit=1)[0]
            else:
                # Use the source path folder name
                destination_name = pathlib.PurePath(source_path).name

        if source_path.rstrip("/") == ".":
            # Clone directly to the target path
            self.clone_repository(url=url, git_ref=git_ref,
                                  destination_path=pathlib.PurePath(destination_parent_path, destination_name))
        else:
            # Clone to a temporary folder
            with tempfile.TemporaryDirectory() as clone_folder:
                self.clone_repository(url=url, git_ref=git_ref, destination_path=clone_folder)
                # Install by moving the source folder
                shutil.move(src=str(pathlib.PurePath(clone_folder, source_path)),
                            dst=str(pathlib.PurePath(destination_parent_path, destination_name)))

    def clone_repository(self, url, git_ref, destination_path):
        """Clone a Git repository to a specified location and check out the specified ref

        Keyword arguments:
        git_ref -- Git ref to check out. Set to None to leave repository checked out at the tip of the default branch.
        destination_path -- destination for the cloned repository. This is the full path of the repository, not the
                            parent path.
        """
        if git_ref is None:
            # Shallow clone is only possible if using the tip of the branch
            clone_arguments = {"depth": 1}
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

    def install_libraries(self):
        """Install Arduino libraries."""
        self.libraries_path.mkdir(parents=True, exist_ok=True)

        libraries = yaml.load(stream="", Loader=yaml.SafeLoader)
        try:
            libraries = yaml.load(stream=self.libraries, Loader=yaml.SafeLoader)
        except yaml.parser.ParserError:
            # This exception occurs when the space separated list items are individually quoted (e.g., '"Foo" "Bar"')
            pass

        library_list = self.Dependencies()
        if type(libraries) is list:
            # libraries input is YAML
            library_list = self.sort_dependency_list(libraries)
        else:
            # libraries input uses the old space-separated list syntax
            library_list.manager = [{self.dependency_name_key: library_name}
                                    for library_name in parse_list_input(self.libraries)]

            # The original behavior of the action was to assume the root of the repo is a library to be installed, so
            # that behavior is retained when using the old input syntax
            library_list.path = [{self.dependency_source_path_key: pathlib.Path(os.environ["GITHUB_WORKSPACE"])}]

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
        lib_install_command = ["lib", "install"]
        lib_install_command.extend([self.get_manager_dependency_name(library) for library in library_list])
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
            elif (
                source_path == pathlib.Path(os.environ["GITHUB_WORKSPACE"])
            ):
                # If source_path is the root of the workspace (i.e., repository root), name the folder according to the
                # repository name, otherwise it will unexpectedly be "workspace"
                destination_name = os.environ["GITHUB_REPOSITORY"].split(sep="/")[1]
            else:
                # Use the existing folder name
                destination_name = source_path.name

            # Install the library by creating a symlink in the sketchbook
            library_symlink_path = self.libraries_path.joinpath(destination_name)
            library_symlink_path.symlink_to(target=source_path, target_is_directory=True)

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

            self.install_from_repository(url=library[self.dependency_source_url_key],
                                         git_ref=git_ref,
                                         source_path=source_path,
                                         destination_parent_path=self.libraries_path,
                                         destination_name=destination_name)

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

            install_from_download(url=library[self.dependency_source_url_key],
                                  source_path=source_path,
                                  destination_parent_path=self.libraries_path,
                                  destination_name=destination_name)

    def find_sketches(self):
        """Return a list of all sketches under the paths specified in the sketch paths list recursively."""
        sketch_list = []
        self.verbose_print("Finding sketches under paths:", list_to_string(self.sketch_paths))
        for sketch_path in self.sketch_paths:
            # The absolute path is used in the code, the sketch path provided by the user is used in the log output
            absolute_sketch_path = absolute_path(sketch_path)
            sketch_path_sketch_list = []
            if not absolute_sketch_path.exists():
                print("::error::Sketch path:", sketch_path, "doesn't exist")
                sys.exit(1)

            # Check if the specified path is a sketch (as opposed to containing sketches in subfolders)
            if absolute_sketch_path.is_file():
                if path_is_sketch(path=absolute_sketch_path):
                    # The path directly to a sketch file was provided, so don't search recursively
                    sketch_list.append(absolute_sketch_path.parent)
                    continue
                else:
                    print("::error::Sketch path:", sketch_path, "is not a sketch")
                    sys.exit(1)
            else:
                # Path is a directory
                if path_is_sketch(path=absolute_sketch_path):
                    # Add sketch to list, but also search the path recursively for more sketches
                    sketch_path_sketch_list.append(absolute_sketch_path)

            # Search the sketch path recursively for sketches
            for sketch in sorted(absolute_sketch_path.rglob("*")):
                if sketch.is_dir() and path_is_sketch(path=sketch):
                    sketch_path_sketch_list.append(sketch)

            if len(sketch_path_sketch_list) == 0:
                # If a path provided via the sketch-paths input doesn't contain sketches, that indicates user error
                print("::error::No sketches were found in", sketch_path)
                sys.exit(1)

            sketch_list.extend(sketch_path_sketch_list)

        return sketch_list

    def compile_sketch(self, sketch_path):
        """Compile the specified sketch and returns an object containing the result:
        sketch -- the sketch path relative to the workspace
        success -- the success of the compilation (True, False)
        output -- stdout from Arduino CLI

        Keyword arguments:
        sketch_path -- path of the sketch to compile
        """
        compilation_command = ["compile", "--warnings", "all", "--fqbn", self.fqbn, sketch_path]

        compilation_data = self.run_arduino_cli_command(
            command=compilation_command, enable_output=self.RunCommandOutput.NONE, exit_on_failure=False)
        # Group compilation output to make the log easy to read
        # https://github.com/actions/toolkit/blob/master/docs/commands.md#group-and-ungroup-log-lines
        print("::group::Compiling sketch:", path_relative_to_workspace(sketch_path))
        print(compilation_data.stdout)
        print("::endgroup::")

        class CompilationResult:
            sketch = path_relative_to_workspace(sketch_path)
            success = compilation_data.returncode == 0
            output = compilation_data.stdout

        if not CompilationResult.success:
            print("::error::Compilation failed")

        return CompilationResult()

    def get_sketch_report(self, compilation_result):
        """Return a dictionary containing data on the sketch:
        sketch_path -- the sketch path relative to the workspace
        compilation_success -- the success of the compilation (True, False)
        flash -- program memory usage of the sketch
        previous_flash -- if size deltas reporting is enabled, flash usage of the sketch at the base ref of the
                          pull request
        flash_delta -- if size deltas reporting is enabled, difference between the flash usage of the pull request head
                       and base refs
        ram -- dynamic memory used by globals
        previous_ram -- if size deltas reporting is enabled, dynamic memory used by globals at the base ref of the
                        pull request
        ram_delta -- if size deltas reporting is enabled, difference between the flash usage of the pull request head
                     and base ref

        Keyword arguments:
        compilation_result -- object returned by compile_sketch()
        """
        current_sketch_report = self.get_sketch_report_from_output(compilation_result=compilation_result)
        if self.do_size_deltas_report(sketch_report=current_sketch_report):
            # Get data for the sketch at the tip of the target repository's default branch
            # Get the pull request's head ref
            repository = git.Repo(path=os.environ["GITHUB_WORKSPACE"])
            original_git_ref = repository.head.object.hexsha

            # git checkout the PR's base ref
            self.checkout_pull_request_base_ref()

            # Compile the sketch again
            print("Compiling previous version of sketch to determine memory usage change")
            previous_compilation_result = self.compile_sketch(sketch_path=absolute_path(path=compilation_result.sketch))

            # git checkout the PR's head ref to return the repository to its previous state
            repository.git.checkout(original_git_ref)

            previous_sketch_report = self.get_sketch_report_from_output(compilation_result=previous_compilation_result)

            # Determine the memory usage change
            sketch_report = self.get_size_deltas(current_sketch_report=current_sketch_report,
                                                 previous_sketch_report=previous_sketch_report)
        else:
            sketch_report = current_sketch_report

        return sketch_report

    def get_sketch_report_from_output(self, compilation_result):
        """Parse the stdout from the compilation process and return a dictionary containing data on the sketch:
        sketch_path -- the sketch path relative to the workspace
        compilation_success -- the success of the compilation (True, False)
        flash -- program memory usage of the sketch
        ram -- dynamic memory used by globals

        Keyword arguments:
        compilation_result -- object returned by compile_sketch()
        """
        flash_regex = r"Sketch uses [0-9]+ bytes .*of program storage space\."
        ram_regex = r"Global variables use [0-9]+ bytes .*of dynamic memory"

        # Set default report values
        sketch_report = {self.report_sketch_key: str(compilation_result.sketch),
                         self.report_compilation_success_key: compilation_result.success,
                         self.report_flash_key: self.not_applicable_indicator,
                         self.report_ram_key: self.not_applicable_indicator}
        if sketch_report[self.report_compilation_success_key] is True:
            # Determine flash usage of the sketch by parsing Arduino CLI's output
            flash_match = re.search(pattern=flash_regex, string=compilation_result.output)
            if flash_match:
                # If any of the following:
                # - recipe.size.regex is not defined in platform.txt
                # - upload.maximum_size is not defined in boards.txt
                # flash usage will not be reported in the Arduino CLI output
                sketch_report[self.report_flash_key] = int(
                    re.search(pattern="[0-9]+", string=flash_match.group(0)).group(0))

            # Determine RAM usage by global variables
            ram_match = re.search(pattern=ram_regex, string=compilation_result.output)
            if ram_match:
                # If any of the following:
                # - recipe.size.regex.data is not defined in platform.txt (e.g., Arduino SAM Boards)
                # - recipe.size.regex is not defined in platform.txt
                # - upload.maximum_size is not defined in boards.txt
                # RAM usage will not be reported in the Arduino CLI output
                sketch_report[self.report_ram_key] = int(
                    re.search(pattern="[0-9]+", string=ram_match.group(0)).group(0))

        return sketch_report

    def do_size_deltas_report(self, sketch_report):
        """Return whether size deltas reporting is enabled for the given sketch.

        Keyword arguments:
        sketch_report -- sketch report dictionary
        """
        return (
            self.enable_size_deltas_report
            and os.environ["GITHUB_EVENT_NAME"] == "pull_request"
            and self.is_report_sketch(sketch_path=sketch_report[self.report_sketch_key])
            and sketch_report[self.report_compilation_success_key]
            and not (sketch_report[self.report_flash_key] == self.not_applicable_indicator
                     and sketch_report[self.report_ram_key] == self.not_applicable_indicator)
        )

    def is_report_sketch(self, sketch_path):
        """Return whether the given sketch is the report sketch.

        Keyword arguments:
        sketch_path -- path to the sketch
        """
        # TODO: yes, it was silly to identify the report sketch only by the name, rather than the path, but the whole
        #       concept of the size report sketch will be removed soon when the behavior is switched to reporting memory
        #       usage for all sketches. So for now, it's best to simply continue with the existing behavior.
        return pathlib.PurePath(sketch_path).name == self.report_sketch

    def checkout_pull_request_base_ref(self):
        """git checkout the base ref of the pull request"""
        repository = git.Repo(path=os.environ["GITHUB_WORKSPACE"])

        # Determine the pull request number, to use for the GitHub API request
        with open(file=os.environ["GITHUB_EVENT_PATH"]) as github_event_file:
            pull_request_number = json.load(github_event_file)["pull_request"]["number"]

        # Get the PR's base ref from the GitHub API
        try:
            repository_api = self.github_api.get_repo(full_name_or_id=os.environ["GITHUB_REPOSITORY"])
        except github.UnknownObjectException:
            print("::error::Unable to access repository data. Please specify the github-token input in your workflow"
                  " configuration.")
            sys.exit(1)

        pull_request_base_ref = repository_api.get_pull(number=pull_request_number).base.ref

        # git fetch the PR's base ref
        origin_remote = repository.remotes["origin"]
        origin_remote.fetch(refspec=pull_request_base_ref, verbose=self.verbose, no_tags=True, prune=True,
                            depth=1)

        # git checkout the PR base ref
        repository.git.checkout(pull_request_base_ref)

    def get_size_deltas(self, current_sketch_report, previous_sketch_report):
        """Return the sketch report with memory usage size deltas data added

        Keyword arguments:
        current_sketch_report -- data from the compilation of the sketch at the pull request's head ref
        previous_sketch_report -- data from the compilation of the sketch at the pull request's base ref
        """
        # Record current memory usage
        sketch_report = current_sketch_report
        # Record previous memory usage
        sketch_report[self.report_previous_flash_key] = previous_sketch_report[self.report_flash_key]
        sketch_report[self.report_previous_ram_key] = previous_sketch_report[self.report_ram_key]

        # Calculate the memory usage change
        if (
            sketch_report[self.report_flash_key] == self.not_applicable_indicator
            or sketch_report[self.report_previous_flash_key] == self.not_applicable_indicator
        ):
            sketch_report[self.report_flash_delta_key] = self.not_applicable_indicator
        else:
            sketch_report[self.report_flash_delta_key] = (sketch_report[self.report_flash_key]
                                                          - sketch_report[self.report_previous_flash_key])

        if (
            sketch_report[self.report_ram_key] == self.not_applicable_indicator
            or sketch_report[self.report_previous_ram_key] == self.not_applicable_indicator
        ):
            sketch_report[self.report_ram_delta_key] = self.not_applicable_indicator
        else:
            sketch_report[self.report_ram_delta_key] = (sketch_report[self.report_ram_key]
                                                        - sketch_report[self.report_previous_ram_key])

        # Print the memory usage change data to the log
        print("Change in flash memory usage:", sketch_report[self.report_flash_delta_key])
        print("Change in RAM used by globals:", sketch_report[self.report_ram_delta_key])

        return sketch_report

    def do_size_trends_report(self):
        """Return whether the size trends report is enabled"""
        return (
            self.enable_size_trends_report
            and os.environ["GITHUB_EVENT_NAME"] == "push"
            and self.is_default_branch()
        )

    def is_default_branch(self):
        """Return whether the current branch is the repository's default branch"""
        current_branch_name = os.environ["GITHUB_REF"].rpartition("/")[2]

        try:
            default_branch_name = self.github_api.get_repo(os.environ["GITHUB_REPOSITORY"]).default_branch
        except github.UnknownObjectException:
            print("::error::Unable to access repository data. Please specify the github-token input in your workflow"
                  " configuration.")
            sys.exit(1)

        if current_branch_name != default_branch_name:
            is_default_branch = False
        else:
            is_default_branch = True

        return is_default_branch

    def get_sketch_report_from_sketches_report(self, sketches_report):
        """Return the report for the report sketch

        Keyword arguments:
        sketches_report -- list containing the reports for all sketches
        """
        # TODO: The plan is to switch to reporting memory usage data for all sketches, rather than only a single sketch.
        #       The current system of unnecessarily storing data for all sketches, then searching back through it for a
        #       single item to report is in anticipation of that change
        for sketch_report in sketches_report:
            if self.is_report_sketch(sketch_path=sketch_report[self.report_sketch_key]):
                return sketch_report

        # Data for the size reports sketch was not found
        print("::error::size-report-sketch:", self.report_sketch, "was not found")
        sys.exit(1)

    def make_size_trends_report(self, sketch_report):
        """Publish the size data for the report sketch to a Google Sheets spreadsheet.

        Keyword arguments:
        sketch_report -- report for the sketch report
        """
        # Get the short hash of the pull request head ref
        self.verbose_print("Making size trends report")
        repository = git.Repo(path=os.environ["GITHUB_WORKSPACE"])
        current_git_ref = repository.git.rev_parse("HEAD", short=True)

        report_size_trends = reportsizetrends.ReportSizeTrends(
            google_key_file=self.google_key_file,
            spreadsheet_id=self.size_trends_report_spreadsheet_id,
            sheet_name=self.size_trends_report_sheet_name,
            sketch_name=sketch_report[self.report_sketch_key],
            commit_hash=current_git_ref,
            commit_url=("https://github.com/"
                        + os.environ["GITHUB_REPOSITORY"]
                        + "/commit/"
                        + current_git_ref),
            fqbn=self.fqbn,
            flash=str(sketch_report[self.report_flash_key]),
            ram=str(sketch_report[self.report_ram_key])
        )

        report_size_trends.report_size_trends()

    def create_sketches_report_file(self, sketches_report):
        """Write the report for the report sketch to a file.

        Keyword arguments:
        sketch_report -- report for the sketch report
        """
        self.verbose_print("Creating sketch report file")
        # Add the FQBN to the report
        # TODO: doing this here is in anticipation of the planned switch to reporting for all sketches, when it will
        #       make sense to only add a single fqbn key to the report
        sketches_report[self.report_fqbn_key] = self.fqbn
        sketches_report_path = absolute_path(path=self.sketches_report_path)

        # Create the report folder
        sketches_report_path.mkdir(parents=True, exist_ok=True)

        # Write the memory usage data to a file named according to the FQBN
        with open(file=sketches_report_path.joinpath(self.fqbn.replace(":", "-") + ".json"), mode="w",
                  encoding="utf-8") as report_file:
            json.dump(obj=sketches_report, fp=report_file, indent=2)


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


def path_relative_to_workspace(path):
    """Returns the path relative to the workspace of the action's Docker container. This is the path used in all
    human-targeted output.

    Keyword arguments:
    path -- the path to make relative
    """
    path = pathlib.PurePath(path)
    return path.relative_to(os.environ["GITHUB_WORKSPACE"])


def absolute_path(path):
    """Returns the absolute path equivalent. Relative paths are assumed to be relative to the workspace of the action's
    Docker container (the root of the repository).

    Keyword arguments:
    path -- the path to make absolute
    """
    path = pathlib.Path(path)
    if not path.is_absolute():
        # path is relative
        path = pathlib.Path(os.environ["GITHUB_WORKSPACE"], path)

    return path


def path_is_sketch(path):
    """Return whether the specified path is an Arduino sketch.

    Keyword arguments:
    path -- path of to check for a sketch
    """
    sketch_extensions = [".ino"]  # TODO: this is preparation for the addition of support for the .pde extension

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


def install_from_download(url, source_path, destination_parent_path, destination_name=None):
    """Download an archive, extract, and install.

    Keyword arguments:
    url -- URL to download the archive from
    source_path -- path relative to the root folder of the archive to install.
    destination_parent_path -- path under which to install
    destination_name -- folder name to use for the installation. Set to None to take the name from source_path.
                        (default None)
    """
    destination_parent_path = pathlib.Path(destination_parent_path)

    # Create temporary folder for the download
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

        # Create temporary folder for the extraction
        with tempfile.TemporaryDirectory("-compilesketches-extract_folder") as extract_folder:
            # Extract archive
            shutil.unpack_archive(filename=str(download_file_path), extract_dir=extract_folder)

            archive_root_path = get_archive_root_path(extract_folder)

            absolute_source_path = pathlib.Path(archive_root_path, source_path).resolve()

            if not absolute_source_path.exists():
                print("::error::Archive source path:", source_path, "not found")
                sys.exit(1)

            if destination_name is None:
                destination_name = absolute_source_path.name

            # Create the parent path if it doesn't already exist
            destination_parent_path.mkdir(parents=True, exist_ok=True)

            # Install by moving the source folder
            shutil.move(src=str(absolute_source_path),
                        dst=str(destination_parent_path.joinpath(destination_name)))


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


# Only execute the following code if the script is run directly, not imported
if __name__ == "__main__":
    main()
