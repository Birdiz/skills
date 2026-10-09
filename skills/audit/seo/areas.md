# seo areas and severity

## Areas

- **Indexability**: status codes, meta robots and `X-Robots-Tag`, canonicals, pages meant to be indexed that cannot be, and the reverse.
- **Crawlability**: internal links, orphan routes, redirect chains, crawl traps (endless parameters, calendars), robots.txt.
- **Sitemaps**: presence, declared in robots.txt, entries indexable and current.
- **Duplicates**: hosts and protocols, trailing slashes, parameters, the same content on several sites or URLs.
- **Titles and descriptions**: present, unique, describing the page.
- **Structure**: one main heading, heading order, language declared.
- **Structured data**: types fitting the content (an event, an organisation), valid against the vocabulary, consistent with the page.
- **Rendering**: content and links present in the HTML as served, or only after JavaScript.
- **International**: language and alternates between language versions, when there are several.
- **Sharing**: Open Graph and similar tags on pages meant to be shared.

## Severity grid

What it does to the pages the owner wants found, and how many.

| | Whole host or site | A template or section | One page |
|---|---|---|---|
| Pages meant to be found cannot be crawled or indexed (`noindex`, blocked, error, canonical elsewhere) | high | medium | low |
| Pages meant to stay out are indexable (accounts, administration, form results, duplicates) | medium | medium | low |
| Conflicting or duplicate signals (canonicals, hosts, titles) | medium | low | low |
| Missing enhancement (description, structured data, sharing tags) | low | low | info |
| Observation | info | info | info |

Moves of one level: `finding-format`, Rating.
