# Enterprise Search (archived — discontinued in Elastic 9.x)

Elastic Enterprise Search (App Search + Workplace Search) was discontinued after
the 8.x line. There is **no `enterprise-search` image for 9.x**; the last release
is `8.18.6`. These files are kept for reference only and are not part of the
active 9.4.3 stack.

## Replacement (native, no separate container)

The capability moved into Elasticsearch/Kibana directly:

- **App Search engines → Search Applications API** (`_application/search_application`)
  plus the Search UI and ES|QL / semantic search in Kibana.
- **Workplace Search content sources → Elastic Connectors.** This repo already
  ships those under `../../elastic__connectors/`.

If you must run the legacy component, deploy it standalone against an **8.x**
Elasticsearch cluster (build arg `ENTERPRISE_SEARCH_VERSION=8.18.6`); it is not
supported against a 9.x server.
