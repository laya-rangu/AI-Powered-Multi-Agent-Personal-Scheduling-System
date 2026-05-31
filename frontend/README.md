# FocusFlow Frontend

The dashboard is a React + Vite frontend for the FocusFlow AI backend. It gives you a single-page control room for:

- submitting a morning check-in
- generating a daily plan through the assistant workflow
- tracking tasks and goals
- reviewing reminders and notifications
- inspecting short human-readable agent logs

## Run

```bash
npm install
npm run dev
```

The app runs on `http://127.0.0.1:5173/` by default.

## API Base URL

Set `VITE_API_BASE_URL` if your backend is not on the default local address:

```bash
cp .env.example .env
```

Example:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Build

```bash
npm run build
```

## Lint

```bash
npm run lint
```
