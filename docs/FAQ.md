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
