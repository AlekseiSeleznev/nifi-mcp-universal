# NiFi client source

The modules in `gateway/nifi/` are derived from
[Cloudera NiFi-MCP-Server](https://github.com/cloudera/NiFi-MCP-Server),
commit `9af7ce2930814e974d9c8b26330f7b2cb7431324` (Apache License 2.0).
The upstream license is reproduced in `licenses/Apache-2.0.txt`.
That upstream revision contains no separate NOTICE file.

These modules have been modified for this gateway, including import paths,
certificate authentication, response sanitization, bounded provenance counts,
read-only enforcement and asynchronous dispatch. They are not an unmodified
copy of the upstream package. Gateway-specific code retains the repository's
MIT license.
