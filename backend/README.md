# Mercúrio Upload Service

Fastify + Supabase backend that stores uploaded files inside a **private Supabase Storage bucket** and registers metadata inside a `uploads` table. Signed URLs are generated on demand so clients can download protected files.

## Setup

1. `cd backend`
2. `npm install` (creates `node_modules`)
3. Copy `.env.example` to `.env` and set:
   - `SUPABASE_URL` – your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY` – service role key (needed for uploading and signing)
   - `SUPABASE_BUCKET` – e.g. `uploads`
   - `PORT` – optional override (default 4000)
   - `SIGNED_URL_EXPIRATION_SECONDS` – TTL for signed URLs (default 900)
4. Create and migrate Supabase schema:
   ```bash
   supabase db push --schema backend/migrations/20260204_create_uploads_table.sql
   ```

## Supabase storage configuration

```bash
supabase storage create-bucket uploads --public=false
```

Once created, keep the bucket private. The backend always requests signed URLs and never exposes public files.

## Running the server

```
npm run dev
```

After building via `npm run build` the compiled output lives under `dist/` (for production `npm run start`).

## API

### `POST /upload`

- Content type: `multipart/form-data`
- Fields:
  - `file` – binary file to upload (required)
  - `metadata` – optional JSON string, e.g. `{ "description": "Relatório diário", "tags": ["financeiro"] }`

Returns the newly created metadata row from the `uploads` table (without a signed URL).

#### cURL example
```
curl -X POST "http://localhost:4000/upload" \
  -F "file=@/path/to/planilha.xlsx" \
  -F 'metadata={"description":"Relatório diário","tags":["financeiro"]};;type=application/json'
```

### `GET /uploads`

Responds with a list of metadata rows (most recent first) and adds `signed_url` for each record using `Supabase Storage #createSignedUrl`.

#### cURL example
```
curl http://localhost:4000/uploads
```

## Types

- `src/types.ts` exposes `UploadMetadata` and `UploadRecord` interfaces so your client or other services can import them and keep contracts consistent.

## Next steps

1. Deploy the Fastify process to your preferred platform.
2. Connect the frontend to `/upload` and `/uploads`.
3. Use the signed URLs in the GET response to stream files securely without exposing the bucket.
