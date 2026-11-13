# GitHub branch simulation

Repo: https://github.com/ItsOyondi/loan-underwriting-copilot

Two long-lived branches:

| Branch | Role |
|---|---|
| `main` | The stable copy. Change it only by merging a pull request from `dev`. |
| `dev` | The integration copy. Feature branches merge here first. |

A third, short-lived branch carries one change: `feature/<short-name>`.

Run every command from `AzTraining/finUseCase`.

`main` and `dev` start on the same commit. A pull request from `dev` into `main` has nothing to merge until you commit something new on `dev`.

## 1. Start a feature branch from dev

```powershell
git checkout dev
git pull
git checkout -b feature/CP-ReadmeNote
```

Edit `README.md` and add one line, then commit and push:

```powershell
git add README.md
git commit -m "Updated readme file"
git push -u origin feature/CP-ReadmeNote
```

## 2. Open a pull request into dev

```powershell
gh pr create --base dev --head  feature/7089-update-simulate --title "Updated readme file" --body "Practice merge into dev."
```

Open the URL that `gh` prints and merge the pull request on GitHub. The change is now on `dev` only. `main` is unchanged.

## 3. Promote dev into main

```powershell
git checkout dev
git pull
gh pr create --base main --head dev --title "readme merge into main from dev" --body "Practice merge into main."
```

Merge that pull request on GitHub.

## Day to day

Start each change from an up-to-date `dev`:

```powershell
git checkout dev
git pull
git checkout -b feature/<short-name>
```

Push the feature branch and open a pull request with `--base dev`. When `dev` is ready to release, open a pull request with `--base main --head dev`.

Leave `main` for those pull requests. Do not commit on it directly.

# Checking copies on Git
```powershell
git branch -a
```

`remotes/origin/main` and `remotes/origin/dev` are the copies on GitHub.
