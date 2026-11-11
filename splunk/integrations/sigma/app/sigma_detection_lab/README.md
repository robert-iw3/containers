# sigma_detection_lab

A Splunk app holding converted Sigma rules as saved searches, the detection
events they produce, and dashboards to read them.

## Colors

Severity is a status scale, so it uses reserved status colors rather than
series colors — a severity color must never be mistaken for "series 4".
Each one is paired with its own text label in every panel, because a status
color must not carry meaning on its own.

| Role | Hex | Source |
|---|---|---|
| brand accent | `#19C1EB` | measured from the Sigma logo, the dominant non-background color |
| brand dark | `#464646` | measured from the Sigma logo |
| critical | `#d03b3b` | status |
| high | `#ec835a` | status |
| medium | `#fab219` | status |
| low | `#0ca30c` | status |
| informational | `#19C1EB` | brand accent |

Measured, not chosen by eye, against the dark chart surface `#1a1a19`:

| Color | Contrast on dark | Verdict |
|---|---|---|
| `#19C1EB` | 8.19 | pass |
| `#fab219` | 9.49 | pass |
| `#ec835a` | 6.60 | pass |
| `#0ca30c` | 5.19 | pass |
| `#d03b3b` | 3.62 | pass |
| `#464646` | 1.85 | **fails 3:1** |

The brand dark grey is therefore not used as a mark color on these
dashboards. It is a text and surface color only. Brand cyan sits at least
26 OKLab units from every status color, so it can appear beside them
without impersonating one.

Single-series charts use the brand accent. A single series needs no legend,
and no other series can collide with it.

## Dashboards

| View | Answers |
|---|---|
| `detection_coverage` | What fired, how severe, on which hosts, and over what period. Tiles first, then detail. |
| `alert_detail` | One rule or host at a time, with the Windows or Linux events that triggered each detection. |

Every table drills through to the source events. The detection event records
`sigma_src_index`, `sigma_src_sourcetype`, `sigma_src_host` and
`sigma_src_time` before `collect` rewrites index and source type, which is
what makes the trail back to the original log possible.
