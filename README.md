# Bigg Boss Tamil 10 – Unofficial Fan Voting App

## Deploy on Render (free web service)
1. Upload this project to a GitHub repository. Keep the repository private if you prefer.
2. Create a PostgreSQL database on Neon and copy its pooled connection string. Keep it secret.
3. On Render, create a new **Web Service** connected to the GitHub repository.
4. Runtime: Python. Build command: `pip install -r requirements.txt`. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`. Select the Free plan.
5. Add environment variables in Render: `SECRET_KEY` (a long random value), `ADMIN_PASSWORD_HASH` (Werkzeug password hash), `DATABASE_URL` (Neon pooled PostgreSQL URL), and `COOKIE_SECURE=1`.
6. Deploy. The app creates its database tables when it starts.

## Local run in Termux
`pip install -r requirements.txt` then `python app.py`. For local testing, SQLite is used if DATABASE_URL is not set.

## Important free-tier notes
- Render free web services sleep after 15 minutes of inactivity and can take around a minute to wake. Their local filesystem is temporary, so do not use local SQLite for live votes.
- Neon Free includes 1 GB database storage and 100 compute-hours per project per month (current plan limits can change).
- Back up/export poll data periodically. Free hosting is suitable for a hobby fan poll, not guaranteed high-availability production use.

## Voting and branding notes
- This is an unofficial fan poll and is not affiliated with Bigg Boss, its broadcaster, or rights holders.
- One vote per day is enforced per browser cookie, not per verified person. Clearing cookies or changing devices/browsers can bypass it.
- Do not use official logos, contestant photos, or copyrighted show artwork unless you have permission.
- SEO routes: `/robots.txt` and `/sitemap.xml`. Search ranking/indexing is not guaranteed.


## SEO improvements included
- Page-specific titles and meta descriptions for the homepage, weekly nomination pages, contestant pages, and results.
- Canonical URLs, Open Graph metadata, and a Twitter summary card.
- Dynamic sitemap containing the homepage, results, every published week, and each contestant page.
- Internal links between weekly pages, contestant pages, and results.
- Clear disclosure that this is an unofficial fan poll and that poll totals are not official programme results.

After deployment, check `/sitemap.xml` and resubmit `sitemap.xml` in Google Search Console. Request indexing for the homepage and important week pages; Google controls crawling, indexing, and ranking timelines.
