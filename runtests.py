#!/usr/bin/env python3
import subprocess
from subprocess import Popen
from sys import argv, exit, executable

# Slow test suites
CMDLINE = 'PythonCmdline'
SAMPLES = 'SamplesSuite'
TYPESHED = 'TypeshedSuite'
PEP561 = 'PEP561Suite'
EVALUATION = 'PythonEvaluation'
DAEMON = 'testdaemon'
STUBGEN_CMD = 'StubgenCmdLine'
STUBGEN_PY = 'StubgenPythonSuite'
MYPYC_RUN = 'TestRun'
MYPYC_RUN_MULTI = 'TestRunMultiFile'
MYPYC_EXTERNAL = 'TestExternal'
MYPYC_COMMAND_LINE = 'TestCommandLine'
ERROR_STREAM = 'ErrorStreamSuite'


ALL_NON_FAST = [
    CMDLINE,
    SAMPLES,
    TYPESHED,
    PEP561,
    EVALUATION,
    DAEMON,
    STUBGEN_CMD,
    STUBGEN_PY,
    MYPYC_RUN,
    MYPYC_RUN_MULTI,
    MYPYC_EXTERNAL,
    MYPYC_COMMAND_LINE,
    ERROR_STREAM,
]


# These must be enabled by explicitly including 'mypyc-extra' on the command line.
MYPYC_OPT_IN = [MYPYC_RUN, MYPYC_RUN_MULTI]

# We split the pytest run into three parts to improve test
# parallelization. Each run should have tests that each take a roughly similar
# time to run.
cmds = {
    'self': [
        executable,
        '-m',
        'mypy',
        '--config-file',
        'mypy_self_check.ini',
        '-p',
        'mypy',
    ],
    'lint': ['flake8', '-j0'],
    'pytest-fast': [
        'pytest',
        '-q',
        '-k',
        f"not ({' or '.join(ALL_NON_FAST)})",
    ],
    'pytest-cmdline': [
        'pytest',
        '-q',
        '-k',
        ' or '.join([CMDLINE, EVALUATION, STUBGEN_CMD, STUBGEN_PY]),
    ],
    'pytest-slow': [
        'pytest',
        '-q',
        '-k',
        ' or '.join(
            [
                SAMPLES,
                TYPESHED,
                PEP561,
                DAEMON,
                MYPYC_EXTERNAL,
                MYPYC_COMMAND_LINE,
                ERROR_STREAM,
            ]
        ),
    ],
    'typeshed-ci': [
        'pytest',
        '-q',
        '-k',
        ' or '.join([CMDLINE, EVALUATION, SAMPLES, TYPESHED]),
    ],
    'mypyc-extra': ['pytest', '-q', '-k', ' or '.join(MYPYC_OPT_IN)],
}


# Stop run immediately if these commands fail
FAST_FAIL = ['self', 'lint']

DEFAULT_COMMANDS = [cmd for cmd in cmds if cmd not in ('mypyc-extra', 'typeshed-ci')]

assert all(cmd in cmds for cmd in FAST_FAIL)


def run_cmd(name: str) -> int:
    status = 0
    cmd = cmds[name]
    print(f'run {name}: {cmd}')
    proc = subprocess.run(cmd, stderr=subprocess.STDOUT)
    if proc.returncode:
        print('\nFAILED: %s' % name)
        status = proc.returncode
        if name in FAST_FAIL:
            exit(status)
    return status


def start_background_cmd(name: str) -> Popen:
    cmd = cmds[name]
    return subprocess.Popen(cmd,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE)


def wait_background_cmd(name: str, proc: Popen) -> int:
    output = proc.communicate()[0]
    status = proc.returncode
    print(f'run {name}: {cmds[name]}')
    if status:
        print(output.decode().rstrip())
        print('\nFAILED: %s' % name)
        if name in FAST_FAIL:
            exit(status)
    return status


def main() -> None:
    prog, *args = argv

    if not set(args).issubset(cmds):
        print("usage:", prog, " ".join(f'[{k}]' for k in cmds))
        print()
        print('Run the given tests. If given no arguments, run everything except mypyc-extra.')
        exit(1)

    if not args:
        args = DEFAULT_COMMANDS[:]

    status = 0

    if 'self' in args and 'lint' in args:
        # Perform lint and self check in parallel as it's faster.
        proc = start_background_cmd('lint')
        if cmd_status := run_cmd('self'):
            status = cmd_status
        if cmd_status := wait_background_cmd('lint', proc):
            status = cmd_status
        args = [arg for arg in args if arg not in ('self', 'lint')]

    for arg in args:
        if cmd_status := run_cmd(arg):
            status = cmd_status

    exit(status)


if __name__ == '__main__':
    main()
