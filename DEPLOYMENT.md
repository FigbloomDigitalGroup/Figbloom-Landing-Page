# Deploying to Render

The Vercel setup no longer applies. Vercel served `frontend/` as static files, but
Django now renders those same pages (`config/views.py`) *and* serves the API, so the
whole site is **one Render web service** — there is no separate frontend deploy.

Everything is described in [render.yaml](render.yaml).

## What Render runs

| | |
|---|---|
| Root directory | `backend` |
| Build | `pip install -r requirements.txt` → `collectstatic` → `migrate` → `createsuperuser` |
| Start | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
| Health check | `/` |

WhiteNoise serves `frontend/` straight from gunicorn (`WHITENOISE_ROOT`), so
`/assets/…`, `/components/…`, `/robots.txt` and `/sitemap.xml` keep working at the
same URLs they had on Vercel. No HTML changes were needed.

## First deploy

1. **Create the service.** Render Dashboard → **New** → **Blueprint** → select this
   repo. Render reads `render.yaml` and provisions the web service plus a Postgres
   instance (`figbloom-db`). `DJANGO_SECRET_KEY` and `DATABASE_URL` are wired up
   automatically.

2. **Create the first admin user.** The free plan has no shell, so set these three
   env vars on the service before the first deploy — the build runs
   `createsuperuser` from them:

   ```
   DJANGO_SUPERUSER_USERNAME=admin
   DJANGO_SUPERUSER_EMAIL=you@figbloom.com
   DJANGO_SUPERUSER_PASSWORD=<a strong password>
   ```

   After the deploy succeeds, log in at `/admin-dashboard/login`, change the
   password, then **delete `DJANGO_SUPERUSER_PASSWORD`** from the env vars. The step
   is idempotent — later deploys skip it because the user already exists.

3. **Set up CV storage** (see below).

4. **Custom domain.** Add it in Render, then set
   `DJANGO_ALLOWED_HOSTS=figbloom.com,www.figbloom.com`. The `*.onrender.com`
   hostname is added automatically from `RENDER_EXTERNAL_HOSTNAME`, and
   `CSRF_TRUSTED_ORIGINS` is derived from the host list — no separate config.

## CV uploads must go to object storage

Render wipes the container filesystem on every deploy and restart. Applicant CVs
written to local disk would be **silently lost**, so `JobApplication.cv_file` is
pointed at Cloudinary whenever `CLOUDINARY_URL` is set:

```
CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
```

Get this from the Cloudinary dashboard home page — it has a "Django" tab that
shows this exact variable, already assembled from your account's API key/secret/
cloud name. Paste the whole string as one env var.

CVs (PDF/DOCX) are uploaded as Cloudinary's "raw" resource type, since Cloudinary
otherwise assumes uploads are images.

**Cloudinary's free tier serves files at public, guessable URLs** — anyone with the
link can view a CV; there's no built-in access control like S3's presigned URLs.
That's an acceptable tradeoff for now, but worth revisiting if CVs need to stay
private.

Until `CLOUDINARY_URL` is set, uploads fall back to local disk and will disappear on
the next deploy.

## Local development

```bash
cd backend
python -m venv venv && ./venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                 # sets DJANGO_DEBUG=true
python manage.py migrate
python manage.py runserver
```

With no `DATABASE_URL` and no `CLOUDINARY_URL`, this keeps using `db.sqlite3` and
`backend/media/` exactly as before.

`DJANGO_DEBUG` defaults to **false** so that a missing env var can never expose
tracebacks in production — which is why `.env` matters locally.

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | `generateValue: true` in render.yaml |
| `DATABASE_URL` | yes | from `figbloom-db`; falls back to SQLite if unset |
| `DJANGO_DEBUG` | — | defaults to `false` |
| `DJANGO_ALLOWED_HOSTS` | custom domains only | comma separated |
| `CLOUDINARY_URL` | for CV uploads | see above |
| `DJANGO_EMAIL_BACKEND` | — | defaults to the console backend; nothing is actually emailed yet |
| `DJANGO_SECURE_SSL_REDIRECT` | — | defaults to `true` when `DEBUG=false` |
| `DJANGO_SUPERUSER_*` | first deploy | remove after use |

## Notes / follow-ups

- **Free Postgres expires after 30 days.** Upgrade the plan in `render.yaml`
  (`basic-256mb`) before that deadline or the database is deleted.
- **Free web services sleep** after ~15 minutes idle; the first request afterwards
  takes ~30 s to cold-start.
- `backend/cv/` holds four test uploads that are **committed to git** — a leftover
  from `MEDIA_ROOT` being unset. `MEDIA_ROOT` is now `backend/media/` (gitignored),
  so nothing new lands there, but the existing files should be removed from history.
- The contact form still posts to Formspree (`contact/index.html`); only the careers
  and newsletter forms go through Django.
- Email is on the console backend, so newsletter signups and applications are stored
  but no notification is sent. Set `DJANGO_EMAIL_BACKEND` + SMTP settings when that
  is wanted.
