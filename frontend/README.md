# PROCURE.AI Frontend

React + Vite UI wired to the existing FastAPI endpoints.

```powershell
cd C:\Users\rajal\PROCURE.AI\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Default backend: `http://127.0.0.1:8000`. Configure `VITE_API_BASE_URL` in `.env` if needed.

If browser requests are blocked, enable FastAPI CORS for `http://localhost:5173` in the backend.
