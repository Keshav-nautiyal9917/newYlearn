# YLearn — Free Hosting (Hindi Guide)

> **Sabse aasaan:** Sirf **Render** use karo — ek jagah pe poora app (frontend + backend).
> Netlify optional hai, baad me kar sakte ho.

---

## Pehle ye ready rakho

1. **Gemini API key** (free): https://aistudio.google.com/app/apikey  
2. **GitHub account** — repo:  
   https://github.com/Keshav-nautiyal9917/newYlearn  
3. **Render account** (free): https://dashboard.render.com/register  

---

## Option A — Sirf Render (recommended, 10 minute)

### Step 1: Render pe deploy

1. Browser me kholo:  
   **https://dashboard.render.com/blueprint/new?repo=https://github.com/Keshav-nautiyal9917/newYlearn**
2. **GitHub se sign in** karo aur repo access allow karo.
3. Blueprint screen pe service dikhegi: `ylearnai-backend` → **Apply**.
4. **Environment** me `GEMINI_API_KEY` ke saamne **Add value** → apni Gemini key paste karo.
5. **Create** / **Deploy** dabao.
6. 5–10 minute wait — status **Live** ho jaye.

### Step 2: Apni site kholo

Render dashboard me service pe click karo → upar URL milega, jaise:

`https://ylearnai-backend.onrender.com`

Yahi tumhari **live website** hai. Share kar sakte ho.

### Step 3: Test

1. URL kholo (pehli baar 30–60 sec lag sakta hai — free tier sleep hota hai).
2. YouTube link daalo (video me **captions** honi chahiye).
3. Notes / quiz try karo.

---

## Option B — Netlify (frontend) + Render (backend)

Tab karo jab custom domain / Netlify CDN chahiye.

### Backend (Render)

Option A jaisa — Render URL note karo, jaise:  
`https://ylearnai-backend.onrender.com`

### Frontend (Netlify)

1. https://app.netlify.com → **Add new site** → **Import an existing project**
2. **GitHub** → repo `majorproject` select
3. Settings:
   - **Branch:** `main`
   - **Build command:** *(khali chhod do)*
   - **Publish directory:** `frontend`
4. **Deploy**

### Netlify ↔ Render connect

1. Repo me `netlify.toml` kholo.
2. Line 7 pe Render URL lagao:

```toml
to = "https://TUMHARA-SERVICE.onrender.com/api/:splat"
```

3. GitHub pe push → Netlify auto-redeploy.

Netlify site: `https://something.netlify.app` — API `/api/*` se Render pe jayegi.

---

## Problem?

| Problem | Solution |
|--------|----------|
| Build fail: `pydantic-core` / `maturin` / Rust error | Render **Python 3.14** use kar raha hai. **Environment** → `PYTHON_VERSION` = `3.11.9`, **Root Directory** = `backend`, phir **Clear build cache & deploy**. Ya repo me latest `render.yaml` + `backend/.python-version` pull karo. |
| Transcript error: YouTube blocking cloud IP | Render pe normal hai. App pehle **browser** se captions leti hai, phir server **Gemini** se backup. `GEMINI_API_KEY` set karo, refresh karke try karo. Video me captions on honi chahiye. |
| "AI generation failed" | Render → Environment → `GEMINI_API_KEY` sahi hai? |
| Bahut slow pehli request | Render free sleep — dubara try karo |
| Transcript error | Video me subtitles/captions on karo |
| Netlify pe API fail | `netlify.toml` me sahi Render URL hai? |

### Manual deploy (Blueprint ke bina)

Agar tumne khud **Web Service** banaya hai, ye settings check karo:

| Setting | Value |
|--------|--------|
| Root Directory | `backend` |
| Build Command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Environment | `PYTHON_VERSION` = `3.11.9`, `GEMINI_API_KEY` = tumhari key |

---

## Main tumhare liye kya nahi kar sakta

- Render / Netlify / Google account **login** (tumhara password chahiye)
- **Gemini key** banana (tumhari Google ID)

Baaki code GitHub pe ready hai — upar wale link se deploy start ho jata hai.
