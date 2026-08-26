# distract-yt

A **distraction-free YouTube** built as a **Python web app**.

Instead of YouTube's endless recommendations, you get a **personal library** that
contains **only the videos, channels and playlists you explicitly allow**. Every
video plays inside this app in a stripped-down embed — **no related videos, no
autoplay, no suggestions**.

## How it works

- **Add content** by searching, or by pasting a URL (video / channel / playlist).
- Adding a **channel** lets you click **Import uploads** to pull its recent
  videos into your library. Adding a **playlist** imports all its items.
- The **home screen is your library** — never YouTube's feed.
- The **watch page** (`/watch/<id>`) embeds a single video with
  `rel=0&iv_load_policy=3&autoplay`: no related/suggested videos, no annotations.

## Tech stack

| Piece    | Choice                                         |
|----------|------------------------------------------------|
| Backend  | Python 3.14 + Flask (REST API)                 |
| Database | PostgreSQL (SQLAlchemy + psycopg3)             |
| YouTube  | Data API v3 (single API key + response cache)  |
| Frontend | Vanilla HTML/CSS/JS served by Flask            |

## Setup

### 1. Configure secrets (`.env`)

```bash
copy .env.example .env
# then edit `.env`:
#   DATABASE_URL      -> your postgres user/password (this machine: port 5000)
#   YOUTUBE_API_KEY   -> real Google API key
```

> **Prefer zero setup?** Set `DATABASE_URL=sqlite:///distract_yt.db` in `.env`
> instead. Everything works the same; you just don't need PostgreSQL running.
> You can switch back to the Postgres value any time.

### 2. Create the database (one-time, PostgreSQL only)

PostgreSQL is already running locally on port **5000**.

```bash
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -p 5000 -h localhost -c "CREATE DATABASE distract_yt;"
```

The app creates the tables automatically on first launch.

**Password authentication failed?** The `postgres` superuser password was
rejected (`FATAL: password authentication failed`). You have two easy options:

- **Use SQLite** (the zero-setup value above) and skip Postgres entirely, or
- **Reset the postgres password** using the PostgreSQL installer's default
  account: open the **pgAdmin** app (comes with Postgres) → connect to your
  cluster → right-click **postgres** → *Properties → Security* set a new
  password, then put it in `.env`. (You can also do this from an admin shell
  via `ALTER USER postgres PASSWORD '...';` after temporarily switching
  `pg_hba.conf` auth to `trust` and restarting the service.)

### 3. Get a free YouTube Data API v3 key

1. [console.cloud.google.com](https://console.cloud.google.com) → new project
2. **APIs & Services → Library → YouTube Data API v3 → Enable**
3. **Credentials → Create credentials → API key**
4. Paste into `.env` as `YOUTUBE_API_KEY`

Free tier: **10,000 units/day** (≈10k `videos.list` calls). Responses are
cached in the DB for 24h to stay well under it.

### 4. Run

```bash
uv sync
uv run distract-yt
# open http://127.0.0.1:8000
```

## Authentication

The app is gated behind a login. Register an account, sign in, and you can use
your library; unauthenticated library API calls return `401`.

- The first screen is **/login** — an animated log-in / sign-up form (blob
  submit button). Sign up creates a user (password stored as a salted hash via
  Werkzeug), login starts a signed session cookie.
- Sign out via the **Sign out** button in the sidebar.
- Sessions use `SECRET_KEY` (set one in `.env` for production; a dev default is
  used otherwise).

## REST API

```
Auth
  POST   /api/auth/register            register a user {username, password}
  POST   /api/auth/login               log in {username, password}
  POST   /api/auth/logout              log out (clears the session)
  GET    /api/auth/me                  current user (401 if not logged in)

Library (all require a logged-in session)
  GET    /api/channels                 list allowed channels
  POST   /api/channels                 add channel by URL / @handle / id
  DELETE /api/channels/<id>            remove channel (and its videos)
  GET    /api/channels/<id>/playlists  list a channel's playlists live (for its menu)
  GET    /api/playlists                list allowed playlists
  POST   /api/playlists                add playlist by URL / id
  DELETE /api/playlists/<id>           remove playlist
  GET    /api/videos                   list library videos (?channel_id= filters)
  GET    /api/videos/<id>              get a single video's metadata
  POST   /api/videos                   add a single video
  DELETE /api/videos                   CLEAR ALL videos (channels/collections stay)
  DELETE /api/videos/<id>              remove a video

Discovery (only used by the "Add content" flow)
  GET    /api/search?q=...&type=video|channel|playlist
  POST   /api/import/channel/<id>      import all uploads of a channel
  POST   /api/import/playlist/<id>     import all items of a playlist

Health (public, no login needed)
  GET    /api/status
```

## YouTube-style interface

- **Home** = auto-generated sections: "Your channels" (click to enter a channel),
  one section **per playlist** and **per channel** you've added (created
  automatically when you add them), plus a "Latest videos" grid.
- Channels, Videos and Collections pages, plus a collapsible sidebar.
- Channels, Videos and Collections pages, plus a collapsible sidebar.
- Clicking a **channel** opens a channel detail page restricted to **only that
  channel's videos** — you cannot browse channels you haven't added. The channel
  menu also lists that channel's **playlists** (fetched live from YouTube) so you
  can add the ones you want to your library.
- **Clear all videos** button in the sidebar and on the Videos page removes every
  video but keeps your channels and collections (re-import anytime).

## Custom player (`/watch/<id>`)

The watch page hides YouTube's controls (`controls=0`, `fs=0`) and provides its
**own player controls**: play/pause, seek bar with time tooltip, current/duration
time, volume + mute, playback speed, fullscreen. At the end there is **no
autoplay and no suggestions** — just a Replay button. The right-hand panel shows
"More from this channel" **only from videos already in your library**.

## Distraction-prevention checklist

- [x] Home screen is your library, **not** a YouTube feed
- [x] Channels you didn't add are unreachable
- [x] Custom player → no related/suggested videos, no autoplay
- [x] Search exists only inside the "Add content" modal
- [x] Annotations & info overlays hidden on the watch page

## Development

```bash
uv run python -c "from distract_yt import create_app; print(create_app())"
uv run pytest
```
