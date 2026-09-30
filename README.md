# Property Listings API

A small REST API for property listings (rent / sale / shortlet) with filtering,
geospatial search, pagination and consistent error handling.

**Stack:** Django 5.1 · Django REST Framework 3.17 · drf-spectacular 0.30 · geopy 2.5 · SQLite

Project layout:

```
manage.py
property_listing_api/      # settings, root urls, wsgi/asgi
listings/                  # the app: models, geo, filters, serializers, views, tests
payloads/                  # sample request bodies + search examples (see "Sample payloads")
requirements.txt
```

---

## Quickstart

```bash
python -m venv .venv
.\.venv\Scripts\activate          # Windows
source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The API is then at http://127.0.0.1:8000/api/ — DRF's browsable API is enabled, so
every endpoint can be clicked through in a browser.

Interactive docs: <http://127.0.0.1:8000/api/docs/> (Swagger UI),
<http://127.0.0.1:8000/api/redoc/> (ReDoc), and the raw schema at
`/api/schema/` (YAML), `/api/schema.json` or `/api/schema.yaml`.

Regenerate the schema on the command line — `--fail-on-warn` turns drf-spectacular's
warnings into a non-zero exit, which is what the test suite runs:

```bash
python manage.py spectacular --file schema.yml --fail-on-warn
```

Run the tests:

```bash
python manage.py test              # 83 tests, ~1.3s
```

Optional environment variables (all have sensible development defaults):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | insecure dev key | Set this in any real deployment |
| `DJANGO_DEBUG` | `True` | Set to `False` outside development |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Comma-separated host list |

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/` | Liveness probe |
| `GET` | `/api/` | Browsable API root |
| `GET` | `/api/listings/` | Paginated list, newest first |
| `POST` | `/api/listings/` | Create a listing |
| `GET` | `/api/listings/search/` | Filter + optional radius search |
| `GET` | `/api/listings/{id}/` | Retrieve one listing |
| `PUT` / `PATCH` | `/api/listings/{id}/` | Replace / partially update |
| `DELETE` | `/api/listings/{id}/` | Delete (`204 No Content`) |
| `GET` | `/api/docs/`, `/api/redoc/` | Swagger UI / ReDoc, generated from the code |
| `GET` | `/api/schema/`, `.json`, `.yaml` | Raw OpenAPI 3 schema |
| — | `/admin/` | Django admin (login: `createsuperuser`) |

### Listing resource

```jsonc
{
  "id": 41,
  "title": "3 Bedroom Bungalow in Yaba",
  "description": "Serviced, quiet compound.",
  "price": "725000.00",          // string, see "Money"
  "type": "sale",                // rent | sale | shortlet
  "bedrooms": 3,
  "agent_id": "agent-002",
  "location": { "name": "Yaba", "lat": 6.5095, "lng": 3.3711 },
  "created_at": "2026-09-29T11:53:38.436691Z",
  "updated_at": "2026-09-29T11:53:38.436691Z"
}
```

Create it with the same body:

```bash
curl -X POST http://127.0.0.1:8000/api/listings/ \
  -H "Content-Type: application/json" \
  -d '{
        "title": "3 Bedroom Bungalow in Yaba",
        "description": "Serviced, quiet compound.",
        "price": "725000.00",
        "type": "sale",
        "bedrooms": 3,
        "agent_id": "agent-002",
        "location": {"name": "Yaba", "lat": 6.5095, "lng": 3.3711}
      }'
```

### Search

`GET /api/listings/search/` accepts any combination of:

| Parameter | Meaning |
| --- | --- |
| `type` | `rent`, `sale` or `shortlet` |
| `min_price`, `max_price` | Inclusive price bounds |
| `bedrooms` | Exact bedroom count |
| `min_bedrooms`, `max_bedrooms` | Inclusive bedroom range |
| `lat`, `lng`, `radius_km` | Distance search — **all three or none** (`radius_km` ≤ 200) |
| `sort` | `newest` (default), `price_asc`, `price_desc`, `bedrooms_desc`, `distance` |
| `page`, `page_size` | Pagination (`page_size` ≤ 100) |

```bash
# 2+ bedroom rentals within 5 km of Lagos Island, nearest first
curl "http://127.0.0.1:8000/api/listings/search/?type=rent&min_bedrooms=2\
&lat=6.4550&lng=3.3900&radius_km=5"
```

Distance searches return an extra `distance_km` field (km, 3 dp) on each row:

```jsonc
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    { "id": 1, "title": "2 Bedroom Self-Contained Apartment in Victoria Island", "price": "850000.00", "distance_km": 4.615 },
    { "id": 2, "title": "Luxury 4 Bedroom Duplex for Rent in Ikoyi", "price": "4200000.00", "distance_km": 4.978 }
  ]
}
```

### Sample payloads

There is no seed command: the sample data lives in `payloads/` as request
payloads, so what you demo with is exactly what the API accepts (and importing it
into Postman/Insomnia/HTTPie is a file open).

- `payloads/listings.json` — 14 create bodies covering all three types, 1–5
  bedrooms, rents from ₦320k to ₦12m and sales up to ₦950m, spread across Lagos
  so the radius searches return meaningful results.
- `payloads/search_requests.json` — query strings for `GET /api/listings/search/`,
  including three deliberately invalid ones (marked `expect_status: 400`).

Post them all:

```bash
# bash / macOS / WSL
for payload in $(jq -c '.[]' payloads/listings.json); do
  curl -s -X POST http://127.0.0.1:8000/api/listings/ \
    -H "Content-Type: application/json" -d "$payload" > /dev/null
done

# PowerShell
Get-Content payloads/listings.json -Raw | ConvertFrom-Json | ForEach-Object {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/listings/ `
    -ContentType "application/json" -Body ($_ | ConvertTo-Json -Depth 5)
}

# one search
curl "http://127.0.0.1:8000/api/listings/search/?lat=6.4550&lng=3.3900&radius_km=5"
```

`listings/tests/test_payloads.py` posts every payload and runs every search
example on each test run, so these files can't go stale.

### Errors

Every error — validation, 404, 405, parse failure, even a 500 — uses one envelope:

```json
{
  "error": {
    "status": 400,
    "code": "validation_error",
    "message": "Validation failed.",
    "details": {
      "price": ["Ensure this value is greater than or equal to 0."],
      "location": {"lat": ["Ensure this value is less than or equal to 90."]}
    }
  }
}
```

Success responses for list endpoints use the standard DRF envelope
(`count` / `next` / `previous` / `results`).

---

## Design decisions

**Django REST Framework over plain Django.** The brief asked for Django; DRF is
the de-facto way to get serialisation, validation, content negotiation, browsable
API and a router without hand-rolling them. A `ModelViewSet` + router gives full
CRUD in a few lines, so the interesting work goes into search and validation.

**Flat columns, nested JSON.** The database stores `latitude` / `longitude` /
`location_name` as columns on `Listing`; the API exposes them as a `location`
object. Normalising into a separate `Location` table buys nothing at this scale
(one location per listing) and would complicate every filter and index. A
`LocationSerializer` gives the API a clean shape without a schema change later.

**Money is a `DecimalField` serialised as a string.** Never a float in the
database, and `"725000.00"` rather than `725000.0` in JSON so clients can parse
it as a decimal type rather than inheriting binary floating-point error.

**Validation lives in serializers, not in views.** `ListingSerializer` rejects
bad payloads; `SearchQuerySerializer` validates query parameters, including
cross-field rules DRF can't express alone (`min_price ≤ max_price`, the
`lat`/`lng`/`radius_km` triple, `sort=distance` only with geo params). It returns
all violations at once under `details`, so a client fixes one round trip's worth
of mistakes instead of one field per request.

**The OpenAPI schema is generated, not written.** drf-spectacular builds it from
the serializers plus `extend_schema` annotations in `listings/views.py`. The
important consequence: `SearchQuerySerializer` is *also* the source of truth for
the search endpoint's query parameters — the same fields that validate the request
appear in Swagger with their constraints and help text, so docs cannot drift from
behaviour. `ErrorEnvelopeSerializer` documents the one error shape every endpoint
returns. A test runs `manage.py spectacular --fail-on-warn`, so an undocumented
operation or an unresolvable type hint fails CI rather than quietly shipping.

**Distance maths comes from geopy, not hand-rolled.** `geopy` is the standard
Python geo library; `geopy.distance.geodesic` wraps GeographicLib's WGS84
ellipsoid solver — the same algorithms PROJ and PostGIS use — so distances are
correct rather than spherical-approximate (it differs from a naive haversine by
~0.03% on real pairs; for one Lagos listing the two disagree at the third
decimal of a km). Bounding boxes come from geopy too, by walking `radius_km`
along each cardinal bearing with `geodesic.destination`.

**Why geopy rather than GeoDjango.** GeoDjango is the natural answer at scale, but
its `PointField` / `Distance` lookups need a spatial database: PostGIS, or SpatiaLite
plus GDAL on the SQLite side. The brief says SQLite, and requiring a compiled
GDAL/SpatiaLite toolchain to run the tests would be a poor trade. So the maths is
standard, the storage stays portable SQLite, and swapping in PostGIS later is a
settings + model + queryset change — `listings/filters.py` is the only caller of
`distance_km` and is written to be deleted wholesale when that happens.

**Two-stage distance search.** SQLite has no spatial index, so:

1. A bounding-box pre-filter (`ListingQuerySet.in_bounding_box`) runs in SQL and
   throws away almost everything cheaply. Longitudes are unwrapped relative to
   the centre so an antimeridian box stays small instead of spanning the globe,
   and the box reaches all longitudes when the circle swallows a pole.
2. Exact geodesic distances are computed for the surviving candidates, and
   anything beyond `radius_km` is dropped — so box corners outside the circle
   don't leak into results.
3. The survivors are re-ordered in SQL with a `CASE` expression keyed on id, which
   lets DRF paginate and `COUNT` normally instead of slicing in Python.

Note this is CPU-bound in Python (~0.2 ms per geopy call), which is invisible at
demo scale and is exactly what the PostGIS path below removes.

**`agent_id` is a plain string.** The brief specifies an agent ID, and no agent
service exists in scope, so the field is an external reference that is indexed
and filterable. A real `Agent` model with a FK (and nested serializer) is the
first thing I'd add if agents were owned by this system.

**Strict `page_size`.** Stock DRF silently ignores a non-numeric `page_size` and
returns the default, which is confusing when debugging. `ListingPagination`
raises a 400 instead, still capped at 100 per page.

**Errors are uniform.** `listings/exceptions.py` wraps DRF's handler, and
`property_listing_api/urls.py` installs `handler400/404/500` so Django's own errors
match. Both only apply JSON under `/api/`, leaving `/admin/` untouched. Unhandled
exceptions still return a generic 500 body — never a traceback.

**Open permissions.** `AllowAny` throughout, since authentication wasn't in scope.
The seam is DRF's `permission_classes`, so adding token auth is a settings change
plus a per-view policy.

**Sample data is payloads, not a seed command.** `payloads/` holds real request
bodies instead of a `manage.py seed_*` command. A generator command would have
been a second, parallel definition of the listing shape — random titles, prices
and coordinates that drift from the serializer and need a `--seed` argument to
reproduce. Files are diffable, import into any HTTP client, and because
`test_payloads.py` replays them on every run they can't go stale.

---

## Tests

83 tests in `listings/tests/`, all through Django's test runner. Each one covers
behaviour the API promises; framework plumbing is not tested for its own sake.

| File | Tests | Covers |
| --- | --- | --- |
| `test_geo.py` | 9 | Geodesic distances against known city pairs and geopy itself, bounding-box corners, minimality, pole and antimeridian behaviour |
| `test_models.py` | 9 | Defaults, ordering, `full_clean` coordinate rejection, each queryset filter |
| `test_serializers.py` | 11 | Nested location writes/reads, partial updates, field validation, search-query cross-field rules |
| `test_api.py` | 22 | CRUD round trips, 404/405/415/malformed JSON, pagination edges, JSON 500 handler |
| `test_search.py` | 22 | Type/price/bedroom filters, every sort, radius filtering, nearest-first ordering, pagination across pages, antimeridian, invalid query params |
| `test_payloads.py` | 4 | Every file in `payloads/` still matches the API: each listing POSTs with 201, each search example returns its advertised status |
| `test_schema.py` | 6 | Schema is warning-free, every endpoint documented, search parameters match the serializer, error envelope documented, Swagger UI and ReDoc render |

Three of these tests caught real bugs during development — a bounding box that ran
past the poles, an antimeridian box that silently dropped the wrapped side, and a
naive min/max over longitudes that turned a 200 m box into a whole-globe one —
which is the argument for testing the geo maths rather than trusting it.

---

## What I'd improve with more time

- **Move to PostGIS.** Swap SQLite for PostGIS and the whole radius search
  becomes one indexed query: `PointField` with a GiST index,
  `ST_DWithin(point, radius)` for the filter and `ST_Distance` for ordering, with
  geopy kept only for coordinate validation. That removes the Python loop and the
  `CASE` ordering below.
- **Two-phase pagination for large radii.** Today's `CASE` ordering embeds one
  branch per match, so SQL grows linearly with the candidate set. At scale I'd
  page over a cursor (`?cursor=<last id/distance>`) after a bounded first query.
- **Auth and ownership.** Token auth, and per-agent permissions so a listing can
  only be edited by its own agent — which also makes `Agent` a real table.
- **CI plus linting.** Run the suite and `manage.py spectacular --fail-on-warn` on
  every push, alongside `ruff`/`mypy`; today the schema check only runs when
  someone remembers.
- **Observability.** Request-ID middleware, structured logging, and timing
  headers; today a slow radius query is invisible in production.
- **More search facets**: free-text on title/description (SQLite FTS5 or
  Postgres `tsvector`), bathrooms, amenities, availability dates, "price per
  square metre", and sorting by recency of update.
- **Docker** for a one-command run, and **soft deletes / status transitions**
  (`draft` → `active` → `expired`) since listings are not really deleted in this
  domain.
