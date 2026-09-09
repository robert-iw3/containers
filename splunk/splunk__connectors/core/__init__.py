"""
Shared machinery for the file-tailing Splunk connectors.

Each format connector supplies a parser and nothing else. Everything that is
not format-specific - offsets, schema matching, time coercion, HEC framing,
retry, delivery accounting - lives here in one copy, so a fix reaches every
format instead of one.

The delivery contract, which the format connectors inherit and must not
weaken:

  A file offset advances only after Splunk acknowledges the events read from
  it. Reading is not delivery. On a crash or a rejected batch the connector
  re-reads rather than skips, so the failure mode is a duplicate rather than
  a silent hole.
"""

__all__ = ["config", "hec", "mapping", "parsers", "runner", "schemas", "state", "timeparse"]
