# Connect Chat2DB to FIS HTML Intelligence

The FIS database is a generated, read-only index. The source HTML files remain authoritative and are not edited through Chat2DB.

## Connection

1. Open **Chat2DB Community**.
2. Choose **New connection** and select **SQLite**.
3. Name the connection `FIS HTML Intelligence`.
4. Use this database file:

   `D:\GitHub\FIS-HTML-Intelligence\state\fis_html.sqlite`

5. If Chat2DB offers a JDBC URL field, use the read-only form:

   `jdbc:sqlite:file:D:/GitHub/FIS-HTML-Intelligence/state/fis_html.sqlite?mode=ro`

6. Test and save the connection.

## Start Here

Open `schema_guide` first. It explains the AI-facing objects:

- `v_page_catalog` — indexed HTML pages, titles, paths, tags, and series positions.
- `v_series_catalog` — detected series and missing positions.
- `v_continuity_map` — next, previous, adjacency, and gap relationships.
- `v_collection_catalog` — logical collections and authority roles.
- `pages_fts` — full-text search index.

Example questions or SQL:

```sql
SELECT * FROM v_series_catalog;

SELECT *
FROM v_collection_catalog
WHERE collection_name = 'AXIOM';

SELECT title, path, tags
FROM v_page_catalog
WHERE series_key = 'drv'
ORDER BY series_part;
```

## Safety Boundary

Chat2DB is the conversational database surface. It does not canonize content, rewrite source HTML, or change authority status. `sqlite-ai` should first be tested against a disposable copy before any extension is loaded into this database.
