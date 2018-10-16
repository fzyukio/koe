# Upgrade checklist:
    * [ ] Stash your change
    * [ ] Pull changes from master
    * [ ] Rebase your branch
    * [ ] Fix conflicts (if any)
    * [ ] Unstash changes


## Activate the environment
On Windows:
```shell
.venv\Scripts\activate.bat
```

On Mac or Linux:
```shell
.venv/bin/activate
```

## Stash your change
```bash
git add -A
git stash
```

## Pull changes from master
```bash
git checkout master
git pull origin master
```

## Rebase your branch
```bash
git rebase master <name of your branch>
```
Fix conflicts (if any)

## Unstash changes
```bash
git stash pop
```
Fix conflicts (if any)
