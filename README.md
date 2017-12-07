# SMS to jwplayer export tooling

This repository contains tooling to implement the University of Cambridge
streaming media service (SMS) to jwplayer migration.

See the documentation at https://uis-sms2jwplayer.rtfd.io/.

## Running tests

Tests are run in multiple Python environments. If a particular environment is
not installed, the test suite is skipped for that environment.

```console
$ pip install tox  # install tox automation tool
$ tox              # run tests
```
