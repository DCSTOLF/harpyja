# Doctor domain

Consolidated, current requirements for the `harpyja doctor` preflight. Each line
carries its originating spec(s) as provenance.

- `harpyja doctor` reports `rg`/`deno` presence on `PATH`, the configured model-endpoint URL, and air-gap status via the same loopback check as the gateway, without making a live endpoint call. (spec 0001)
