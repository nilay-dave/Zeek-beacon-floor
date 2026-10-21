# Security policy

## Reporting a vulnerability

Report privately through GitHub's
[security advisory form](https://github.com/__GITHUB_USERNAME__/zeek-beacon-floor/security/advisories/new)
rather than in a public issue. You should get a first response within a week.

## Scope

This tool reads files and computes. It opens no network connection at all, and
CI enforces that: no module under `src/` may reference a socket, `urllib`,
`requests` or `httpx`. An analyst should be able to run it on an isolated host
holding evidence, and that property is worth more here than any feature that
would cost it.

In scope: anything that makes the tool execute data it read, write outside the
path it was given, or consume unbounded memory on a crafted log.

## A note on what you feed it

A conn.log is a record of who on your network talked to whom, when, and for how
long. It is evidence in the legal sense and personal data in the regulatory
one.

This tool keeps no copy. It streams the log, holds the timestamps it needs, and
writes nothing except where you point it. The issue templates ask people not to
paste a conn.log into a bug report, and `zbf fields` exists partly so a reader
problem can be diagnosed from column names alone.

## A note on what a high score means

A high score means the traffic is periodic. It does not mean the traffic is
malicious, and the tool says so in its own output. A monitoring agent, a
software update check and a certificate revocation poll are all periodic. Acting
on a score from this tool as though it were a verdict is the most likely way to
cause harm with it, and that is a usage problem rather than a vulnerability, but
it belongs on this page.
