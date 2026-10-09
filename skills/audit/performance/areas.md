# performance areas and severity

## Areas

- **Server response**: time to first byte of the main pages, and the work behind it.
- **Database**: queries per request, queries repeated per item, unbounded result sets, indexes against the queries, locks held long.
- **Remote calls**: third-party and internal calls made while the user waits, their timeouts, retries in the request path.
- **Deferred work**: what the request does that a queue or a later job could, and whether that queue keeps up.
- **Caching**: HTTP caching headers, application and query caches, what is recomputed on every request.
- **Runtime**: production settings of the language runtime and server (bytecode cache, worker mode, preloading, connection pools).
- **Loading**: largest contentful paint, render-blocking resources, critical path, fonts.
- **Assets**: weight and count, compression, image formats and sizes, unused code.
- **Layout stability**: layout shift and its causes (images without dimensions, late content).
- **Interactivity**: total blocking time and long tasks, script cost, third-party scripts.
- **Growth**: cost that rises with accumulated data, without page size or limit.

## Severity grid

What users wait for, and where. "Main flow" is a flow of the codebase map.

| | Main flow | Other pages | Administration or background only |
|---|---|---|---|
| Fails at expected volume (timeout, memory exhausted, connection pool drained) | high | medium | low |
| "Poor" on a Core Web Vital, or a wait users notice on every visit, measured on a production-like configuration | high | medium | low |
| "Needs improvement", or cost that grows with data without bound, shown in code | medium | low | low |
| Waste with no user effect measured (uncompressed asset, missing cache header) | low | low | info |
| Observation | info | info | info |

`critical` only when the failure is shown to happen now. Moves of one level:
`finding-format`, Rating.
