# Frequently Asked Questions

## How can I install dependencies of a boards platform?

### Managed Dependencies

The Arduino **Boards Manager** system installs tool dependencies along with a platform. When you specify a [**Boards Manager**-sourced platform dependency](../README.md#boards-manager) via the action's [`platforms` input](../README.md#platforms) the managed platform dependencies are installed automatically.

If an alternative [platform dependency source](../README.md#supported-platform-sources) is used this automatic tool dependency installation does not occur. The convenient way to install the tool dependencies in this case is to install a **Boards Manager**-sourced platform that has a dependency on the required tools in addition to the target platform from the alternative source.

---

**Example:**

```yaml
- uses: arduino/compile-sketches@v1
  with:
    platforms: |
      # Use Boards Manager to install the latest release of the platform to get the toolchain.
      - name: arduino:avr
      # Overwrite the Boards Manager installation with the development version of the platform.
      - source-url: https://github.com/arduino/ArduinoCore-avr.git
        name: arduino:avr
```

---

### External Dependencies

Arduino boards platforms typically bundle all dependencies. However, there are some platforms that require the user to manually install dependencies on their system in order to use the platform.

The **arduino/compile-sketches** action runs in the same environment as the rest of the steps of the [workflow job](https://docs.github.com/actions/using-jobs/using-jobs-in-a-workflow), which means you can simply perform the dependency installation in a prior [step](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idsteps) of the job.

---

**Example:**

```yaml
- run: <some dependency installation command>
- uses: arduino/compile-sketches@v1
```

---

#### Python Packages

The **arduino/compile-sketches** action uses a Python [virtual environment](https://docs.python.org/glossary.html#term-virtual-environment). In order to enable user installation of Python [package](https://docs.python.org/glossary.html#term-package) dependencies of boards platforms, the packages installed in the "[user site-packages](https://peps.python.org/pep-0370/)" folder are included in this virtual environment.

In order to be certain your installation of a package dependency will be available to the platform, add the [`--ignore-installed`](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-ignore-installed) and [`--user`](https://pip.pypa.io/en/stable/cli/pip_install/#install-user) flags to the [**pip**](https://pip.pypa.io/) command used to install the package.

---

**Example:**

```yaml
- run: pip install --ignore-installed --user pyserial
- uses: arduino/compile-sketches@v1
```

---

## How can I install a platform or library dependency from an external private repository?

The **arduino/compile-sketches** action supports installing platform and library dependencies of the sketches by cloning the repository specified via the `source-url` field of the [`platforms`](../README.md#platforms) or [`libraries`](../README.md#libraries) inputs.

With a public repository, the dependency definition will look something like this:

```yaml
libraries: |
  - source-url: https://github.com/arduino-libraries/Servo.git
```

However, if `arduino-libraries/Servo` was a private repository the installation of this library by the action would fail:

```text
fatal: could not read Username for 'https://github.com': No such device or address
```

In this case is necessary to configure the repository URL to provide the authentication required for **Git** to clone the repository, as documented [**here**](https://git-scm.com/docs/git-clone#_git_urls). For private GitHub repositories, the following URL format can be used:

```text
https://<token>@github.com/<repo slug>.git
```

where `<token>` is a "[personal access token](https://docs.github.com/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#about-personal-access-tokens)" with `repo` scope from the account of a user with access to the private repository.

---

**ⓘ** You might find it convenient to create the token under a ["machine user" account](https://docs.github.com/authentication/connecting-to-github-with-ssh/managing-deploy-keys#machine-users).

---

In order to avoid leaking the token, it must be stored in a [secret](https://docs.github.com/actions/security-guides/using-secrets-in-github-actions), and that secret [referenced](https://docs.github.com/actions/security-guides/using-secrets-in-github-actions#using-secrets-in-a-workflow) in the URL.

---

**Example:**

```yaml
- uses: arduino/compile-sketches@v1
  with:
    libraries: |
      - source-url: https://${{ secrets.REPO_SCOPE_TOKEN }}@github.com/octocat/SomePrivateLib.git
```

---

**ⓘ** The automatically generated [`GITHUB_TOKEN` secret](https://docs.github.com/actions/security-guides/automatic-token-authentication#about-the-github_token-secret) can not be used for this purpose as it lacks the necessary permissions.

---
