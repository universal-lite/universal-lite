# Universal-Lite

`Universal-Lite` is a custom [Universal Blue](https://universal-blue.org/) image for old x86_64 Chromebooks and similar low-end laptops. The goal is a machine that boots into a lightweight Wayland desktop, automatically updates itself, and stays simple enough for a non-technical family member to use.

## Design goals

- Keep the default graphical session lean enough for 2 GB RAM hardware.
- Use a lightweight Wayland stack based on `labwc`.
- Present a Chromebook-like shelf with `Waybar`.
- Expose only the basic graphical settings a normal user actually needs:
  - panel edge placement
  - panel density
  - light/dark accent preset
  - wallpaper selection
- Include Google Chrome and RPM Fusion multimedia support in the image build so codec and browser setup stay maintainable.
- Follow Universal Blue conventions so updates and rollback behave like a normal bootc image.

## Included stack

- Base image: `ghcr.io/ublue-os/base-main:latest`
- Compositor: `labwc`
- Panel: `waybar`
- Launcher: `fuzzel`
- Greeter: `greetd` + `gtkgreet`
- Notifications: `mako`
- Wallpaper: `swaybg`
- Settings app: `universal-lite-settings`
- Browser: `google-chrome-stable`

## Local development

Build the OCI image:

```bash
just build
```

Build local artifacts:

```bash
just build-raw
just build-iso
```

Run syntax checks:

```bash
just check
bash -n build_files/build.sh
python3 -m py_compile files/usr/bin/universal-lite-settings files/usr/libexec/universal-lite-apply-settings
```

## GitHub setup

The repo expects the final image to publish as:

```text
ghcr.io/noitatsidem/universal-lite
```

Before enabling signed builds, generate a cosign key pair and add the private key as `SIGNING_SECRET` in GitHub Actions:

```bash
COSIGN_PASSWORD='' cosign generate-key-pair
gh secret set SIGNING_SECRET < cosign.key
```

The main container build runs automatically on pushes to `main` and on a daily schedule. The disk-image workflow produces:

- OCI image updates through GHCR
- RAW image artifacts for direct flashing
- Anaconda ISO artifacts for first-time installs

The disk-image workflow keeps S3 upload support, but it is optional.

## First install and rebase

After the image is published, switch an existing bootc/atomic system with:

```bash
sudo bootc switch ghcr.io/noitatsidem/universal-lite:latest
```

For fresh installs, use the generated ISO or RAW image. The installer bootstraps into the same OCI image, so future updates come from the image pipeline instead of manual package management.

## Customization layout

- [`Containerfile`](./Containerfile): base image selection and build entrypoint
- [`build_files/build.sh`](./build_files/build.sh): packages, repo setup, and image defaults
- [`files/`](./files): system config overlays, session scripts, wallpapers, and the settings app
- [`.github/workflows/build.yml`](./.github/workflows/build.yml): OCI build and signing
- [`.github/workflows/build-disk.yml`](./.github/workflows/build-disk.yml): ISO and RAW artifact generation

## Current assumptions

- v1 targets x86_64 only.
- Automatic updates come from the normal Universal Blue / bootc image flow.
- Panel customization is intentionally limited to a stable, simple settings surface.
- Hardware-specific Chromebook quirks may still need model-specific follow-up work.
