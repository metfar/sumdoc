# SUM CLI migration — sumdoc 0.3.2.8

The command-line entry points in this local development snapshot adopt the
`sumui.cli.SumArgumentParser` contract where appropriate, retaining historical
arguments and specialized behavior. The `sumcore` package is the architectural
exception: its own executable uses `sys.argv` and its auxiliary programs stay
independent of `sumUI`.

This is a **local development build**, not a published release. Verify normal
runtime behavior in the target environment before promoting to the repository.

`lessans` is now a registered standalone multicall name; `lessrich` / `md2rich` opens an interactive pager on a TTY and preserves streaming output otherwise. Use `--no-pager` to opt out explicitly.

<p align=center><b>- oOo -</b></p>
