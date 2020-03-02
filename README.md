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

## Example usage

```yaml
uses: arduino/actions/libraries/compile-examples@master
with:
  fqbn: 'arduino:avr:uno'
```
