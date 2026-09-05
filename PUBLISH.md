# Publishing EarthSystem to GitHub and GitHub Pages

Everything needed is already in this folder: `.github/workflows/pages.yml` (the deploy
workflow), `.nojekyll`, `.gitignore`, `LICENSE`, and the root `index.html` that forwards
to `web/`.

---

## 1. Create the repository on GitHub

Go to https://github.com/new and create an **empty** repository — no README, no
.gitignore, no licence (this folder already has them).

Name it **`earthsystem`** if you want the demo URL in the README to be correct:

    https://emadroshandel.github.io/earthsystem/

If you choose a different name, edit the two demo links at the top of `README.md`.

## 2. Push this folder

Open a terminal **in this folder** (in File Explorer: type `cmd` in the address bar and
press Enter), then:

```
git init -b main
git add .
git commit -m "EarthSystem v1.1.0 - earthing system design"
git remote add origin https://github.com/emadroshandel/earthsystem.git
git push -u origin main
```

If `git` is not recognised, install it from https://git-scm.com/download/win and reopen
the terminal.

The two `_EarthSystem_v*.tar.gz` archives, `startup_log.txt`, `outputs/` and
`__pycache__/` are excluded automatically by `.gitignore`.

## 3. Turn on Pages

Settings → Pages → **Build and deployment**:

* **Source: GitHub Actions** — leave it exactly as you have it. The workflow in
  `.github/workflows/pages.yml` does the rest.

That is the piece that was missing: with "GitHub Actions" selected, GitHub waits for a
workflow. There was none, so nothing was ever deployed.

> Alternative, if you prefer no workflow at all: set **Source: Deploy from a branch**,
> branch `main`, folder `/ (root)`. That also works — `.nojekyll` is there for it.

## 4. Watch it deploy

The **Actions** tab shows the run (about a minute). When it goes green, the site is at

    https://<your-username>.github.io/<repo-name>/

The root page forwards to `web/`, which detects that there is no server and starts the
Python engine in the browser through Pyodide.

## 5. What visitors see

First load fetches Pyodide and numpy (about 20 MB) and shows a progress splash; after
that the browser caches it. Every calculation then runs locally in their browser —
nothing is uploaded anywhere. Save/Open to disk are hidden in that mode; Export/Import
JSON still work.

---

## Updating later

```
git add .
git commit -m "what changed"
git push
```

The workflow redeploys automatically on every push to `main`.

## Troubleshooting

**The Actions run fails with a permissions error.** Settings → Actions → General →
Workflow permissions → select *Read and write permissions*.

**The site loads but stays on the splash.** Open the browser console. If it cannot reach
`cdn.jsdelivr.net`, the network is blocking the CDN — the local Windows launchers are
unaffected.

**404 at the repository URL.** The deployment has not finished, or Pages is still set to
a branch that does not exist. Check the Actions tab first.
