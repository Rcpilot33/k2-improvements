# Project workflow rules

- Never include `codex` in names created for branches, files, folders, or other
  project artifacts unless the user explicitly requests it. Preserve exact
  names supplied by the user.
- Before pushing a change that alters an installed component, determine whether
  existing installations must rerun that component's installer. If they must,
  add a new, permanent entry to `installer/migrations/catalog.sh` using the
  correct component and detector, and add or update a regression test proving
  that the migration recommends that component exactly once.
- Do not push an installer-affecting change until its migration tracking is in
  the same commit or an earlier commit. Verify the migration catalog tests and
  confirm that the update workflow will offer the required reinstall/reload;
  component detection alone is not sufficient.
