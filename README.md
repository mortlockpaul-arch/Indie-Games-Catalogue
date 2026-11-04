# Indie Games global catalogue

The public, reviewed catalogue used automatically by Indie Games Build Manager.

## For downloaders

Open Build Manager's Global Project Catalogue. Approved packages appear automatically; no catalogue file or GitHub account is needed to browse and download. The app retains the last verified catalogue for offline browsing. Actual package downloads use BitTorrent and need a reachable seeder.

## For contributors

1. Choose **Connect GitHub** in Build Manager and complete GitHub's browser sign-in. The app installs GitHub CLI if necessary; GitHub CLI manages the sign-in credential.
2. Choose **Publish project**, select source, playable game, or both, and review the file preview.
3. Choose **Publish for approval**. Build Manager packages and seeds the files, creates a branch in your fork, and opens a pull request here. There is no catalogue file to send.
4. Keep seeding. The owner reviews the entry, and merging the request publishes it automatically. **My submissions** opens your requests. Packages remain local until accepted.

Existing local shares can be submitted with **Publish selected**. Retrying the same submission reuses its pull request. Rejected requests are shown as Closed; update the package to submit a new snapshot.

Only submit material you have permission to distribute. A catalogue entry is metadata, not an assurance that a package is safe to run or compatible with your PC.

## For the owner

Review requests at https://github.com/mortlockpaul-arch/Indie-Games-Catalogue/pulls. Check the submitter, package description, sizes, hash and whether a seeder is available. Reject unsuitable entries by closing their request. Approve suitable contributions and merge their request. The publish workflow regenerates `catalogue.json` on the `catalogue` branch; Build Manager refreshes when opened, on request and every five minutes while the catalogue window is visible. The initial catalogue is empty until entries are approved.

The `main` branch requires a passing validation check and a code-owner review for normal contributors. The owner retains GitHub's administrator override so they can maintain the service and merge their own submissions after checking them. There is no automatic merge. The generated `catalogue` branch is written by GitHub Actions after changes reach `main`.

Submissions add one file per torrent under `entries/<infohash>.json`, using the version 1 Build Manager catalogue format with exactly one project. Do not edit generated `catalogue.json` by hand. Entries can be removed or corrected through reviewed changes; apps retain their own downloaded files and active transfers.

Catalogue checks use the validator from the base branch and never execute submitted code. Validation checks torrent metadata and catalogue structure; it does not download or execute package content. Generation runs only after changes reach `main`.

No GitHub credential is shipped with Build Manager or stored in catalogue metadata. Reading the catalogue is public. Contributors use their own GitHub account and do not receive write access to this repository.
