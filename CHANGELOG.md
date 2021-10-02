# Releases

## Unreleased Changes

- Fix typos (#24, @didiksupriadi41)

## v2.0.3

- Show search box on source package page
- Corrected package count on main page
- Fix an issue that would cause packages to have their pages deleted

## v2.0.2

- Fixed an issue that would occur when getting a bad HTTP status while downloading package databases
## v2.0.1

- Fixed a character escaping issue
## v2.0.0

- Changed package data structure to always place packages under their parent source package
    - This resolves issues with packages that share names getting "overshadowed" by each other
    - URLs have been changed from `/pkgs/<pkg name>` to `/pkgs/<src pkg>/<pkg name>`
- Changes made to searching:
    - Searches may now be filtered by Fedora release
    - Searches will now group results by source package by default
    - Searches will look at package names, source package names, and package summaries. Previously, searches were only preformed against package names.
- Changed package contact email to `-maintainers` (#21, @churchyard)
- Added static index (#9, @abitrolly)
- Datagrepper queries now use the `delta` parameter
- Lots of miscellaneous bugfixes and improvements

## v1.0.0

Initial release
