# libraries/compile-examples action

This action compiles all of the examples contained in the library.

## Inputs

### `cli-version`

The version of `arduino-cli` to use. Default `"latest"`.

### `fqbn`

**Required** The fully qualified board name to use when compiling. Default `"arduino:avr:uno"`.

### `libraries`

List of library dependencies to install (space separated). Default `""`.

## Example usage

```yaml
uses: arduino/actions/libraries/compile-examples@master
with:
  fqbn: 'arduino:avr:uno'
```
