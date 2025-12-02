# Provider Icons

This directory contains provider logo/icon files.

## Format
- **Preferred**: SVG format for scalability
- **Supported**: PNG format as fallback

## Naming Convention
Files should be named using the provider identifier:
- `apple.svg` - Apple Health icon
- `garmin.svg` - Garmin icon
- `polar.svg` - Polar icon
- `suunto.svg` - Suunto icon

## Usage
Icons are automatically served at `/static/provider-icons/{provider}.svg` and referenced in the provider settings API response via the `icon_url` field.

## Adding New Provider Icons
1. Add the icon file with the correct name format
2. The strategy will automatically reference it via the `icon_url` property
