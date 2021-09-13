# Releases

## v1.0.0

Initial release

## v2.0.0

- Changed package data structure to always place packages under their parent source package.
    - This resolves issues with packages that share names getting "overshadowed" by each other.
    - URLs have been changed from `/pkgs/<pkg name>` to `/pkgs/<src pkg>/<pkg name>`
- Changes made to searching:
    - Searches may now be filtered by Fedora release
    - Searches will now group results by source package by default
    - Searches will look at package names, source package names, and package summaries. Previously, searches were only preformed against package names.
- Changed package contact email to `-maintainers` (#21, @churchyard)
- Added static index (#9, @abitrolly)
- Datagrepper queries now use the `delta` parameter
- Lots of miscellaneous bugfixes and improvements
